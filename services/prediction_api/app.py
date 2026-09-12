"""The prediction service itself.

The service is deliberately small. It loads one model at start up, answers with
it, and reports what it is answering with.

The three endpoints answer three different questions, and keeping them apart
matters for whoever operates it.

``/health`` answers "is this process alive". It never touches the model, so a
restart loop caused by a slow model load is still visible as a live process.

``/ready`` answers "can this process serve". It reports the model, so a
deployment can be confirmed by reading which version is live.

``/predict`` answers the actual question, and names the model in every
response.

The model is loaded once and never swapped. A promotion takes effect by
restarting the process, so every answer a process gave came from the model it
reported.

Only ``/health`` answers without a credential. Liveness is asked by whatever
restarts the process — Docker, an orchestrator — and making that question need
a credential turns an expired credential into a restart loop. It reveals
nothing: it says that a process is running, not what it serves. Everything
else names the model or the numbers behind it, and is authorized.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from ml.observability.logging import (
    CORRELATION_ID_HEADER,
    LogContext,
    configure_logging,
    extended_context,
    log_context,
    new_correlation_id,
)
from ml.observability.metrics import (
    METRICS_CONTENT_TYPE,
    OUTCOME_INVALID,
    OUTCOME_SUCCESS,
    OUTCOME_UNAVAILABLE,
    PredictionMetrics,
)
from ml.security.domain import Permission
from ml.semiconductor_quality.domain import POSITIVE_LABEL
from services.security.http import ACCESS_POLICY_STATE, requires

from .config import ServiceConfig
from .domain import (
    SERVICE_NAME,
    ModelMismatchError,
    ModelUnavailableError,
    Prediction,
    ServedModel,
    ServiceError,
    feature_row,
)
from .model_source import load_served_model
from .schemas import (
    ErrorResponse,
    HealthResponse,
    Measurement,
    ModelDescription,
    PredictedSample,
    PredictionRequest,
    PredictionResponse,
    ReadinessResponse,
)


SERVED_MODEL_STATE = "served_model"
METRICS_STATE = "metrics"

ALIVE = "alive"
READY = "ready"

logger = logging.getLogger(SERVICE_NAME)

# 応答の失敗は、呼び出し側の入力の誤りではなくサービス側の状態である。
# 503 を返して、リトライしてよい種類の失敗だと伝える。
UNAVAILABLE = status.HTTP_503_SERVICE_UNAVAILABLE

# 401 と 403 は違う話をしている。前者は「誰か分からない」、後者は
# 「誰かは分かるが、それは許されていない」。混ぜると、権限の問題を
# 資格情報の問題として調べ続けることになる。
ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "No credential was presented, or it belongs to no known caller.",
    },
    status.HTTP_403_FORBIDDEN: {
        "model": ErrorResponse,
        "description": "The caller is known, and was not granted this.",
    },
    UNAVAILABLE: {
        "model": ErrorResponse,
        "description": "The service has no model to answer with.",
    },
}


def create_app(config: ServiceConfig | None = None) -> FastAPI:
    """Build the service around exactly one model.

    The model is loaded while the application starts, so a process that cannot
    serve never begins accepting requests.
    """
    settings = (config or ServiceConfig.from_environment()).validate()
    configure_logging()
    metrics = PredictionMetrics()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        with log_context(LogContext(correlation_id=new_correlation_id(), service=SERVICE_NAME)):
            logger.info("loading the model to serve")
            model = load_served_model(settings)
            setattr(application.state, SERVED_MODEL_STATE, model)
            metrics.record_model(model.training_failure_share)
            logger.info(
                "serving",
                extra={
                    "model_version": model.model_version,
                    "dataset_version": model.dataset_version,
                    "train_task_id": model.train_task_id,
                },
            )
        yield

    application = FastAPI(
        title="Semiconductor quality prediction",
        summary="Judge whether a product passes, using the model in production.",
        version="1.0.0",
        lifespan=lifespan,
    )
    setattr(application.state, METRICS_STATE, metrics)
    setattr(application.state, ACCESS_POLICY_STATE, settings.clients)
    _register_observability(application, metrics)
    _register_routes(application)
    _register_error_handling(application)
    return application


def _register_observability(application: FastAPI, metrics: PredictionMetrics) -> None:
    """Give every request an identity, and count what happened to it.

    The middleware wraps the whole request, so a failure that never reaches a
    handler is still counted and still logged with the identifier the caller
    was given. Counting inside the handlers would miss exactly the requests
    worth counting.
    """

    @application.middleware("http")
    async def observe(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or new_correlation_id()
        endpoint = request.url.path
        started = time.perf_counter()

        with log_context(LogContext(correlation_id=correlation_id, service=SERVICE_NAME)):
            response = await call_next(request)
            seconds = time.perf_counter() - started
            metrics.record_request(endpoint, _outcome_of(response.status_code), seconds)
            logger.info(
                "request answered",
                extra={
                    "endpoint": endpoint,
                    "method": request.method,
                    "status": response.status_code,
                    "duration_seconds": round(seconds, 6),
                },
            )

        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response

    @application.get(
        "/metrics",
        include_in_schema=False,
        dependencies=[Depends(requires(Permission.METRICS_READ))],
    )
    def report_metrics(request: Request) -> Response:
        """The current numbers, in the format Prometheus reads."""
        return Response(
            content=_metrics(request).expose(),
            media_type=METRICS_CONTENT_TYPE,
        )


def _outcome_of(status_code: int) -> str:
    """Group a status into the three things that matter for an alert.

    A 4xx is the caller's problem and must not raise an alarm about the
    service; a 5xx is the service's. Mixing them makes the error rate useless.
    """
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return OUTCOME_UNAVAILABLE
    if status_code >= status.HTTP_400_BAD_REQUEST:
        return OUTCOME_INVALID
    return OUTCOME_SUCCESS


def _metrics(request: Request) -> PredictionMetrics:
    metrics = getattr(request.app.state, METRICS_STATE, None)
    if not isinstance(metrics, PredictionMetrics):  # pragma: no cover - 起動経路の取り違え
        raise ModelUnavailableError("the service was started without metrics")
    return metrics


def _register_routes(application: FastAPI) -> None:
    @application.get("/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        """Answer whether the process is alive, without touching the model."""
        return HealthResponse(service=SERVICE_NAME, status=ALIVE)

    @application.get(
        "/ready",
        response_model=ReadinessResponse,
        responses=ERROR_RESPONSES,
        tags=["operations"],
        dependencies=[Depends(requires(Permission.MODEL_READ))],
    )
    def ready(request: Request) -> ReadinessResponse:
        """Answer whether the process can serve, and with which model."""
        model = _served_model(request)
        return ReadinessResponse(
            service=SERVICE_NAME,
            status=READY,
            model=ModelDescription(**model.describe()),
        )

    @application.post(
        "/predict",
        response_model=PredictionResponse,
        responses=ERROR_RESPONSES,
        tags=["prediction"],
        dependencies=[Depends(requires(Permission.PREDICT))],
    )
    def predict(payload: PredictionRequest, request: Request) -> PredictionResponse:
        """Judge a batch of products with the model this process serves."""
        model = _served_model(request)
        with extended_context(
            model_version=model.model_version,
            dataset_version=model.dataset_version,
            # 答えたモデルを作った学習Taskを、予測1件の行から名指しする。
            # 障害時に辿るのはモデルではなく、それを作った実行だからである。
            task_id=model.train_task_id,
        ):
            predictions = _predict(model, payload.measurements)
            _metrics(request).record_predictions(
                (prediction.label for prediction in predictions),
                POSITIVE_LABEL,
            )
            logger.info(
                "products judged",
                extra={"measurements": len(payload.measurements)},
            )
        return PredictionResponse(
            model=ModelDescription(**model.describe()),
            predictions=[
                PredictedSample(
                    sample_id=prediction.sample_id,
                    label=prediction.label,
                    confidence=prediction.confidence,
                )
                for prediction in predictions
            ],
        )


def _register_error_handling(application: FastAPI) -> None:
    @application.exception_handler(ServiceError)
    async def _service_error(_request: Request, error: Exception) -> JSONResponse:
        """Report a service that cannot answer as a state, not as a bad request."""
        logger.error("the service could not answer", exc_info=error)
        return JSONResponse(status_code=UNAVAILABLE, content={"detail": str(error)})


def _served_model(request: Request) -> ServedModel:
    model = getattr(request.app.state, SERVED_MODEL_STATE, None)
    if model is None:
        raise HTTPException(
            status_code=UNAVAILABLE,
            detail="the service has not finished loading its model",
        )
    if not isinstance(model, ServedModel):  # pragma: no cover - 起動経路の取り違え
        raise ModelMismatchError("the service was started without a usable model")
    return model


def _predict(model: ServedModel, measurements: Sequence[Measurement]) -> list[Prediction]:
    """Ask the model about every measurement, in one call rather than per row."""
    rows = [feature_row(measurement.model_dump()) for measurement in measurements]
    try:
        answered = model.predict(rows)
    except ServiceError:
        raise
    except Exception as error:  # 失敗の理由は報告する。握り潰さない。
        raise ModelUnavailableError(f"the model failed to answer: {error}") from error

    if len(answered.labels) != len(measurements):
        raise ModelUnavailableError(
            f"the model answered {len(answered.labels)} times for "
            f"{len(measurements)} measurements"
        )

    return [
        Prediction(
            sample_id=measurement.sample_id,
            label=answered.labels[index],
            confidence=answered.confidence_at(index),
        )
        for index, measurement in enumerate(measurements)
    ]


__all__ = ["SERVED_MODEL_STATE", "ModelUnavailableError", "create_app"]

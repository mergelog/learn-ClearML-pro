"""Expose the state of the training side as metrics.

The queue, the agents and the tasks cannot be scraped: none of them answers an
HTTP request. This process does it on their behalf, by asking ClearML and
publishing the answers in the format Prometheus reads.

The reading is taken when it is scraped, not on a timer. A number that is
older than the scrape that returned it is worse than no number, because it
looks current.

A ClearML that cannot be reached is reported as such rather than as zeroes. A
queue depth of zero and "the server did not answer" are opposite facts, and an
alert built on the first must not fire because of the second.

The reading is authorized; being alive is not. ``/health`` is what restarts
this process, and it says nothing beyond "the process runs".
"""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Response
from prometheus_client import CollectorRegistry, Gauge, generate_latest

from ml.observability.logging import LogContext, configure_logging, log_context, new_correlation_id
from ml.observability.metrics import METRICS_CONTENT_TYPE
from ml.security.domain import Permission
from services.security.http import ACCESS_POLICY_STATE, requires

from .config import OpsExporterConfig
from .domain import SERVICE_NAME, OpsSnapshot


logger = logging.getLogger(SERVICE_NAME)

SOURCE_STATE = "ops_source"
CONFIG_STATE = "ops_config"


def create_app(config: OpsExporterConfig | None = None, source: object | None = None) -> FastAPI:
    """Build the exporter.

    ``source`` is injected so that the exporter can be exercised without a
    ClearML Server. Nothing else about the process changes.
    """
    settings = (config or OpsExporterConfig.from_environment()).validate()
    configure_logging()

    application = FastAPI(
        title="Semiconductor operations exporter",
        summary="Publish queue depth, agent count and recent task outcomes.",
        version="1.0.0",
    )
    setattr(application.state, CONFIG_STATE, settings)
    setattr(application.state, ACCESS_POLICY_STATE, settings.clients)
    setattr(application.state, SOURCE_STATE, source or _clearml_source(settings))

    @application.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        """Answer whether the process is alive, without asking ClearML."""
        return {"service": SERVICE_NAME, "status": "alive"}

    @application.get(
        "/metrics",
        include_in_schema=False,
        dependencies=[Depends(requires(Permission.METRICS_READ))],
    )
    def metrics() -> Response:
        reader = getattr(application.state, SOURCE_STATE)
        with log_context(LogContext(correlation_id=new_correlation_id(), service=SERVICE_NAME)):
            return Response(
                content=_expose(reader),
                media_type=METRICS_CONTENT_TYPE,
            )

    return application


def _clearml_source(settings: OpsExporterConfig) -> object:
    # ClearMLへの接続は、メトリクスを取りに来られたときに初めて必要になる。
    # 起動時に作ると、サーバが後から立ち上がる構成で起動できなくなる。
    from .clearml_source import ClearmlOps

    return ClearmlOps(settings.projects, settings.recent_minutes)


def _expose(reader: object) -> bytes:
    """Take one reading and render it, or say that it could not be taken."""
    registry = CollectorRegistry()
    reachable = Gauge(
        "clearml_reachable",
        "1 when the last reading reached the ClearML Server.",
        registry=registry,
    )

    try:
        snapshot = reader.read()  # type: ignore[attr-defined]
    # 理由は報告する。監視が落ちて監視対象が無事、を見分けられるようにする。
    except Exception as error:
        logger.error("the ClearML Server could not be read", exc_info=error)
        reachable.set(0)
        return generate_latest(registry)

    reachable.set(1)
    _publish(registry, snapshot)
    return generate_latest(registry)


def _publish(registry: CollectorRegistry, snapshot: OpsSnapshot) -> None:
    queued = Gauge(
        "clearml_queue_pending_tasks",
        "Tasks waiting on a queue.",
        labelnames=("queue",),
        registry=registry,
    )
    workers = Gauge(
        "clearml_queue_workers",
        "Agents listening to a queue.",
        labelnames=("queue",),
        registry=registry,
    )
    completed = Gauge(
        "clearml_tasks_completed_recent",
        "Tasks that finished successfully in the recent window.",
        labelnames=("project",),
        registry=registry,
    )
    failed = Gauge(
        "clearml_tasks_failed_recent",
        "Tasks that failed in the recent window.",
        labelnames=("project",),
        registry=registry,
    )

    for queue in snapshot.queues:
        queued.labels(queue=queue.name).set(queue.queued)
        workers.labels(queue=queue.name).set(queue.workers)

    for outcome in snapshot.outcomes:
        completed.labels(project=outcome.project).set(outcome.completed)
        failed.labels(project=outcome.project).set(outcome.failed)

    for queue in snapshot.unattended_queues:
        logger.warning(
            "work is waiting on a queue nobody is listening to",
            extra={"queue": queue.name, "pending": queue.queued},
        )

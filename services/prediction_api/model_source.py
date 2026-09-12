"""ClearML boundary of the prediction service.

Every call into the ClearML SDK the service makes is made from here, so the
request handling and the contract checks stay free of it.

Loading a model happens once, at start up, and either succeeds completely or
fails completely. There is no half loaded state: a process either has a model
that answers the contract, or it refuses to start. That is what makes
``model_version`` in a response trustworthy — every answer a process gave came
from the model it reported.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import joblib
import numpy as np
from clearml import Model
from sklearn.pipeline import Pipeline

from ml.model_lifecycle.domain import (
    METADATA_DATASET_ID,
    METADATA_DATASET_VERSION,
    METADATA_MODEL_VERSION,
    METADATA_TRAIN_TASK_ID,
    METADATA_TRAINING_FAILURE_SHARE,
    stage_of,
)
from ml.semiconductor_quality.clearml_tracking import connected_settings
from ml.semiconductor_quality.domain import FEATURE_COLUMNS, MODEL_NAME, FeatureMatrix

from .config import ServiceConfig
from .domain import (
    SERVED_STAGE,
    ModelUnavailableError,
    PredictFunction,
    PredictionBatch,
    ServedModel,
    require_contract,
    require_labels,
    require_servable,
)


PREPROCESSOR_STEP = "preprocessor"


def load_served_model(config: ServiceConfig) -> ServedModel:
    """Find the model this process will answer with, and prove it can.

    Everything that could make an answer meaningless is checked here: the
    model exists, it was promoted, it reads the columns this service sends, and
    it answers with labels this service publishes.
    """
    connected_settings()
    model = _locate(config)
    described = _describe(model)

    require_servable(described.stage)
    pipeline = _load_pipeline(model)
    require_contract(_feature_names(pipeline))
    require_labels([str(label) for label in pipeline.classes_])

    return ServedModel(
        model_id=described.model_id,
        model_version=described.model_version,
        stage=described.stage,
        dataset_id=described.dataset_id,
        dataset_version=described.dataset_version,
        train_task_id=described.train_task_id,
        predict=_predict_with(pipeline),
        training_failure_share=described.training_failure_share,
    )


class _Described:
    """What the registry says about one model, without loading its weights."""

    def __init__(self, model: Model) -> None:
        tags = tuple(str(tag) for tag in (model.tags or ()))
        metadata = {
            name: str(entry.get("value", ""))
            for name, entry in (model.get_all_metadata() or {}).items()
        }
        self.model_id = str(model.id)
        self.stage = stage_of(tags)
        self.model_version = metadata.get(METADATA_MODEL_VERSION, self.model_id)
        self.dataset_id = metadata.get(METADATA_DATASET_ID, "")
        self.dataset_version = metadata.get(METADATA_DATASET_VERSION, "")
        self.train_task_id = metadata.get(METADATA_TRAIN_TASK_ID, "")
        self.training_failure_share = _share(metadata.get(METADATA_TRAINING_FAILURE_SHARE))


def _describe(model: Model) -> _Described:
    return _Described(model)


def _share(value: str | None) -> float | None:
    """Read a share the model recorded, treating anything unreadable as absent.

    A model registered before this was recorded simply does not carry it, and
    inventing a number would make the comparison against it meaningless.
    """
    if not value:
        return None
    try:
        share = float(value)
    except ValueError:
        return None
    return share if 0.0 <= share <= 1.0 else None


def _locate(config: ServiceConfig) -> Model:
    if config.pinned_model_id is not None:
        return _by_id(config.pinned_model_id)
    return _in_production()


def _by_id(model_id: str) -> Model:
    try:
        return Model(model_id=model_id)
    except Exception as error:
        raise ModelUnavailableError(f"model {model_id} cannot be read: {error}") from error


def _in_production() -> Model:
    # 停止中のClearMLは、SDKの内部の型のまま失敗する。どこを読もうとして
    # 失敗したのかを言わないと、起動しない理由がモデル側の問題なのか
    # サーバ側の問題なのかを見分けられない。`_by_id` は既にこう扱っている。
    try:
        found: Sequence[Model] = Model.query_models(
            model_name=MODEL_NAME,
            tags=[SERVED_STAGE.tag],
            include_archived=True,
        )
    except Exception as error:
        raise ModelUnavailableError(
            f"the model registry cannot be read: {error}. "
            "The service cannot know what it would be serving"
        ) from error

    if not found:
        raise ModelUnavailableError(
            f"no model is marked {SERVED_STAGE}, so there is nothing to serve. "
            "Promote a model before starting the service"
        )
    if len(found) > 1:
        raise ModelUnavailableError(
            f"{len(found)} models are marked {SERVED_STAGE}, which cannot be true. "
            "Fix the registry before starting the service"
        )
    return found[0]


def _load_pipeline(model: Model) -> Pipeline:
    try:
        local = model.get_local_copy()
    except Exception as error:
        raise ModelUnavailableError(
            f"the weights of model {model.id} cannot be downloaded: {error}"
        ) from error

    # SDKは取得できなかったことを例外ではなく ``None`` で伝えることがある。
    # そのまま読み込みへ進むと「ファイル 'None' がない」という、原因を
    # 何も語らない失敗になる。
    if not local:
        raise ModelUnavailableError(
            f"the weights of model {model.id} cannot be downloaded from {model.url!r}. "
            "A model registered as a path on the machine that produced it cannot be served"
        )

    loaded = _read_weights(Path(str(local)), model.id)
    if not isinstance(loaded, Pipeline):
        raise ModelUnavailableError(
            f"model {model.id} does not hold a fitted pipeline, so it cannot answer"
        )
    return loaded


def _read_weights(path: Path, model_id: str) -> object:
    """Read the stored weights, saying what could not be read when it fails.

    A half written or truncated artifact does not fail as "the file is
    damaged". ``joblib`` reports it as whatever it happened to trip over while
    unpickling — ``KeyError: 0`` for a file that is not an archive at all,
    ``EOFError`` for one that was cut off. Neither says which model, which
    file, or that the file is the problem, and this runs while the process is
    starting: the operator sees it in a restart loop with nothing to go on.

    Every failure to read is caught, because the set of exceptions a damaged
    pickle can raise is not something this service can enumerate.
    """
    try:
        return joblib.load(path)
    except Exception as error:
        raise ModelUnavailableError(
            f"the weights of model {model_id} at {path} cannot be read "
            f"({type(error).__name__}: {error}). The artifact is damaged or "
            "was written by an incompatible version"
        ) from error


def _feature_names(pipeline: Pipeline) -> tuple[str, ...]:
    """Read which columns the stored pipeline was fitted on.

    The pipeline addresses its columns by position, so what is checked is the
    number of columns the preprocessing expects, mapped back onto the contract
    it must have been fitted from.
    """
    preprocessor = pipeline.named_steps.get(PREPROCESSOR_STEP)
    expected = getattr(preprocessor, "n_features_in_", None)
    if expected is None:
        return FEATURE_COLUMNS
    return FEATURE_COLUMNS[: int(expected)]


def _predict_with(pipeline: Pipeline) -> PredictFunction:
    """Wrap the fitted pipeline as the one thing the service asks of a model."""

    def predict(rows: Sequence[Sequence[object]]) -> PredictionBatch:
        features: FeatureMatrix = np.array([list(row) for row in rows], dtype=object)
        labels = tuple(str(label) for label in pipeline.predict(features))
        return PredictionBatch(labels=labels, confidences=_confidences(pipeline, features))

    return predict


def _confidences(pipeline: Pipeline, features: FeatureMatrix) -> tuple[float, ...] | None:
    """Read how sure the model is, when the algorithm can say.

    A model that does not report probabilities is not given an invented number.
    The response simply omits the field.
    """
    if not hasattr(pipeline, "predict_proba"):
        return None
    probabilities = np.asarray(pipeline.predict_proba(features), dtype=float)
    return tuple(float(row.max()) for row in probabilities)

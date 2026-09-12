"""Contracts of the prediction service.

The service exists to answer one question — will this product pass or fail —
and to be honest about when it cannot answer.

Three rules shape what is here.

A prediction names the model that made it. A caller that keeps the answer
without knowing which model produced it cannot explain, later, why two
identical inputs got different answers.

The service refuses to start without a model. A prediction API that starts,
accepts traffic and answers nothing useful is worse than one that fails to
start, because the failure is then discovered by whoever depends on it rather
than by whoever deployed it.

Only a model that reached production may be served. The evaluation gate and
the promotion flow exist to decide that; the service does not decide it again,
it only refuses anything else.

This module never contacts ClearML and never loads a model. It states what a
served model is and what a prediction is.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from ml.model_lifecycle.domain import ModelStage
from ml.semiconductor_quality.domain import (
    CATEGORICAL_FEATURE_COLUMNS,
    FEATURE_COLUMNS,
    LABELS,
    NUMERIC_FEATURE_COLUMNS,
)


# 読み込んだモデルに問いかける関数。SDKもscikit-learnも知らずに済むよう、
# 呼び出し側からは「行を渡すと答えが返る」という形だけを見る。
PredictFunction = Callable[[Sequence[Sequence[object]]], "PredictionBatch"]

SERVICE_NAME = "semiconductor-quality-prediction"

# 提供してよいのは production に昇格したモデルだけである。
SERVED_STAGE = ModelStage.PRODUCTION

# 1リクエストで受け付ける最大件数。無制限にすると、1回の呼び出しが
# サービス全体の応答時間を占有できてしまう。
MAXIMUM_BATCH_SIZE = 500


class ServiceError(RuntimeError):
    """Raised when the service cannot serve, and says why."""


class ModelUnavailableError(ServiceError):
    """Raised when no model may be served."""


class ModelMismatchError(ServiceError):
    """Raised when the loaded model does not match the contract it must answer."""


@dataclass(frozen=True)
class PredictionBatch:
    """What a model answered for a batch of rows.

    ``confidences`` is optional because not every algorithm reports one, and a
    service that invented a number would be reporting confidence it does not
    have.
    """

    labels: tuple[str, ...]
    confidences: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        # 件数が食い違うということは、答えと確信度の対応が崩れている。
        # 黙って片方を捨てると、別の行の確信度を返してしまう。
        if self.confidences is not None and len(self.confidences) != len(self.labels):
            raise ModelMismatchError(
                f"the model answered {len(self.labels)} labels but "
                f"{len(self.confidences)} confidences"
            )

    def confidence_at(self, index: int) -> float | None:
        if self.confidences is None:
            return None
        return self.confidences[index]


@dataclass(frozen=True)
class ServedModel:
    """The one model this process answers with.

    It is loaded once at start up and never swapped while the process runs. A
    deployment replaces the process, so every answer a process gave came from
    the same model, and ``model_version`` in a response is enough to reproduce
    it.
    """

    model_id: str
    model_version: str
    stage: ModelStage
    dataset_id: str
    dataset_version: str
    train_task_id: str
    predict: PredictFunction
    # 学習時に見た不良の割合。いま返している割合と比べることで、
    # 誰も壊れていないのに世界が変わったことに気付ける。
    training_failure_share: float | None = None

    def describe(self) -> dict[str, str]:
        """What a caller needs to reproduce or audit an answer."""
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "stage": self.stage.value,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "train_task_id": self.train_task_id,
        }


@dataclass(frozen=True)
class Prediction:
    """One answer, and which model gave it."""

    sample_id: str
    label: str
    confidence: float | None


def require_servable(stage: ModelStage) -> None:
    """Refuse to serve a model that was never promoted."""
    if stage is not SERVED_STAGE:
        raise ModelUnavailableError(
            f"only a {SERVED_STAGE} model may be served, but the model to load is "
            f"{stage}. Promote it first, or point the service at another model"
        )


def require_contract(feature_names: Sequence[str]) -> None:
    """Refuse a model that does not read the columns this service sends.

    A model fitted on other columns would still answer, silently, with numbers
    that mean nothing. Checking at start up turns that into a deployment that
    fails rather than a service that lies.
    """
    if tuple(feature_names) != FEATURE_COLUMNS:
        raise ModelMismatchError(
            "the model was fitted on other columns than this service sends. "
            f"Expected {list(FEATURE_COLUMNS)}, but the model reads "
            f"{list(feature_names)}"
        )


def require_labels(labels: Sequence[str]) -> None:
    """Refuse a model that answers with labels the caller cannot read."""
    unknown = [label for label in labels if label not in LABELS]
    if unknown:
        raise ModelMismatchError(
            f"the model answers with labels this service does not publish: "
            f"{', '.join(unknown)}. Expected only {', '.join(LABELS)}"
        )


def feature_row(values: Mapping[str, object]) -> tuple[object, ...]:
    """Lay one request out in the column order of the data contract.

    The order is the contract's, not the caller's, because a fitted pipeline
    addresses its columns by position.
    """
    return tuple(values[column] for column in FEATURE_COLUMNS)


NUMERIC_COLUMNS = NUMERIC_FEATURE_COLUMNS
CATEGORICAL_COLUMNS = CATEGORICAL_FEATURE_COLUMNS

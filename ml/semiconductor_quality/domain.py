"""Data contracts shared by the training flow.

This module intentionally depends on nothing but the standard library and numpy.
Keeping it free of the ClearML SDK lets the data preparation, training and
evaluation steps be exercised without a running ClearML Server.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt


# 特徴量は数値列とカテゴリ列が同居するため、object行列として運ぶ。数値化は
# 前処理のColumnTransformerが担当し、この層では列の意味だけを保つ。
FeatureMatrix = npt.NDArray[np.object_]

# ラベルはデータ契約の文字列をそのまま保持する。整数へ符号化しないことで、
# どのラベルが陽性かを読む側が取り違えられなくなる。
LabelVector = npt.NDArray[np.str_]

# 混同行列は件数なので整数。
CountMatrix = npt.NDArray[np.int64]


IDENTIFIER_COLUMN = "sample_id"
TARGET_COLUMN = "result"
LABELS = ("pass", "fail")
POSITIVE_LABEL = "fail"

NUMERIC_FEATURE_COLUMNS = (
    "temperature",
    "pressure",
    "process_time",
    "gas_flow",
    "sensor_1",
    "sensor_2",
    "inspection_value",
)
CATEGORICAL_FEATURE_COLUMNS = (
    "equipment_id",
    "process_step",
)

# Numeric columns come first so that a fitted pipeline keeps addressing the
# same feature by the same column index.
FEATURE_COLUMNS = NUMERIC_FEATURE_COLUMNS + CATEGORICAL_FEATURE_COLUMNS
REQUIRED_COLUMNS = (IDENTIFIER_COLUMN, *FEATURE_COLUMNS, TARGET_COLUMN)

# 学習が生み出す成果物の名前。学習側とモデルライフサイクル側の両方が同じ名前を
# 指す必要があるため、どちらの実装でもなくデータ契約の側に置く。
MODEL_NAME = "semiconductor-quality-classifier"

TRAIN_SPLIT = "train"
VALIDATION_SPLIT = "validation"
TEST_SPLIT = "test"


@dataclass(frozen=True)
class FetchedDataset:
    """A registered ClearML Dataset version, materialised in the local cache.

    ``local_root`` is the read-only copy that ClearML built for this version.
    It is the only place a training run is allowed to read its input from.

    ``parents`` are the versions this one was built on top of. They are carried
    because a Dataset alone answers "these are the rows" and not "these rows
    came from those rows", which is the question asked when something looks
    wrong months later.
    """

    dataset_id: str
    dataset_project: str
    dataset_name: str
    dataset_version: str
    local_root: Path
    parents: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatasetSource:
    """Identity of the ClearML Dataset version that an execution actually resolved."""

    dataset_id: str
    dataset_project: str
    dataset_name: str
    dataset_version: str
    csv_path: Path


@dataclass(frozen=True)
class DatasetValidationReport:
    """Outcome of validating the CSV that was fetched from the ClearML Dataset."""

    source: DatasetSource
    row_count: int
    feature_names: tuple[str, ...]
    numeric_feature_names: tuple[str, ...]
    categorical_feature_names: tuple[str, ...]
    label_counts: Mapping[str, int]


@dataclass(frozen=True)
class TrainingInput:
    """Validated learning input, with the identifier and target columns removed."""

    report: DatasetValidationReport
    features: FeatureMatrix
    targets: LabelVector


@dataclass(frozen=True)
class SplitPart:
    """One mutually exclusive part of the stratified train / validation / test split."""

    name: str
    features: FeatureMatrix
    targets: LabelVector
    label_counts: Mapping[str, int]

    @property
    def row_count(self) -> int:
        return int(self.targets.shape[0])


@dataclass(frozen=True)
class DataSplit:
    train: SplitPart
    validation: SplitPart
    test: SplitPart

    @property
    def parts(self) -> tuple[SplitPart, ...]:
        return (self.train, self.validation, self.test)


@dataclass(frozen=True)
class EvaluationResult:
    """Metrics of a single split, reported under its own ClearML metric series."""

    split_name: str
    metrics: Mapping[str, float]
    confusion_matrix: CountMatrix
    labels: tuple[str, ...] = LABELS


@dataclass(frozen=True)
class ModelCost:
    """What a model costs to produce and to use.

    Two models can score the same and still be very different to run. A
    comparison that only reports precision and recall cannot answer "which one
    do we deploy", so the price of each is measured alongside.

    The measurements are wall clock and file size on the machine that ran them.
    They are not benchmarks: they are comparable to each other within one run
    of a comparison, and not across machines.
    """

    training_seconds: float
    inference_seconds: float
    inference_rows: int
    model_bytes: int

    @property
    def milliseconds_per_1000_rows(self) -> float:
        """Inference cost in a unit that stays readable as the data grows."""
        if self.inference_rows <= 0:
            return 0.0
        return self.inference_seconds * 1_000_000 / self.inference_rows

    @property
    def model_kilobytes(self) -> float:
        return self.model_bytes / 1024


@dataclass(frozen=True)
class TrainingEvaluation:
    """Every split a run is allowed to score, kept apart from one another.

    ``validation`` confirmed the settings of the run and ``test`` is the single
    final evaluation, so the two are never merged into one figure.
    """

    validation: EvaluationResult
    test: EvaluationResult

    @property
    def results(self) -> tuple[EvaluationResult, ...]:
        return (self.validation, self.test)

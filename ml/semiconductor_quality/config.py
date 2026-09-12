"""Execution contract of the training command.

Two kinds of settings live here and are deliberately kept apart.

``ClearmlSettings`` carries connection endpoints and credentials. It is read
from the environment only, never hard-coded, and never tracked as a ClearML
Task Parameter.

``TrainingConfig`` carries the reproducible part of an execution: which Dataset
version to learn from, where the Task is created, and how the model is fitted.
Everything it holds is safe to record on the Task.

All validation in this module is offline, so an invalid execution is rejected
before a ClearML Task is created.
"""

from __future__ import annotations

import math
import ntpath
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, fields
from enum import Enum
from pathlib import PurePosixPath
from typing import ClassVar, TypeVar, Union


DEFAULT_DATASET_PROJECT = "Semiconductor Quality Prediction"
DEFAULT_DATASET_NAME = "semiconductor-quality-data"
DEFAULT_DATASET_CSV_PATH = "semiconductor_quality.csv"
DEFAULT_DATASET_ALIAS = "training-dataset"

DEFAULT_TASK_PROJECT = f"{DEFAULT_DATASET_PROJECT}/Training"
DEFAULT_TASK_NAME = "random-forest-quality-classifier"

# Agentが購読するQueue。Composeで起動するAgentと同じ名前を既定にしておき、
# 「どのQueueへ入れたか」を指定し忘れても行き先が決まるようにする。
DEFAULT_TRAINING_QUEUE = "semiconductor-training"

# Pipelineの制御役を載せるQueue。ステップ用と分けるのは、制御役が
# ステップの終了を待つ間ずっとAgentを占有するためである。同じQueueに
# 入れると、制御役が待っているのにステップを動かすAgentがいなくなる。
DEFAULT_PIPELINE_QUEUE = "semiconductor-pipeline"

DEFAULT_RANDOM_SEED = 20260906

DEFAULT_API_HOST = "http://localhost:8008"
DEFAULT_WEB_HOST = "http://localhost:8080"
DEFAULT_FILES_HOST = "http://localhost:8081"

RATIO_TOLERANCE = 1e-9


class ConfigurationError(ValueError):
    """Raised when the execution contract is unsatisfiable without contacting ClearML."""


ContractT = TypeVar("ContractT", bound="Contract")


class Contract:
    """A part of the execution contract that can be refused offline.

    Every contract answers the same two questions: what is wrong with it, and
    is it usable. Collecting the reasons rather than raising on the first one
    means an invalid invocation is reported in full instead of one mistake per
    attempt.

    ``error_heading`` names the contract in that report, so a message says
    which part of the invocation was refused.
    """

    error_heading: ClassVar[str] = "Invalid configuration"

    def collect_errors(self) -> tuple[str, ...]:
        raise NotImplementedError

    def validate(self: ContractT) -> ContractT:
        errors = self.collect_errors()
        if errors:
            raise ConfigurationError(
                f"{self.error_heading}:\n"
                + "\n".join(f"- {message}" for message in errors)
            )
        return self


@dataclass(frozen=True)
class DatasetConfig(Contract):
    """Which registered ClearML Dataset version the training reads."""

    error_heading: ClassVar[str] = "Invalid dataset configuration"

    dataset_version: str
    dataset_project: str = DEFAULT_DATASET_PROJECT
    dataset_name: str = DEFAULT_DATASET_NAME
    dataset_csv_path: str = DEFAULT_DATASET_CSV_PATH
    dataset_alias: str = DEFAULT_DATASET_ALIAS

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        errors.extend(_require_text("dataset_version", self.dataset_version))
        errors.extend(_require_text("dataset_project", self.dataset_project))
        errors.extend(_require_text("dataset_name", self.dataset_name))
        errors.extend(_require_text("dataset_alias", self.dataset_alias))
        errors.extend(_require_relative_path("dataset_csv_path", self.dataset_csv_path))
        return tuple(errors)


@dataclass(frozen=True)
class TaskConfig(Contract):
    """Where the training Task itself is created, kept separate from the Dataset."""

    error_heading: ClassVar[str] = "Invalid task configuration"

    task_project: str = DEFAULT_TASK_PROJECT
    task_name: str = DEFAULT_TASK_NAME

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        errors.extend(_require_text("task_project", self.task_project))
        errors.extend(_require_text("task_name", self.task_name))
        return tuple(errors)


@dataclass(frozen=True)
class SplitConfig(Contract):
    """Ratios of the mutually exclusive train / validation / test split."""

    error_heading: ClassVar[str] = "Invalid split configuration"

    train_ratio: float = 0.6
    validation_ratio: float = 0.2
    test_ratio: float = 0.2

    @property
    def total_ratio(self) -> float:
        return self.train_ratio + self.validation_ratio + self.test_ratio

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        errors.extend(_require_ratio("train_ratio", self.train_ratio))
        errors.extend(_require_ratio("validation_ratio", self.validation_ratio))
        errors.extend(_require_ratio("test_ratio", self.test_ratio))
        if not errors and not math.isclose(self.total_ratio, 1.0, abs_tol=RATIO_TOLERANCE):
            errors.append(
                "train_ratio, validation_ratio and test_ratio must sum to 1.0, "
                f"but they sum to {self.total_ratio}"
            )
        return tuple(errors)


class Algorithm(str, Enum):
    """Which learning algorithm a run fits.

    Three are offered, and no more. They were chosen because they learn
    differently, not because they are the strongest available.

    ``logistic-regression`` is a linear baseline. If a much heavier model
    cannot beat it, the extra weight is not buying anything.

    ``random-forest`` is the model this project started with, kept as the point
    of comparison.

    ``hist-gradient-boosting`` builds trees in sequence rather than in
    parallel, so it fails and succeeds on different data than a forest does.
    """

    LOGISTIC_REGRESSION = "logistic-regression"
    RANDOM_FOREST = "random-forest"
    HIST_GRADIENT_BOOSTING = "hist-gradient-boosting"

    def __str__(self) -> str:
        return self.value


class ClassWeight(str, Enum):
    """How much a run lets the rare label weigh.

    The Dataset holds far more passing products than failing ones, and the
    thing worth finding is the rare one. Left alone, every one of the three
    algorithms minimises a loss the majority label dominates, so it buys its
    score by agreeing that almost everything passes.

    ``balanced`` weighs each label by how rare it is, which is the same
    correction in all three algorithms. It is offered rather than imposed
    because it trades precision for recall, and which of the two costs more is
    a decision about the process, not about the code.
    """

    NONE = "none"
    BALANCED = "balanced"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class RandomForestConfig(Contract):
    """Settings of the forest: many independent trees, averaged."""

    error_heading: ClassVar[str] = "Invalid RandomForest configuration"

    n_estimators: int = 300
    max_depth: int | None = None
    min_samples_leaf: int = 4

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        errors.extend(_require_positive_int("n_estimators", self.n_estimators))
        errors.extend(_require_positive_int("min_samples_leaf", self.min_samples_leaf))
        if self.max_depth is not None:
            errors.extend(_require_positive_int("max_depth", self.max_depth))
        return tuple(errors)


@dataclass(frozen=True)
class LogisticRegressionConfig(Contract):
    """Settings of the linear baseline.

    ``regularisation`` is scikit-learn's ``C``: smaller values pull the
    coefficients harder towards zero. It is named for what it does rather than
    for the letter it is called in the library, because a Task Parameter is
    read by people.
    """

    error_heading: ClassVar[str] = "Invalid LogisticRegression configuration"

    regularisation: float = 1.0
    max_iterations: int = 500

    def collect_errors(self) -> tuple[str, ...]:
        return (
            *_require_positive_number("regularisation", self.regularisation),
            *_require_positive_int("max_iterations", self.max_iterations),
        )


@dataclass(frozen=True)
class HistGradientBoostingConfig(Contract):
    """Settings of the boosting model: trees built one after another."""

    error_heading: ClassVar[str] = "Invalid HistGradientBoosting configuration"

    learning_rate: float = 0.1
    max_iterations: int = 200
    max_depth: int | None = None
    min_samples_leaf: int = 20

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        errors.extend(_require_positive_number("learning_rate", self.learning_rate))
        errors.extend(_require_positive_int("max_iterations", self.max_iterations))
        errors.extend(_require_positive_int("min_samples_leaf", self.min_samples_leaf))
        if self.max_depth is not None:
            errors.extend(_require_positive_int("max_depth", self.max_depth))
        return tuple(errors)


# ひとつのアルゴリズムが読む設定の型。どれもfrozen dataclassなので、
# 記録するときは同じやり方で平坦にできる。
EstimatorSettings = Union[
    "RandomForestConfig",
    "LogisticRegressionConfig",
    "HistGradientBoostingConfig",
]

# どのアルゴリズムでも同じ意味を持つ設定。アルゴリズム固有の設定ブロックでは
# なく EstimatorConfig 自身が持つため、名前をここに挙げておく。
SHARED_ESTIMATOR_PARAMETERS = ("class_weight",)


@dataclass(frozen=True)
class EstimatorConfig(Contract):
    """Which algorithm one run fits, together with the settings of each one.

    All three settings blocks are carried, so that switching ``algorithm`` is
    the only change a comparison run needs and the others keep their defaults.
    Only the block the chosen algorithm reads is validated and recorded, so a
    Task never lists parameters that had no effect on its result.
    """

    error_heading: ClassVar[str] = "Invalid estimator configuration"

    algorithm: Algorithm = Algorithm.RANDOM_FOREST
    forest: RandomForestConfig = field(default_factory=RandomForestConfig)
    logistic: LogisticRegressionConfig = field(default_factory=LogisticRegressionConfig)
    boosting: HistGradientBoostingConfig = field(default_factory=HistGradientBoostingConfig)
    class_weight: ClassWeight = ClassWeight.NONE
    decision_threshold: float | None = None

    @property
    def active(self) -> EstimatorSettings:
        """The settings block the chosen algorithm actually reads."""
        return _ACTIVE_SETTINGS[self.algorithm](self)

    @property
    def searchable(self) -> tuple[str, ...]:
        """The names a search may vary, for the algorithm this run fits."""
        return searchable_parameters(self.algorithm)

    def collect_errors(self) -> tuple[str, ...]:
        if not isinstance(self.algorithm, Algorithm):
            known = ", ".join(str(algorithm) for algorithm in Algorithm)
            return (f"algorithm must be one of {known}, but was {self.algorithm!r}",)
        return (
            *self.active.collect_errors(),
            *_require_class_weight("class_weight", self.class_weight),
            *_require_optional_probability("decision_threshold", self.decision_threshold),
        )


def searchable_parameters(algorithm: Algorithm) -> tuple[str, ...]:
    """Which settings of one algorithm a search is allowed to vary.

    The list is derived from the settings block the algorithm reads rather
    than written down a second time, so a search space that names a setting
    the algorithm does not have is refused instead of quietly ignored.

    ``decision_threshold`` is deliberately absent. It is not searched: it is
    chosen inside a trial from the folds that trial fitted, because a
    threshold is only meaningful next to the model it cuts.
    """
    settings = _ACTIVE_SETTINGS[algorithm](EstimatorConfig(algorithm=algorithm))
    return (*(field_.name for field_ in fields(settings)), *SHARED_ESTIMATOR_PARAMETERS)


@dataclass(frozen=True)
class ExecutionPlan(Contract):
    """Where one execution runs, kept apart from what it computes.

    ``queue`` of ``None`` means the run stays in the process that started it.
    A queue name means this process only creates and hands over the Task, and
    a ClearML Agent runs it on a machine that carries the training image.

    The same :class:`TrainingConfig` is used either way. Moving a run between
    the two therefore changes where it executes and nothing about what it
    computes, which is what makes the two results comparable.
    """

    error_heading: ClassVar[str] = "Invalid execution plan"

    queue: str | None = None

    @property
    def runs_locally(self) -> bool:
        return self.queue is None

    def collect_errors(self) -> tuple[str, ...]:
        if self.queue is None:
            return ()
        return _require_text("queue", self.queue)


@dataclass(frozen=True)
class TrainingConfig(Contract):
    """Complete, reproducible contract of one training execution.

    A single ``random_seed`` drives both the split and the estimator so that
    one recorded value is enough to reproduce a run.

    ``estimator`` is the only part that says which algorithm is fitted.
    Everything around it — the Dataset, the split, the preprocessing, the
    metrics — is the same whichever algorithm a run chooses, which is what
    makes two runs comparable.
    """

    error_heading: ClassVar[str] = "Invalid training configuration"

    dataset: DatasetConfig
    task: TaskConfig = field(default_factory=TaskConfig)
    split: SplitConfig = field(default_factory=SplitConfig)
    estimator: EstimatorConfig = field(default_factory=EstimatorConfig)
    random_seed: int = DEFAULT_RANDOM_SEED

    def collect_errors(self) -> tuple[str, ...]:
        return (
            *self.dataset.collect_errors(),
            *self.task.collect_errors(),
            *self.split.collect_errors(),
            *self.estimator.collect_errors(),
            *_require_int("random_seed", self.random_seed),
        )


@dataclass(frozen=True)
class ClearmlSettings(Contract):
    """ClearML connection settings, read from the environment only.

    Credentials are excluded from ``repr`` and must never be recorded as Task
    Parameters. When they are absent the ClearML SDK falls back to its own
    configuration file.
    """

    error_heading: ClassVar[str] = "Invalid ClearML settings"

    api_host: str = DEFAULT_API_HOST
    web_host: str = DEFAULT_WEB_HOST
    files_host: str = DEFAULT_FILES_HOST
    access_key: str | None = field(default=None, repr=False)
    secret_key: str | None = field(default=None, repr=False)

    @classmethod
    def from_environment(cls) -> ClearmlSettings:
        return cls(
            api_host=os.getenv("CLEARML_API_HOST", DEFAULT_API_HOST).rstrip("/"),
            web_host=os.getenv("CLEARML_WEB_HOST", DEFAULT_WEB_HOST).rstrip("/"),
            files_host=os.getenv("CLEARML_FILES_HOST", DEFAULT_FILES_HOST).rstrip("/"),
            access_key=_optional_environment_value("CLEARML_API_ACCESS_KEY"),
            secret_key=_optional_environment_value("CLEARML_API_SECRET_KEY"),
        )

    @property
    def has_explicit_credentials(self) -> bool:
        return self.access_key is not None and self.secret_key is not None

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        errors.extend(_require_text("api_host", self.api_host))
        errors.extend(_require_text("web_host", self.web_host))
        errors.extend(_require_text("files_host", self.files_host))
        if (self.access_key is None) != (self.secret_key is None):
            errors.append(
                "CLEARML_API_ACCESS_KEY and CLEARML_API_SECRET_KEY must be set together"
            )
        return tuple(errors)


# どの設定ブロックがどのアルゴリズムのものかを、1か所だけで宣言する。
_ACTIVE_SETTINGS: Mapping[Algorithm, Callable[[EstimatorConfig], EstimatorSettings]] = {
    Algorithm.LOGISTIC_REGRESSION: lambda estimator: estimator.logistic,
    Algorithm.RANDOM_FOREST: lambda estimator: estimator.forest,
    Algorithm.HIST_GRADIENT_BOOSTING: lambda estimator: estimator.boosting,
}


def _optional_environment_value(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _require_text(name: str, value: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value.strip():
        return (f"{name} is required",)
    return ()


def _require_relative_path(name: str, value: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value.strip():
        return (f"{name} is required",)
    if "\\" in value:
        return (f"{name} must use '/' as the path separator, but was {value!r}",)
    if value.startswith("/") or ntpath.isabs(value):
        return (f"{name} must be relative to the dataset root, but was {value!r}",)
    if ".." in PurePosixPath(value).parts:
        return (f"{name} must not contain '..', but was {value!r}",)
    return ()


def _require_int(name: str, value: int) -> tuple[str, ...]:
    if isinstance(value, bool) or not isinstance(value, int):
        return (f"{name} must be an integer, but was {value!r}",)
    return ()


def _require_positive_int(name: str, value: int) -> tuple[str, ...]:
    errors = _require_int(name, value)
    if errors:
        return errors
    if value <= 0:
        return (f"{name} must be greater than 0, but was {value}",)
    return ()


def _require_positive_number(name: str, value: float) -> tuple[str, ...]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return (f"{name} must be a number, but was {value!r}",)
    if not math.isfinite(value):
        return (f"{name} must be a finite number, but was {value!r}",)
    if value <= 0:
        return (f"{name} must be greater than 0, but was {value}",)
    return ()


def _require_class_weight(name: str, value: ClassWeight) -> tuple[str, ...]:
    if not isinstance(value, ClassWeight):
        known = ", ".join(str(weight) for weight in ClassWeight)
        return (f"{name} must be one of {known}, but was {value!r}",)
    return ()


def _require_optional_probability(name: str, value: float | None) -> tuple[str, ...]:
    """A probability cut, or nothing at all.

    ``None`` means the run does not move the cut, which is not the same as
    cutting at 0. A cut of exactly 0 or 1 answers the same label for every
    row, so both ends are refused rather than accepted as a degenerate model.
    """
    if value is None:
        return ()
    return _require_ratio(name, value)


def _require_ratio(name: str, value: float) -> tuple[str, ...]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return (f"{name} must be a number, but was {value!r}",)
    if not math.isfinite(value):
        return (f"{name} must be a finite number, but was {value!r}",)
    if not 0.0 < value < 1.0:
        return (f"{name} must be greater than 0 and less than 1, but was {value}",)
    return ()

"""Contracts of one hyperparameter search.

A search is not a training run with more arguments. It is a budgeted process
that fits many models, keeps one, and has to be able to say afterwards *why*
that one. This module states the four things such a process needs before it
starts, so that all four end up on the Task rather than in somebody's shell
history.

``SearchSpace`` says what may vary. ``Objective`` says what "better" means.
``Budget`` says when to stop looking. ``TrialPlan`` says how a single
candidate is judged.

Two rules shape everything here.

A search only ever sees the training part of the split. The validation part is
what the evaluation gate later judges the winner on, and the test part is the
single final evaluation. A search that touched either would be choosing a
model with the same rows it is later judged by, and the judgement would mean
nothing.

Nothing in this module contacts ClearML, reads a file or fits a model. It
depends on the training configuration contract alone, so a search can be
described, validated and refused without a server.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

from ml.semiconductor_quality.config import (
    Algorithm,
    Contract,
    EstimatorConfig,
    _require_positive_int,
    _require_positive_number,
    _require_text,
    searchable_parameters,
)
from ml.semiconductor_quality.evaluate import F1, METRIC_NAMES


# 探索が作るTaskの置き場所。学習Taskや Pipeline のステップと混ざらないよう
# 分けてある。数十件が一度に増えるのは探索だけである。
OPTIMIZATION_PROJECT = "Semiconductor Quality Prediction/Optimization"
TRIAL_PROJECT = f"{OPTIMIZATION_PROJECT}/Trials"

TRIAL_TASK_NAME = "optimization-trial"
OPTIMIZER_TASK_NAME = "hyperparameter-optimization"

# 試行が目的指標を報告するグラフ。ClearMLの探索はこの title / series を読んで
# 良し悪しを決めるので、報告する側と探索する側が同じ名前を指す必要がある。
OBJECTIVE_TITLE = "objective"

# 試行だけが読む区画。Dataset / Split / Model / Execution は学習Taskと同じ
# 区画名を使い、探索固有の設定だけをここへ置く。
SEARCH_SECTION = "Search"

FOLDS_PARAMETER = "cross_validation_folds"
TUNE_THRESHOLD_PARAMETER = "tune_decision_threshold"
THRESHOLD_FOLDS_PARAMETER = "threshold_folds"
OBJECTIVE_METRIC_PARAMETER = "objective_metric"

TRIAL_RESULT_ARTIFACT = "trial_result"
SEARCH_PLAN_ARTIFACT = "search_plan"
BEST_TRIAL_ARTIFACT = "best_trial"

# 探索が触ってよいのは学習用の部分だけである。検証用は評価ゲートが、
# 試験用は最終評価が一度だけ使う。
SEARCH_SPLIT = "train"

# 空の候補を人が読むときの書き方。値としては空文字のままで、
# 「指示していない」を意味する。
UNSET_VALUE = "(unset)"


class ExperimentError(RuntimeError):
    """Raised when a search cannot be carried out as it was described."""


class Environment(str, Enum):
    """Which environment's settings a search runs under.

    The three differ in what they are allowed to spend and where they run,
    not in what they compute. A search in ``dev`` exists to show that the
    machinery works; one in ``production`` exists to find a model.
    """

    DEVELOPMENT = "dev"
    STAGING = "staging"
    PRODUCTION = "production"

    def __str__(self) -> str:
        return self.value


class Direction(str, Enum):
    """Whether a larger or a smaller objective is the better one."""

    MAXIMISE = "maximise"
    MINIMISE = "minimise"

    @property
    def clearml_sign(self) -> str:
        return "max" if self is Direction.MAXIMISE else "min"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Objective(Contract):
    """What the search is trying to make better, and in which direction.

    Only the measures the evaluation already reports may be named. A search
    that optimised something the gate never sees would produce a winner
    nobody can judge.
    """

    error_heading: ClassVar[str] = "Invalid search objective"

    metric: str = F1
    direction: Direction = Direction.MAXIMISE

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.metric not in METRIC_NAMES:
            known = ", ".join(METRIC_NAMES)
            errors.append(f"metric must be one of {known}, but was {self.metric!r}")
        if not isinstance(self.direction, Direction):
            known = ", ".join(str(direction) for direction in Direction)
            errors.append(f"direction must be one of {known}, but was {self.direction!r}")
        return tuple(errors)

    def describe(self) -> str:
        return f"{self.direction} the {self.metric} of the {SEARCH_SPLIT} split"


@dataclass(frozen=True)
class ParameterRange(Contract):
    """One setting a search is allowed to vary, and the values it may take."""

    error_heading: ClassVar[str] = "Invalid search parameter"

    name: str

    def collect_errors(self) -> tuple[str, ...]:
        return _require_text("name", self.name)

    def describe(self) -> str:
        raise NotImplementedError

    def as_document(self) -> dict[str, object]:
        raise NotImplementedError


@dataclass(frozen=True)
class NumberRange(ParameterRange):
    """A continuous range, optionally sampled on a logarithmic scale.

    ``logarithmic`` matters for settings whose useful values span orders of
    magnitude — a learning rate is as likely to want 0.01 as 0.1, and a
    uniform draw between 0.01 and 0.3 would almost never try the small end.
    """

    minimum: float = 0.0
    maximum: float = 1.0
    logarithmic: bool = False

    def collect_errors(self) -> tuple[str, ...]:
        errors = list(super().collect_errors())
        errors.extend(_require_bounds(self.name, self.minimum, self.maximum))
        if self.logarithmic and not errors and self.minimum <= 0:
            errors.append(
                f"{self.name} is drawn logarithmically, so its minimum must be "
                f"greater than 0, but was {self.minimum}"
            )
        return tuple(errors)

    def describe(self) -> str:
        scale = " on a logarithmic scale" if self.logarithmic else ""
        return f"{self.name}: {self.minimum} to {self.maximum}{scale}"

    def as_document(self) -> dict[str, object]:
        return {
            "kind": "number",
            "minimum": float(self.minimum),
            "maximum": float(self.maximum),
            "logarithmic": self.logarithmic,
        }


@dataclass(frozen=True)
class IntegerRange(ParameterRange):
    """A whole numbered range, walked in steps."""

    minimum: int = 1
    maximum: int = 2
    step: int = 1

    def collect_errors(self) -> tuple[str, ...]:
        errors = list(super().collect_errors())
        errors.extend(_require_bounds(self.name, self.minimum, self.maximum))
        errors.extend(_require_positive_int(f"{self.name} step", self.step))
        return tuple(errors)

    def describe(self) -> str:
        return f"{self.name}: {self.minimum} to {self.maximum} in steps of {self.step}"

    def as_document(self) -> dict[str, object]:
        return {
            "kind": "integer",
            "minimum": int(self.minimum),
            "maximum": int(self.maximum),
            "step": int(self.step),
        }


@dataclass(frozen=True)
class ChoiceRange(ParameterRange):
    """A fixed set of values, tried as they are written.

    The values are carried as text because a Task Parameter is text. That is
    also what lets a choice express "no limit": the readers of the training
    parameters treat an empty value as "not instructed", so an unbounded tree
    depth is a choice like any other.
    """

    values: tuple[str, ...] = ()

    def collect_errors(self) -> tuple[str, ...]:
        errors = list(super().collect_errors())
        if len(self.values) < 2:
            errors.append(
                f"{self.name} is a choice, so it needs at least two values to "
                f"choose between, but has {len(self.values)}"
            )
        if len(set(self.values)) != len(self.values):
            errors.append(f"{self.name} lists the same value more than once")
        return tuple(errors)

    def describe(self) -> str:
        shown = ", ".join(value or UNSET_VALUE for value in self.values)
        return f"{self.name}: one of {shown}"

    def as_document(self) -> dict[str, object]:
        return {"kind": "choice", "values": list(self.values)}


@dataclass(frozen=True)
class SearchSpace(Contract):
    """Which algorithm is searched, and which of its settings may vary.

    The algorithm itself is fixed for one search. Comparing algorithms is a
    different question, answered by the comparison spike, and mixing the two
    would leave a result nobody can attribute to either.
    """

    error_heading: ClassVar[str] = "Invalid search space"

    algorithm: Algorithm = Algorithm.RANDOM_FOREST
    ranges: tuple[ParameterRange, ...] = ()

    def collect_errors(self) -> tuple[str, ...]:
        if not isinstance(self.algorithm, Algorithm):
            known = ", ".join(str(algorithm) for algorithm in Algorithm)
            return (f"algorithm must be one of {known}, but was {self.algorithm!r}",)

        errors: list[str] = []
        if not self.ranges:
            errors.append("a search needs at least one parameter to vary")

        allowed = searchable_parameters(self.algorithm)
        seen: set[str] = set()
        for parameter in self.ranges:
            errors.extend(parameter.collect_errors())
            if parameter.name in seen:
                errors.append(f"{parameter.name} is varied more than once")
            seen.add(parameter.name)
            if parameter.name not in allowed:
                errors.append(
                    f"{self.algorithm} does not read {parameter.name!r}. "
                    f"It reads: {', '.join(allowed)}"
                )
        return tuple(errors)

    def describe(self) -> str:
        return "\n".join(f"- {parameter.describe()}" for parameter in self.ranges)

    def as_document(self) -> dict[str, object]:
        return {
            "algorithm": self.algorithm.value,
            "parameters": {
                parameter.name: parameter.as_document() for parameter in self.ranges
            },
        }


@dataclass(frozen=True)
class Budget(Contract):
    """What the search may spend before it has to stop.

    Every limit here exists because a search left alone does not end. The
    three answer different runaways: too many trials, one trial that never
    finishes, and a search that keeps going all night.

    ``minimum_folds`` protects the pruning from itself. A trial is allowed to
    be abandoned early only after it has reported this many folds, so a model
    is never dropped on the evidence of a single unlucky fold.
    """

    error_heading: ClassVar[str] = "Invalid search budget"

    max_trials: int = 8
    parallel_trials: int = 1
    trial_minutes: float = 10.0
    total_minutes: float = 30.0
    keep_top: int = 5
    minimum_folds: int = 2

    def collect_errors(self) -> tuple[str, ...]:
        return (
            *_require_positive_int("max_trials", self.max_trials),
            *_require_positive_int("parallel_trials", self.parallel_trials),
            *_require_positive_number("trial_minutes", self.trial_minutes),
            *_require_positive_number("total_minutes", self.total_minutes),
            *_require_positive_int("keep_top", self.keep_top),
            *_require_positive_int("minimum_folds", self.minimum_folds),
        )

    def describe(self) -> str:
        return (
            f"at most {self.max_trials} trials, {self.parallel_trials} at a time, "
            f"{self.trial_minutes} minutes per trial and {self.total_minutes} "
            "minutes in total"
        )

    def as_document(self) -> dict[str, object]:
        return {
            "max_trials": self.max_trials,
            "parallel_trials": self.parallel_trials,
            "trial_minutes": float(self.trial_minutes),
            "total_minutes": float(self.total_minutes),
            "keep_top": self.keep_top,
            "minimum_folds": self.minimum_folds,
        }


@dataclass(frozen=True)
class TrialPlan(Contract):
    """How one candidate is judged, before it is compared with the others.

    A single train / validation split answers "how did this model do on those
    particular rows". Repeating the fit over ``folds`` mutually exclusive
    parts of the training rows answers "how does this model do", which is the
    question a search has to compare on. Trading a fold for speed is a budget
    decision, so the number is configuration rather than a constant.

    ``tune_threshold`` moves the probability cut of each candidate to where it
    serves the objective best. The cut is chosen by an inner split of the
    fitted rows, never on the rows the fold is scored on, so a threshold
    cannot borrow the answer.
    """

    error_heading: ClassVar[str] = "Invalid trial plan"

    folds: int = 5
    tune_threshold: bool = True
    threshold_folds: int = 3

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        errors.extend(_require_at_least("folds", self.folds, 2))
        if self.tune_threshold:
            errors.extend(_require_at_least("threshold_folds", self.threshold_folds, 2))
        return tuple(errors)

    def describe(self) -> str:
        cut = (
            f", with the probability cut chosen on {self.threshold_folds} inner folds"
            if self.tune_threshold
            else ", with the probability cut left where the algorithm puts it"
        )
        return f"{self.folds} fold cross validation over the {SEARCH_SPLIT} split{cut}"

    def as_document(self) -> dict[str, object]:
        return {
            "folds": self.folds,
            "tune_threshold": self.tune_threshold,
            "threshold_folds": self.threshold_folds,
        }


@dataclass(frozen=True)
class ExecutionPlacement(Contract):
    """Where the trials run, and where the search that starts them runs.

    They are separate queues for the same reason the pipeline controller has
    its own: the search occupies one worker for as long as it is waiting, so
    putting it on the queue it is waiting for would leave nothing to run the
    trials.
    """

    error_heading: ClassVar[str] = "Invalid search execution plan"

    trial_queue: str = ""
    optimizer_queue: str = ""

    def collect_errors(self) -> tuple[str, ...]:
        return (
            *_require_text("trial_queue", self.trial_queue),
            *_require_text("optimizer_queue", self.optimizer_queue),
        )


@dataclass(frozen=True)
class ExperimentPlan(Contract):
    """One complete, reproducible description of a search.

    This is what is recorded on the optimization Task: which environment's
    settings it ran under, what it varied, what it optimised, what it was
    allowed to spend, and how each candidate was judged. Everything a later
    reader needs in order to run the same search again is here, and nothing
    that would be a credential is.
    """

    error_heading: ClassVar[str] = "Invalid experiment plan"

    environment: Environment
    space: SearchSpace
    objective: Objective = field(default_factory=Objective)
    budget: Budget = field(default_factory=Budget)
    trial: TrialPlan = field(default_factory=TrialPlan)
    placement: ExecutionPlacement = field(default_factory=ExecutionPlacement)
    estimator: EstimatorConfig = field(default_factory=EstimatorConfig)

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not isinstance(self.environment, Environment):
            known = ", ".join(str(environment) for environment in Environment)
            errors.append(
                f"environment must be one of {known}, but was {self.environment!r}"
            )
        errors.extend(self.space.collect_errors())
        errors.extend(self.objective.collect_errors())
        errors.extend(self.budget.collect_errors())
        errors.extend(self.trial.collect_errors())
        errors.extend(self.placement.collect_errors())
        errors.extend(self.estimator.collect_errors())
        if (
            isinstance(self.space.algorithm, Algorithm)
            and self.estimator.algorithm is not self.space.algorithm
        ):
            errors.append(
                f"the search varies {self.space.algorithm}, but the settings it "
                f"starts from are for {self.estimator.algorithm}"
            )
        return tuple(errors)

    def describe(self) -> str:
        return "\n".join(
            (
                f"Environment: {self.environment}",
                f"Algorithm: {self.space.algorithm}",
                f"Objective: {self.objective.describe()}",
                f"Judged by: {self.trial.describe()}",
                f"Budget: {self.budget.describe()}",
                f"Trials run on: {self.placement.trial_queue}",
                "Varying:",
                self.space.describe(),
            )
        )

    def as_document(self) -> dict[str, object]:
        return {
            "environment": self.environment.value,
            "objective": {
                "metric": self.objective.metric,
                "direction": self.objective.direction.value,
                "split": SEARCH_SPLIT,
            },
            "search_space": self.space.as_document(),
            "budget": self.budget.as_document(),
            "trial": self.trial.as_document(),
            "execution": {
                "trial_queue": self.placement.trial_queue,
                "optimizer_queue": self.placement.optimizer_queue,
            },
        }


@dataclass(frozen=True)
class FoldScore:
    """What one fold of one trial measured."""

    fold: int
    metrics: Mapping[str, float]
    threshold: float | None
    rows: int

    def as_document(self) -> dict[str, object]:
        return {
            "fold": self.fold,
            "rows": self.rows,
            "threshold": self.threshold,
            "metrics": {name: float(value) for name, value in self.metrics.items()},
        }


@dataclass(frozen=True)
class TrialResult:
    """What one candidate scored, and the cut it was scored at.

    ``objective`` is the mean over the folds, which is the number the search
    compares. The folds are kept next to it because a mean of five that hides
    one collapsed fold is a different model than a mean of five that does not.
    """

    objective_metric: str
    objective: float
    folds: tuple[FoldScore, ...]
    threshold: float | None

    @property
    def fold_objectives(self) -> tuple[float, ...]:
        return tuple(float(fold.metrics[self.objective_metric]) for fold in self.folds)

    def as_document(self) -> dict[str, object]:
        return {
            "objective_metric": self.objective_metric,
            "objective": float(self.objective),
            "split": SEARCH_SPLIT,
            "decision_threshold": self.threshold,
            "folds": [fold.as_document() for fold in self.folds],
        }


def _require_bounds(name: str, minimum: float, maximum: float) -> tuple[str, ...]:
    for label, value in (("minimum", minimum), ("maximum", maximum)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return (f"{name} {label} must be a number, but was {value!r}",)
    if minimum >= maximum:
        return (
            f"{name} must have a minimum below its maximum, but was "
            f"{minimum} to {maximum}",
        )
    return ()


def _require_at_least(name: str, value: int, least: int) -> tuple[str, ...]:
    errors = _require_positive_int(name, value)
    if errors:
        return errors
    if value < least:
        return (f"{name} must be at least {least}, but was {value}",)
    return ()

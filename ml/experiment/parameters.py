"""Read and write the Parameters that describe one trial.

A trial is started by cloning a template Task and editing its Parameters, so
everything a trial needs has to survive the trip through text. Which Dataset,
which ratios, which settings and which seed are spelled exactly as a pipeline
step spells them — the readers and writers are the pipeline's, not copies of
them — so a value means the same thing wherever it is read.

What is new here is the ``Search`` section: how many folds judge a candidate,
whether the probability cut may move, and which measure decides. Those are
properties of the search rather than of a training run, which is why they are
their own section and why a training Task never carries them.

Reading a Parameter that cannot be read is reported as a
:class:`PipelineError`, because that is this project's error for "a Task said
something a Task cannot say", and a trial is read the same way a step is.
"""

from __future__ import annotations

from collections.abc import Mapping

from ml.pipeline.domain import MODEL_SECTION
from ml.pipeline.parameters import flag_of, text_of, whole_of
from ml.semiconductor_quality.clearml_tracking import DECISION_THRESHOLD_PARAMETER
from ml.semiconductor_quality.evaluate import METRIC_NAMES

from .domain import (
    FOLDS_PARAMETER,
    OBJECTIVE_METRIC_PARAMETER,
    SEARCH_SECTION,
    THRESHOLD_FOLDS_PARAMETER,
    TUNE_THRESHOLD_PARAMETER,
    Direction,
    ExperimentError,
    Objective,
    TrialPlan,
)


def search_parameters(trial: TrialPlan, objective: Objective) -> dict[str, str]:
    """What a trial has to be told about the search it belongs to."""
    return {
        f"{SEARCH_SECTION}/{OBJECTIVE_METRIC_PARAMETER}": objective.metric,
        f"{SEARCH_SECTION}/{FOLDS_PARAMETER}": str(trial.folds),
        f"{SEARCH_SECTION}/{TUNE_THRESHOLD_PARAMETER}": _flag(trial.tune_threshold),
        f"{SEARCH_SECTION}/{THRESHOLD_FOLDS_PARAMETER}": str(trial.threshold_folds),
    }


def read_trial_plan(parameters: Mapping[str, str]) -> TrialPlan:
    """Read how this trial judges its candidate."""
    defaults = TrialPlan()
    return TrialPlan(
        folds=whole_of(parameters, SEARCH_SECTION, FOLDS_PARAMETER, defaults.folds),
        tune_threshold=flag_of(
            parameters,
            SEARCH_SECTION,
            TUNE_THRESHOLD_PARAMETER,
            defaults.tune_threshold,
        ),
        threshold_folds=whole_of(
            parameters,
            SEARCH_SECTION,
            THRESHOLD_FOLDS_PARAMETER,
            defaults.threshold_folds,
        ),
    )


def read_objective(parameters: Mapping[str, str]) -> Objective:
    """Read what this trial is being judged on.

    Only the direction is assumed. Every measure this project reports is one
    where more is better, and a trial that could silently be minimising recall
    would be worse than one that refuses to start.
    """
    defaults = Objective()
    metric = text_of(parameters, SEARCH_SECTION, OBJECTIVE_METRIC_PARAMETER, defaults.metric)
    if metric not in METRIC_NAMES:
        known = ", ".join(METRIC_NAMES)
        raise ExperimentError(
            f"{SEARCH_SECTION}/{OBJECTIVE_METRIC_PARAMETER} must be one of {known}, "
            f"but was {metric!r}"
        )
    return Objective(metric=metric, direction=Direction.MAXIMISE).validate()


def threshold_parameter(threshold: float | None) -> dict[str, str]:
    """The probability cut a completed search hands to the training pipeline."""
    return {f"{MODEL_SECTION}/{DECISION_THRESHOLD_PARAMETER}": _text(threshold)}


def _flag(value: bool) -> str:
    return "true" if value else "false"


def _text(value: float | None) -> str:
    # 未指定は空で残す。読む側はそれを「指示されていない」として扱う。
    return "" if value is None else str(value)

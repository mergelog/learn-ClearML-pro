"""Judge one candidate, without letting it see what will judge it later.

A search compares candidates, so the number it compares them by has to be
about the settings and not about one lucky division of the rows. This module
therefore fits each candidate several times, over mutually exclusive parts of
the *training* rows alone, and reports the mean.

Three boundaries are deliberate, and each one closes a way of cheating.

Only the training part is used. The validation part is what the evaluation
gate later holds the winner to, and the test part is the single final
evaluation. A search that scored on either would be choosing a model with the
rows that are supposed to judge it independently afterwards.

The probability cut is chosen inside the rows a fold fitted on, by an inner
split, and is then applied to rows that fold has not seen. Choosing it on the
scored rows would move the cut to wherever the answer already is.

The preprocessing is inside the fitted pipeline, so it is fitted per fold on
that fold's rows. Scaling the whole training part first and then splitting it
would leak the held out rows into what the model was fitted with.

Nothing here contacts ClearML. It is handed rows and settings and answers a
:class:`TrialResult`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import replace

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    make_scorer,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, TunedThresholdClassifierCV
from sklearn.pipeline import Pipeline

from ml.semiconductor_quality.algorithms import build_classifier
from ml.semiconductor_quality.config import EstimatorConfig
from ml.semiconductor_quality.domain import (
    POSITIVE_LABEL,
    FeatureMatrix,
    LabelVector,
    SplitPart,
)
from ml.semiconductor_quality.evaluate import ACCURACY, F1, PRECISION, RECALL, score
from ml.semiconductor_quality.preprocess import build_contract_preprocessor
from ml.semiconductor_quality.train import CLASSIFIER_STEP, PREPROCESSOR_STEP

from .domain import (
    SEARCH_SPLIT,
    ExperimentError,
    FoldScore,
    Objective,
    TrialPlan,
    TrialResult,
)


ScorerFactory = Callable[[], object]

# 目的指標ごとの採点方法。しきい値の選定はこの採点を最大化する点を探す。
# 陽性は不良なので、precision / recall / f1 は不良側について測る。
_SCORERS: Mapping[str, ScorerFactory] = {
    ACCURACY: lambda: make_scorer(accuracy_score),
    PRECISION: lambda: make_scorer(precision_score, pos_label=POSITIVE_LABEL, zero_division=0),
    RECALL: lambda: make_scorer(recall_score, pos_label=POSITIVE_LABEL, zero_division=0),
    F1: lambda: make_scorer(f1_score, pos_label=POSITIVE_LABEL, zero_division=0),
}


def build_trial_pipeline(
    estimator: EstimatorConfig,
    plan: TrialPlan,
    objective: Objective,
    random_seed: int,
) -> Pipeline:
    """Build what one fold fits: the preprocessing, the estimator, and the cut.

    The candidate's own ``decision_threshold`` is dropped on purpose. A search
    is what decides where the cut goes; carrying one in would mean measuring a
    cut that was chosen somewhere else.
    """
    classifier = build_classifier(replace(estimator, decision_threshold=None), random_seed)
    if plan.tune_threshold:
        classifier = TunedThresholdClassifierCV(
            classifier,
            scoring=_scorer(objective),
            cv=_folds(plan.threshold_folds, random_seed),
            refit=True,
            random_state=random_seed,
        )
    return Pipeline(
        steps=[
            (PREPROCESSOR_STEP, build_contract_preprocessor()),
            (CLASSIFIER_STEP, classifier),
        ]
    )


def cross_validate(
    part: SplitPart,
    estimator: EstimatorConfig,
    plan: TrialPlan,
    objective: Objective,
    random_seed: int,
) -> TrialResult:
    """Fit one candidate over every fold, and report what it scored."""
    return summarise(
        tuple(iter_folds(part, estimator, plan, objective, random_seed)),
        objective,
    )


def iter_folds(
    part: SplitPart,
    estimator: EstimatorConfig,
    plan: TrialPlan,
    objective: Objective,
    random_seed: int,
) -> Iterator[FoldScore]:
    """Fit one candidate fold by fold, answering each score as it is measured.

    The folds are stratified and seeded, so two candidates are compared over
    exactly the same divisions of exactly the same rows. That is what makes
    the difference between their means a difference between the candidates.

    They are yielded one at a time rather than returned together so that a
    caller can report progress while the trial is still running. That is what
    lets a search abandon a candidate that is clearly behind, instead of
    paying for folds whose outcome will not change the decision.
    """
    _require_searchable(part, plan)

    divisions = _folds(plan.folds, random_seed).split(part.features, part.targets)
    for number, (fitted_rows, scored_rows) in enumerate(divisions, start=1):
        yield _score_fold(
            number=number,
            pipeline=build_trial_pipeline(estimator, plan, objective, random_seed),
            fitted=(part.features[fitted_rows], part.targets[fitted_rows]),
            scored=(part.features[scored_rows], part.targets[scored_rows]),
        )


def summarise(folds: Sequence[FoldScore], objective: Objective) -> TrialResult:
    """Turn the folds a candidate was measured over into the one number compared."""
    if not folds:
        raise ExperimentError("a trial needs at least one fold to be judged by")
    return TrialResult(
        objective_metric=objective.metric,
        objective=running_objective(folds, objective.metric),
        folds=tuple(folds),
        threshold=_agreed_threshold(tuple(folds)),
    )


def running_objective(folds: Sequence[FoldScore], metric: str) -> float:
    """The mean over the folds measured so far.

    A trial reports this after every fold, so the value a search reads while a
    trial is still running means the same thing as the value it reads when the
    trial is done: "this is how the candidate is doing, over everything it has
    been measured on".
    """
    if not folds:
        raise ExperimentError("a running objective needs at least one fold")
    return float(np.mean([float(fold.metrics[metric]) for fold in folds]))


def _score_fold(
    number: int,
    pipeline: Pipeline,
    fitted: tuple[FeatureMatrix, LabelVector],
    scored: tuple[FeatureMatrix, LabelVector],
) -> FoldScore:
    features, targets = fitted
    held_features, held_targets = scored
    pipeline.fit(features, targets)
    predictions: LabelVector = np.asarray(pipeline.predict(held_features))
    return FoldScore(
        fold=number,
        metrics=score(held_targets, predictions),
        threshold=_chosen_threshold(pipeline),
        rows=int(held_targets.shape[0]),
    )


def _chosen_threshold(pipeline: Pipeline) -> float | None:
    """Read back the cut a fold chose, when the fold was allowed to choose one."""
    classifier = pipeline.named_steps[CLASSIFIER_STEP]
    if not isinstance(classifier, TunedThresholdClassifierCV):
        return None
    return float(classifier.best_threshold_)


def _agreed_threshold(folds: tuple[FoldScore, ...]) -> float | None:
    """One cut out of the several the folds chose.

    The median is taken rather than the mean, because a single fold whose best
    cut sits at an extreme should not drag the answer with it. What is wanted
    is the cut the folds broadly agreed on, which is then what the model that
    gets registered is fitted with.
    """
    chosen = [fold.threshold for fold in folds if fold.threshold is not None]
    if not chosen:
        return None
    return float(np.median(chosen))


def _scorer(objective: Objective) -> object:
    factory = _SCORERS.get(objective.metric)
    if factory is None:
        known = ", ".join(sorted(_SCORERS))
        raise ExperimentError(
            f"{objective.metric!r} cannot be used to choose a probability cut. "
            f"Known: {known}"
        )
    return factory()


def _folds(count: int, random_seed: int) -> StratifiedKFold:
    return StratifiedKFold(n_splits=count, shuffle=True, random_state=random_seed)


def _require_searchable(part: SplitPart, plan: TrialPlan) -> None:
    """Refuse a division that cannot be made, instead of failing inside a fit.

    Every fold has to hold both labels, and the inner split that chooses the
    cut divides a fold again. So the rarest label has to survive being divided
    twice, which is a property of the rows and is worth saying plainly.
    """
    if part.name != SEARCH_SPLIT:
        raise ExperimentError(
            f"a search may only use the {SEARCH_SPLIT} split, but was given "
            f"the {part.name} split"
        )

    rarest = min(part.label_counts.values(), default=0)
    needed = plan.folds * (plan.threshold_folds if plan.tune_threshold else 1)
    if rarest < needed:
        raise ExperimentError(
            f"the rarest label holds {rarest} rows in the {part.name} split, which "
            f"cannot fill {plan.folds} folds divided again into "
            f"{plan.threshold_folds if plan.tune_threshold else 1}. "
            f"At least {needed} are needed"
        )

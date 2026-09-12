"""Build the estimator one run fits.

The training flow was built around a RandomForest. That was deliberate while
the pipeline and the evaluation gate were being put together: one algorithm
means one thing to explain when something does not line up.

Now that they work, this module separates "which algorithm" from "how the run
is carried out". Everything else — the data contract, the split, the
preprocessing, the metrics, the gate, the registry — stays the same, which is
what makes two algorithms comparable at all.

This module never contacts ClearML and never touches data. It answers "given
these settings, which estimator", and the settings themselves are declared in
:mod:`config` so that they can be validated without scikit-learn.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from sklearn.base import ClassifierMixin
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import FixedThresholdClassifier

from .config import Algorithm, ClassWeight, EstimatorConfig
from .domain import POSITIVE_LABEL


EstimatorBuilder = Callable[[EstimatorConfig, int], ClassifierMixin]

# 予測確率のうち、どちら側を「不良」と読むか。閾値はこのラベルの確率に当たる。
THRESHOLD_RESPONSE = "predict_proba"

# 森を1つの流れで育て、1つの流れで予測する。
#
# 木を並列に走らせると、予測確率を足し合わせる順序が実行ごとに変わり、
# 浮動小数の下位桁が動く。ラベルだけを見ているうちは気付かないが、
# 確率のしきい値を動かすようになると、同じ種で同じデータを学習しても
# 選ばれるしきい値が変わる。探索は「同じ設定なら同じ成績」を前提に
# 候補を比べるので、ここでは速度より再現性を採る。
# 数千行規模では、この選択の代償は1回あたり1秒に満たない。
FOREST_WORKERS = 1


def build_classifier(estimator: EstimatorConfig, random_seed: int) -> ClassifierMixin:
    """Build the estimator of the run, seeded so that a rerun repeats it."""
    fitted = _BUILDERS[estimator.algorithm](estimator, random_seed)
    return _with_threshold(fitted, estimator.decision_threshold)


def _with_threshold(classifier: ClassifierMixin, threshold: float | None) -> ClassifierMixin:
    """Cut the predicted probability where the run says, not at one half.

    Half is the default of every classifier and is almost never the right
    place for a quality gate: missing a bad product and rejecting a good one
    do not cost the same. Moving the cut is therefore part of the model rather
    than something the caller applies afterwards, so the file that is stored,
    registered and deployed already answers labels at the cut it was chosen
    with.

    A run that names no threshold keeps the estimator itself, so nothing about
    the earlier runs changes.
    """
    if threshold is None:
        return classifier
    return FixedThresholdClassifier(
        classifier,
        threshold=threshold,
        pos_label=POSITIVE_LABEL,
        response_method=THRESHOLD_RESPONSE,
    )


def _class_weight(estimator: EstimatorConfig) -> str | None:
    """Translate the imbalance policy into what scikit-learn expects.

    All three algorithms take the same ``class_weight`` argument, so the
    policy is one decision rather than three.
    """
    if estimator.class_weight is ClassWeight.BALANCED:
        return ClassWeight.BALANCED.value
    return None


def _build_logistic(estimator: EstimatorConfig, random_seed: int) -> ClassifierMixin:
    settings = estimator.logistic
    return LogisticRegression(
        C=settings.regularisation,
        max_iter=settings.max_iterations,
        class_weight=_class_weight(estimator),
        random_state=random_seed,
    )


def _build_forest(estimator: EstimatorConfig, random_seed: int) -> ClassifierMixin:
    settings = estimator.forest
    return RandomForestClassifier(
        n_estimators=settings.n_estimators,
        max_depth=settings.max_depth,
        min_samples_leaf=settings.min_samples_leaf,
        class_weight=_class_weight(estimator),
        random_state=random_seed,
        n_jobs=FOREST_WORKERS,
    )


def _build_boosting(estimator: EstimatorConfig, random_seed: int) -> ClassifierMixin:
    settings = estimator.boosting
    return HistGradientBoostingClassifier(
        learning_rate=settings.learning_rate,
        max_iter=settings.max_iterations,
        max_depth=settings.max_depth,
        min_samples_leaf=settings.min_samples_leaf,
        class_weight=_class_weight(estimator),
        random_state=random_seed,
    )


_BUILDERS: Mapping[Algorithm, EstimatorBuilder] = {
    Algorithm.LOGISTIC_REGRESSION: _build_logistic,
    Algorithm.RANDOM_FOREST: _build_forest,
    Algorithm.HIST_GRADIENT_BOOSTING: _build_boosting,
}

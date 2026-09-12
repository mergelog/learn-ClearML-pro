"""Compare two Dataset versions, and say what changed.

A Dataset can meet every expectation and still be a different Dataset than the
one a model was trained on. Equipment gets replaced, a recipe is retuned, a
season passes. The model keeps predicting, and keeps being wrong in a way no
error rate shows until somebody looks.

This module answers "what changed between these two versions". It compares
measured profiles, not raw rows, so the comparison works between versions that
are no longer both downloaded.

Two measures are used, and neither is clever.

For a numeric column: how far the mean moved, in units of the earlier
version's spread. Moving half a standard deviation is a different process;
moving a hundredth is noise. Expressing it in spread rather than in units
means one threshold works for a temperature and for a normalised sensor.

For a categorical column: how much of the distribution had to move to turn one
into the other. Half the sum of the absolute differences in share, which is
0 for identical distributions and 1 for distributions with nothing in common.

This module never contacts ClearML.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .domain import CategoricalSummary, DatasetProfile, NumericSummary


# 既定の閾値。ここを超えたら「別のDatasetになった」として報告する。
DEFAULT_NUMERIC_THRESHOLD = 0.5
DEFAULT_CATEGORICAL_THRESHOLD = 0.2
DEFAULT_LABEL_THRESHOLD = 0.1

# 標準偏差がこれ以下の列は、平均の移動を「広がりの何倍か」で測れない。
# 割ると値が跳ね上がり、意味のない大きな数になる。
NEGLIGIBLE_SPREAD = 1e-9


@dataclass(frozen=True)
class ColumnDrift:
    """How far one column moved between two versions."""

    column: str
    measure: float
    threshold: float
    detail: str

    @property
    def exceeded(self) -> bool:
        return self.measure > self.threshold

    def describe(self) -> str:
        verdict = "exceeded" if self.exceeded else "within"
        return f"{self.column}: {self.detail} ({verdict} the threshold of {self.threshold})"


@dataclass(frozen=True)
class DriftThresholds:
    """How much movement is accepted before it is worth reporting."""

    numeric: float = DEFAULT_NUMERIC_THRESHOLD
    categorical: float = DEFAULT_CATEGORICAL_THRESHOLD
    labels: float = DEFAULT_LABEL_THRESHOLD


@dataclass(frozen=True)
class DriftReport:
    """What changed between two Dataset versions."""

    reference: str
    current: str
    columns: tuple[ColumnDrift, ...]

    @property
    def exceeded(self) -> tuple[ColumnDrift, ...]:
        return tuple(drift for drift in self.columns if drift.exceeded)

    @property
    def has_drifted(self) -> bool:
        return bool(self.exceeded)

    def describe(self) -> str:
        heading = f"comparing {self.current} against {self.reference}"
        if not self.has_drifted:
            return f"{heading}: no column moved beyond its threshold"
        moved = "\n".join(f"- {drift.describe()}" for drift in self.exceeded)
        return (
            f"{heading}: {len(self.exceeded)} column(s) moved beyond their threshold\n{moved}"
        )

    def as_document(self) -> dict[str, object]:
        return {
            "reference": self.reference,
            "current": self.current,
            "has_drifted": self.has_drifted,
            "columns": [
                {
                    "column": drift.column,
                    "measure": drift.measure,
                    "threshold": drift.threshold,
                    "exceeded": drift.exceeded,
                    "detail": drift.detail,
                }
                for drift in self.columns
            ],
        }


def compare(
    reference: DatasetProfile,
    current: DatasetProfile,
    *,
    reference_name: str,
    current_name: str,
    thresholds: DriftThresholds | None = None,
) -> DriftReport:
    """Measure how far ``current`` moved away from ``reference``."""
    limits = thresholds or DriftThresholds()
    columns: list[ColumnDrift] = []

    for column, earlier in reference.numeric.items():
        later = current.numeric.get(column)
        if later is not None:
            columns.append(_numeric_drift(column, earlier, later, limits.numeric))

    for column, earlier_categorical in reference.categorical.items():
        later_categorical = current.categorical.get(column)
        if later_categorical is not None:
            columns.append(
                _categorical_drift(
                    column,
                    earlier_categorical,
                    later_categorical,
                    limits.categorical,
                )
            )

    columns.append(_label_drift(reference, current, limits.labels))

    return DriftReport(
        reference=reference_name,
        current=current_name,
        columns=tuple(columns),
    )


def _numeric_drift(
    column: str,
    reference: NumericSummary,
    current: NumericSummary,
    threshold: float,
) -> ColumnDrift:
    """How far the mean moved, in units of the earlier spread."""
    if reference.mean is None or current.mean is None:
        return ColumnDrift(
            column=column,
            measure=0.0,
            threshold=threshold,
            detail="one of the versions holds no readable values, so nothing can be compared",
        )

    shift = abs(current.mean - reference.mean)
    spread = reference.standard_deviation or 0.0
    if spread <= NEGLIGIBLE_SPREAD:
        # 広がりが無い列は、動いたかどうかしか言えない。
        measure = 0.0 if shift <= NEGLIGIBLE_SPREAD else 1.0
        detail = (
            f"the earlier version held a single value; the mean moved by {shift:.4f}"
        )
        return ColumnDrift(column=column, measure=measure, threshold=threshold, detail=detail)

    measure = shift / spread
    detail = (
        f"the mean moved from {reference.mean:.4f} to {current.mean:.4f}, "
        f"which is {measure:.2f} of the earlier spread"
    )
    return ColumnDrift(column=column, measure=measure, threshold=threshold, detail=detail)


def _categorical_drift(
    column: str,
    reference: CategoricalSummary,
    current: CategoricalSummary,
    threshold: float,
) -> ColumnDrift:
    measure = _distribution_distance(
        _shares(reference.counts, reference.count),
        _shares(current.counts, current.count),
    )
    appeared = sorted(set(current.counts) - set(reference.counts))
    disappeared = sorted(set(reference.counts) - set(current.counts))

    detail = f"the distribution moved by {measure:.2f}"
    if appeared:
        detail += f"; new values: {', '.join(appeared)}"
    if disappeared:
        detail += f"; values that stopped appearing: {', '.join(disappeared)}"

    return ColumnDrift(column=column, measure=measure, threshold=threshold, detail=detail)


def _label_drift(
    reference: DatasetProfile,
    current: DatasetProfile,
    threshold: float,
) -> ColumnDrift:
    """How much the balance of answers moved.

    This one matters more than the others: the share of failures is what the
    model is being asked to find, so a change here changes what "good" means.
    """
    measure = _distribution_distance(
        _shares(reference.label_counts, reference.row_count),
        _shares(current.label_counts, current.row_count),
    )
    return ColumnDrift(
        column="result",
        measure=measure,
        threshold=threshold,
        detail=f"the balance of labels moved by {measure:.2f}",
    )


def _shares(counts: Mapping[str, int], total: int) -> dict[str, float]:
    if total <= 0:
        return {}
    return {value: count / total for value, count in counts.items()}


def _distribution_distance(reference: Mapping[str, float], current: Mapping[str, float]) -> float:
    """Half the sum of absolute differences in share.

    0 when the two distributions are identical, 1 when they have nothing in
    common. Halving is what keeps the answer inside that range.
    """
    values = set(reference) | set(current)
    if not values:
        return 0.0
    return sum(abs(current.get(value, 0.0) - reference.get(value, 0.0)) for value in values) / 2

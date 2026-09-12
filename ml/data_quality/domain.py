"""What a Dataset has to look like, beyond having the right columns.

The training input validation in :mod:`ml.semiconductor_quality.dataset`
answers one question: can these rows be learned from at all. It refuses a
missing column, a value that is not a number, a label outside the contract.

That is not the same as "these rows are fit to train on". A Dataset can pass
every one of those checks and still be wrong: a sensor stuck at its maximum,
a new piece of equipment nobody declared, a month where almost nothing failed.
Those produce a model that trains cleanly and predicts badly.

This module states the second kind of expectation. It depends on nothing but
the standard library, so a Dataset can be judged without a ClearML Server and
the expectations can be read by a person.

Two rules shape it.

An expectation names a bound, not a value. "temperature is between 0 and 1000"
survives a new production line; "temperature is 415.2" does not.

A violation says which column, what was expected and what was found. A report
that only says "the data is bad" leaves whoever reads it to start over.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum


class DataQualityError(ValueError):
    """Raised when a Dataset cannot be judged, or fails the expectations."""


class ColumnKind(str, Enum):
    """How a column is measured, which decides what can be expected of it."""

    NUMERIC = "numeric"
    CATEGORICAL = "categorical"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class NumericExpectation:
    """What a numeric column may hold.

    ``minimum`` and ``maximum`` are the range a value can physically be in,
    not the range this Dataset happens to cover. A pressure below zero is not
    a measurement; a pressure higher than usual is.
    """

    minimum: float
    maximum: float
    maximum_missing_share: float = 0.0

    def collect_errors(self, column: str) -> tuple[str, ...]:
        errors: list[str] = []
        if self.minimum >= self.maximum:
            errors.append(
                f"{column}: minimum must be below maximum, but they are "
                f"{self.minimum} and {self.maximum}"
            )
        errors.extend(_share_errors(f"{column}.maximum_missing_share", self.maximum_missing_share))
        return tuple(errors)


@dataclass(frozen=True)
class CategoricalExpectation:
    """What a categorical column may hold.

    ``allowed`` is the set somebody declared. A value outside it is not
    necessarily wrong data, but it is always something nobody planned for, and
    a model has never seen it. Saying so before training is the point.

    ``maximum_unknown_share`` exists because a single new equipment id in a
    million rows is a note, while a tenth of the rows on unknown equipment is a
    different Dataset.
    """

    allowed: tuple[str, ...]
    maximum_missing_share: float = 0.0
    maximum_unknown_share: float = 0.0

    def collect_errors(self, column: str) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.allowed:
            errors.append(f"{column}: at least one allowed value is required")
        errors.extend(_share_errors(f"{column}.maximum_missing_share", self.maximum_missing_share))
        errors.extend(_share_errors(f"{column}.maximum_unknown_share", self.maximum_unknown_share))
        return tuple(errors)


@dataclass(frozen=True)
class LabelExpectation:
    """How the answers have to be distributed.

    A quality classifier learns from the failures. A Dataset where almost
    nothing failed trains a model that predicts "pass" and scores well doing
    it, so the share of every label is bounded from below.
    """

    minimum_share: float = 0.05

    def collect_errors(self) -> tuple[str, ...]:
        return _share_errors("labels.minimum_share", self.minimum_share)


@dataclass(frozen=True)
class DataQualityContract:
    """Everything expected of a Dataset, in one place."""

    numeric: Mapping[str, NumericExpectation] = field(default_factory=dict)
    categorical: Mapping[str, CategoricalExpectation] = field(default_factory=dict)
    labels: LabelExpectation = field(default_factory=LabelExpectation)
    maximum_duplicate_identifier_share: float = 0.0

    @property
    def columns(self) -> tuple[str, ...]:
        return (*self.numeric, *self.categorical)

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        for column, numeric in self.numeric.items():
            errors.extend(numeric.collect_errors(column))
        for column, categorical in self.categorical.items():
            errors.extend(categorical.collect_errors(column))
        errors.extend(self.labels.collect_errors())
        errors.extend(
            _share_errors(
                "maximum_duplicate_identifier_share",
                self.maximum_duplicate_identifier_share,
            )
        )
        return tuple(errors)

    def validate(self) -> DataQualityContract:
        errors = self.collect_errors()
        if errors:
            raise DataQualityError(
                "Invalid data quality contract:\n"
                + "\n".join(f"- {message}" for message in errors)
            )
        return self


@dataclass(frozen=True)
class NumericSummary:
    """What one numeric column actually holds."""

    column: str
    count: int
    missing: int
    minimum: float | None
    maximum: float | None
    mean: float | None
    standard_deviation: float | None

    @property
    def missing_share(self) -> float:
        return _share(self.missing, self.count)


@dataclass(frozen=True)
class CategoricalSummary:
    """What one categorical column actually holds."""

    column: str
    count: int
    missing: int
    counts: Mapping[str, int]

    @property
    def missing_share(self) -> float:
        return _share(self.missing, self.count)

    @property
    def unique_share(self) -> float:
        """How varied the column is. A key column approaches 1, a flag approaches 0."""
        return _share(len(self.counts), self.count)

    def unknown_share(self, allowed: Sequence[str]) -> float:
        known = set(allowed)
        unknown = sum(count for value, count in self.counts.items() if value not in known)
        return _share(unknown, self.count)


@dataclass(frozen=True)
class DatasetProfile:
    """What one Dataset version holds, measured rather than declared.

    A profile is the thing that gets compared: against the contract to decide
    whether a Dataset may be used, and against another version to see what
    changed between them.
    """

    row_count: int
    duplicate_identifiers: int
    numeric: Mapping[str, NumericSummary]
    categorical: Mapping[str, CategoricalSummary]
    label_counts: Mapping[str, int]

    @property
    def duplicate_identifier_share(self) -> float:
        return _share(self.duplicate_identifiers, self.row_count)

    def label_share(self, label: str) -> float:
        return _share(self.label_counts.get(label, 0), self.row_count)

    def as_document(self) -> dict[str, object]:
        """The profile as plain data, so it can be stored and read back."""
        return {
            "row_count": self.row_count,
            "duplicate_identifiers": self.duplicate_identifiers,
            "numeric": {
                column: {
                    "count": summary.count,
                    "missing": summary.missing,
                    "minimum": summary.minimum,
                    "maximum": summary.maximum,
                    "mean": summary.mean,
                    "standard_deviation": summary.standard_deviation,
                }
                for column, summary in self.numeric.items()
            },
            "categorical": {
                column: {
                    "count": summary.count,
                    "missing": summary.missing,
                    "counts": dict(summary.counts),
                }
                for column, summary in self.categorical.items()
            },
            "label_counts": dict(self.label_counts),
        }


@dataclass(frozen=True)
class Violation:
    """One expectation that was not met, with both sides of the comparison."""

    column: str
    expectation: str
    found: str

    def describe(self) -> str:
        return f"{self.column}: expected {self.expectation}, but found {self.found}"


@dataclass(frozen=True)
class QualityReport:
    """Whether a Dataset may be used, and why not when it may not."""

    violations: tuple[Violation, ...]

    @property
    def passed(self) -> bool:
        return not self.violations

    def describe(self) -> str:
        if self.passed:
            return "the dataset meets every expectation of the data quality contract"
        return "the dataset does not meet the data quality contract:\n" + "\n".join(
            f"- {violation.describe()}" for violation in self.violations
        )

    def as_document(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "violations": [
                {
                    "column": violation.column,
                    "expected": violation.expectation,
                    "found": violation.found,
                }
                for violation in self.violations
            ],
        }


def _share(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return part / whole


def _share_errors(name: str, value: float) -> tuple[str, ...]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return (f"{name} must be a number, but was {value!r}",)
    if not 0.0 <= value <= 1.0:
        return (f"{name} must be between 0 and 1, but was {value}",)
    return ()

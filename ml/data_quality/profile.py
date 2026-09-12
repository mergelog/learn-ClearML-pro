"""Measure what a Dataset actually holds.

A profile is deliberately computed from the raw rows, before the strict
training input validation runs. That validation refuses a missing value
outright, so anything measured after it would report no missing values by
construction — and the number would mean nothing.

Measuring first also means the same profile can be compared against another
version, which is what makes drift visible.

This module never contacts ClearML. It is handed rows and answers what is in
them.
"""

from __future__ import annotations

import csv
import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from ml.semiconductor_quality.domain import (
    CATEGORICAL_FEATURE_COLUMNS,
    IDENTIFIER_COLUMN,
    NUMERIC_FEATURE_COLUMNS,
    TARGET_COLUMN,
)

from .domain import (
    CategoricalSummary,
    DataQualityError,
    DatasetProfile,
    NumericSummary,
)


def profile_csv(path: Path) -> DatasetProfile:
    """Measure one CSV, reading every value as the text it is stored as."""
    try:
        with path.open(newline="", encoding="utf-8-sig") as csv_file:
            rows = list(csv.DictReader(csv_file))
    except OSError as error:
        raise DataQualityError(f"the dataset at {path} cannot be read: {error}") from error

    if not rows:
        raise DataQualityError(f"the dataset at {path} holds no rows to measure")
    return profile_rows(rows)


def profile_rows(rows: Sequence[Mapping[str, str]]) -> DatasetProfile:
    """Measure rows that were read as text."""
    return DatasetProfile(
        row_count=len(rows),
        duplicate_identifiers=_duplicate_identifiers(rows),
        numeric={column: _numeric(column, rows) for column in NUMERIC_FEATURE_COLUMNS},
        categorical={column: _categorical(column, rows) for column in CATEGORICAL_FEATURE_COLUMNS},
        label_counts=_labels(rows),
    )


def _numeric(column: str, rows: Sequence[Mapping[str, str]]) -> NumericSummary:
    """Summarise one numeric column, counting what could not be read as missing.

    A value that is blank and a value that is not a number are both "no
    measurement here". Separating them would suggest the second is recoverable,
    and it is not.
    """
    values = [number for number in (_number(row.get(column)) for row in rows) if number is not None]
    missing = len(rows) - len(values)

    if not values:
        return NumericSummary(
            column=column,
            count=len(rows),
            missing=missing,
            minimum=None,
            maximum=None,
            mean=None,
            standard_deviation=None,
        )

    mean = sum(values) / len(values)
    return NumericSummary(
        column=column,
        count=len(rows),
        missing=missing,
        minimum=min(values),
        maximum=max(values),
        mean=mean,
        standard_deviation=_standard_deviation(values, mean),
    )


def _categorical(column: str, rows: Sequence[Mapping[str, str]]) -> CategoricalSummary:
    counts: Counter[str] = Counter()
    missing = 0
    for row in rows:
        value = (row.get(column) or "").strip()
        if value:
            counts[value] += 1
        else:
            missing += 1

    return CategoricalSummary(
        column=column,
        count=len(rows),
        missing=missing,
        counts=dict(counts),
    )


def _labels(rows: Sequence[Mapping[str, str]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        value = (row.get(TARGET_COLUMN) or "").strip()
        if value:
            counts[value] += 1
    return dict(counts)


def _duplicate_identifiers(rows: Sequence[Mapping[str, str]]) -> int:
    """How many rows carry an identifier that another row also carries.

    The first occurrence is not counted, so the number reads as "how many rows
    are surplus" rather than "how many rows are involved".
    """
    counts = Counter((row.get(IDENTIFIER_COLUMN) or "").strip() for row in rows)
    return sum(count - 1 for count in counts.values() if count > 1)


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _standard_deviation(values: Iterable[float], mean: float) -> float:
    numbers = list(values)
    if len(numbers) < 2:
        return 0.0
    variance = sum((number - mean) ** 2 for number in numbers) / (len(numbers) - 1)
    return math.sqrt(variance)

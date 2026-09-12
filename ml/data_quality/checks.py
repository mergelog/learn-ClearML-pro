"""Judge a measured Dataset against the expectations.

The comparison is deliberately dull: every expectation produces at most one
violation, and a violation carries both sides of it. Nothing here decides what
to do about a failure — that belongs to whoever asked.

The order of the checks is the order a person reads them in: how much data
there is, then each column, then the answers. A report that jumps around is
harder to act on than one that walks the Dataset.
"""

from __future__ import annotations

from .contract import known_labels
from .domain import (
    CategoricalExpectation,
    CategoricalSummary,
    DataQualityContract,
    DatasetProfile,
    NumericExpectation,
    NumericSummary,
    QualityReport,
    Violation,
)


IDENTIFIER_SUBJECT = "sample_id"
LABEL_SUBJECT = "result"
DATASET_SUBJECT = "dataset"

# 何行あれば「学習できるDataset」と言えるか。これを下回ると、指標は出るが
# 何も意味しない。
MINIMUM_ROWS = 100


def check(contract: DataQualityContract, profile: DatasetProfile) -> QualityReport:
    """Answer whether this Dataset may be used, and name every reason it may not."""
    violations: list[Violation] = [
        *_check_size(profile),
        *_check_identifiers(contract, profile),
    ]

    for column, expectation in contract.numeric.items():
        summary = profile.numeric.get(column)
        if summary is None:
            violations.append(_missing_column(column))
            continue
        violations.extend(_check_numeric(column, expectation, summary))

    for column, categorical in contract.categorical.items():
        found = profile.categorical.get(column)
        if found is None:
            violations.append(_missing_column(column))
            continue
        violations.extend(_check_categorical(column, categorical, found))

    violations.extend(_check_labels(contract, profile))
    return QualityReport(violations=tuple(violations))


def _check_size(profile: DatasetProfile) -> list[Violation]:
    if profile.row_count >= MINIMUM_ROWS:
        return []
    return [
        Violation(
            column=DATASET_SUBJECT,
            expectation=f"at least {MINIMUM_ROWS} rows",
            found=f"{profile.row_count} rows",
        )
    ]


def _check_identifiers(contract: DataQualityContract, profile: DatasetProfile) -> list[Violation]:
    share = profile.duplicate_identifier_share
    if share <= contract.maximum_duplicate_identifier_share:
        return []
    return [
        Violation(
            column=IDENTIFIER_SUBJECT,
            expectation=(
                f"at most {_percent(contract.maximum_duplicate_identifier_share)} duplicated"
            ),
            found=f"{profile.duplicate_identifiers} duplicated rows ({_percent(share)})",
        )
    ]


def _check_numeric(
    column: str,
    expectation: NumericExpectation,
    summary: NumericSummary,
) -> list[Violation]:
    violations: list[Violation] = []

    if summary.missing_share > expectation.maximum_missing_share:
        violations.append(
            Violation(
                column=column,
                expectation=f"at most {_percent(expectation.maximum_missing_share)} missing",
                found=f"{summary.missing} of {summary.count} missing "
                f"({_percent(summary.missing_share)})",
            )
        )

    if summary.minimum is not None and summary.minimum < expectation.minimum:
        violations.append(
            Violation(
                column=column,
                expectation=f"no value below {expectation.minimum}",
                found=f"a value of {summary.minimum}",
            )
        )

    if summary.maximum is not None and summary.maximum > expectation.maximum:
        violations.append(
            Violation(
                column=column,
                expectation=f"no value above {expectation.maximum}",
                found=f"a value of {summary.maximum}",
            )
        )

    # 分散がゼロの列は、学習の入力としては存在しないのと同じである。
    # 範囲には収まるので、範囲の検査だけでは見つからない。
    if summary.standard_deviation == 0.0 and summary.count > 1 and summary.missing == 0:
        violations.append(
            Violation(
                column=column,
                expectation="values that vary between rows",
                found=f"every row holds {summary.minimum}",
            )
        )

    return violations


def _check_categorical(
    column: str,
    expectation: CategoricalExpectation,
    summary: CategoricalSummary,
) -> list[Violation]:
    violations: list[Violation] = []

    if summary.missing_share > expectation.maximum_missing_share:
        violations.append(
            Violation(
                column=column,
                expectation=f"at most {_percent(expectation.maximum_missing_share)} missing",
                found=f"{summary.missing} of {summary.count} missing "
                f"({_percent(summary.missing_share)})",
            )
        )

    unknown_share = summary.unknown_share(expectation.allowed)
    if unknown_share > expectation.maximum_unknown_share:
        unknown = sorted(value for value in summary.counts if value not in expectation.allowed)
        violations.append(
            Violation(
                column=column,
                expectation=f"only the declared values: {', '.join(expectation.allowed)}",
                found=f"{', '.join(unknown)} ({_percent(unknown_share)} of the rows)",
            )
        )

    return violations


def _check_labels(contract: DataQualityContract, profile: DatasetProfile) -> list[Violation]:
    violations: list[Violation] = []
    for label in known_labels():
        share = profile.label_share(label)
        if share < contract.labels.minimum_share:
            violations.append(
                Violation(
                    column=LABEL_SUBJECT,
                    expectation=f"at least {_percent(contract.labels.minimum_share)} {label!r}",
                    found=f"{profile.label_counts.get(label, 0)} rows ({_percent(share)})",
                )
            )
    return violations


def _missing_column(column: str) -> Violation:
    return Violation(
        column=column,
        expectation="the column to be present",
        found="no such column in the dataset",
    )


def _percent(share: float) -> str:
    return f"{share * 100:.2f}%"

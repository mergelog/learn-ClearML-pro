"""Read the data quality contract, and keep it in step with the code.

The structure of the data — which columns exist, which are numeric, which
carries the answer — lives in :mod:`ml.semiconductor_quality.domain`, because
the type system and every step of the pipeline depend on it.

What each column may *hold* lives in ``config/data_quality.yaml``, because
those bounds change with the process rather than with the code, and the people
who know them are not the people who deploy.

Two files, one contract. The danger is that they drift apart: a column added
to the code but not to the file would silently go unchecked. So the file is
cross-checked against the code every time it is read, and a mismatch is
refused rather than worked around.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml

from ml.semiconductor_quality.domain import (
    CATEGORICAL_FEATURE_COLUMNS,
    LABELS,
    NUMERIC_FEATURE_COLUMNS,
)

from .domain import (
    CategoricalExpectation,
    DataQualityContract,
    DataQualityError,
    LabelExpectation,
    NumericExpectation,
)


DEFAULT_CONTRACT_FILE = Path(__file__).resolve().parents[2] / "config" / "data_quality.yaml"

NUMERIC_KEY = "numeric"
CATEGORICAL_KEY = "categorical"
LABELS_KEY = "labels"
IDENTIFIERS_KEY = "identifiers"


def load_contract(path: Path | None = None) -> DataQualityContract:
    """Read the expectations, and refuse a file that no longer matches the code."""
    contract_file = path or DEFAULT_CONTRACT_FILE
    document = _read(contract_file)

    contract = DataQualityContract(
        numeric=_read_numeric(document, contract_file),
        categorical=_read_categorical(document, contract_file),
        labels=_read_labels(document),
        maximum_duplicate_identifier_share=_share(
            _optional_section(document, IDENTIFIERS_KEY),
            "maximum_duplicate_share",
            0.0,
            contract_file,
        ),
    )
    _require_same_columns(contract, contract_file)
    return contract.validate()


def _read(path: Path) -> Mapping[str, object]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise DataQualityError(
            f"the data quality contract at {path} cannot be read: {error}"
        ) from error
    except yaml.YAMLError as error:
        raise DataQualityError(
            f"the data quality contract at {path} is not valid YAML: {error}"
        ) from error

    if not isinstance(document, dict):
        raise DataQualityError(f"the data quality contract at {path} does not hold a mapping")
    return document


def _read_numeric(
    document: Mapping[str, object],
    path: Path,
) -> dict[str, NumericExpectation]:
    section = _section(document, NUMERIC_KEY, path)
    return {
        column: NumericExpectation(
            minimum=_number(values, "minimum", column, path),
            maximum=_number(values, "maximum", column, path),
            maximum_missing_share=_share(values, "maximum_missing_share", 0.0, path),
        )
        for column, values in section.items()
    }


def _read_categorical(
    document: Mapping[str, object],
    path: Path,
) -> dict[str, CategoricalExpectation]:
    section = _section(document, CATEGORICAL_KEY, path)
    return {
        column: CategoricalExpectation(
            allowed=_texts(values, "allowed", column, path),
            maximum_missing_share=_share(values, "maximum_missing_share", 0.0, path),
            maximum_unknown_share=_share(values, "maximum_unknown_share", 0.0, path),
        )
        for column, values in section.items()
    }


def _read_labels(document: Mapping[str, object]) -> LabelExpectation:
    section = document.get(LABELS_KEY)
    if not isinstance(section, dict):
        return LabelExpectation()
    minimum = section.get("minimum_share", LabelExpectation().minimum_share)
    if isinstance(minimum, bool) or not isinstance(minimum, (int, float)):
        raise DataQualityError(f"{LABELS_KEY}.minimum_share must be a number, but was {minimum!r}")
    return LabelExpectation(minimum_share=float(minimum))


def _require_same_columns(contract: DataQualityContract, path: Path) -> None:
    """Refuse a contract that no longer describes the columns the code declares.

    Both directions matter. A column in the code but not the file goes
    unchecked; a column in the file but not the code is an expectation nobody
    will ever apply, and reads as protection that is not there.
    """
    _require_match("numeric", NUMERIC_FEATURE_COLUMNS, tuple(contract.numeric), path)
    _require_match("categorical", CATEGORICAL_FEATURE_COLUMNS, tuple(contract.categorical), path)


def _require_match(
    kind: str,
    declared: tuple[str, ...],
    described: tuple[str, ...],
    path: Path,
) -> None:
    missing = [column for column in declared if column not in described]
    extra = [column for column in described if column not in declared]
    if not missing and not extra:
        return

    reasons: list[str] = []
    if missing:
        reasons.append(f"the code declares {kind} columns the file does not: {', '.join(missing)}")
    if extra:
        reasons.append(f"the file describes {kind} columns the code does not: {', '.join(extra)}")
    raise DataQualityError(
        f"the data quality contract at {path} no longer matches the data contract. "
        + "; ".join(reasons)
    )


def _section(
    document: Mapping[str, object],
    key: str,
    path: Path,
) -> Mapping[str, Mapping[str, object]]:
    section = document.get(key, {})
    if not isinstance(section, dict):
        raise DataQualityError(f"{key} in {path} must map a column to its expectations")
    for column, values in section.items():
        if not isinstance(values, dict):
            raise DataQualityError(f"{key}.{column} in {path} must hold a mapping")
    return section


def _optional_section(document: Mapping[str, object], key: str) -> Mapping[str, object]:
    """A section that may be left out entirely, in which case the defaults hold."""
    section = document.get(key)
    return section if isinstance(section, dict) else {}


def _number(values: Mapping[str, object], key: str, column: str, path: Path) -> float:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataQualityError(f"{column}.{key} in {path} must be a number, but was {value!r}")
    return float(value)


def _share(values: Mapping[str, object], key: str, default: float, path: Path) -> float:
    value = values.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataQualityError(f"{key} in {path} must be a number, but was {value!r}")
    return float(value)


def _texts(values: Mapping[str, object], key: str, column: str, path: Path) -> tuple[str, ...]:
    value = values.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise DataQualityError(f"{column}.{key} in {path} must be a list of text values")
    return tuple(str(item) for item in value)


def known_labels() -> tuple[str, ...]:
    """The labels the data contract declares, so the checks read them from one place."""
    return LABELS

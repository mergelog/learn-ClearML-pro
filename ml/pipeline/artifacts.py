"""Read and write what the pipeline steps hand to each other.

A single training process passes its intermediate results in memory. Steps of
a pipeline run in separate processes, on separate machines, at separate
times, so they pass them as files instead. This module is the only place that
decides what those files look like.

The split is stored without pickling anything. A pickled object carries the
class it was written from, so an artifact would stop being readable as soon as
the code around it changed, and re-running one step of an old pipeline is
exactly when that matters. The numeric and the categorical columns are
therefore stored as two plain arrays and rebuilt into the feature matrix on
the way back.

This module never contacts ClearML. It is handed a path and works on it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import numpy.typing as npt

from ml.semiconductor_quality.domain import (
    CATEGORICAL_FEATURE_COLUMNS,
    LABELS,
    NUMERIC_FEATURE_COLUMNS,
    TEST_SPLIT,
    TRAIN_SPLIT,
    VALIDATION_SPLIT,
    DataSplit,
    FeatureMatrix,
    LabelVector,
    SplitPart,
)

from .domain import PipelineError


# 保存する2つの塊。数値列は実数、カテゴリ列とラベルは文字列で持つ。
NumericBlock = npt.NDArray[np.float64]
CategoricalBlock = npt.NDArray[np.str_]

SPLIT_FILE_NAME = "split.npz"

NUMERIC_SUFFIX = "numeric"
CATEGORICAL_SUFFIX = "categorical"
TARGETS_SUFFIX = "targets"

PART_NAMES = (TRAIN_SPLIT, VALIDATION_SPLIT, TEST_SPLIT)


def write_split(directory: Path, split: DataSplit) -> Path:
    """Write the three parts of a split as one file of plain arrays."""
    arrays: dict[str, NumericBlock | CategoricalBlock] = {}
    for part in split.parts:
        numeric, categorical = _divide(part.features)
        arrays[f"{part.name}_{NUMERIC_SUFFIX}"] = numeric
        arrays[f"{part.name}_{CATEGORICAL_SUFFIX}"] = categorical
        arrays[f"{part.name}_{TARGETS_SUFFIX}"] = part.targets

    path = directory / SPLIT_FILE_NAME
    # 書く側でもpickleを禁じる。読む側だけの約束にすると、いつか誰かが
    # オブジェクトを混ぜて書けてしまう。
    # 型情報上は ``allow_pickle`` と配列のキーワードが区別できないため、
    # ここだけ検査を外す。
    np.savez_compressed(str(path), allow_pickle=False, **arrays)  # type: ignore[arg-type]
    return path


def read_split(path: Path) -> DataSplit:
    """Read back a split that another step wrote.

    ``allow_pickle`` stays off. An artifact that only holds numbers and text
    cannot execute anything when it is read, which is the point of storing it
    that way.
    """
    try:
        with np.load(path, allow_pickle=False) as stored:
            parts = {name: _read_part(name, stored) for name in PART_NAMES}
    except (OSError, ValueError, KeyError) as error:
        raise PipelineError(f"the split artifact at {path} cannot be read: {error}") from error

    return DataSplit(
        train=parts[TRAIN_SPLIT],
        validation=parts[VALIDATION_SPLIT],
        test=parts[TEST_SPLIT],
    )


def describe_split(split: DataSplit) -> dict[str, object]:
    """Summarise a split as the readable half of what a step produced."""
    return {
        part.name: {
            "row_count": part.row_count,
            "label_counts": dict(part.label_counts),
        }
        for part in split.parts
    }


def write_json(directory: Path, name: str, content: Mapping[str, object]) -> Path:
    path = directory / f"{name}.json"
    path.write_text(json.dumps(content, indent=2, sort_keys=False), encoding="utf-8")
    return path


def read_json(path: Path) -> dict[str, object]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PipelineError(f"the artifact at {path} cannot be read: {error}") from error

    if not isinstance(content, dict):
        raise PipelineError(f"the artifact at {path} does not hold an object")
    return content


def _divide(features: FeatureMatrix) -> tuple[NumericBlock, CategoricalBlock]:
    """Cut the feature matrix into the two blocks the data contract declares."""
    numeric_columns = len(NUMERIC_FEATURE_COLUMNS)
    expected = numeric_columns + len(CATEGORICAL_FEATURE_COLUMNS)
    if features.shape[1] != expected:
        raise PipelineError(
            f"the split holds {features.shape[1]} feature columns, but the data "
            f"contract declares {expected}"
        )

    numeric = np.asarray(features[:, :numeric_columns], dtype=np.float64)
    categorical = np.asarray(features[:, numeric_columns:], dtype=np.str_)
    return numeric, categorical


def _read_part(name: str, stored: Mapping[str, object]) -> SplitPart:
    numeric: NumericBlock = np.asarray(stored[f"{name}_{NUMERIC_SUFFIX}"], dtype=np.float64)
    categorical: CategoricalBlock = np.asarray(
        stored[f"{name}_{CATEGORICAL_SUFFIX}"],
        dtype=np.str_,
    )
    targets: LabelVector = np.asarray(stored[f"{name}_{TARGETS_SUFFIX}"], dtype=np.str_)

    if numeric.shape[0] != targets.shape[0] or categorical.shape[0] != targets.shape[0]:
        raise PipelineError(
            f"the {name} part of the split holds a different number of feature "
            f"rows than labels"
        )

    features: FeatureMatrix = np.empty(
        (targets.shape[0], numeric.shape[1] + categorical.shape[1]),
        dtype=object,
    )
    features[:, : numeric.shape[1]] = numeric
    features[:, numeric.shape[1] :] = categorical

    return SplitPart(
        name=name,
        features=features,
        targets=targets,
        label_counts={label: int(np.sum(targets == label)) for label in LABELS},
    )

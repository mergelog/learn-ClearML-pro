from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt


# 生成データも学習側と同じ持ち方に合わせる。数値列とカテゴリ列が同居する
# ためobject行列、ラベルは文字列、混同行列は件数の整数。
FeatureMatrix = npt.NDArray[np.object_]
LabelVector = npt.NDArray[np.str_]
CountMatrix = npt.NDArray[np.int64]


@dataclass(frozen=True)
class DatasetVersion:
    version: str
    row_count: int
    random_seed_offset: int
    description: str


@dataclass(frozen=True)
class GeneratedDataset:
    definition: DatasetVersion
    csv_path: Path
    features: FeatureMatrix
    targets: LabelVector


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    group: str
    dataset_version: str
    model_kind: str
    parameters: dict[str, object]
    final_status: str = "completed"
    register_model: bool = False


@dataclass(frozen=True)
class ExperimentResult:
    metrics: dict[str, float]
    confusion_matrix: CountMatrix
    model: object


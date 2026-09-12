"""Read and write the Parameters a Task carries.

One module owns the spelling of every Parameter this project reads, so the
side that writes a Task and the side that reads it back cannot drift apart.
The writers are used by whoever builds a Task — the pipeline controller, the
search — and the readers by whoever runs as one.

Task Parameters are text. A step that reads them straight into a fit would
turn a mistyped value into a confusing failure deep inside scikit-learn, or
worse, into a run that silently used a default.

Everything here therefore converts explicitly and refuses what it cannot
convert, naming the parameter in the message. This module never contacts
ClearML: it is handed the mapping a Task answered with.
"""

from __future__ import annotations

from collections.abc import Mapping

from ml.semiconductor_quality.clearml_tracking import (
    ALGORITHM_PARAMETER,
    CLASS_WEIGHT_PARAMETER,
    DECISION_THRESHOLD_PARAMETER,
)
from ml.semiconductor_quality.clearml_tracking import (
    model_parameters as recorded_parameters,
)
from ml.semiconductor_quality.config import (
    Algorithm,
    ClassWeight,
    DatasetConfig,
    EstimatorConfig,
    HistGradientBoostingConfig,
    LogisticRegressionConfig,
    RandomForestConfig,
    SplitConfig,
)

from .domain import (
    DATASET_SECTION,
    EXECUTION_SECTION,
    MODEL_SECTION,
    SPLIT_SECTION,
    PipelineError,
)


RANDOM_SEED_PARAMETER = "random_seed"

# ClearMLのWeb UIで空にされた値と、書かれなかった値を同じに扱う。
# どちらも「指示されていない」であって、0でも空文字でもない。
ABSENT_VALUES = ("", "none", "null")

# 入り切りの設定として受け付ける綴り。
TRUE_VALUES = ("true", "yes", "1")
FALSE_VALUES = ("false", "no", "0")


def read_dataset(parameters: Mapping[str, str]) -> DatasetConfig:
    """Read which registered Dataset version this step works on."""
    defaults = DatasetConfig(dataset_version="")
    return DatasetConfig(
        dataset_version=text_of(parameters, DATASET_SECTION, "dataset_version"),
        dataset_project=text_of(
            parameters,
            DATASET_SECTION,
            "dataset_project",
            defaults.dataset_project,
        ),
        dataset_name=text_of(parameters, DATASET_SECTION, "dataset_name", defaults.dataset_name),
        dataset_csv_path=text_of(
            parameters,
            DATASET_SECTION,
            "dataset_csv_path",
            defaults.dataset_csv_path,
        ),
        dataset_alias=text_of(
            parameters,
            DATASET_SECTION,
            "dataset_alias",
            defaults.dataset_alias,
        ),
    )


def read_split(parameters: Mapping[str, str]) -> SplitConfig:
    defaults = SplitConfig()
    return SplitConfig(
        train_ratio=number_of(parameters, SPLIT_SECTION, "train_ratio", defaults.train_ratio),
        validation_ratio=number_of(
            parameters,
            SPLIT_SECTION,
            "validation_ratio",
            defaults.validation_ratio,
        ),
        test_ratio=number_of(parameters, SPLIT_SECTION, "test_ratio", defaults.test_ratio),
    )


def read_estimator(parameters: Mapping[str, str]) -> EstimatorConfig:
    """Read which algorithm a step fits, and the settings that algorithm reads.

    Only the block belonging to the chosen algorithm is filled from the Task.
    The other two keep their defaults, are not validated and never reach a fit,
    so a Task that carries a stale value for an algorithm it is not using
    cannot change the result.

    The imbalance policy and the probability cut are read whichever algorithm
    was chosen, because both mean the same thing in all three.
    """
    algorithm = _algorithm(parameters)
    class_weight = _class_weight(parameters)
    threshold = optional_number_of(parameters, MODEL_SECTION, DECISION_THRESHOLD_PARAMETER)

    if algorithm is Algorithm.RANDOM_FOREST:
        return EstimatorConfig(
            algorithm=algorithm,
            forest=_read_forest(parameters),
            class_weight=class_weight,
            decision_threshold=threshold,
        )
    if algorithm is Algorithm.LOGISTIC_REGRESSION:
        return EstimatorConfig(
            algorithm=algorithm,
            logistic=_read_logistic(parameters),
            class_weight=class_weight,
            decision_threshold=threshold,
        )
    return EstimatorConfig(
        algorithm=algorithm,
        boosting=_read_boosting(parameters),
        class_weight=class_weight,
        decision_threshold=threshold,
    )


def _algorithm(parameters: Mapping[str, str]) -> Algorithm:
    default = EstimatorConfig().algorithm
    named = text_of(parameters, MODEL_SECTION, ALGORITHM_PARAMETER, default.value)
    try:
        return Algorithm(named)
    except ValueError as error:
        known = ", ".join(str(algorithm) for algorithm in Algorithm)
        raise PipelineError(
            f"{MODEL_SECTION}/{ALGORITHM_PARAMETER} must be one of {known}, "
            f"but was {named!r}"
        ) from error


def _class_weight(parameters: Mapping[str, str]) -> ClassWeight:
    default = EstimatorConfig().class_weight
    named = text_of(parameters, MODEL_SECTION, CLASS_WEIGHT_PARAMETER, default.value)
    try:
        return ClassWeight(named)
    except ValueError as error:
        known = ", ".join(str(weight) for weight in ClassWeight)
        raise PipelineError(
            f"{MODEL_SECTION}/{CLASS_WEIGHT_PARAMETER} must be one of {known}, "
            f"but was {named!r}"
        ) from error


def _read_forest(parameters: Mapping[str, str]) -> RandomForestConfig:
    defaults = RandomForestConfig()
    return RandomForestConfig(
        n_estimators=whole_of(parameters, MODEL_SECTION, "n_estimators", defaults.n_estimators),
        max_depth=optional_whole_of(parameters, MODEL_SECTION, "max_depth"),
        min_samples_leaf=whole_of(
            parameters,
            MODEL_SECTION,
            "min_samples_leaf",
            defaults.min_samples_leaf,
        ),
    )


def _read_logistic(parameters: Mapping[str, str]) -> LogisticRegressionConfig:
    defaults = LogisticRegressionConfig()
    return LogisticRegressionConfig(
        regularisation=number_of(
            parameters,
            MODEL_SECTION,
            "regularisation",
            defaults.regularisation,
        ),
        max_iterations=whole_of(
            parameters,
            MODEL_SECTION,
            "max_iterations",
            defaults.max_iterations,
        ),
    )


def _read_boosting(parameters: Mapping[str, str]) -> HistGradientBoostingConfig:
    defaults = HistGradientBoostingConfig()
    return HistGradientBoostingConfig(
        learning_rate=number_of(
            parameters,
            MODEL_SECTION,
            "learning_rate",
            defaults.learning_rate,
        ),
        max_iterations=whole_of(
            parameters,
            MODEL_SECTION,
            "max_iterations",
            defaults.max_iterations,
        ),
        max_depth=optional_whole_of(parameters, MODEL_SECTION, "max_depth"),
        min_samples_leaf=whole_of(
            parameters,
            MODEL_SECTION,
            "min_samples_leaf",
            defaults.min_samples_leaf,
        ),
    )


def read_random_seed(parameters: Mapping[str, str], default: int) -> int:
    return whole_of(parameters, EXECUTION_SECTION, RANDOM_SEED_PARAMETER, default)


def lookup(parameters: Mapping[str, str], section: str, name: str) -> str | None:
    value = str(parameters.get(f"{section}/{name}", "")).strip()
    if value.lower() in ABSENT_VALUES:
        return None
    return value


def text_of(
    parameters: Mapping[str, str],
    section: str,
    name: str,
    default: str | None = None,
) -> str:
    value = lookup(parameters, section, name)
    if value is not None:
        return value
    if default is None:
        raise PipelineError(f"this step needs {section}/{name} to be set")
    return default


def number_of(parameters: Mapping[str, str], section: str, name: str, default: float) -> float:
    value = lookup(parameters, section, name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as error:
        raise PipelineError(
            f"{section}/{name} must be a number, but was {value!r}"
        ) from error


def whole_of(parameters: Mapping[str, str], section: str, name: str, default: int) -> int:
    value = lookup(parameters, section, name)
    if value is None:
        return default
    return _as_whole(section, name, value)


def optional_whole_of(parameters: Mapping[str, str], section: str, name: str) -> int | None:
    value = lookup(parameters, section, name)
    if value is None:
        return None
    return _as_whole(section, name, value)


def optional_number_of(parameters: Mapping[str, str], section: str, name: str) -> float | None:
    """A number the run may leave unset, which is not the same as zero."""
    value = lookup(parameters, section, name)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as error:
        raise PipelineError(
            f"{section}/{name} must be a number, but was {value!r}"
        ) from error


def flag_of(parameters: Mapping[str, str], section: str, name: str, default: bool) -> bool:
    """Read a setting that is either on or off.

    Only the spellings a person would actually write are accepted. Treating
    anything unrecognised as ``False`` would turn a typo into a silently
    disabled feature.
    """
    value = lookup(parameters, section, name)
    if value is None:
        return default
    if value.lower() in TRUE_VALUES:
        return True
    if value.lower() in FALSE_VALUES:
        return False
    raise PipelineError(
        f"{section}/{name} must be one of "
        f"{', '.join((*TRUE_VALUES, *FALSE_VALUES))}, but was {value!r}"
    )


def _as_whole(section: str, name: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise PipelineError(
            f"{section}/{name} must be a whole number, but was {value!r}"
        ) from error


def dataset_parameters(dataset: DatasetConfig) -> dict[str, str]:
    return {
        f"{DATASET_SECTION}/dataset_version": dataset.dataset_version,
        f"{DATASET_SECTION}/dataset_project": dataset.dataset_project,
        f"{DATASET_SECTION}/dataset_name": dataset.dataset_name,
        f"{DATASET_SECTION}/dataset_csv_path": dataset.dataset_csv_path,
        f"{DATASET_SECTION}/dataset_alias": dataset.dataset_alias,
    }


def split_parameters(split: SplitConfig) -> dict[str, str]:
    return {
        f"{SPLIT_SECTION}/train_ratio": str(split.train_ratio),
        f"{SPLIT_SECTION}/validation_ratio": str(split.validation_ratio),
        f"{SPLIT_SECTION}/test_ratio": str(split.test_ratio),
    }


def estimator_parameters(estimator: EstimatorConfig) -> dict[str, str]:
    """The algorithm of a run, and only the settings that algorithm reads.

    Writing the settings of all three algorithms onto the step would invite
    somebody to change one that has no effect on the result.
    """
    return {
        f"{MODEL_SECTION}/{name}": _as_parameter(value)
        for name, value in recorded_parameters(estimator).items()
    }


def _as_parameter(value: object) -> str:
    # 未指定（深さ無制限など）は0でも "None" でもなく、空で残す。
    # 読む側はそれを「指示されていない」として扱う。
    return "" if value is None else str(value)


def seed_parameters(random_seed: int) -> dict[str, str]:
    return {f"{EXECUTION_SECTION}/{RANDOM_SEED_PARAMETER}": str(random_seed)}

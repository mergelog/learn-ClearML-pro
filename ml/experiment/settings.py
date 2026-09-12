"""Read the settings a search runs under, one environment at a time.

Until now every setting of this project was a single file, because every
setting meant the same thing everywhere: the columns of the Dataset, the bar
the evaluation gate holds models to. A search is the first thing that does
not. What may be spent, how long it may run and which queue it runs on are
genuinely different in a developer's environment, in the environment a change
is verified in, and in the one that produces the model that gets deployed.

So the settings are read in two layers. ``base.yaml`` holds what a search
means — what it varies, what it optimises, how a candidate is judged — and is
the same everywhere. ``<environment>.yaml`` holds only what that environment
changes, which is almost always the budget and the queues. Reading them as
"the shared meaning, then this environment's limits" is what keeps a
production budget from being copied into a developer's file by accident.

Three rules are enforced here rather than left to the reader.

An unknown key is refused. A setting that was renamed, or misspelled, would
otherwise be silently ignored and the search would quietly run with a default
nobody chose.

A credential is refused. These files are read by everyone and committed;
connection settings and credentials come from the environment
(:class:`ClearmlSettings`) and never from here. The check is the same detector
the repository wide secret scan uses, applied before the file is parsed.

The parsing of the estimator settings is borrowed from the pipeline rather
than written again, so a value means exactly the same thing whether it arrives
from a file, from a Task Parameter or from the command line.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from ml.pipeline.domain import MODEL_SECTION, PipelineError
from ml.pipeline.parameters import read_estimator
from ml.security.secrets import scan_text
from ml.semiconductor_quality.clearml_tracking import ALGORITHM_PARAMETER
from ml.semiconductor_quality.config import Algorithm, EstimatorConfig

from .domain import (
    Budget,
    ChoiceRange,
    Direction,
    Environment,
    ExecutionPlacement,
    ExperimentError,
    ExperimentPlan,
    IntegerRange,
    NumberRange,
    Objective,
    ParameterRange,
    SearchSpace,
    TrialPlan,
)


DEFAULT_SETTINGS_DIRECTORY = Path(__file__).resolve().parents[2] / "config" / "experiment"

BASE_FILE_NAME = "base.yaml"

# どの環境の設定で走るかを指示する環境変数。指定が無ければ開発環境として扱う。
# 本番の予算で走らせるには、必ずどこかで明示しなければならない。
ENVIRONMENT_VARIABLE = "EXPERIMENT_ENVIRONMENT"
DEFAULT_ENVIRONMENT = Environment.DEVELOPMENT

OBJECTIVE_KEY = "objective"
SEARCH_KEY = "search"
BUDGET_KEY = "budget"
TRIAL_KEY = "trial"
EXECUTION_KEY = "execution"

SECTION_KEYS = (OBJECTIVE_KEY, SEARCH_KEY, BUDGET_KEY, TRIAL_KEY, EXECUTION_KEY)

ALGORITHM_KEY = "algorithm"
PARAMETERS_KEY = "parameters"
DEFAULTS_KEY = "defaults"

INTEGER_KIND = "integer"
NUMBER_KIND = "number"
CHOICE_KIND = "choice"
RANGE_KINDS = (INTEGER_KIND, NUMBER_KIND, CHOICE_KIND)

OBJECTIVE_FIELDS = ("metric", "direction")
SEARCH_FIELDS = (ALGORITHM_KEY, PARAMETERS_KEY, DEFAULTS_KEY)
BUDGET_FIELDS = (
    "max_trials",
    "parallel_trials",
    "trial_minutes",
    "total_minutes",
    "keep_top",
    "minimum_folds",
)
TRIAL_FIELDS = ("folds", "tune_threshold", "threshold_folds")
EXECUTION_FIELDS = ("trial_queue", "optimizer_queue")

INTEGER_FIELDS = ("minimum", "maximum", "step")
NUMBER_FIELDS = ("minimum", "maximum", "logarithmic")


def resolve_environment(name: str | None = None) -> Environment:
    """Answer which environment's settings to read.

    A name given on the command line wins over the environment variable, and
    an unknown name is refused rather than falling back to the development
    budget under a production label.
    """
    requested = (name or os.environ.get(ENVIRONMENT_VARIABLE) or "").strip()
    if not requested:
        return DEFAULT_ENVIRONMENT
    try:
        return Environment(requested)
    except ValueError as error:
        known = ", ".join(str(environment) for environment in Environment)
        raise ExperimentError(
            f"{requested!r} is not an environment of this project. Known: {known}"
        ) from error


def settings_files(environment: Environment, directory: Path | None = None) -> tuple[Path, Path]:
    """The two files one environment is read from, in the order they are layered."""
    root = directory or DEFAULT_SETTINGS_DIRECTORY
    return root / BASE_FILE_NAME, root / f"{environment.value}.yaml"


def load_plan(
    environment: Environment | None = None,
    directory: Path | None = None,
) -> ExperimentPlan:
    """Read one environment's search settings, or refuse them."""
    resolved = environment or DEFAULT_ENVIRONMENT
    base_file, overlay_file = settings_files(resolved, directory)
    document = _merged(_read(base_file), _read(overlay_file))
    _require_known(document, SECTION_KEYS, "the settings", overlay_file)

    space = _read_space(document, base_file)
    return ExperimentPlan(
        environment=resolved,
        space=space,
        objective=_read_objective(document, base_file),
        budget=_read_budget(document, overlay_file),
        trial=_read_trial(document, base_file),
        placement=_read_placement(document, overlay_file),
        estimator=_read_estimator_defaults(document, space.algorithm, base_file),
    ).validate()


def _read(path: Path) -> Mapping[str, Any]:
    """Read one settings file, refusing anything that carries a credential."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ExperimentError(
            f"the experiment settings at {path} cannot be read: {error}"
        ) from error

    findings = scan_text(text, str(path))
    if findings:
        raise ExperimentError(
            f"{path} holds what looks like a credential, and settings files are "
            "read by everyone. Connection settings come from the environment:\n"
            + "\n".join(f"- {finding.describe()}" for finding in findings)
        )

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ExperimentError(
            f"the experiment settings at {path} are not valid YAML: {error}"
        ) from error

    if document is None:
        return {}
    if not isinstance(document, dict):
        raise ExperimentError(f"the experiment settings at {path} do not hold a mapping")
    return document


def _merged(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """Lay one environment's settings over the shared ones.

    Mappings are merged key by key so that an environment can change one limit
    without repeating the section it sits in. Anything else replaces what it
    covers, because a list that was half overridden would be neither.
    """
    merged = dict(base)
    for key, value in overlay.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _merged(existing, value)
        else:
            merged[key] = value
    return merged


def _require_known(
    document: Mapping[str, Any],
    known: Sequence[str],
    what: str,
    path: Path,
) -> None:
    unknown = sorted(set(document) - set(known))
    if unknown:
        raise ExperimentError(
            f"{what} in {path} names settings this project does not read: "
            f"{', '.join(unknown)}. Known: {', '.join(known)}"
        )


def _section(document: Mapping[str, Any], key: str, path: Path) -> Mapping[str, Any]:
    value = document.get(key, {})
    if not isinstance(value, dict):
        raise ExperimentError(f"{key} in {path} must hold a mapping, but was {value!r}")
    return value


def _read_objective(document: Mapping[str, Any], path: Path) -> Objective:
    section = _section(document, OBJECTIVE_KEY, path)
    _require_known(section, OBJECTIVE_FIELDS, OBJECTIVE_KEY, path)
    defaults = Objective()
    return Objective(
        metric=str(section.get("metric", defaults.metric)),
        direction=_direction(section.get("direction", defaults.direction.value), path),
    )


def _direction(value: object, path: Path) -> Direction:
    try:
        return Direction(str(value))
    except ValueError as error:
        known = ", ".join(str(direction) for direction in Direction)
        raise ExperimentError(
            f"direction in {path} must be one of {known}, but was {value!r}"
        ) from error


def _read_space(document: Mapping[str, Any], path: Path) -> SearchSpace:
    section = _section(document, SEARCH_KEY, path)
    _require_known(section, SEARCH_FIELDS, SEARCH_KEY, path)
    parameters = _section(section, PARAMETERS_KEY, path)
    return SearchSpace(
        algorithm=_algorithm(section.get(ALGORITHM_KEY, Algorithm.RANDOM_FOREST.value), path),
        ranges=tuple(
            _read_range(name, declaration, path) for name, declaration in parameters.items()
        ),
    )


def _algorithm(value: object, path: Path) -> Algorithm:
    try:
        return Algorithm(str(value))
    except ValueError as error:
        known = ", ".join(str(algorithm) for algorithm in Algorithm)
        raise ExperimentError(
            f"algorithm in {path} must be one of {known}, but was {value!r}"
        ) from error


def _read_range(name: str, declaration: object, path: Path) -> ParameterRange:
    """Build one parameter range out of the one shape it declares."""
    if not isinstance(declaration, dict):
        raise ExperimentError(
            f"{SEARCH_KEY}.{PARAMETERS_KEY}.{name} in {path} must declare one of "
            f"{', '.join(RANGE_KINDS)}, but was {declaration!r}"
        )

    declared = [kind for kind in RANGE_KINDS if kind in declaration]
    _require_known(declaration, RANGE_KINDS, f"{PARAMETERS_KEY}.{name}", path)
    if len(declared) != 1:
        raise ExperimentError(
            f"{SEARCH_KEY}.{PARAMETERS_KEY}.{name} in {path} must declare exactly "
            f"one of {', '.join(RANGE_KINDS)}, but declared {len(declared)}"
        )

    kind = declared[0]
    body = declaration[kind]
    if kind == CHOICE_KIND:
        return _read_choice(name, body, path)
    if not isinstance(body, dict):
        raise ExperimentError(
            f"{SEARCH_KEY}.{PARAMETERS_KEY}.{name}.{kind} in {path} must hold a "
            f"mapping, but was {body!r}"
        )
    if kind == INTEGER_KIND:
        _require_known(body, INTEGER_FIELDS, f"{PARAMETERS_KEY}.{name}.{kind}", path)
        defaults = IntegerRange(name=name)
        return IntegerRange(
            name=name,
            minimum=_whole(body.get("minimum", defaults.minimum), name, path),
            maximum=_whole(body.get("maximum", defaults.maximum), name, path),
            step=_whole(body.get("step", defaults.step), name, path),
        )
    _require_known(body, NUMBER_FIELDS, f"{PARAMETERS_KEY}.{name}.{kind}", path)
    number_defaults = NumberRange(name=name)
    return NumberRange(
        name=name,
        minimum=_number(body.get("minimum", number_defaults.minimum), name, path),
        maximum=_number(body.get("maximum", number_defaults.maximum), name, path),
        logarithmic=bool(body.get("logarithmic", number_defaults.logarithmic)),
    )


def _read_choice(name: str, body: object, path: Path) -> ChoiceRange:
    """Read a choice, keeping the values as the text a Task Parameter carries."""
    if not isinstance(body, list):
        raise ExperimentError(
            f"{SEARCH_KEY}.{PARAMETERS_KEY}.{name}.{CHOICE_KIND} in {path} must "
            f"hold a list of values, but was {body!r}"
        )
    return ChoiceRange(name=name, values=tuple(_as_parameter_text(value) for value in body))


def _as_parameter_text(value: object) -> str:
    """Render one choice as the text a Task carries.

    ``None`` becomes the empty value on purpose: that is how the readers of the
    training parameters spell "not instructed", which is what an unlimited
    tree depth is.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _read_budget(document: Mapping[str, Any], path: Path) -> Budget:
    section = _section(document, BUDGET_KEY, path)
    _require_known(section, BUDGET_FIELDS, BUDGET_KEY, path)
    defaults = Budget()
    return Budget(
        max_trials=_whole(section.get("max_trials", defaults.max_trials), "max_trials", path),
        parallel_trials=_whole(
            section.get("parallel_trials", defaults.parallel_trials),
            "parallel_trials",
            path,
        ),
        trial_minutes=_number(
            section.get("trial_minutes", defaults.trial_minutes),
            "trial_minutes",
            path,
        ),
        total_minutes=_number(
            section.get("total_minutes", defaults.total_minutes),
            "total_minutes",
            path,
        ),
        keep_top=_whole(section.get("keep_top", defaults.keep_top), "keep_top", path),
        minimum_folds=_whole(
            section.get("minimum_folds", defaults.minimum_folds),
            "minimum_folds",
            path,
        ),
    )


def _read_trial(document: Mapping[str, Any], path: Path) -> TrialPlan:
    section = _section(document, TRIAL_KEY, path)
    _require_known(section, TRIAL_FIELDS, TRIAL_KEY, path)
    defaults = TrialPlan()
    return TrialPlan(
        folds=_whole(section.get("folds", defaults.folds), "folds", path),
        tune_threshold=bool(section.get("tune_threshold", defaults.tune_threshold)),
        threshold_folds=_whole(
            section.get("threshold_folds", defaults.threshold_folds),
            "threshold_folds",
            path,
        ),
    )


def _read_placement(document: Mapping[str, Any], path: Path) -> ExecutionPlacement:
    section = _section(document, EXECUTION_KEY, path)
    _require_known(section, EXECUTION_FIELDS, EXECUTION_KEY, path)
    defaults = ExecutionPlacement()
    return ExecutionPlacement(
        trial_queue=str(section.get("trial_queue", defaults.trial_queue)).strip(),
        optimizer_queue=str(section.get("optimizer_queue", defaults.optimizer_queue)).strip(),
    )


def _read_estimator_defaults(
    document: Mapping[str, Any],
    algorithm: Algorithm,
    path: Path,
) -> EstimatorConfig:
    """Read the settings a search starts from, for what it does not vary.

    A search that varies two settings still has to fit the rest of them. They
    are read through the same reader the pipeline steps use, so a value
    written here means what it would mean on a Task.
    """
    section = _section(document, SEARCH_KEY, path)
    defaults = _section(section, DEFAULTS_KEY, path)
    parameters = {f"{MODEL_SECTION}/{ALGORITHM_PARAMETER}": algorithm.value}
    parameters.update(
        {f"{MODEL_SECTION}/{name}": _as_parameter_text(value) for name, value in defaults.items()}
    )
    try:
        return read_estimator(parameters)
    except PipelineError as error:
        raise ExperimentError(
            f"{SEARCH_KEY}.{DEFAULTS_KEY} in {path} cannot be read: {error}"
        ) from error


def _whole(value: object, name: str, path: Path) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExperimentError(f"{name} in {path} must be a whole number, but was {value!r}")
    return value


def _number(value: object, name: str, path: Path) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExperimentError(f"{name} in {path} must be a number, but was {value!r}")
    return float(value)

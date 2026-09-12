"""ClearML boundary of the pipeline steps.

Every call into the ClearML SDK that a step makes is made from here, so the
work each step performs stays in :mod:`ml.semiconductor_quality` and can be
exercised without a server.

A step reads its inputs in one of two ways, and the difference matters.

Parameters say *what* to do: which Dataset version, which ratios, which forest
settings. The Pipeline controller writes them onto the cloned Task before the
step starts, which is how one pipeline definition serves many runs.

Artifacts say *what the previous step produced*. A step is told the Task id of
each upstream step it declared, and reads named Artifacts off those Tasks.
Nothing is passed implicitly through a shared directory, so a step can run on
a different machine, later, without the steps before it still existing in
memory.

The Dataset is deliberately re-read by identifier rather than by version. The
validation step records the identifier it resolved, and the preprocessing step
reads that identifier, so the rows a model is fitted on are provably the rows
that were validated, even if the version label is later moved.
"""

from __future__ import annotations

import getpass
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

import joblib
from clearml import Logger, OutputModel, Task
from clearml.model import Framework
from sklearn.pipeline import Pipeline

from ml.data_quality.checks import check as apply_quality_checks
from ml.data_quality.contract import load_contract as load_quality_contract
from ml.data_quality.domain import DatasetProfile
from ml.data_quality.drift import compare as compare_profiles
from ml.data_quality.lineage import (
    LineageRecord,
    LineageStage,
    Producer,
    build_link,
)
from ml.data_quality.profile import profile_csv
from ml.model_lifecycle.domain import (
    METADATA_DATASET_ID,
    METADATA_DATASET_VERSION,
    METADATA_EVALUATE_TASK_ID,
    METADATA_MODEL_VERSION,
    METADATA_PREVIOUS_STAGE,
    METADATA_PROMOTED_AT,
    METADATA_PROMOTED_BY,
    METADATA_PROMOTION_REASON,
    METADATA_REGISTER_TASK_ID,
    METADATA_STAGE,
    METADATA_TRAIN_TASK_ID,
    METADATA_TRAINING_FAILURE_SHARE,
    ModelStage,
    build_model_version,
    utc_now,
)
from ml.model_lifecycle.gate import apply_gate, load_criteria
from ml.model_lifecycle.registry import METADATA_TYPE
from ml.semiconductor_quality.clearml_tracking import (
    CONFUSION_MATRIX_COMMENT,
    CONFUSION_MATRIX_TITLE,
    METRICS_ITERATION,
    MODEL_COMMENT,
    MODEL_LABEL_ENUMERATION,
    fetch_dataset,
    fetch_dataset_by_id,
)
from ml.semiconductor_quality.config import DatasetConfig
from ml.semiconductor_quality.dataset import load_training_input, resolve_csv_path
from ml.semiconductor_quality.domain import (
    MODEL_NAME,
    POSITIVE_LABEL,
    DatasetValidationReport,
    EvaluationResult,
    FetchedDataset,
)
from ml.semiconductor_quality.evaluate import evaluate_split
from ml.semiconductor_quality.preprocess import split_training_input
from ml.semiconductor_quality.train import (
    MODEL_FILE_NAME,
    build_contract_pipeline,
    fit_pipeline,
    predict_part,
)

from .artifacts import describe_split, read_json, read_split, write_split
from .domain import (
    DATA_DRIFT_ARTIFACT,
    DATA_PROFILE_ARTIFACT,
    DATA_QUALITY_ARTIFACT,
    DATA_QUALITY_SECTION,
    DATASET_SECTION,
    DECISION_ARTIFACT,
    EVALUATION_ARTIFACT,
    LINEAGE_ARTIFACT,
    MODEL_WEIGHTS_ARTIFACT,
    RESOLVED_DATASET_SECTION,
    SPLIT_ARTIFACT,
    SPLIT_SUMMARY_ARTIFACT,
    VALIDATION_REPORT_ARTIFACT,
    PipelineError,
    StepInputs,
    StepName,
)
from .parameters import read_dataset, read_estimator, read_random_seed
from .parameters import read_split as read_split_config


DEFAULT_RANDOM_SEED_FALLBACK = 20260906

# candidate へ入れたのは人ではなく基準そのものである。承認者としてそう記録する。
# staging 以降は人の承認が要る（ml/model_lifecycle/cli.py）。
GATE_APPROVER = "evaluation-gate"

# 実行したマシンの中だけを指すURL。ここに登録されたモデルは配備できない。
LOCAL_URL_PREFIX = "file://"

# 比較対象のDataset Versionを指すパラメータ。空なら比較しない。
DRIFT_REFERENCE_PARAMETER = "drift_reference_version"

# driftが閾値を超えたTaskに付ける印。一覧から絞り込める唯一の手段である。
DRIFT_TAG = "data-drift"

RESOLVED_DATASET_ID = "dataset_id"
RESOLVED_DATASET_VERSION = "dataset_version"


class StepTask:
    """The ClearML Task one pipeline step runs as."""

    def __init__(self, task: Task) -> None:
        self._task = task

    @property
    def id(self) -> str:
        return str(self._task.id)

    @property
    def parameters(self) -> Mapping[str, str]:
        """What the Pipeline controller told this step to do."""
        return _as_text(self._task.get_parameters())

    def parameters_of(self, task_id: str) -> Mapping[str, str]:
        """Read the Parameters an upstream step recorded."""
        upstream: Task = Task.get_task(task_id=task_id)
        return _as_text(upstream.get_parameters())

    def record(self, section: str, values: Mapping[str, str]) -> None:
        """Write what this step resolved, so the next step can read it back."""
        for name, value in values.items():
            self._task.set_parameter(f"{section}/{name}", value)

    def upload_file(self, name: str, path: Path) -> None:
        """Hand a file to the next step under a name it can address."""
        self._task.upload_artifact(name, artifact_object=path, wait_on_upload=True)

    def upload_json(self, name: str, content: Mapping[str, object]) -> None:
        self._task.upload_artifact(
            name,
            artifact_object=dict(content),
            wait_on_upload=True,
            auto_pickle=False,
            sort_keys=False,
        )

    def fetch_json(self, task_id: str, name: str) -> Mapping[str, object]:
        """Read a JSON artifact an upstream step uploaded, as the object it is.

        ClearML hands a dictionary artifact back directly, so there is nothing
        to download and nothing to parse. An artifact that is missing or is not
        an object is reported as empty, because the callers of this treat a
        missing measurement as "not known" rather than as a failure.
        """
        upstream: Task = Task.get_task(task_id=task_id)
        artifact = upstream.artifacts.get(name)
        if artifact is None:
            return {}
        content = artifact.get()
        return content if isinstance(content, dict) else {}

    def fetch_artifact(self, task_id: str, name: str) -> Path:
        """Take a local copy of a named Artifact of an upstream step."""
        upstream: Task = Task.get_task(task_id=task_id)
        artifact = upstream.artifacts.get(name)
        if artifact is None:
            raise PipelineError(
                f"the {name!r} artifact is missing from Task {task_id}, so this "
                "step has nothing to read"
            )
        return Path(str(artifact.get_local_copy()))

    def warn(self, message: str) -> None:
        """Put something on the Task log that a person has to read.

        Used for facts that do not stop the run but change what it means, so
        they survive on the Task rather than only in the console of whoever
        happened to be watching.
        """
        self._task.get_logger().report_text(message)

    def tag(self, tag: str) -> None:
        """Mark the Task, so it can be found again from a list."""
        self._task.add_tags([tag])

    def report_result(self, result: EvaluationResult) -> None:
        logger: Logger = self._task.get_logger()
        for name, value in result.metrics.items():
            logger.report_scalar(
                title=name,
                series=result.split_name,
                value=float(value),
                iteration=METRICS_ITERATION,
            )
        logger.report_confusion_matrix(
            title=CONFUSION_MATRIX_TITLE,
            series=result.split_name,
            matrix=result.confusion_matrix,
            iteration=METRICS_ITERATION,
            xlabels=list(result.labels),
            ylabels=list(result.labels),
            comment=CONFUSION_MATRIX_COMMENT,
        )

    def register_model(
        self,
        weights: Path,
        *,
        tags: Sequence[str],
        metadata: Mapping[str, str],
    ) -> str:
        """Attach the fitted pipeline as the Output Model of this step.

        The stage tag and the record of how the model got it are written
        before the weights are uploaded, so a model never exists in the
        registry without a stage somebody can account for.
        """
        model = OutputModel(
            task=self._task,
            name=MODEL_NAME,
            framework=Framework.scikitlearn,
            label_enumeration=dict(MODEL_LABEL_ENUMERATION),
            comment=MODEL_COMMENT,
        )
        model.tags = list(tags)
        for name, value in metadata.items():
            model.set_metadata(name, value, METADATA_TYPE)
        model.update_weights(
            weights_filename=str(weights),
            auto_delete_file=False,
            async_enable=False,
        )
        _require_shared_weights(model)
        return str(model.id)


def run_validate(task: StepTask, _work_dir: Path) -> None:
    """Refuse the run here, or state exactly which rows the rest may use.

    This is the only step that reads the raw Dataset, and it judges it twice.

    First against the data quality contract: are these rows fit to train on at
    all. That is measured on the raw text, before anything is parsed, because
    a strict parse would have already thrown away the evidence — a missing
    value cannot be counted once it has been refused.

    Then against the training input contract: can these rows be turned into a
    learning input. Both have to pass before any model is fitted, which is why
    a broken Dataset version stops the pipeline here.

    A comparison against an earlier version is made when one is named. Drift
    does not stop the run: the data is still usable, but somebody has to know
    the world moved.
    """
    config = read_dataset(task.parameters).validate()
    fetched = fetch_dataset(config)
    csv_path = resolve_csv_path(fetched.local_root, config.dataset_csv_path)

    profile = profile_csv(csv_path)
    quality = apply_quality_checks(load_quality_contract(), profile)
    task.upload_json(DATA_PROFILE_ARTIFACT, profile.as_document())
    task.upload_json(DATA_QUALITY_ARTIFACT, quality.as_document())
    if not quality.passed:
        raise PipelineError(quality.describe())

    training_input = load_training_input(fetched, config.dataset_csv_path)
    report = training_input.report

    task.upload_json(LINEAGE_ARTIFACT, _describe_lineage(fetched, profile).as_document())
    _record_drift(task, config, profile)

    task.record(
        RESOLVED_DATASET_SECTION,
        {
            RESOLVED_DATASET_ID: report.source.dataset_id,
            RESOLVED_DATASET_VERSION: report.source.dataset_version,
        },
    )
    task.upload_json(VALIDATION_REPORT_ARTIFACT, _describe_report(report))


def _failure_share(task: StepTask, validate_task_id: str) -> float:
    """The share of failures the model was trained against.

    It is recorded on the model so that the prediction service can compare it
    with what it is actually answering. A model that saw a quarter failures and
    now reports none is not necessarily broken, but somebody has to look.
    """
    profile = task.fetch_json(validate_task_id, DATA_PROFILE_ARTIFACT)
    counts = profile.get("label_counts")
    rows = profile.get("row_count")
    if not isinstance(counts, dict) or not isinstance(rows, int) or rows <= 0:
        return 0.0
    return float(counts.get(POSITIVE_LABEL, 0)) / rows


def _record_drift(task: StepTask, config: DatasetConfig, profile: DatasetProfile) -> None:
    """Compare against an earlier version, when the run named one.

    Drift is reported rather than refused. A Dataset that moved is still a
    Dataset somebody may want to train on; what must not happen is training on
    it without anybody noticing that it moved.
    """
    reference_version = str(
        task.parameters.get(f"{DATA_QUALITY_SECTION}/{DRIFT_REFERENCE_PARAMETER}", "")
    ).strip()
    if not reference_version:
        return

    reference = fetch_dataset(replace(config, dataset_version=reference_version))
    reference_profile = profile_csv(
        resolve_csv_path(reference.local_root, config.dataset_csv_path)
    )
    report = compare_profiles(
        reference_profile,
        profile,
        reference_name=reference_version,
        current_name=config.dataset_version,
    )

    task.upload_json(DATA_DRIFT_ARTIFACT, report.as_document())
    if report.has_drifted:
        # 通知の代わりにTaskへ痕跡を残す。タグは一覧から絞り込める唯一の手段で、
        # ログは「何がどれだけ動いたか」を残す場所である。
        task.warn(report.describe())
        task.tag(DRIFT_TAG)


def run_preprocess(task: StepTask, work_dir: Path) -> None:
    """Divide the approved rows into the three parts the rest of the run uses."""
    inputs = StepInputs.from_parameters(task.parameters)
    validate_task_id = inputs.required(StepName.VALIDATE)

    approved = _approved_dataset(task, validate_task_id)
    fetched = fetch_dataset_by_id(approved.dataset_id, alias=approved.dataset_alias)
    training_input = load_training_input(fetched, approved.csv_path)

    split = split_training_input(
        training_input,
        read_split_config(task.parameters).validate(),
        read_random_seed(task.parameters, DEFAULT_RANDOM_SEED_FALLBACK),
    )

    task.upload_file(SPLIT_ARTIFACT, write_split(work_dir, split))
    task.upload_json(SPLIT_SUMMARY_ARTIFACT, describe_split(split))


def run_train(task: StepTask, work_dir: Path) -> None:
    """Fit the model on the training part, and on nothing else."""
    inputs = StepInputs.from_parameters(task.parameters)
    split = read_split(
        task.fetch_artifact(inputs.required(StepName.PREPROCESS), SPLIT_ARTIFACT)
    )

    pipeline = build_contract_pipeline(
        read_estimator(task.parameters).validate(),
        read_random_seed(task.parameters, DEFAULT_RANDOM_SEED_FALLBACK),
    )
    fit_pipeline(pipeline, split.train)

    weights = work_dir / MODEL_FILE_NAME
    joblib.dump(pipeline, weights)
    task.upload_file(MODEL_WEIGHTS_ARTIFACT, weights)


def run_evaluate(task: StepTask, _work_dir: Path) -> None:
    """Score the fitted model, spending the test part exactly once."""
    inputs = StepInputs.from_parameters(task.parameters)
    split = read_split(
        task.fetch_artifact(inputs.required(StepName.PREPROCESS), SPLIT_ARTIFACT)
    )
    weights = task.fetch_artifact(inputs.required(StepName.TRAIN), MODEL_WEIGHTS_ARTIFACT)
    pipeline = _load_pipeline(weights)

    results = tuple(
        evaluate_split(part, predict_part(pipeline, part))
        for part in (split.validation, split.test)
    )
    for result in results:
        task.report_result(result)

    task.upload_json(EVALUATION_ARTIFACT, _describe_results(results))


def run_register_candidate(task: StepTask, _work_dir: Path) -> None:
    """Register the model, but only if it cleared the evaluation gate.

    A model that did not clear it is not registered at all. Keeping it out of
    the registry is a stronger guarantee than marking it, and the numbers it
    was refused for stay readable on this Task either way.

    The step fails when the gate refuses, so the pipeline run is red rather
    than a green run that quietly produced nothing.
    """
    inputs = StepInputs.from_parameters(task.parameters)
    validate_task_id = inputs.required(StepName.VALIDATE)
    train_task_id = inputs.required(StepName.TRAIN)
    evaluate_task_id = inputs.required(StepName.EVALUATE)

    evaluation = read_json(task.fetch_artifact(evaluate_task_id, EVALUATION_ARTIFACT))
    verdict = apply_gate(load_criteria(), evaluation)

    decision: dict[str, object] = {
        "registered": verdict.passed,
        "gate": verdict.as_metadata(),
        "validate_task_id": validate_task_id,
        "train_task_id": train_task_id,
        "evaluate_task_id": evaluate_task_id,
        "evaluation": evaluation,
    }

    if not verdict.passed:
        task.upload_json(DECISION_ARTIFACT, decision)
        raise PipelineError(verdict.describe())

    approved = _approved_dataset(task, validate_task_id)
    dataset_version = _upstream_value(
        task.parameters_of(validate_task_id),
        RESOLVED_DATASET_VERSION,
        approved.dataset_id,
        section=RESOLVED_DATASET_SECTION,
    )
    model_version = build_model_version(dataset_version, train_task_id, datetime.now(timezone.utc))

    model_id = task.register_model(
        task.fetch_artifact(train_task_id, MODEL_WEIGHTS_ARTIFACT),
        tags=[ModelStage.CANDIDATE.tag],
        metadata={
            METADATA_STAGE: ModelStage.CANDIDATE.value,
            METADATA_MODEL_VERSION: model_version,
            METADATA_DATASET_ID: approved.dataset_id,
            METADATA_DATASET_VERSION: dataset_version,
            METADATA_TRAIN_TASK_ID: train_task_id,
            METADATA_TRAINING_FAILURE_SHARE: str(_failure_share(task, validate_task_id)),
            METADATA_EVALUATE_TASK_ID: evaluate_task_id,
            METADATA_REGISTER_TASK_ID: task.id,
            METADATA_PREVIOUS_STAGE: ModelStage.CANDIDATE.value,
            METADATA_PROMOTED_BY: GATE_APPROVER,
            METADATA_PROMOTED_AT: utc_now(),
            METADATA_PROMOTION_REASON: verdict.describe(),
            **verdict.as_metadata(),
        },
    )

    decision["model_id"] = model_id
    decision["model_version"] = model_version
    task.upload_json(DECISION_ARTIFACT, decision)


STEP_IMPLEMENTATIONS: Mapping[StepName, Callable[[StepTask, Path], None]] = {
    StepName.VALIDATE: run_validate,
    StepName.PREPROCESS: run_preprocess,
    StepName.TRAIN: run_train,
    StepName.EVALUATE: run_evaluate,
    StepName.REGISTER_CANDIDATE: run_register_candidate,
}


def run_step(step: StepName, task: StepTask, work_dir: Path) -> None:
    """Carry out one named step of the pipeline."""
    STEP_IMPLEMENTATIONS[step](task, work_dir)


def _require_shared_weights(model: OutputModel) -> None:
    """Refuse a model whose weights only exist on the machine that made it.

    When a Task has no output destination, ClearML records the local path of
    the file instead of uploading it. The model then looks registered and is
    unusable from anywhere else, which is discovered much later — by whoever
    tries to deploy it.
    """
    url = str(model.url or "")
    if not url or url.startswith(LOCAL_URL_PREFIX):
        raise PipelineError(
            f"the model was registered as {url!r}, which is a path on this machine "
            "rather than a location the rest of the system can read. The Task has "
            "no output destination"
        )


def _as_text(parameters: Mapping[str, object] | None) -> Mapping[str, str]:
    """Read a Task's Parameters as the text they are stored as.

    A Task that holds no parameters answers ``None``, which is the same thing
    as holding none, and the readers already refuse what they need and cannot
    find.
    """
    return {name: str(value) for name, value in (parameters or {}).items()}


@dataclass(frozen=True)
class ApprovedDataset:
    """The exact rows the validation step approved, and where to read them."""

    dataset_id: str
    csv_path: str
    dataset_alias: str


def _approved_dataset(task: StepTask, validate_task_id: str) -> ApprovedDataset:
    """Address the exact Dataset the validation step approved.

    The identifier is used instead of the version, because a version label can
    be moved onto other rows while an identifier cannot.
    """
    upstream = task.parameters_of(validate_task_id)
    dataset_id = str(
        upstream.get(f"{RESOLVED_DATASET_SECTION}/{RESOLVED_DATASET_ID}", "")
    ).strip()
    if not dataset_id:
        raise PipelineError(
            f"Task {validate_task_id} did not record which Dataset it approved, "
            "so this step cannot read the same rows"
        )

    # 版数はもう使わない。必要なのは「どのファイルを、どの別名で読むか」だけで、
    # どの行を読むかは識別子がすでに決めている。
    defaults = DatasetConfig(dataset_version=dataset_id)
    return ApprovedDataset(
        dataset_id=dataset_id,
        csv_path=_upstream_value(upstream, "dataset_csv_path", defaults.dataset_csv_path),
        dataset_alias=_upstream_value(upstream, "dataset_alias", defaults.dataset_alias),
    )


def _upstream_value(
    upstream: Mapping[str, str],
    name: str,
    default: str,
    section: str = DATASET_SECTION,
) -> str:
    return str(upstream.get(f"{section}/{name}", "")).strip() or default


def _load_pipeline(weights: Path) -> Pipeline:
    """Read the weights the training step handed on.

    A damaged artifact fails as whatever ``joblib`` tripped over while
    unpickling (``KeyError: 0``, ``EOFError``), which names neither the file
    nor the fact that the file is the problem. The step is running under an
    agent, so that message is all anybody gets. Every failure to read is
    caught, because the set of exceptions a damaged pickle can raise is not
    something this step can enumerate.
    """
    try:
        loaded = joblib.load(weights)
    except Exception as error:
        raise PipelineError(
            f"the model artifact at {weights} cannot be read "
            f"({type(error).__name__}: {error}). It did not survive the transfer "
            "from the step that produced it"
        ) from error

    if not isinstance(loaded, Pipeline):
        raise PipelineError(
            f"the model artifact at {weights} does not hold a fitted pipeline"
        )
    return loaded


def _describe_lineage(fetched: FetchedDataset, profile: DatasetProfile) -> LineageRecord:
    """Build the chain this Dataset version sits at the end of.

    What can be seen from here is the Dataset and the versions it was built on
    top of. The raw measurements and any curation happened before ClearML was
    involved, so they are recorded as the parents rather than invented.
    """
    producer = Producer(
        name=fetched.dataset_name,
        version=fetched.dataset_version,
        executed_by=getpass.getuser(),
    )
    links = [
        build_link(
            LineageStage.RAW,
            parent,
            producer,
            notes="a Dataset version this one was built on top of",
        )
        for parent in fetched.parents
    ]
    links.append(
        build_link(
            LineageStage.TRAINING,
            fetched.dataset_id,
            producer,
            sources=fetched.parents,
            source_stage=LineageStage.RAW if fetched.parents else None,
            row_count=profile.row_count,
            notes=f"version {fetched.dataset_version} of {fetched.dataset_name}",
        )
    )
    return LineageRecord(links=tuple(links))


def _describe_report(report: DatasetValidationReport) -> dict[str, object]:
    return {
        "dataset": {
            "id": report.source.dataset_id,
            "project": report.source.dataset_project,
            "name": report.source.dataset_name,
            "version": report.source.dataset_version,
            "csv_path": str(report.source.csv_path),
        },
        "row_count": report.row_count,
        "features": {
            "all": list(report.feature_names),
            "numeric": list(report.numeric_feature_names),
            "categorical": list(report.categorical_feature_names),
        },
        "label_counts": dict(report.label_counts),
    }


def _describe_results(results: tuple[EvaluationResult, ...]) -> dict[str, object]:
    return {
        result.split_name: {
            "metrics": {name: float(value) for name, value in result.metrics.items()},
            "labels": list(result.labels),
            "confusion_matrix": result.confusion_matrix.tolist(),
            "confusion_matrix_layout": CONFUSION_MATRIX_COMMENT,
        }
        for result in results
    }

"""ClearML SDK boundary of the training flow.

Every call into the ClearML SDK is made from this module, so the data
preparation, training and evaluation steps stay free of the SDK and can be
exercised without a ClearML Server.

The boundary is opened before the Dataset is fetched. A run that fails while
resolving the Dataset, validating the input or fitting the model is therefore
recorded as a failed ClearML Task instead of leaving no trace at all.

Model registration is an explicit step of this flow, so the scikit-learn and
joblib automatic model tracking of the SDK is turned off. Parameters are
recorded explicitly for the same reason, so the automatic argument parser
binding is turned off as well and the recorded contract has a single source.
Credentials are taken from ``ClearmlSettings`` and are never recorded as Task
Parameters. That is not left to care: every section written from here is
searched for credentials first, and a section that carries one is refused
rather than recorded. A Task Parameter is readable by everybody with access to
the Server and outlives the run, so the moment before it is written is the
last moment at which a mistake is still cheap.

A run either stays in this process or is handed to a ClearML Agent. Both
paths create the same Task and record the same contract; they differ only in
who carries it out. Once a Task is handed over, this process stops writing to
it, so results on a queued Task always come from the Agent alone.

The execution dependencies are recorded explicitly from the pinned
``requirements/training.txt``. Recording the lock rather than the declared
ranges is what lets an Agent install the same versions the run was developed
against. Resolving the file from this module keeps the recorded contract
independent of the directory from which training is started.
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from clearml import Dataset, Logger, OutputModel, Task
from clearml.model import Framework

from ml.security.secrets import refuse_secrets

from .config import (
    ClearmlSettings,
    DatasetConfig,
    EstimatorConfig,
    ExecutionPlan,
    TrainingConfig,
)
from .domain import (
    LABELS,
    MODEL_NAME,
    DatasetSource,
    DatasetValidationReport,
    DataSplit,
    EvaluationResult,
    FetchedDataset,
    ModelCost,
    TrainingEvaluation,
)
from .provenance import ExecutionProvenance, collect_provenance


DISABLED_MODEL_FRAMEWORKS: Mapping[str, bool] = {"scikit": False, "joblib": False}
REQUIREMENTS_FILE = Path(__file__).resolve().parents[2] / "requirements" / "training.txt"

DATASET_SECTION = "Dataset"
RESOLVED_DATASET_SECTION = "Resolved Dataset"
SPLIT_SECTION = "Split"
MODEL_SECTION = "Model"

ALGORITHM_PARAMETER = "algorithm"
# どのアルゴリズムでも同じ意味を持つ設定。アルゴリズム固有の設定と同じ区画へ
# 並べるが、名前はここで一度だけ決める。
CLASS_WEIGHT_PARAMETER = "class_weight"
DECISION_THRESHOLD_PARAMETER = "decision_threshold"
EXECUTION_SECTION = "Execution"
PROVENANCE_SECTION = "Provenance"
RUNTIME_SECTION = "Runtime"

COMMAND_LINE_PARAMETER = "command_line"

# 「どこへ書こうとしたか」を、拒否したときの説明に使う。
PARAMETER_ORIGIN = "task parameters"

# clearml-agent はTaskを実行するプロセスへ、この環境変数でTask idを渡す。
AGENT_TASK_ID_ENVIRONMENT_KEY = "CLEARML_TASK_ID"

ENQUEUED_STATUS_MESSAGE = "Handed over to a ClearML Agent."

DATA_VALIDATION_ARTIFACT = "data_validation"
EVALUATION_ARTIFACT = "evaluation"
COST_ARTIFACT = "cost"

COST_TITLE = "Cost"

# One execution reports one final figure per metric, so every value of a run
# shares the same iteration and the Web UI compares runs, not steps.
METRICS_ITERATION = 0
CONFUSION_MATRIX_TITLE = "Confusion Matrix"
CONFUSION_MATRIX_COMMENT = "Rows are actual labels; columns are predicted labels."

MODEL_COMMENT = "RandomForest pipeline, including the preprocessing it was fitted with."
MODEL_LABEL_ENUMERATION: Mapping[str, int] = {
    label: index for index, label in enumerate(LABELS)
}


class EnqueueError(RuntimeError):
    """Raised when a Task cannot be handed to a queue."""


class TrainingTask:
    """A started ClearML Task, closed exactly once with an explicit outcome."""

    def __init__(self, task: Task) -> None:
        self._task = task
        self._closed = False

    @property
    def id(self) -> str:
        return str(self._task.id)

    def record_configuration(
        self,
        config: TrainingConfig,
        command_line: Sequence[str] = (),
    ) -> None:
        """Track how the run was invoked and which contract it resolved to.

        Only the settings the chosen algorithm reads are recorded. A Task that
        listed the settings of all three algorithms would invite somebody to
        change one that had no effect on the result.
        """
        connect_parameters(self._task, asdict(config.dataset), DATASET_SECTION)
        connect_parameters(self._task, asdict(config.split), SPLIT_SECTION)
        connect_parameters(self._task, model_parameters(config.estimator), MODEL_SECTION)
        connect_parameters(
            self._task,
            {
                COMMAND_LINE_PARAMETER: shlex.join(command_line),
                "random_seed": config.random_seed,
            },
            EXECUTION_SECTION,
        )

    def record_provenance(self, provenance: ExecutionProvenance) -> None:
        """Record who asked for this Task, and what is carrying it out."""
        record_provenance(self._task, provenance)

    def record_dataset_source(self, source: DatasetSource) -> None:
        """Record which Dataset version the run resolved, next to the one it asked for.

        The Dataset alias already links Task and Dataset inside ClearML. The id
        is recorded here as well, so the Task alone still answers which data it
        learned from once the alias link is followed no further.
        """
        connect_parameters(
            self._task,
            {
                "dataset_id": source.dataset_id,
                "dataset_project": source.dataset_project,
                "dataset_name": source.dataset_name,
                "dataset_version": source.dataset_version,
                "csv_path": str(source.csv_path),
            },
            RESOLVED_DATASET_SECTION,
        )

    def record_input(self, report: DatasetValidationReport, split: DataSplit) -> None:
        """Upload what the run learned from, and how it was divided.

        The features are part of the payload, because the execution contract
        records which Dataset was read but not which of its columns a model was
        allowed to see.
        """
        self._upload_json(DATA_VALIDATION_ARTIFACT, _describe_input(report, split))

    def record_evaluation(self, evaluation: TrainingEvaluation) -> None:
        """Report every scored split under its own series, and keep the numbers.

        The scalars and the confusion matrices are what the Web UI compares
        between runs. The artifact holds the same figures as a readable file,
        so a result stays available once a plot has been left behind.
        """
        logger = self._task.get_logger()
        for result in evaluation.results:
            _report_result(logger, result)
        self._upload_json(EVALUATION_ARTIFACT, _describe_evaluation(evaluation))

    def record_cost(self, cost: ModelCost) -> None:
        """Report what the model cost to fit and to use.

        These go next to the scores as scalars, because choosing between two
        algorithms is a trade between how well they predict and what they cost
        to run, and a comparison that shows only one half cannot be made.
        """
        logger = self._task.get_logger()
        for name, value in _describe_cost(cost).items():
            logger.report_scalar(
                title=COST_TITLE,
                series=name,
                value=float(value),
                iteration=METRICS_ITERATION,
            )
        self._upload_json(COST_ARTIFACT, dict(_describe_cost(cost)))

    def register_model(self, weights: Path) -> None:
        """Attach the fitted pipeline as the single Output Model of this Task.

        The automatic scikit-learn and joblib tracking is disabled at ``init``,
        so this is the only place a model is registered and a Task cannot end
        up holding the same pipeline twice.
        """
        model = OutputModel(
            task=self._task,
            name=MODEL_NAME,
            framework=Framework.scikitlearn,
            label_enumeration=dict(MODEL_LABEL_ENUMERATION),
            comment=MODEL_COMMENT,
        )
        model.update_weights(
            weights_filename=str(weights),
            auto_delete_file=False,
            async_enable=False,
        )

    def _upload_json(self, name: str, content: dict[str, object]) -> None:
        # ``auto_pickle=False`` turns a payload that cannot be serialised into a
        # failure, instead of a pickle nobody can read from the Web UI. The
        # upload is awaited so that the caller may delete what it handed over.
        self._task.upload_artifact(
            name,
            artifact_object=content,
            wait_on_upload=True,
            auto_pickle=False,
            sort_keys=False,
        )

    def hand_over(self, queue: str) -> None:
        """Put this Task on a queue, and stop taking responsibility for it.

        A Task that is still in progress cannot be queued, so the local
        process gives up its claim before enqueueing. Marking the boundary
        closed here is what keeps :meth:`complete` and :meth:`fail` from
        writing an outcome onto a Task that an Agent now owns.
        """
        if self._closed:
            raise EnqueueError(f"task {self.id} was already closed and cannot be queued")
        self._closed = True
        self._task.flush(wait_for_uploads=True)
        self._task.mark_stopped(force=True, status_message=ENQUEUED_STATUS_MESSAGE)
        Task.enqueue(self._task, queue_name=queue)

    def complete(self) -> None:
        """Wait for every upload to finish, then close the Task as completed.

        Under an Agent the final status belongs to the Agent. Closing the Task
        from inside the run looks to the Agent like somebody changed the status
        behind its back, and it reports an otherwise successful run as aborted.
        So the boundary only waits for the uploads and lets the Agent finish.
        """
        if self._closed:
            return
        self._closed = True
        self._task.flush(wait_for_uploads=True)
        if running_under_agent():
            return
        self._task.close()

    def fail(self, error: Exception) -> None:
        """Close the Task as failed, with the reason left on the Task log."""
        if self._closed:
            return
        self._closed = True
        self._task.get_logger().report_text(f"Training failed: {error}")
        self._task.mark_failed(
            status_reason=type(error).__name__,
            status_message=str(error),
            force=True,
        )
        self._task.close()


def start_training_task(
    config: TrainingConfig,
    *,
    settings: ClearmlSettings | None = None,
    command_line: Sequence[str] = (),
    plan: ExecutionPlan | None = None,
) -> TrainingTask:
    """Validate the execution contract offline, then create one new Task.

    ``reuse_last_task_id=False`` keeps every execution a separate Task, so two
    runs of the same project and Task name stay comparable.

    The provenance is collected here rather than by the caller, because it
    describes the process that is creating the Task. For a queued run that is
    the process that requested it, which is exactly the fact an audit needs.
    """
    config.validate()
    execution = (plan or ExecutionPlan()).validate()
    connection = connected_settings(settings)

    # ``Task.init`` の戻り値は SDK の型情報からは確定しないため、境界である
    # ここで一度だけ ``Task`` として受け止める。
    task: Task = Task.init(
        project_name=config.task.task_project,
        task_name=config.task.task_name,
        task_type=Task.TaskTypes.training,
        reuse_last_task_id=False,
        auto_connect_arg_parser=False,
        auto_connect_frameworks=dict(DISABLED_MODEL_FRAMEWORKS),
        output_uri=connection.files_host,
    )
    task.set_packages(str(REQUIREMENTS_FILE))
    training_task = TrainingTask(task)
    training_task.record_configuration(config, command_line=command_line)
    training_task.record_provenance(
        collect_provenance(execution.queue, environment=os.environ)
    )
    return training_task


@contextmanager
def training_task(
    config: TrainingConfig,
    *,
    settings: ClearmlSettings | None = None,
    command_line: Sequence[str] = (),
    plan: ExecutionPlan | None = None,
) -> Iterator[TrainingTask]:
    """Execution boundary of one run.

    The Task exists before the caller reads the Dataset, and the run leaves the
    boundary either completed or failed. ``KeyboardInterrupt`` is deliberately
    not turned into a failure, so a manually stopped run is reported as stopped
    by the SDK itself.
    """
    task = start_training_task(
        config,
        settings=settings,
        command_line=command_line,
        plan=plan,
    )
    try:
        yield task
    except Exception as error:
        task.fail(error)
        raise
    task.complete()


def connect_parameters(task: Task, fields: Mapping[str, object], name: str) -> None:
    """Record one section of the contract, or refuse it because of what it holds.

    Refusing is deliberately loud. A run that stops because a credential was
    about to be recorded costs one execution; a run that records it costs a
    rotation, and only after somebody notices.
    """
    refuse_secrets(fields, f"{PARAMETER_ORIGIN}/{name}")
    task.connect(dict(fields), name=name)


def record_provenance(task: Task, provenance: ExecutionProvenance) -> None:
    """Record who asked for a Task, and what is carrying it out.

    The request is connected, so a Task that is queued keeps the revision, the
    person and the queue it was created from even though an Agent runs the
    same code again.

    The runtime is written rather than connected, because it describes the
    process running right now. A queued Task is created by one process and
    carried out by another, and the second one is the environment a result has
    to be reproducible from.

    Both are Parameters rather than log lines, because this is what a later
    audit filters and compares Tasks by. Every Task that produces something a
    model can be traced back to records them, which is why this is a function
    rather than a method of the training boundary alone.
    """
    connect_parameters(task, provenance.request_parameters(), PROVENANCE_SECTION)
    runtime = provenance.runtime_parameters()
    refuse_secrets(dict(runtime), f"{PARAMETER_ORIGIN}/{RUNTIME_SECTION}")
    for name, value in runtime.items():
        task.set_parameter(f"{RUNTIME_SECTION}/{name}", value)


def model_parameters(estimator: EstimatorConfig) -> dict[str, object]:
    """Flatten the estimator of a run into the shape a Parameter section takes.

    The algorithm comes first, because it is what decides which of the
    remaining values mean anything.

    The two settings every algorithm shares come last, so the block reads as
    "this algorithm, tuned like this, then cut like that". They are recorded
    even when they are at their defaults, because "this run did not weigh the
    rare label" is a fact about the run and not an absence.
    """
    return {
        ALGORITHM_PARAMETER: estimator.algorithm.value,
        **asdict(estimator.active),
        CLASS_WEIGHT_PARAMETER: estimator.class_weight.value,
        DECISION_THRESHOLD_PARAMETER: estimator.decision_threshold,
    }


def connected_settings(settings: ClearmlSettings | None = None) -> ClearmlSettings:
    """Validate the connection settings and point the SDK at that server.

    Every entry point that talks to ClearML goes through here, so there is one
    place that decides which server is contacted and one place that refuses an
    unusable configuration.
    """
    connection = (settings or ClearmlSettings.from_environment()).validate()
    _apply_connection_settings(connection)
    return connection


def running_under_agent() -> bool:
    """Answer whether a ClearML Agent, rather than a person, started this process."""
    return not bool(Task.running_locally())


def queued_command_line() -> tuple[str, ...]:
    """Read back the invocation a queued run was created with.

    An Agent re-runs the entry point without the arguments the run was asked
    for, so the invocation is taken from the Task instead. The Task is the
    single source either way: it is written from the command line when a run
    is queued, and read from here when the Agent carries it out.
    """
    task_id = os.getenv(AGENT_TASK_ID_ENVIRONMENT_KEY, "").strip()
    if not task_id:
        raise EnqueueError(
            f"{AGENT_TASK_ID_ENVIRONMENT_KEY} is not set, so the queued invocation "
            "cannot be read back"
        )

    task: Task = Task.get_task(task_id=task_id)
    recorded = task.get_parameter(
        f"{EXECUTION_SECTION}/{COMMAND_LINE_PARAMETER}",
        default="",
    )
    return tuple(shlex.split(str(recorded or "")))


def fetch_dataset(config: DatasetConfig) -> FetchedDataset:
    """Resolve the requested Dataset version and download its read-only copy.

    The version is always given, so a run never silently follows the latest
    Dataset. ``alias`` makes ClearML link the resolved Dataset to the Task that
    is already running, which is why this is called inside the Task boundary.
    """
    dataset = Dataset.get(
        dataset_project=config.dataset_project,
        dataset_name=config.dataset_name,
        dataset_version=config.dataset_version,
        alias=config.dataset_alias,
        only_completed=True,
    )
    return FetchedDataset(
        dataset_id=str(dataset.id),
        dataset_project=config.dataset_project,
        dataset_name=str(dataset.name or config.dataset_name),
        dataset_version=str(dataset.version or config.dataset_version),
        local_root=Path(dataset.get_local_copy()),
        parents=_parents_of(dataset),
    )


def fetch_dataset_by_id(dataset_id: str, *, alias: str) -> FetchedDataset:
    """Download the exact Dataset version another execution already resolved.

    A version label can be moved onto other rows; an identifier cannot. A step
    that continues the work of an earlier step therefore addresses the Dataset
    by the identifier that step recorded, so the rows it reads are provably the
    rows that were approved.
    """
    dataset = Dataset.get(dataset_id=dataset_id, alias=alias, only_completed=True)
    return FetchedDataset(
        dataset_id=str(dataset.id),
        dataset_project=str(dataset.project or ""),
        dataset_name=str(dataset.name or ""),
        dataset_version=str(dataset.version or ""),
        local_root=Path(dataset.get_local_copy()),
        parents=_parents_of(dataset),
    )


def _parents_of(dataset: Dataset) -> tuple[str, ...]:
    """Read which versions a Dataset was built on top of.

    ClearML keeps this as a dependency graph rather than as a field, so the
    entry for this Dataset is what names its immediate parents. A version that
    carries none is the start of its own chain, which is a fact rather than a
    failure.
    """
    try:
        graph = dataset.get_dependency_graph()
    except Exception:
        return ()

    parents = graph.get(str(dataset.id)) if isinstance(graph, dict) else None
    if not parents:
        return ()
    return tuple(str(parent) for parent in parents)


def _describe_input(report: DatasetValidationReport, split: DataSplit) -> dict[str, object]:
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
        "split": {
            part.name: {
                "row_count": part.row_count,
                "label_counts": dict(part.label_counts),
            }
            for part in split.parts
        },
    }


def _describe_cost(cost: ModelCost) -> Mapping[str, float]:
    """The cost of a model, in units that stay readable as the data grows."""
    return {
        "training_seconds": cost.training_seconds,
        "inference_microseconds_per_row": cost.milliseconds_per_1000_rows,
        "model_kilobytes": cost.model_kilobytes,
    }


def _describe_evaluation(evaluation: TrainingEvaluation) -> dict[str, object]:
    return {result.split_name: _describe_result(result) for result in evaluation.results}


def _describe_result(result: EvaluationResult) -> dict[str, object]:
    return {
        "metrics": {name: float(value) for name, value in result.metrics.items()},
        "labels": list(result.labels),
        "confusion_matrix": result.confusion_matrix.tolist(),
        "confusion_matrix_layout": CONFUSION_MATRIX_COMMENT,
    }


def _report_result(logger: Logger, result: EvaluationResult) -> None:
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


def _apply_connection_settings(settings: ClearmlSettings) -> None:
    """Point the SDK at the configured server.

    Blank credentials are ignored by the SDK, which then falls back to its own
    configuration file.
    """
    Task.set_credentials(
        api_host=settings.api_host,
        web_host=settings.web_host,
        files_host=settings.files_host,
        key=settings.access_key,
        secret=settings.secret_key,
    )

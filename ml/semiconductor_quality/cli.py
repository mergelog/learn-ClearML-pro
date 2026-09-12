"""Command line contract of the training run.

Parsing builds the execution contract and validates it offline, so a malformed
invocation is rejected before :mod:`clearml_tracking` creates a ClearML Task.
The arguments are kept alongside the resolved contract, because the Task
records both how the run was asked for and what it resolved to.

One invocation may be carried out in one of two places. Without ``--queue``
the run happens in this process. With ``--queue`` the process records the
contract and the provenance of the request, hands the Task to a ClearML Agent
and stops; the Agent then re-runs this same entry point.

The Agent starts the entry point without the arguments the run was asked for,
so a run that finds itself under an Agent reads its invocation back from the
Task and carries it out instead of queueing it a second time.

This module is also the composition root of a run: it connects the ClearML
boundary to the data preparation, and turns the outcome into a process exit
code. It deliberately holds no data handling or evaluation of its own.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from .clearml_tracking import (
    fetch_dataset,
    queued_command_line,
    running_under_agent,
    start_training_task,
    training_task,
)
from .config import (
    DEFAULT_DATASET_CSV_PATH,
    DEFAULT_DATASET_NAME,
    DEFAULT_DATASET_PROJECT,
    DEFAULT_RANDOM_SEED,
    DEFAULT_TASK_NAME,
    DEFAULT_TASK_PROJECT,
    DEFAULT_TRAINING_QUEUE,
    Algorithm,
    ClassWeight,
    ConfigurationError,
    DatasetConfig,
    EstimatorConfig,
    ExecutionPlan,
    HistGradientBoostingConfig,
    LogisticRegressionConfig,
    RandomForestConfig,
    SplitConfig,
    TaskConfig,
    TrainingConfig,
)
from .dataset import load_training_input
from .domain import (
    DatasetValidationReport,
    EvaluationResult,
    SplitPart,
    TrainingEvaluation,
)
from .evaluate import evaluate_model
from .train import TrainedModel, measure_cost, saved_pipeline, train_classifier


SPLIT_DEFAULTS = SplitConfig()
ESTIMATOR_DEFAULTS = EstimatorConfig()
FOREST_DEFAULTS = RandomForestConfig()
BOOSTING_DEFAULTS = HistGradientBoostingConfig()
LOGISTIC_DEFAULTS = LogisticRegressionConfig()

# ``pnpm run ml:train -- --dataset-version 1.0.0`` forwards the separator itself,
# so the script has to recognise it as the package manager's and not as its own.
ARGUMENT_SEPARATOR = "--"

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_INVALID_USAGE = 2
EXIT_INTERRUPTED = 130


@dataclass(frozen=True)
class TrainingCommand:
    """One parsed invocation: what to run, where to run it, and how it was asked for."""

    config: TrainingConfig
    command_line: tuple[str, ...]
    plan: ExecutionPlan = field(default_factory=ExecutionPlan)

    def carried_out_here(self) -> TrainingCommand:
        """The same command, carried out in this process instead of on a queue.

        This is what an Agent turns a queued invocation into. The recorded
        command line is left untouched, because it states how the run was
        asked for and not where it ended up running.
        """
        return replace(self, plan=ExecutionPlan())


@dataclass(frozen=True)
class TrainingOutcome:
    """What one execution produced, and the ClearML Task it was recorded on."""

    task_id: str
    model: TrainedModel
    evaluation: TrainingEvaluation


@dataclass(frozen=True)
class QueuedTraining:
    """A Task that was handed to an Agent, and has produced nothing yet."""

    task_id: str
    queue: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Train a semiconductor quality classifier from a registered ClearML "
            "Dataset version and track the run as a ClearML Task."
        ),
    )

    dataset_group = parser.add_argument_group("dataset")
    dataset_group.add_argument(
        "--dataset-version",
        required=True,
        help="Version of the registered ClearML Dataset to train on. Never inferred.",
    )
    dataset_group.add_argument(
        "--dataset-project",
        default=DEFAULT_DATASET_PROJECT,
        help="ClearML project the Dataset belongs to.",
    )
    dataset_group.add_argument(
        "--dataset-name",
        default=DEFAULT_DATASET_NAME,
        help="Name of the registered ClearML Dataset.",
    )
    dataset_group.add_argument(
        "--dataset-csv-path",
        default=DEFAULT_DATASET_CSV_PATH,
        help="CSV to read, relative to the root of the fetched Dataset.",
    )

    task_group = parser.add_argument_group("task")
    task_group.add_argument(
        "--task-project",
        default=DEFAULT_TASK_PROJECT,
        help="ClearML project the training Task is created in.",
    )
    task_group.add_argument(
        "--task-name",
        default=DEFAULT_TASK_NAME,
        help="Name of the training Task.",
    )

    split_group = parser.add_argument_group("split")
    split_group.add_argument(
        "--train-ratio",
        type=float,
        default=SPLIT_DEFAULTS.train_ratio,
        help="Share of the rows used to fit the model.",
    )
    split_group.add_argument(
        "--validation-ratio",
        type=float,
        default=SPLIT_DEFAULTS.validation_ratio,
        help="Share of the rows used to confirm the settings of the run.",
    )
    split_group.add_argument(
        "--test-ratio",
        type=float,
        default=SPLIT_DEFAULTS.test_ratio,
        help="Share of the rows kept for the final evaluation.",
    )

    model_group = parser.add_argument_group("model")
    model_group.add_argument(
        "--algorithm",
        choices=[algorithm.value for algorithm in Algorithm],
        default=ESTIMATOR_DEFAULTS.algorithm.value,
        help=(
            "Which learning algorithm to fit. Everything else about the run stays "
            "the same, so two algorithms can be compared."
        ),
    )
    model_group.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help=(
            "Maximum depth of a tree, for the tree based algorithms. "
            "Omit to grow the trees without a limit."
        ),
    )
    model_group.add_argument(
        "--min-samples-leaf",
        type=int,
        default=None,
        help=(
            "Minimum number of samples required at a leaf, for the tree based "
            "algorithms. Omit to use the default of the chosen algorithm."
        ),
    )
    model_group.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help=(
            "Iteration budget, for logistic regression and boosting. "
            "Omit to use the default of the chosen algorithm."
        ),
    )
    model_group.add_argument(
        "--n-estimators",
        type=int,
        default=FOREST_DEFAULTS.n_estimators,
        help="Number of trees in the forest. Read by random-forest only.",
    )
    model_group.add_argument(
        "--learning-rate",
        type=float,
        default=BOOSTING_DEFAULTS.learning_rate,
        help="How much each boosting round corrects. Read by hist-gradient-boosting only.",
    )
    model_group.add_argument(
        "--regularisation",
        type=float,
        default=LOGISTIC_DEFAULTS.regularisation,
        help=(
            "How freely the coefficients may grow; smaller pulls them towards zero. "
            "Read by logistic-regression only."
        ),
    )
    model_group.add_argument(
        "--class-weight",
        choices=[weight.value for weight in ClassWeight],
        default=ESTIMATOR_DEFAULTS.class_weight.value,
        help=(
            "Whether to weigh the rare label by how rare it is. Read by every "
            "algorithm. 'balanced' buys recall with precision."
        ),
    )
    model_group.add_argument(
        "--decision-threshold",
        type=float,
        default=None,
        help=(
            "Cut the predicted probability of a failure here instead of at one "
            "half. Omit to leave the cut where the algorithm puts it."
        ),
    )

    parser.add_argument(
        "--random-seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help="Seed shared by the split and the estimator, so a run stays reproducible.",
    )

    execution_group = parser.add_argument_group("execution")
    execution_group.add_argument(
        "--queue",
        nargs="?",
        const=DEFAULT_TRAINING_QUEUE,
        default=None,
        help=(
            "Hand the run to a ClearML Agent on this queue instead of running it here. "
            f"Without a value the queue is {DEFAULT_TRAINING_QUEUE!r}."
        ),
    )
    return parser


def parse_arguments(argv: Sequence[str]) -> TrainingCommand:
    """Build the execution contract of one invocation, or reject the invocation."""
    arguments = build_parser().parse_args(list(argv))
    config = TrainingConfig(
        dataset=DatasetConfig(
            dataset_version=arguments.dataset_version,
            dataset_project=arguments.dataset_project,
            dataset_name=arguments.dataset_name,
            dataset_csv_path=arguments.dataset_csv_path,
        ),
        task=TaskConfig(
            task_project=arguments.task_project,
            task_name=arguments.task_name,
        ),
        split=SplitConfig(
            train_ratio=arguments.train_ratio,
            validation_ratio=arguments.validation_ratio,
            test_ratio=arguments.test_ratio,
        ),
        estimator=build_estimator(arguments),
        random_seed=arguments.random_seed,
    )
    plan = ExecutionPlan(queue=arguments.queue)
    return TrainingCommand(
        config=config.validate(),
        command_line=tuple(argv),
        plan=plan.validate(),
    )


def build_estimator(arguments: argparse.Namespace) -> EstimatorConfig:
    """Build every algorithm's settings out of one invocation.

    The settings shared by several algorithms default to ``None`` rather than
    to a number, so an argument that was not given leaves each algorithm on its
    own default. Only the block the chosen algorithm reads is validated and
    recorded, so carrying all three costs nothing.

    The imbalance policy and the probability cut sit outside the three blocks,
    because they mean the same thing whichever algorithm is fitted.
    """
    return EstimatorConfig(
        algorithm=Algorithm(arguments.algorithm),
        class_weight=ClassWeight(arguments.class_weight),
        decision_threshold=arguments.decision_threshold,
        forest=RandomForestConfig(
            n_estimators=arguments.n_estimators,
            max_depth=arguments.max_depth,
            min_samples_leaf=_or_default(
                arguments.min_samples_leaf,
                FOREST_DEFAULTS.min_samples_leaf,
            ),
        ),
        logistic=LogisticRegressionConfig(
            regularisation=arguments.regularisation,
            max_iterations=_or_default(
                arguments.max_iterations,
                LOGISTIC_DEFAULTS.max_iterations,
            ),
        ),
        boosting=HistGradientBoostingConfig(
            learning_rate=arguments.learning_rate,
            max_iterations=_or_default(
                arguments.max_iterations,
                BOOSTING_DEFAULTS.max_iterations,
            ),
            max_depth=arguments.max_depth,
            min_samples_leaf=_or_default(
                arguments.min_samples_leaf,
                BOOSTING_DEFAULTS.min_samples_leaf,
            ),
        ),
    )


def _or_default(given: int | None, default: int) -> int:
    return default if given is None else given


def build_command(argv: Sequence[str]) -> TrainingCommand:
    """Build the command this process will carry out.

    A queued run is started twice: once by the person who asked for it, who
    records the invocation and hands the Task over, and once by the Agent,
    which starts the entry point without those arguments. The Agent therefore
    reads the invocation back from the Task and carries it out, rather than
    queueing the same run again.
    """
    if running_under_agent():
        return parse_arguments(queued_command_line()).carried_out_here()
    return parse_arguments(_forwarded_arguments(argv))


def carry_out(command: TrainingCommand) -> TrainingOutcome | QueuedTraining:
    """Run the command here, or hand it to the queue it named."""
    if command.plan.runs_locally:
        return run_training(command)
    return enqueue_training(command)


def enqueue_training(command: TrainingCommand) -> QueuedTraining:
    """Create the Task an Agent will run, and hand it to the queue.

    Nothing is trained here. The Task is created so that the request itself is
    recorded, with the same contract and the provenance of whoever asked for
    it, and is then given away. A failure before the hand over leaves a failed
    Task rather than a Task nobody owns.
    """
    queue = command.plan.queue
    if queue is None:
        raise ConfigurationError("a queued run needs a queue name")

    task = start_training_task(
        command.config,
        command_line=command.command_line,
        plan=command.plan,
    )
    try:
        task.hand_over(queue)
    except Exception as error:
        task.fail(error)
        raise
    return QueuedTraining(task_id=task.id, queue=queue)


def run_training(command: TrainingCommand) -> TrainingOutcome:
    """Run one tracked execution, from the started Task to the registered model.

    Everything inside the boundary is attributed to a single ClearML Task, so a
    Dataset version that cannot be resolved, an input that fails validation or
    a fit that raises is left behind as a failed Task rather than as no Task at
    all. The Task is completed only after the last upload, which is why the
    model is registered while the boundary is still open.
    """
    config = command.config
    with training_task(
        config,
        command_line=command.command_line,
        plan=command.plan,
    ) as task:
        fetched = fetch_dataset(config.dataset)
        training_input = load_training_input(fetched, config.dataset.dataset_csv_path)
        task.record_dataset_source(training_input.report.source)

        model = train_classifier(training_input, config)
        task.record_input(model.report, model.split)

        evaluation = evaluate_model(model)
        task.record_evaluation(evaluation)

        with saved_pipeline(model.pipeline) as weights:
            # 費用は保存したファイルから測る。モデルの大きさは、保存した形が
            # 配布される形だからである。
            task.record_cost(measure_cost(model, weights))
            task.register_model(weights)

        return TrainingOutcome(task_id=task.id, model=model, evaluation=evaluation)


def main(argv: Sequence[str] | None = None) -> int:
    """Carry out one training command and report its outcome as an exit code."""
    try:
        command = build_command(sys.argv[1:] if argv is None else argv)
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return EXIT_INVALID_USAGE

    try:
        outcome = carry_out(command)
    except KeyboardInterrupt:
        print("Training was interrupted before it completed.", file=sys.stderr)
        return EXIT_INTERRUPTED
    # 理由は報告する。握り潰さないための広い捕捉である。
    except Exception as error:
        print(f"Training failed: {error}", file=sys.stderr)
        return EXIT_FAILURE

    print(_describe(outcome))
    return EXIT_SUCCESS


def _forwarded_arguments(argv: Sequence[str]) -> list[str]:
    """Drop the separator a package manager puts in front of the arguments.

    Without this, argparse would read the leading ``--`` as "the rest are
    positional" and reject an otherwise valid invocation. Removing it keeps the
    documented pnpm command and a direct call to the module equivalent.
    """
    arguments = list(argv)
    if arguments and arguments[0] == ARGUMENT_SEPARATOR:
        del arguments[0]
    return arguments


def _describe(outcome: TrainingOutcome | QueuedTraining) -> str:
    if isinstance(outcome, QueuedTraining):
        return _describe_queued(outcome)

    model = outcome.model
    parts = " ".join(_describe_part(part) for part in model.split.parts)
    return "\n".join(
        (
            _describe_dataset(model.report),
            f"Trained on {parts}",
            *(_describe_result(result) for result in outcome.evaluation.results),
            f"Recorded as ClearML Task {outcome.task_id}",
        )
    )


def _describe_queued(queued: QueuedTraining) -> str:
    return "\n".join(
        (
            f"Queued ClearML Task {queued.task_id} on {queued.queue}.",
            "Nothing was trained here. A ClearML Agent carries the Task out.",
        )
    )


def _describe_result(result: EvaluationResult) -> str:
    scores = " ".join(f"{name}={value:.4f}" for name, value in result.metrics.items())
    return f"{result.split_name}: {scores}"


def _describe_dataset(report: DatasetValidationReport) -> str:
    return (
        f"Dataset {report.source.dataset_name} {report.source.dataset_version} "
        f"({report.source.dataset_id}) validated: "
        f"{report.row_count} rows, {len(report.feature_names)} features, "
        f"{_describe_labels(report.label_counts)}"
    )


def _describe_part(part: SplitPart) -> str:
    return f"{part.name}={part.row_count} ({_describe_labels(part.label_counts)})"


def _describe_labels(label_counts: Mapping[str, int]) -> str:
    return ", ".join(f"{label}={count}" for label, count in label_counts.items())


if __name__ == "__main__":
    raise SystemExit(main())

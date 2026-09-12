"""Command line contract of the training pipeline.

One invocation describes one pipeline run: which Dataset version to learn
from, how to divide it, which forest to fit, and which queue the steps are
carried out on. The arguments mirror ``ml.semiconductor_quality.cli`` so that a
result from the pipeline is comparable with a single training run.

The controller itself runs in this process by default. It creates no models
and holds no data: it clones the step Tasks, fills in their Parameters and
waits. Running it here rather than on a queue keeps the number of Agents a
learning environment needs at one, and the Pipeline view in the Web UI is the
same either way.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence

from clearml.automation import PipelineController

from ml.semiconductor_quality.cli import build_estimator
from ml.semiconductor_quality.config import (
    DEFAULT_DATASET_CSV_PATH,
    DEFAULT_DATASET_NAME,
    DEFAULT_DATASET_PROJECT,
    DEFAULT_PIPELINE_QUEUE,
    DEFAULT_RANDOM_SEED,
    DEFAULT_TRAINING_QUEUE,
    Algorithm,
    ClassWeight,
    ConfigurationError,
    DatasetConfig,
    EstimatorConfig,
    HistGradientBoostingConfig,
    LogisticRegressionConfig,
    RandomForestConfig,
    SplitConfig,
)

from .controller import (
    PipelineRequest,
    RunOrigin,
    build_controller,
    connect_to_server,
    ensure_templates,
)
from .domain import PIPELINE_NAME, PIPELINE_PROJECT, PipelineError, StepName


SPLIT_DEFAULTS = SplitConfig()
ESTIMATOR_DEFAULTS = EstimatorConfig()
FOREST_DEFAULTS = RandomForestConfig()
BOOSTING_DEFAULTS = HistGradientBoostingConfig()
LOGISTIC_DEFAULTS = LogisticRegressionConfig()

ARGUMENT_SEPARATOR = "--"

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_INVALID_USAGE = 2
EXIT_INTERRUPTED = 130

COMPLETED_STATUS = "completed"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the semiconductor quality training pipeline: validate the "
            "Dataset, preprocess it, fit a model, score it and register the "
            "candidate, each as its own ClearML Task."
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
    dataset_group.add_argument(
        "--drift-reference-version",
        default="",
        help=(
            "Compare the Dataset against this earlier version and report what "
            "moved. Drift is reported, not refused."
        ),
    )

    split_group = parser.add_argument_group("split")
    split_group.add_argument("--train-ratio", type=float, default=SPLIT_DEFAULTS.train_ratio)
    split_group.add_argument(
        "--validation-ratio",
        type=float,
        default=SPLIT_DEFAULTS.validation_ratio,
    )
    split_group.add_argument("--test-ratio", type=float, default=SPLIT_DEFAULTS.test_ratio)

    model_group = parser.add_argument_group("model")
    model_group.add_argument(
        "--algorithm",
        choices=[algorithm.value for algorithm in Algorithm],
        default=ESTIMATOR_DEFAULTS.algorithm.value,
    )
    model_group.add_argument("--max-depth", type=int, default=None)
    model_group.add_argument("--min-samples-leaf", type=int, default=None)
    model_group.add_argument("--max-iterations", type=int, default=None)
    model_group.add_argument("--n-estimators", type=int, default=FOREST_DEFAULTS.n_estimators)
    model_group.add_argument("--learning-rate", type=float, default=BOOSTING_DEFAULTS.learning_rate)
    model_group.add_argument(
        "--regularisation",
        type=float,
        default=LOGISTIC_DEFAULTS.regularisation,
    )
    model_group.add_argument(
        "--class-weight",
        choices=[weight.value for weight in ClassWeight],
        default=ESTIMATOR_DEFAULTS.class_weight.value,
        help="Whether to weigh the rare label by how rare it is. Read by every algorithm.",
    )
    model_group.add_argument(
        "--decision-threshold",
        type=float,
        default=None,
        help=(
            "Cut the predicted probability of a failure here instead of at one half. "
            "This is what a completed search hands over."
        ),
    )

    parser.add_argument(
        "--random-seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help="Seed shared by the split and the forest, so a run stays reproducible.",
    )

    execution_group = parser.add_argument_group("execution")
    execution_group.add_argument(
        "--queue",
        default=DEFAULT_TRAINING_QUEUE,
        help="Queue the steps are carried out on by a ClearML Agent.",
    )
    execution_group.add_argument(
        "--pipeline-queue",
        default=DEFAULT_PIPELINE_QUEUE,
        help=(
            "Queue the pipeline controller itself is carried out on when it is "
            "submitted rather than run here."
        ),
    )
    execution_group.add_argument(
        "--submit",
        action="store_true",
        help=(
            "Hand the pipeline itself to a ClearML Agent instead of running the "
            "controller here. The run then exists as a Task that can be cloned "
            "and started again from the Web UI."
        ),
    )
    execution_group.add_argument(
        "--origin-search-task-id",
        default="",
        help=(
            "The search that chose these settings, when this run was asked for "
            "by one. Recorded on the pipeline Task."
        ),
    )
    execution_group.add_argument(
        "--origin-trial-task-id",
        default="",
        help="The trial that measured these settings, for the same reason.",
    )
    execution_group.add_argument(
        "--templates-only",
        action="store_true",
        help="Create or refresh the step templates and stop, without running them.",
    )
    return parser


def parse_arguments(argv: Sequence[str]) -> PipelineRequest:
    """Build the contract of one pipeline run, or reject the invocation."""
    arguments = build_parser().parse_args(list(argv))
    request = PipelineRequest(
        dataset=DatasetConfig(
            dataset_version=arguments.dataset_version,
            dataset_project=arguments.dataset_project,
            dataset_name=arguments.dataset_name,
            dataset_csv_path=arguments.dataset_csv_path,
        ),
        queue=arguments.queue,
        drift_reference_version=arguments.drift_reference_version,
        pipeline_queue=arguments.pipeline_queue,
        submitted=arguments.submit,
        split=SplitConfig(
            train_ratio=arguments.train_ratio,
            validation_ratio=arguments.validation_ratio,
            test_ratio=arguments.test_ratio,
        ),
        estimator=build_estimator(arguments),
        random_seed=arguments.random_seed,
        origin=RunOrigin(
            search_task_id=arguments.origin_search_task_id,
            trial_task_id=arguments.origin_trial_task_id,
        ),
    )
    return request.validate()


def run_pipeline(request: PipelineRequest) -> PipelineController:
    """Create the run and wait for it, whether it succeeds or stops early."""
    controller = build_controller(request, ensure_templates(request))
    controller.start_locally(run_pipeline_steps_locally=False)
    return controller


def submit_pipeline(request: PipelineRequest) -> PipelineController:
    """Hand the pipeline itself to an Agent, and stop.

    The controller then exists as a Task of its own. That is what lets a run be
    started again from the Web UI, or from the Angular application, by cloning
    it and changing one parameter — without anybody having a Python environment.
    """
    controller = build_controller(request, ensure_templates(request))
    controller.start(queue=request.pipeline_queue, wait=False)
    return controller


def main(argv: Sequence[str] | None = None) -> int:
    """Run one pipeline and report its outcome as an exit code."""
    arguments = _forwarded_arguments(sys.argv[1:] if argv is None else argv)
    templates_only = "--templates-only" in arguments

    try:
        request = parse_arguments(arguments)
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return EXIT_INVALID_USAGE

    connect_to_server()
    try:
        if templates_only:
            print(_describe_templates(ensure_templates(request)))
            return EXIT_SUCCESS
        if request.submitted:
            controller = submit_pipeline(request)
            print(_describe_submission(controller, request))
            return EXIT_SUCCESS
        controller = run_pipeline(request)
    except KeyboardInterrupt:
        print("The pipeline was interrupted before it completed.", file=sys.stderr)
        return EXIT_INTERRUPTED
    except PipelineError as error:
        print(error, file=sys.stderr)
        return EXIT_FAILURE
    # 理由は報告する。握り潰さないための広い捕捉である。
    except Exception as error:
        print(f"The pipeline failed: {error}", file=sys.stderr)
        return EXIT_FAILURE

    # 走り終えた後の判断材料はPipeline Task自身の状態にある。
    # 途中で止まった実行を「成功」と報告しないために、ここで読み直す。
    status = str(controller.task.get_status())
    # 型情報上は Node の列だが、実際には走り終えたステップ名が返る。
    processed = [str(node) for node in controller.get_processed_nodes()]
    print(_describe_run(status, processed, str(controller.task.id)))
    return EXIT_SUCCESS if status == COMPLETED_STATUS else EXIT_FAILURE


def _forwarded_arguments(argv: Sequence[str]) -> list[str]:
    """Drop the separator a package manager puts in front of the arguments."""
    arguments = list(argv)
    if arguments and arguments[0] == ARGUMENT_SEPARATOR:
        del arguments[0]
    return arguments


def _describe_templates(templates: Mapping[StepName, str]) -> str:
    lines = [f"Step templates in {PIPELINE_PROJECT}:"]
    lines.extend(f"  {step}: {task_id}" for step, task_id in templates.items())
    return "\n".join(lines)


def _describe_submission(controller: PipelineController, request: PipelineRequest) -> str:
    return "\n".join(
        (
            f"Submitted pipeline Task {controller.task.id} to {request.pipeline_queue}.",
            "Nothing ran here. A ClearML Agent carries the pipeline out.",
        )
    )


def _describe_run(status: str, processed: Sequence[str], task_id: str = "") -> str:
    """Name the run and the steps that actually ran.

    A pipeline that stopped early lists fewer steps than it declares, which is
    the quickest way to see where it stopped.
    """
    lines = [f"Pipeline {PIPELINE_NAME} finished with status {status}."]
    if task_id:
        lines.append(f"Recorded as ClearML Task {task_id}")
    lines.append(f"Steps that ran: {', '.join(processed) if processed else 'none'}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

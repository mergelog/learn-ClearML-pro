"""Command line contract of one hyperparameter search.

One invocation describes one search: which environment's settings it runs
under, which Dataset version it searches on, and whether the winner is handed
straight to the training pipeline.

What is searched, what counts as better and what may be spent are *not*
arguments. They are read from ``config/experiment``, because a search is a
budgeted process an environment owns rather than a command somebody types.
Leaving the budget on the command line is how a production sized search ends
up running on a laptop, and how nobody can say afterwards what a past search
was allowed to do.

The search never sees the validation or the test rows, so its winner still has
to clear the evaluation gate on rows it has not been tuned against.
``--handoff`` is what starts that: the winning settings, including the
probability cut the trials agreed on, are handed to the training pipeline,
which fits the model, spends the test part exactly once and registers the
candidate only if the gate lets it through.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from collections.abc import Sequence

from clearml import Task

from ml.semiconductor_quality.config import (
    DEFAULT_DATASET_CSV_PATH,
    DEFAULT_DATASET_NAME,
    DEFAULT_DATASET_PROJECT,
    DEFAULT_RANDOM_SEED,
    ConfigurationError,
    DatasetConfig,
    SplitConfig,
)

from .domain import Environment, ExperimentError, ExperimentPlan
from .optimizer import (
    BestTrial,
    SearchRequest,
    best_trial,
    build_optimizer,
    ensure_trial_template,
    handoff_arguments,
    record_winner,
    start_optimization_task,
    start_search,
    trial_parameters,
)
from .settings import load_plan, resolve_environment


SPLIT_DEFAULTS = SplitConfig()

ARGUMENT_SEPARATOR = "--"

# 引き渡し先。Pipelineは自分自身の入口として起動する。
PIPELINE_MODULE = "ml.pipeline.cli"

# ClearML SDKが「この子プロセスは親と同じTaskの一部だ」と伝えるために使う
# 環境変数。学習の途中で立てた補助プロセスなら正しい振る舞いだが、
# 引き渡しは別のTaskを作る別の実行なので、そのまま渡すとPipelineが
# 探索Taskへ相乗りし、探索の記録がPipelineの記録に上書きされる。
CLEARML_PROCESS_VARIABLES = (
    "CLEARML_PROC_MASTER_ID",
    "TRAINS_PROC_MASTER_ID",
    "CLEARML_TASK_ID",
    "TRAINS_TASK_ID",
)

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_INVALID_USAGE = 2
EXIT_INTERRUPTED = 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Search for the settings that fit the semiconductor quality data "
            "best, over the training rows only, and hand the winner to the "
            "training pipeline."
        ),
    )
    parser.add_argument(
        "--environment",
        choices=[environment.value for environment in Environment],
        default=None,
        help=(
            "Which environment's search settings to run under. Defaults to "
            "EXPERIMENT_ENVIRONMENT, and to the development budget when that "
            "is unset."
        ),
    )

    dataset_group = parser.add_argument_group("dataset")
    dataset_group.add_argument(
        "--dataset-version",
        required=True,
        help="Version of the registered ClearML Dataset to search on. Never inferred.",
    )
    dataset_group.add_argument("--dataset-project", default=DEFAULT_DATASET_PROJECT)
    dataset_group.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    dataset_group.add_argument("--dataset-csv-path", default=DEFAULT_DATASET_CSV_PATH)

    split_group = parser.add_argument_group("split")
    split_group.add_argument("--train-ratio", type=float, default=SPLIT_DEFAULTS.train_ratio)
    split_group.add_argument(
        "--validation-ratio",
        type=float,
        default=SPLIT_DEFAULTS.validation_ratio,
    )
    split_group.add_argument("--test-ratio", type=float, default=SPLIT_DEFAULTS.test_ratio)

    parser.add_argument(
        "--random-seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help=(
            "Seed shared by the split, the folds and the estimators. The run "
            "that fits the winner has to use the same one, or it would fit "
            "rows the search never scored on."
        ),
    )

    execution_group = parser.add_argument_group("execution")
    execution_group.add_argument(
        "--handoff",
        action="store_true",
        help=(
            "Start the training pipeline with the settings the search chose, "
            "so the winner is judged by the evaluation gate and registered as "
            "a candidate if it clears it."
        ),
    )
    execution_group.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print the search this invocation describes and stop, without "
            "contacting ClearML. This is how a search is reviewed before it "
            "is allowed to spend anything."
        ),
    )
    return parser


def parse_arguments(argv: Sequence[str]) -> tuple[SearchRequest, bool, bool]:
    """Build the contract of one search, or reject the invocation."""
    arguments = build_parser().parse_args(list(argv))
    plan = load_plan(resolve_environment(arguments.environment))
    request = SearchRequest(
        plan=plan,
        dataset=DatasetConfig(
            dataset_version=arguments.dataset_version,
            dataset_project=arguments.dataset_project,
            dataset_name=arguments.dataset_name,
            dataset_csv_path=arguments.dataset_csv_path,
        ),
        split=SplitConfig(
            train_ratio=arguments.train_ratio,
            validation_ratio=arguments.validation_ratio,
            test_ratio=arguments.test_ratio,
        ),
        random_seed=arguments.random_seed,
    )
    return request.validate(), arguments.handoff, arguments.dry_run


def run_search(request: SearchRequest) -> tuple[Task, BestTrial | None]:
    """Carry out one search, and answer the Task that records it.

    The Task exists before the first trial, so a search that is stopped
    halfway still says what it was trying to do. The winner is written onto it
    when the search ends, whether it ends because the budget ran out or
    because every candidate was tried.

    The trials themselves run on the trial queue. This process only describes
    them, starts them and reads their scores, which is why it is cheap to
    leave running while a search takes an hour.
    """
    task = start_optimization_task(request)
    optimizer = build_optimizer(request, ensure_trial_template(request), task=task)
    start_search(optimizer)

    winner = best_trial(optimizer, request.plan.objective.metric)
    if winner is not None:
        record_winner(task, winner)
    return task, winner


def hand_over(task: Task, request: SearchRequest, winner: BestTrial) -> int:
    """Give the winning settings to the training pipeline, and wait for it.

    The pipeline is the only path a model reaches the registry by, so a search
    hands over settings rather than a model. What it found still has to fit on
    the training rows, clear the gate on the validation rows and be evaluated
    once on the test rows, exactly as any other run does.

    It is started as the program it is, in its own process. A ClearML Task
    remembers the program that created it: a pipeline created from inside this
    process would name the search as its program, and cloning that Task to
    re-run the pipeline — which is what the Web UI and the Angular application
    do — would start another search instead.

    The run is waited for rather than left behind, because the answer a search
    is asked for is not "which settings won" but "did the winner clear the
    gate".
    """
    print(f"Handing the settings of trial {winner.task_id} to the training pipeline.")
    command = [
        sys.executable,
        "-m",
        PIPELINE_MODULE,
        *handoff_arguments(request, winner, str(task.id)),
    ]
    completed = subprocess.run(command, check=False, env=independent_environment())
    return int(completed.returncode)


def independent_environment() -> dict[str, str]:
    """The environment of a process that is not part of this one's Task.

    Everything else is inherited, including where ClearML is and how to
    authenticate to it. Only the two hints that say "you are a child of that
    Task" are removed.
    """
    environment = dict(os.environ)
    for name in CLEARML_PROCESS_VARIABLES:
        environment.pop(name, None)
    return environment


def main(argv: Sequence[str] | None = None) -> int:
    """Carry out one search and report its outcome as an exit code."""
    try:
        request, handoff, dry_run = parse_arguments(
            _forwarded_arguments(sys.argv[1:] if argv is None else argv)
        )
    except (ConfigurationError, ExperimentError) as error:
        print(error, file=sys.stderr)
        return EXIT_INVALID_USAGE

    if dry_run:
        print(_describe_plan(request.plan, request))
        return EXIT_SUCCESS

    try:
        task, winner = run_search(request)
    except KeyboardInterrupt:
        print("The search was interrupted before it completed.", file=sys.stderr)
        return EXIT_INTERRUPTED
    # 理由は報告する。握り潰さないための広い捕捉である。
    except Exception as error:
        print(f"The search failed: {error}", file=sys.stderr)
        return EXIT_FAILURE

    if winner is None:
        print(
            f"Search {task.id} finished without a trial that reported a score.",
            file=sys.stderr,
        )
        return EXIT_FAILURE

    print("\n".join((f"Search recorded as ClearML Task {task.id}", winner.describe())))
    if not handoff:
        print(
            "Nothing was registered. Run again with --handoff to put the winner "
            "through the evaluation gate, or start the pipeline yourself:\n"
            f"  python -m {PIPELINE_MODULE} "
            # 貼り付けて動く形にする。Dataset projectのように空白を含む値があるため、
            # 単純に並べると別々の引数として読まれてしまう。
            + shlex.join(handoff_arguments(request, winner, str(task.id)))
        )
        return EXIT_SUCCESS

    # 引き渡した実行の成否が、この探索の成否である。ゲートに落ちた実行を
    # 「成功」と報告すると、次に見る人は登録されたと思う。
    return EXIT_SUCCESS if hand_over(task, request, winner) == EXIT_SUCCESS else EXIT_FAILURE


def _forwarded_arguments(argv: Sequence[str]) -> list[str]:
    """Drop the separator a package manager puts in front of the arguments."""
    arguments = list(argv)
    if arguments and arguments[0] == ARGUMENT_SEPARATOR:
        del arguments[0]
    return arguments


def _describe_plan(plan: ExperimentPlan, request: SearchRequest) -> str:
    lines = [plan.describe(), "", "Every trial starts from:"]
    lines.extend(f"  {name} = {value!r}" for name, value in trial_parameters(request).items())
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

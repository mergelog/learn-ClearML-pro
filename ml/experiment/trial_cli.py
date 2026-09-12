"""Entry point that one trial of a search runs as.

A trial is a training run with a different question. A training run asks "what
model do these settings produce"; a trial asks "how good are these settings",
and answers with a number the search can compare. So it fits several models
and keeps none of them: what it produces is a score and the probability cut
that score was measured at.

Like a pipeline step, a trial is started by cloning a template Task and
editing its Parameters, so it reads what to do from the Task rather than from
a command line. That is what lets a search change one setting and start it
again, thirty times, without generating thirty commands.

The score is reported after every fold rather than once at the end. A search
reads those as it goes, which is what lets it abandon a candidate that is
already behind — and what makes the last reported value, once every fold has
run, the mean the search actually decides on.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence

from clearml import Logger, Task

from ml.pipeline.domain import PipelineError
from ml.pipeline.parameters import (
    read_dataset,
    read_estimator,
    read_random_seed,
    read_split,
)
from ml.semiconductor_quality.clearml_tracking import (
    DISABLED_MODEL_FRAMEWORKS,
    REQUIREMENTS_FILE,
    connected_settings,
    fetch_dataset,
    record_provenance,
)
from ml.semiconductor_quality.config import DEFAULT_RANDOM_SEED
from ml.semiconductor_quality.dataset import load_training_input
from ml.semiconductor_quality.domain import SplitPart
from ml.semiconductor_quality.preprocess import split_training_input
from ml.semiconductor_quality.provenance import collect_provenance

from .domain import (
    OBJECTIVE_TITLE,
    TRIAL_PROJECT,
    TRIAL_RESULT_ARTIFACT,
    TRIAL_TASK_NAME,
    ExperimentError,
    FoldScore,
    Objective,
    TrialPlan,
    TrialResult,
)
from .parameters import read_objective, read_trial_plan
from .trials import iter_folds, running_objective, summarise


# しきい値は「どこで切ったか」であって目的指標ではないので、別のグラフへ出す。
THRESHOLD_TITLE = "decision threshold"
THRESHOLD_SERIES = "agreed"

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_INVALID_USAGE = 2


class TrialTask:
    """The ClearML Task one trial runs as."""

    def __init__(self, task: Task) -> None:
        self._task = task

    @property
    def id(self) -> str:
        return str(self._task.id)

    @property
    def parameters(self) -> Mapping[str, str]:
        """What the search told this trial to try."""
        return {name: str(value) for name, value in (self._task.get_parameters() or {}).items()}

    def report_progress(self, objective: Objective, folds: Sequence[FoldScore]) -> None:
        """Say how the candidate is doing over everything measured so far.

        The iteration is the number of folds behind the value, so a search
        that is deciding whether to keep waiting can tell a candidate judged
        by one fold from one judged by five.
        """
        logger: Logger = self._task.get_logger()
        logger.report_scalar(
            title=OBJECTIVE_TITLE,
            series=objective.metric,
            value=running_objective(folds, objective.metric),
            iteration=len(folds),
        )

    def report_threshold(self, result: TrialResult) -> None:
        if result.threshold is None:
            return
        self._task.get_logger().report_scalar(
            title=THRESHOLD_TITLE,
            series=THRESHOLD_SERIES,
            value=result.threshold,
            iteration=len(result.folds),
        )

    def upload_result(self, result: TrialResult) -> None:
        self._task.upload_artifact(
            TRIAL_RESULT_ARTIFACT,
            artifact_object=result.as_document(),
            wait_on_upload=True,
            auto_pickle=False,
            sort_keys=False,
        )


def start_trial_task() -> TrialTask:
    """Create or attach to the ClearML Task this trial runs as."""
    connection = connected_settings()
    task: Task = Task.init(
        project_name=TRIAL_PROJECT,
        task_name=TRIAL_TASK_NAME,
        task_type=Task.TaskTypes.training,
        reuse_last_task_id=False,
        auto_connect_arg_parser=False,
        auto_connect_frameworks=dict(DISABLED_MODEL_FRAMEWORKS),
        output_uri=connection.files_host,
    )
    task.set_packages(str(REQUIREMENTS_FILE))
    # 試行も来歴を残す。採用された設定が「どのコードのどの実行で選ばれたか」
    # まで遡れる必要があり、その鎖は試行Taskを通る。
    record_provenance(task, collect_provenance(environment=os.environ))
    return TrialTask(task)


def run_trial(task: TrialTask) -> TrialResult:
    """Judge one candidate over the training rows, and report as it goes.

    Only the training part of the split reaches the judgement. The validation
    part is what the evaluation gate later holds the winner to, and the test
    part is the single final evaluation, so a search that scored on either
    would be marking its own homework.
    """
    parameters = task.parameters
    plan = read_trial_plan(parameters).validate()
    objective = read_objective(parameters)

    dataset = read_dataset(parameters).validate()
    training_input = load_training_input(fetch_dataset(dataset), dataset.dataset_csv_path)
    split = split_training_input(
        training_input,
        read_split(parameters).validate(),
        read_random_seed(parameters, DEFAULT_RANDOM_SEED),
    )

    result = _judge(task, split.train, parameters, plan, objective)
    task.report_threshold(result)
    task.upload_result(result)
    return result


def _judge(
    task: TrialTask,
    part: SplitPart,
    parameters: Mapping[str, str],
    plan: TrialPlan,
    objective: Objective,
) -> TrialResult:
    measured: list[FoldScore] = []
    for fold in iter_folds(
        part,
        read_estimator(parameters).validate(),
        plan,
        objective,
        read_random_seed(parameters, DEFAULT_RANDOM_SEED),
    ):
        measured.append(fold)
        task.report_progress(objective, measured)
    return summarise(measured, objective)


def main(argv: Sequence[str] | None = None) -> int:
    """Carry out one trial and report its outcome as an exit code."""
    _ = argv
    task = start_trial_task()
    try:
        result = run_trial(task)
    except (ExperimentError, PipelineError) as error:
        print(error, file=sys.stderr)
        return EXIT_INVALID_USAGE
    # 理由は報告する。握り潰さないための広い捕捉である。
    except Exception as error:
        print(f"Trial failed: {error}", file=sys.stderr)
        return EXIT_FAILURE

    print(
        f"Trial {task.id} scored {result.objective_metric}={result.objective:.4f} "
        f"over {len(result.folds)} folds at threshold {result.threshold}"
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())

"""ClearML boundary of one search.

A search is a Task that creates Tasks. This module builds the three things
that needs: a template a trial can be cloned from, the translation of the
search space into what the optimizer samples, and the record of the search
itself.

The record matters as much as the result. A number at the top of a leaderboard
answers "which settings won" and nothing else; six months later the question
is "what was it allowed to try, what did it call better, and what did it stop
for". So the space, the objective and the budget are written onto the
optimization Task before a single trial starts, and the winner is written onto
it when the search ends.

The optimizer itself is Optuna, driven by ClearML. It is chosen for one
property the built in random search does not have: it reads the score a trial
reports after each fold and abandons the candidates that are already behind,
so the budget is spent on the candidates that might still win.
"""

from __future__ import annotations

import math
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import ClassVar

from clearml import Task
from clearml.automation import (
    DiscreteParameterRange,
    HyperParameterOptimizer,
    LogUniformParameterRange,
    UniformIntegerParameterRange,
    UniformParameterRange,
)
from clearml.automation.optuna import OptimizerOptuna
from clearml.automation.parameters import Parameter

from ml.pipeline.domain import MODEL_SECTION
from ml.pipeline.parameters import (
    dataset_parameters,
    estimator_parameters,
    read_estimator,
    seed_parameters,
    split_parameters,
)
from ml.semiconductor_quality.clearml_tracking import (
    DISABLED_MODEL_FRAMEWORKS,
    REQUIREMENTS_FILE,
    connect_parameters,
    connected_settings,
    model_parameters,
    record_provenance,
)
from ml.semiconductor_quality.config import (
    DEFAULT_RANDOM_SEED,
    Contract,
    DatasetConfig,
    EstimatorConfig,
    SplitConfig,
)
from ml.semiconductor_quality.provenance import collect_provenance

from .domain import (
    BEST_TRIAL_ARTIFACT,
    OBJECTIVE_TITLE,
    OPTIMIZATION_PROJECT,
    OPTIMIZER_TASK_NAME,
    SEARCH_PLAN_ARTIFACT,
    SEARCH_SPLIT,
    TRIAL_PROJECT,
    TRIAL_RESULT_ARTIFACT,
    TRIAL_TASK_NAME,
    ChoiceRange,
    ExperimentError,
    ExperimentPlan,
    IntegerRange,
    NumberRange,
    ParameterRange,
    SearchSpace,
)
from .parameters import search_parameters


TRIAL_MODULE = "ml.experiment.trial_cli"

# 探索の制御役だけが必要とする依存。試行Taskは学習と同じ依存で足りる。
OPTIMIZATION_REQUIREMENTS_FILE = (
    Path(__file__).resolve().parents[2] / "requirements" / "optimization.txt"
)

# 探索そのものを記録するTaskの区画。
OBJECTIVE_SECTION = "Objective"
BUDGET_SECTION = "Budget"
TRIAL_SECTION = "Trial"
PLACEMENT_SECTION = "Execution"
SPACE_SECTION = "Search Space"

# 探索が対数目盛で値を引くときの底。ClearMLはこの底の指数で範囲を受け取る。
LOG_BASE = 10.0

# 制御役が試行の状態を見に行く間隔（分）。既定は2分だが、ここでの試行は
# 1分に満たないので、それでは待ち時間のほうが計算より長くなる。
# 短くするほどClearML Serverへの問い合わせは増えるため、試行の長さに
# 合わせた値にしてある。
POOL_PERIOD_MINUTES = 0.2

# 探索が自分のTaskへ進み具合を書く間隔（分）。既定は5分。
# これは表示のためだけの値に見えるが、探索が終わったあと制御役が
# 「最後の報告」を待つ時間でもある。既定のままだと、最後の試行が
# 終わってから最大5分、何もせずに待つことになる。
REPORT_PERIOD_MINUTES = 0.5


@dataclass(frozen=True)
class SearchRequest(Contract):
    """One search: what it varies, on which rows, and where it runs.

    The Dataset, the ratios and the seed are the same contract a training run
    and a pipeline run take. They have to be, because the winner of a search is
    handed straight to the pipeline: if the search divided the rows differently
    from the run that follows it, the settings it chose would have been chosen
    for rows the final model never sees.
    """

    error_heading: ClassVar[str] = "Invalid search request"

    plan: ExperimentPlan
    dataset: DatasetConfig
    split: SplitConfig = field(default_factory=SplitConfig)
    random_seed: int = DEFAULT_RANDOM_SEED

    def collect_errors(self) -> tuple[str, ...]:
        return (
            *self.plan.collect_errors(),
            *self.dataset.collect_errors(),
            *self.split.collect_errors(),
        )


@dataclass(frozen=True)
class BestTrial:
    """The candidate a finished search kept, and what it scored.

    The settings are read back from the Task the search actually ran, not from
    what the search intended to run. That is the difference between "this is
    what won" and "this is what we think won".
    """

    task_id: str
    objective_metric: str
    objective: float
    estimator: EstimatorConfig

    def as_document(self) -> dict[str, object]:
        return {
            "trial_task_id": self.task_id,
            "objective_metric": self.objective_metric,
            "objective": float(self.objective),
            "split": SEARCH_SPLIT,
            "estimator": dict(estimator_parameters(self.estimator)),
        }

    def describe(self) -> str:
        return (
            f"Trial {self.task_id} scored {self.objective_metric}="
            f"{self.objective:.4f} on the {SEARCH_SPLIT} split"
        )


def trial_parameters(request: SearchRequest) -> dict[str, str]:
    """Everything a trial has to be told, before the search varies any of it.

    The template carries a complete, runnable set of values rather than empty
    placeholders, so a trial Task can be cloned and started by hand from the
    Web UI to reproduce exactly one point of the search.
    """
    parameters: dict[str, str] = {}
    parameters.update(dataset_parameters(request.dataset))
    parameters.update(split_parameters(request.split))
    parameters.update(estimator_parameters(request.plan.estimator))
    parameters.update(seed_parameters(request.random_seed))
    parameters.update(search_parameters(request.plan.trial, request.plan.objective))
    return parameters


def hyper_parameters(space: SearchSpace) -> list[Parameter]:
    """Translate the search space into what the optimizer samples."""
    return [_translate(parameter) for parameter in space.ranges]


def _translate(parameter: ParameterRange) -> Parameter:
    name = estimator_parameter_name(parameter.name)
    if isinstance(parameter, ChoiceRange):
        return DiscreteParameterRange(name, values=list(parameter.values))
    if isinstance(parameter, IntegerRange):
        return UniformIntegerParameterRange(
            name,
            min_value=parameter.minimum,
            max_value=parameter.maximum,
            step_size=parameter.step,
        )
    if isinstance(parameter, NumberRange):
        if not parameter.logarithmic:
            return UniformParameterRange(
                name,
                min_value=parameter.minimum,
                max_value=parameter.maximum,
            )
        # ClearMLの対数範囲は値ではなく「底の指数」で受け取る。0.01〜0.3 を
        # そのまま渡すと 10^0.01〜10^0.3 を探すことになるので、ここで換算する。
        return LogUniformParameterRange(
            name,
            min_value=math.log(parameter.minimum, LOG_BASE),
            max_value=math.log(parameter.maximum, LOG_BASE),
            base=LOG_BASE,
        )
    raise ExperimentError(f"{parameter.name} has a kind this search cannot sample")


def estimator_parameter_name(name: str) -> str:
    """The full Parameter path a trial reads one searched setting from.

    The optimizer edits Parameters by their full path, so a search that named
    them differently from the way a trial reads them would sample values that
    change nothing.
    """
    return f"{MODEL_SECTION}/{name}"


def ensure_trial_template(request: SearchRequest) -> str:
    """Make sure the Task a trial is cloned from exists, and says what it does.

    The template is looked up by name and only created when missing, so two
    searches do not leave two definitions of a trial behind. Its Parameters
    are written every time, because a trial that starts reading a new
    Parameter must not keep a template that does not declare it.
    """
    task = _existing_template() or _new_template()
    for name, value in trial_parameters(request).items():
        task.set_parameter(name, value)
    return str(task.id)


def start_optimization_task(request: SearchRequest) -> Task:
    """Create the Task that records the search, before anything is tried.

    Everything needed to run the same search again is written here: what may
    vary, what counts as better, what may be spent and where it runs. A search
    whose record is written only at the end is a search that explains nothing
    when it is stopped halfway.
    """
    connection = connected_settings()
    task: Task = Task.init(
        project_name=OPTIMIZATION_PROJECT,
        task_name=OPTIMIZER_TASK_NAME,
        task_type=Task.TaskTypes.optimizer,
        reuse_last_task_id=False,
        auto_connect_arg_parser=False,
        auto_connect_frameworks=dict(DISABLED_MODEL_FRAMEWORKS),
        output_uri=connection.files_host,
    )
    task.set_packages(str(OPTIMIZATION_REQUIREMENTS_FILE))
    record_provenance(task, collect_provenance(environment=os.environ))
    record_plan(task, request)
    return task


def record_plan(task: Task, request: SearchRequest) -> None:
    """Write the description of the search onto its own Task."""
    plan = request.plan
    connect_parameters(
        task,
        {
            "metric": plan.objective.metric,
            "direction": plan.objective.direction.value,
            "split": SEARCH_SPLIT,
        },
        OBJECTIVE_SECTION,
    )
    connect_parameters(task, dict(plan.budget.as_document()), BUDGET_SECTION)
    connect_parameters(task, dict(plan.trial.as_document()), TRIAL_SECTION)
    connect_parameters(
        task,
        {
            "environment": plan.environment.value,
            "trial_queue": plan.placement.trial_queue,
            "optimizer_queue": plan.placement.optimizer_queue,
        },
        PLACEMENT_SECTION,
    )
    connect_parameters(
        task,
        {parameter.name: parameter.describe() for parameter in plan.space.ranges},
        SPACE_SECTION,
    )
    task.upload_artifact(
        SEARCH_PLAN_ARTIFACT,
        artifact_object=plan.as_document(),
        wait_on_upload=True,
        auto_pickle=False,
        sort_keys=False,
    )


def build_optimizer(
    request: SearchRequest,
    base_task_id: str,
    task: Task | None = None,
) -> HyperParameterOptimizer:
    """Describe the search: what to sample, what to read, and when to stop.

    Every limit the budget names is handed over here. A search with no limit
    does not end: it keeps finding a fourth decimal place until somebody
    notices the queue is full.
    """
    plan = request.plan
    return HyperParameterOptimizer(
        base_task_id=base_task_id,
        hyper_parameters=hyper_parameters(plan.space),
        objective_metric_title=OBJECTIVE_TITLE,
        objective_metric_series=plan.objective.metric,
        objective_metric_sign=plan.objective.direction.clearml_sign,
        optimizer_class=OptimizerOptuna,
        execution_queue=plan.placement.trial_queue,
        max_number_of_concurrent_tasks=plan.budget.parallel_trials,
        total_max_jobs=plan.budget.max_trials,
        optimization_time_limit=plan.budget.total_minutes,
        time_limit_per_job=plan.budget.trial_minutes,
        # 「反復」はfoldの数である。全fold終えた値が最終成績で、
        # そこまでの値は途中経過として打ち切りの判断に使われる。
        max_iteration_per_job=plan.trial.folds,
        min_iteration_per_job=plan.budget.minimum_folds,
        save_top_k_tasks_only=plan.budget.keep_top,
        pool_period_min=POOL_PERIOD_MINUTES,
        spawn_project=TRIAL_PROJECT,
        auto_connect_task=task if task is not None else True,
    )


def start_search(optimizer: HyperParameterOptimizer) -> None:
    """Start the trials, and wait for the search to end.

    The reporting period is set before starting, because it is also how long
    the controller waits for its last progress report after the final trial.
    Left at its default, a search that finished in three minutes would sit
    idle for five more.
    """
    optimizer.set_report_period(REPORT_PERIOD_MINUTES)
    optimizer.start()
    try:
        optimizer.wait()
    finally:
        optimizer.stop()


def best_trial(optimizer: HyperParameterOptimizer, metric: str) -> BestTrial | None:
    """Read back the candidate the search kept, from the Task that ran it."""
    experiments: Sequence[Task] = optimizer.get_top_experiments(top_k=1)
    if not experiments:
        return None
    return read_trial(experiments[0], metric)


def read_trial(task: Task, metric: str) -> BestTrial:
    """Build the winning contract out of what one trial Task recorded.

    The searched settings are read from its Parameters and the probability cut
    from its result, because the cut is not something the search chose: each
    trial chose its own, from the folds it fitted.
    """
    parameters = {name: str(value) for name, value in (task.get_parameters() or {}).items()}
    result = _trial_result(task)
    objective = result.get("objective")
    if not isinstance(objective, (int, float)):
        raise ExperimentError(
            f"Task {task.id} did not record what it scored, so it cannot be "
            "handed on as the winner of the search"
        )

    threshold = result.get("decision_threshold")
    estimator = read_estimator(parameters)
    return BestTrial(
        task_id=str(task.id),
        objective_metric=str(result.get("objective_metric", metric)),
        objective=float(objective),
        estimator=replace(
            estimator,
            decision_threshold=float(threshold) if isinstance(threshold, (int, float)) else None,
        ).validate(),
    )


def handoff_arguments(request: SearchRequest, winner: BestTrial, search_task_id: str) -> list[str]:
    """The invocation that turns the winning settings into a pipeline run.

    The winner is handed over as an invocation of the training pipeline rather
    than as a call into it. A ClearML Task remembers the program that created
    it, so a pipeline created from inside the search would carry the search as
    its program: cloning that Task to re-run the pipeline would start another
    search instead. Building the command here, and running it as the program
    it names, keeps a pipeline run a pipeline run.

    The estimator is flattened by the same function that records it on a Task,
    so a setting cannot be recorded under one name and handed over under
    another. Every name it produces is an argument of the pipeline command,
    with underscores spelled as dashes.
    """
    arguments = [
        "--dataset-version",
        request.dataset.dataset_version,
        "--dataset-project",
        request.dataset.dataset_project,
        "--dataset-name",
        request.dataset.dataset_name,
        "--dataset-csv-path",
        request.dataset.dataset_csv_path,
        "--train-ratio",
        str(request.split.train_ratio),
        "--validation-ratio",
        str(request.split.validation_ratio),
        "--test-ratio",
        str(request.split.test_ratio),
        "--random-seed",
        str(request.random_seed),
        "--queue",
        request.plan.placement.trial_queue,
        "--pipeline-queue",
        request.plan.placement.optimizer_queue,
        "--origin-search-task-id",
        search_task_id,
        "--origin-trial-task-id",
        winner.task_id,
    ]
    for name, value in model_parameters(winner.estimator).items():
        # 指示されなかった設定は渡さない。渡す側が既定値を書き写すと、
        # 「探索が選んだ値」と「たまたま既定だった値」が区別できなくなる。
        if value is None:
            continue
        arguments.extend((f"--{name.replace('_', '-')}", str(value)))
    return arguments


def record_winner(task: Task, winner: BestTrial) -> None:
    """Write the outcome of the search onto the Task that ran it."""
    task.upload_artifact(
        BEST_TRIAL_ARTIFACT,
        artifact_object=winner.as_document(),
        wait_on_upload=True,
        auto_pickle=False,
        sort_keys=False,
    )


def _trial_result(task: Task) -> Mapping[str, object]:
    artifact = task.artifacts.get(TRIAL_RESULT_ARTIFACT)
    if artifact is None:
        raise ExperimentError(
            f"Task {task.id} holds no {TRIAL_RESULT_ARTIFACT!r}, so what it "
            "scored cannot be read back"
        )
    content = artifact.get()
    if not isinstance(content, dict):
        raise ExperimentError(f"the {TRIAL_RESULT_ARTIFACT!r} of Task {task.id} is not a result")
    return content


def _new_template() -> Task:
    created: Task = Task.create(
        project_name=TRIAL_PROJECT,
        task_name=TRIAL_TASK_NAME,
        task_type=Task.TaskTypes.training.value,
        module=TRIAL_MODULE,
        # 試行が要るのは学習と同じ依存だけである。探索の枝刈りを進める
        # 側の依存は、制御役のTaskにしか要らない。
        requirements_file=str(REQUIREMENTS_FILE),
        add_task_init_call=False,
        # このリポジトリにはgit remoteが無く、Agentはcloneできない。
        # コードはAgentへ持ち込んだ作業ツリーから読む。
        detect_repository=False,
    )
    return created


def _existing_template() -> Task | None:
    tasks: Sequence[Task] = Task.get_tasks(
        project_name=TRIAL_PROJECT,
        task_name=f"^{re.escape(TRIAL_TASK_NAME)}$",
    )
    for task in tasks:
        if task.name == TRIAL_TASK_NAME:
            found: Task = Task.get_task(task_id=str(task.id))
            return found
    return None

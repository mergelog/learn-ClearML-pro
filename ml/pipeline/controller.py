"""Assemble the training pipeline out of the step Tasks.

A ClearML Pipeline does not carry code. It carries a graph of Tasks, and for
each run it clones them and edits their Parameters. So the pipeline needs two
things that this module provides.

First, a template Task per step: a Task that names the entry point, the
dependencies to install and the step it carries out, but has never run. The
templates are created once and reused, which is what makes a pipeline run
cheap and what lets the Web UI show the same step across runs.

Second, the per run overrides: which Dataset version, which ratios, which
forest, and which upstream execution each step reads. The upstream ids are
written as ``${step.id}`` placeholders, which the controller resolves while the
run is in progress, so a step always reads the execution from its own run.

Nothing here trains anything. This module builds the description of a run and
hands it to ClearML.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import ClassVar

from clearml import Task
from clearml.automation import PipelineController

from ml.semiconductor_quality.clearml_tracking import (
    REQUIREMENTS_FILE,
    connected_settings,
)
from ml.semiconductor_quality.config import (
    DEFAULT_PIPELINE_QUEUE,
    DEFAULT_RANDOM_SEED,
    Contract,
    DatasetConfig,
    EstimatorConfig,
    SplitConfig,
    _require_text,
)

from .domain import (
    DATA_QUALITY_SECTION,
    PIPELINE_NAME,
    PIPELINE_PROJECT,
    PIPELINE_VERSION,
    STEP_INPUTS,
    STEP_PROJECT,
    STEP_SECTION,
    StepName,
    input_placeholders,
)
from .parameters import (
    dataset_parameters,
    estimator_parameters,
    seed_parameters,
    split_parameters,
)
from .step_cli import STEP_NAME_PARAMETER
from .steps import DRIFT_REFERENCE_PARAMETER


STEP_MODULE = "ml.pipeline.step_cli"

# 実行を頼んだ側を記録する区画。探索から渡された実行にだけ入る。
HANDOFF_SECTION = "Handoff"
SEARCH_TASK_PARAMETER = "search_task_id"
TRIAL_TASK_PARAMETER = "trial_task_id"

# Pipelineの各ステップが「未達成のまま次へ進まない」ことを担保する。
# 上流が失敗したら後続を動かさない、が既定の振る舞いである。
CONTINUE_ON_FAILURE = False


@dataclass(frozen=True)
class RunOrigin:
    """Where a run came from, when it did not come from a person.

    A search chooses settings and then asks for a run with them. Recording
    which search and which trial on the run itself is what lets somebody
    holding a registered model ask "why these settings" and get an answer,
    rather than a shrug.
    """

    search_task_id: str = ""
    trial_task_id: str = ""

    @property
    def is_known(self) -> bool:
        return bool(self.search_task_id or self.trial_task_id)

    def parameters(self) -> dict[str, str]:
        return {
            f"{HANDOFF_SECTION}/{SEARCH_TASK_PARAMETER}": self.search_task_id,
            f"{HANDOFF_SECTION}/{TRIAL_TASK_PARAMETER}": self.trial_task_id,
        }


@dataclass(frozen=True)
class PipelineRequest(Contract):
    """What one pipeline run computes, and where its steps run.

    This is the same contract a single training run takes, plus the queue the
    steps are carried out on. Keeping them the same is what lets a result from
    the pipeline be compared with a result from ``ml:train``.
    """

    error_heading: ClassVar[str] = "Invalid pipeline request"

    dataset: DatasetConfig
    queue: str
    # 比較対象のDataset Version。空なら比較しない。
    drift_reference_version: str = ""
    # この実行を頼んだ側。探索から渡されたときだけ入る。
    origin: RunOrigin = field(default_factory=lambda: RunOrigin())
    pipeline_queue: str = DEFAULT_PIPELINE_QUEUE
    submitted: bool = False
    split: SplitConfig = field(default_factory=SplitConfig)
    estimator: EstimatorConfig = field(default_factory=EstimatorConfig)
    random_seed: int = DEFAULT_RANDOM_SEED

    def collect_errors(self) -> tuple[str, ...]:
        return (
            *self.dataset.collect_errors(),
            *self.split.collect_errors(),
            *self.estimator.collect_errors(),
            *_require_text("queue", self.queue),
            *_require_text("pipeline_queue", self.pipeline_queue),
        )


def template_parameters(step: StepName, request: PipelineRequest) -> dict[str, str]:
    """The Parameters a step reads, with the values a run starts from.

    Only the sections a step actually reads are put on its template. A Task
    page that lists parameters a step ignores invites somebody to change one
    and wonder why nothing happened.
    """
    parameters: dict[str, str] = {f"{STEP_SECTION}/{STEP_NAME_PARAMETER}": step.value}
    parameters.update(dict.fromkeys(input_placeholders(step), ""))

    if step is StepName.VALIDATE:
        parameters.update(dataset_parameters(request.dataset))
        parameters[f"{DATA_QUALITY_SECTION}/{DRIFT_REFERENCE_PARAMETER}"] = (
            request.drift_reference_version or ""
        )
    if step is StepName.PREPROCESS:
        parameters.update(split_parameters(request.split))
        parameters.update(seed_parameters(request.random_seed))
    if step is StepName.TRAIN:
        parameters.update(estimator_parameters(request.estimator))
        parameters.update(seed_parameters(request.random_seed))
    return parameters


def run_overrides(step: StepName, request: PipelineRequest) -> dict[str, str]:
    """What this run changes on the cloned template of one step."""
    overrides = dict(input_placeholders(step))
    overrides.update(
        {
            name: value
            for name, value in template_parameters(step, request).items()
            if name not in overrides and not name.startswith(f"{STEP_SECTION}/")
        }
    )
    return overrides


def ensure_templates(request: PipelineRequest) -> dict[StepName, str]:
    """Make sure a template Task exists for every step, and is up to date.

    Templates are looked up by name and only created when missing, so running
    the pipeline twice does not leave two definitions of the same step behind.

    The Parameters are written every time, including on a template that
    already existed. A step that starts reading a new Parameter would
    otherwise keep an old template that does not declare it, and the Task page
    would no longer show what the step actually reads.
    """
    return {step: _ensure_template(step, request) for step in StepName}


def build_controller(
    request: PipelineRequest,
    templates: Mapping[StepName, str],
) -> PipelineController:
    """Describe one pipeline run: the steps, their order, and their inputs.

    Where the run came from is written onto the pipeline Task itself, before
    it starts. A run that was asked for by a search says so from the moment it
    exists, rather than once somebody remembers to write it down.
    """
    controller = PipelineController(
        name=PIPELINE_NAME,
        project=PIPELINE_PROJECT,
        version=PIPELINE_VERSION,
        add_pipeline_tags=True,
        target_project=PIPELINE_PROJECT,
    )
    controller.set_default_execution_queue(request.queue)

    for step in StepName:
        controller.add_step(
            name=step.value,
            base_task_id=templates[step],
            parents=[parent.value for parent in STEP_INPUTS[step]],
            parameter_override=run_overrides(step, request),
            execution_queue=request.queue,
            continue_on_fail=CONTINUE_ON_FAILURE,
        )

    if request.origin.is_known:
        for name, value in request.origin.parameters().items():
            controller.task.set_parameter(name, value)
    return controller


def _ensure_template(step: StepName, request: PipelineRequest) -> str:
    task = _existing_template(step) or _new_template(step)
    for name, value in template_parameters(step, request).items():
        task.set_parameter(name, value)
    return str(task.id)


def _new_template(step: StepName) -> Task:
    created: Task = Task.create(
        project_name=STEP_PROJECT,
        task_name=step.task_name,
        task_type=Task.TaskTypes.custom.value,
        module=STEP_MODULE,
        requirements_file=str(REQUIREMENTS_FILE),
        add_task_init_call=False,
        # このリポジトリにはgit remoteが無く、Agentはcloneできない。
        # コードはAgentへ持ち込んだ作業ツリーから読む。
        detect_repository=False,
    )
    return created


def _existing_template(step: StepName) -> Task | None:
    task_id = _find_template(step)
    if task_id is None:
        return None
    found: Task = Task.get_task(task_id=task_id)
    return found


def _find_template(step: StepName) -> str | None:
    tasks: Sequence[Task] = Task.get_tasks(
        project_name=STEP_PROJECT,
        task_name=f"^{re.escape(step.task_name)}$",
    )
    for task in tasks:
        if task.name == step.task_name:
            return str(task.id)
    return None


def connect_to_server() -> None:
    """Point the SDK at the configured server before any Task is looked up."""
    connected_settings()

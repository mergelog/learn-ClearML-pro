"""Contracts of the training pipeline.

The single training command does data validation, preprocessing, fitting,
scoring and model registration in one process. That is enough to reproduce a
run, but not enough to see where a run stopped, to re-run one part of it, or
to reuse a part between runs.

This module states what the pipeline splits that work into. It depends on
nothing but the standard library, so the shape of the pipeline can be
exercised without a ClearML Server.

Two rules shape every contract here.

A step never reads the arguments of the run. It reads its own Parameters and
the Artifacts of the steps it declares as inputs. That is what lets the
Pipeline controller decide, per run, which upstream execution a step consumes.

A step names its outputs. Downstream steps address them by name, so a change
in what a step produces is visible as a change in this file rather than as a
missing key at runtime.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


PIPELINE_PROJECT = "Semiconductor Quality Prediction/Pipeline"
STEP_PROJECT = f"{PIPELINE_PROJECT}/Steps"

PIPELINE_NAME = "semiconductor-quality-training"
PIPELINE_VERSION = "1.0.0"

# 各Taskが自分の入力を読む区画。Pipelineはここへ上書きを書き込む。
DATASET_SECTION = "Dataset"
SPLIT_SECTION = "Split"
MODEL_SECTION = "Model"
EXECUTION_SECTION = "Execution"
STEP_SECTION = "Step"
INPUT_SECTION = "Inputs"
RESOLVED_DATASET_SECTION = "Resolved Dataset"
DATA_QUALITY_SECTION = "Data Quality"

# 上流の実行を指すパラメータ。Pipelineが `${step.id}` で埋める。
VALIDATE_TASK_PARAMETER = "validate_task_id"
PREPROCESS_TASK_PARAMETER = "preprocess_task_id"
TRAIN_TASK_PARAMETER = "train_task_id"
EVALUATE_TASK_PARAMETER = "evaluate_task_id"

# ステップ間で受け渡すArtifactの名前。
VALIDATION_REPORT_ARTIFACT = "validation_report"
DATA_PROFILE_ARTIFACT = "data_profile"
DATA_QUALITY_ARTIFACT = "data_quality"
DATA_DRIFT_ARTIFACT = "data_drift"
LINEAGE_ARTIFACT = "lineage"
SPLIT_ARTIFACT = "split"
SPLIT_SUMMARY_ARTIFACT = "split_summary"
MODEL_WEIGHTS_ARTIFACT = "model_weights"
EVALUATION_ARTIFACT = "evaluation"
DECISION_ARTIFACT = "registration_decision"


class StepName(str, Enum):
    """The steps a pipeline run is divided into.

    The order of the members is the order of the pipeline, and each member is
    both the name of the step in the Pipeline view and the suffix of the Task
    that carries it out.
    """

    VALIDATE = "validate"
    PREPROCESS = "preprocess"
    TRAIN = "train"
    EVALUATE = "evaluate"
    REGISTER_CANDIDATE = "register-candidate"

    @property
    def task_name(self) -> str:
        return f"pipeline-step-{self.value}"

    def __str__(self) -> str:
        return self.value


# どのステップがどのステップの結果を必要とするか。Pipelineの依存関係は
# ここから組み立てるので、依存の宣言はこの1か所にしかない。
STEP_INPUTS: Mapping[StepName, tuple[StepName, ...]] = {
    StepName.VALIDATE: (),
    StepName.PREPROCESS: (StepName.VALIDATE,),
    StepName.TRAIN: (StepName.PREPROCESS,),
    StepName.EVALUATE: (StepName.PREPROCESS, StepName.TRAIN),
    # 登録するモデルには、どのDatasetから来たかを記録する。そのため
    # 検証ステップの結果も入力として宣言する。
    StepName.REGISTER_CANDIDATE: (StepName.VALIDATE, StepName.TRAIN, StepName.EVALUATE),
}

# 上流ステップを指すパラメータ名。入力の宣言と対になる。
STEP_PARAMETERS: Mapping[StepName, str] = {
    StepName.VALIDATE: VALIDATE_TASK_PARAMETER,
    StepName.PREPROCESS: PREPROCESS_TASK_PARAMETER,
    StepName.TRAIN: TRAIN_TASK_PARAMETER,
    StepName.EVALUATE: EVALUATE_TASK_PARAMETER,
}


class PipelineError(RuntimeError):
    """Raised when a step cannot be carried out as the pipeline described it."""


@dataclass(frozen=True)
class StepInputs:
    """Which upstream executions one step was told to read.

    The ids are text because they arrive as Task Parameters. An empty id means
    the pipeline did not connect that input, which is a mistake in the
    pipeline rather than in the step, and is reported as such.
    """

    task_ids: Mapping[StepName, str]

    def required(self, step: StepName) -> str:
        task_id = self.task_ids.get(step, "").strip()
        if not task_id:
            raise PipelineError(
                f"this step needs the {step} step to have run, but no Task was "
                f"named in {INPUT_SECTION}/{STEP_PARAMETERS[step]}"
            )
        return task_id

    @classmethod
    def from_parameters(cls, parameters: Mapping[str, str]) -> StepInputs:
        """Read the upstream Task ids out of the Parameters of one step."""
        return cls(
            task_ids={
                step: str(parameters.get(f"{INPUT_SECTION}/{parameter}", "")).strip()
                for step, parameter in STEP_PARAMETERS.items()
            }
        )


def input_placeholders(step: StepName) -> dict[str, str]:
    """Build the Parameter overrides that connect one step to its inputs.

    ``${validate.id}`` is resolved by the Pipeline controller when the run
    starts, which is what makes every step read the execution of *this* run
    rather than whichever Task happened to run last.
    """
    return {
        f"{INPUT_SECTION}/{STEP_PARAMETERS[upstream]}": f"${{{upstream.value}.id}}"
        for upstream in STEP_INPUTS[step]
    }

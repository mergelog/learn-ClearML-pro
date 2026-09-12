"""Entry point that one pipeline step runs as.

Every step of the pipeline is the same program. Which step it carries out is
part of the Task, not part of the invocation, because a Pipeline controller
clones a Task and edits its Parameters. It cannot edit a command line.

Running it by hand is still possible with ``--step``, which is how a single
step is reproduced outside a pipeline run while looking at what it did.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from clearml import Task

from ml.semiconductor_quality.clearml_tracking import (
    DISABLED_MODEL_FRAMEWORKS,
    REQUIREMENTS_FILE,
    connected_settings,
    record_provenance,
)
from ml.semiconductor_quality.provenance import collect_provenance

from .domain import STEP_PROJECT, STEP_SECTION, PipelineError, StepName
from .steps import StepTask, run_step


STEP_NAME_PARAMETER = "name"

# ``--step`` を付けずに起動された場合のTask名。Agentの下では既存のTaskへ
# 結び付くので、この名前が使われるのは手元で試すときだけである。
UNNAMED_STEP_TASK_NAME = "pipeline-step"

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_INVALID_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Carry out one step of the semiconductor quality training pipeline. "
            "Inside a pipeline run the step is named by the Task itself."
        ),
    )
    parser.add_argument(
        "--step",
        choices=[step.value for step in StepName],
        default=None,
        help="Carry out this step, instead of the one the Task names.",
    )
    return parser


def start_step_task(step: StepName | None) -> StepTask:
    """Create or attach to the ClearML Task this step runs as."""
    connection = connected_settings()

    task: Task = Task.init(
        project_name=STEP_PROJECT,
        task_name=step.task_name if step is not None else UNNAMED_STEP_TASK_NAME,
        task_type=Task.TaskTypes.custom,
        reuse_last_task_id=False,
        auto_connect_arg_parser=False,
        auto_connect_frameworks=dict(DISABLED_MODEL_FRAMEWORKS),
        output_uri=connection.files_host,
    )
    # Agent配下では ``Task.init(output_uri=...)`` は既存Taskの設定を上書きしない。
    # 明示しないと成果物がAgentのローカルパスのまま登録され、別のプロセスからは
    # 読めないモデルができあがる。置き場所は誰でも取得できるfile serverにする。
    # SDKの型情報では読み取り専用に見えるが、setterは公開APIとして存在する。
    task.output_uri = connection.files_host  # type: ignore[misc]
    task.set_packages(str(REQUIREMENTS_FILE))
    # ステップも来歴を残す。昇格したモデルから「どのコードが動いたか」まで
    # 遡れる必要があり、その鎖はステップTaskを通る。
    record_provenance(task, collect_provenance(environment=os.environ))
    return StepTask(task)


def resolve_step(task: StepTask, requested: StepName | None) -> StepName:
    """Answer which step this Task carries out.

    A step run by a pipeline is named by its Task. A step run by hand is named
    on the command line. A Task that names neither is a mistake in how the
    pipeline templates were created, and is refused rather than guessed.
    """
    if requested is not None:
        return requested

    recorded = str(task.parameters.get(f"{STEP_SECTION}/{STEP_NAME_PARAMETER}", "")).strip()
    if not recorded:
        raise PipelineError(
            f"this Task does not say which step it is: {STEP_SECTION}/"
            f"{STEP_NAME_PARAMETER} is empty and --step was not given"
        )

    try:
        return StepName(recorded)
    except ValueError as error:
        known = ", ".join(step.value for step in StepName)
        raise PipelineError(
            f"{recorded!r} is not a step of this pipeline. Known steps: {known}"
        ) from error


def main(argv: Sequence[str] | None = None) -> int:
    """Carry out one step and report its outcome as an exit code."""
    arguments = build_parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    requested = StepName(arguments.step) if arguments.step else None

    task = start_step_task(requested)
    try:
        step = resolve_step(task, requested)
        with TemporaryDirectory(prefix="pipeline-step-") as directory:
            run_step(step, task, Path(directory))
    except PipelineError as error:
        print(error, file=sys.stderr)
        return EXIT_INVALID_USAGE
    # 理由は報告する。握り潰さないための広い捕捉である。
    except Exception as error:
        print(f"Step failed: {error}", file=sys.stderr)
        return EXIT_FAILURE

    print(f"Step {step} completed as ClearML Task {task.id}")
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

from ml.pipeline import step_cli
from ml.pipeline.domain import STEP_SECTION, PipelineError, StepName
from ml.pipeline.step_cli import (
    EXIT_FAILURE,
    EXIT_INVALID_USAGE,
    EXIT_SUCCESS,
    STEP_NAME_PARAMETER,
    build_parser,
    main,
    resolve_step,
)
from ml.pipeline.steps import StepTask


def task_naming(step: str | None) -> StepTask:
    task = mock.MagicMock(spec=StepTask)
    task.id = "step-task"
    task.parameters = {} if step is None else {f"{STEP_SECTION}/{STEP_NAME_PARAMETER}": step}
    return task


class StepArgumentTest(unittest.TestCase):
    def test_a_step_can_be_named_on_the_command_line(self) -> None:
        arguments = build_parser().parse_args(["--step", "train"])

        self.assertEqual(arguments.step, "train")

    def test_no_step_is_named_by_default(self) -> None:
        self.assertIsNone(build_parser().parse_args([]).step)

    def test_a_step_that_is_not_part_of_the_pipeline_is_rejected(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args(["--step", "deploy"])


class ResolveStepTest(unittest.TestCase):
    def test_the_task_says_which_step_it_carries_out(self) -> None:
        self.assertEqual(resolve_step(task_naming("evaluate"), None), StepName.EVALUATE)

    def test_the_command_line_wins_when_a_step_is_run_by_hand(self) -> None:
        resolved = resolve_step(task_naming("evaluate"), StepName.TRAIN)

        self.assertEqual(resolved, StepName.TRAIN)

    def test_a_task_that_names_no_step_is_refused(self) -> None:
        with self.assertRaises(PipelineError) as raised:
            resolve_step(task_naming(None), None)

        self.assertIn(f"{STEP_SECTION}/{STEP_NAME_PARAMETER}", str(raised.exception))

    def test_a_task_that_names_an_unknown_step_is_refused(self) -> None:
        with self.assertRaises(PipelineError) as raised:
            resolve_step(task_naming("deploy"), None)

        self.assertIn("deploy", str(raised.exception))

    def test_surrounding_space_does_not_hide_the_step(self) -> None:
        self.assertEqual(resolve_step(task_naming("  train  "), None), StepName.TRAIN)


class StepExitCodeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.task = task_naming("train")
        self.run_step = mock.MagicMock(name="run_step")
        for name, replacement in (
            ("start_step_task", mock.MagicMock(name="start_step_task", return_value=self.task)),
            ("run_step", self.run_step),
        ):
            patcher = mock.patch.object(step_cli, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_a_completed_step_names_the_task_it_can_be_reviewed_on(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = main([])

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("step-task", stdout.getvalue())
        self.assertIn("train", stdout.getvalue())

    def test_the_step_is_carried_out_in_a_directory_of_its_own(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            main([])

        step, task, work_dir = self.run_step.call_args.args
        self.assertEqual(step, StepName.TRAIN)
        self.assertIs(task, self.task)
        self.assertTrue(work_dir.name.startswith("pipeline-step-"))

    def test_a_step_the_pipeline_wired_up_wrongly_is_a_usage_error(self) -> None:
        # ``parameters`` は読み取り専用のプロパティなので、Taskごと差し替える。
        step_cli.start_step_task.return_value = task_naming(None)  # type: ignore[attr-defined]

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = main([])

        self.assertEqual(code, EXIT_INVALID_USAGE)
        self.assertIn(STEP_NAME_PARAMETER, stderr.getvalue())

    def test_a_step_that_raises_is_reported_as_a_failure(self) -> None:
        self.run_step.side_effect = RuntimeError("the artifact could not be downloaded")

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = main([])

        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("the artifact could not be downloaded", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

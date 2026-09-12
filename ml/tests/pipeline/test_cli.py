from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

from ml.pipeline import cli
from ml.pipeline.cli import (
    EXIT_FAILURE,
    EXIT_INVALID_USAGE,
    EXIT_SUCCESS,
    main,
    parse_arguments,
)
from ml.pipeline.domain import PipelineError, StepName
from ml.semiconductor_quality.config import (
    DEFAULT_DATASET_NAME,
    DEFAULT_DATASET_PROJECT,
    DEFAULT_RANDOM_SEED,
    DEFAULT_TRAINING_QUEUE,
    ConfigurationError,
)


ARGUMENTS = ["--dataset-version", "1.0.0"]


class PipelineArgumentTest(unittest.TestCase):
    def test_the_dataset_version_is_required(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_arguments([])

    def test_the_defaults_match_the_single_training_run(self) -> None:
        request = parse_arguments(ARGUMENTS)

        self.assertEqual(request.dataset.dataset_project, DEFAULT_DATASET_PROJECT)
        self.assertEqual(request.dataset.dataset_name, DEFAULT_DATASET_NAME)
        self.assertEqual(request.random_seed, DEFAULT_RANDOM_SEED)

    def test_the_steps_run_on_the_queue_the_agent_subscribes_to(self) -> None:
        self.assertEqual(parse_arguments(ARGUMENTS).queue, DEFAULT_TRAINING_QUEUE)

    def test_another_queue_can_be_named(self) -> None:
        request = parse_arguments([*ARGUMENTS, "--queue", "gpu-training"])

        self.assertEqual(request.queue, "gpu-training")

    def test_a_split_that_does_not_sum_to_one_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            parse_arguments([*ARGUMENTS, "--train-ratio", "0.9"])

    def test_the_forest_can_be_varied_per_run(self) -> None:
        request = parse_arguments([*ARGUMENTS, "--n-estimators", "42", "--max-depth", "5"])

        self.assertEqual(request.estimator.forest.n_estimators, 42)
        self.assertEqual(request.estimator.forest.max_depth, 5)


class PipelineExitCodeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = mock.MagicMock(name="controller")
        self.controller.task.get_status.return_value = "completed"
        self.controller.get_processed_nodes.return_value = [step.value for step in StepName]
        self.templates = {step: f"{step.value}-task" for step in StepName}

        for name, replacement in (
            ("connect_to_server", mock.MagicMock(name="connect_to_server")),
            ("run_pipeline", mock.MagicMock(name="run_pipeline", return_value=self.controller)),
            (
                "ensure_templates",
                mock.MagicMock(name="ensure_templates", return_value=self.templates),
            ),
        ):
            patcher = mock.patch.object(cli, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_a_completed_run_reports_success_and_the_steps_that_ran(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = main(ARGUMENTS)

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("completed", stdout.getvalue())
        self.assertIn("register-candidate", stdout.getvalue())

    def test_a_run_that_stopped_early_is_not_reported_as_success(self) -> None:
        self.controller.task.get_status.return_value = "failed"
        self.controller.get_processed_nodes.return_value = ["validate"]

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = main(ARGUMENTS)

        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("Steps that ran: validate", stdout.getvalue())

    def test_an_unsatisfiable_request_is_reported_as_a_usage_error(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = main([*ARGUMENTS, "--queue", " "])

        self.assertEqual(code, EXIT_INVALID_USAGE)
        self.assertIn("queue", stderr.getvalue())

    def test_a_failure_while_running_is_reported_as_a_failure(self) -> None:
        cli.run_pipeline.side_effect = PipelineError("the queue does not exist")  # type: ignore[attr-defined]

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = main(ARGUMENTS)

        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("the queue does not exist", stderr.getvalue())

    def test_the_templates_can_be_created_without_running_them(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = main([*ARGUMENTS, "--templates-only"])

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("validate-task", stdout.getvalue())
        cli.run_pipeline.assert_not_called()  # type: ignore[attr-defined]

    def test_a_forwarded_separator_still_starts_the_run(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["--", *ARGUMENTS])

        self.assertEqual(code, EXIT_SUCCESS)


if __name__ == "__main__":
    unittest.main()

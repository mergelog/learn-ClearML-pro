from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

from ml.model_lifecycle import cli
from ml.model_lifecycle.cli import EXIT_INVALID_USAGE, EXIT_SUCCESS, main
from ml.model_lifecycle.domain import (
    LifecycleError,
    ModelIdentity,
    ModelStage,
    PromotionRecord,
)
from ml.model_lifecycle.registry import RegisteredModel


def build_model(model_id: str, stage: ModelStage) -> RegisteredModel:
    return RegisteredModel(
        identity=ModelIdentity(
            model_id=model_id,
            model_version=f"1.0.0-20260908T043015Z-{model_id}",
            stage=stage,
            dataset_id="dataset-id",
            dataset_version="1.0.0",
            train_task_id="train-task",
        ),
        tags=(stage.tag,),
        metadata={"promoted_by": "reviewer", "promotion_reason": "the trial went well"},
    )


def build_record() -> PromotionRecord:
    return PromotionRecord(
        model_id="model-a",
        model_version="1.0.0-20260908T043015Z-model-a",
        previous_stage=ModelStage.STAGING,
        stage=ModelStage.PRODUCTION,
        approved_by="reviewer",
        reason="the trial went well",
        promoted_at="2026-09-08T04:30:15Z",
        demoted=("model-old",),
    )


class LifecycleCommandTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = mock.MagicMock(name="registry")
        self.registry.in_stage.return_value = ()
        self.registry.promote.return_value = build_record()
        self.registry.rollback.return_value = build_record()
        self.registry.find.return_value = build_model("model-a", ModelStage.PRODUCTION)

        for name, replacement in (
            ("connected_settings", mock.MagicMock(name="connected_settings")),
            ("ModelRegistry", mock.MagicMock(name="ModelRegistry", return_value=self.registry)),
        ):
            patcher = mock.patch.object(cli, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_command(self, argv: list[str]) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()


class StatusCommandTest(LifecycleCommandTestCase):
    def test_a_registry_with_nothing_in_it_says_so_per_stage(self) -> None:
        code, printed, _ = self.run_command(["status"])

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("production: none", printed)
        self.assertIn("candidate: none", printed)

    def test_the_model_that_serves_is_named_with_its_version(self) -> None:
        self.registry.in_stage.side_effect = lambda stage: (
            (build_model("model-a", stage),) if stage is ModelStage.PRODUCTION else ()
        )

        _, printed, _ = self.run_command(["status"])

        self.assertIn("1.0.0-20260908T043015Z-model-a", printed)
        self.assertIn("model-a", printed)


class PromoteCommandTest(LifecycleCommandTestCase):
    def test_a_move_carries_who_decided_it_and_why(self) -> None:
        code, printed, _ = self.run_command(
            [
                "promote",
                "--model-id",
                "model-a",
                "--to",
                "production",
                "--approved-by",
                "reviewer",
                "--reason",
                "the trial went well",
            ]
        )

        self.assertEqual(code, EXIT_SUCCESS)
        request = self.registry.promote.call_args.args[0]
        self.assertEqual(request.model_id, "model-a")
        self.assertEqual(request.target, ModelStage.PRODUCTION)
        self.assertEqual(request.approved_by, "reviewer")
        self.assertIn("reviewer", printed)

    def test_the_model_that_stepped_aside_is_reported(self) -> None:
        _, printed, _ = self.run_command(
            [
                "promote",
                "--model-id",
                "model-a",
                "--to",
                "production",
                "--approved-by",
                "reviewer",
                "--reason",
                "the trial went well",
            ]
        )

        self.assertIn("archived: model-old", printed)

    def test_a_move_without_an_approver_is_rejected_by_the_parser(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["promote", "--model-id", "model-a", "--to", "production"])

    def test_a_move_the_lifecycle_refuses_is_reported_as_a_usage_error(self) -> None:
        self.registry.promote.side_effect = LifecycleError(
            "a candidate model cannot become production"
        )

        code, _, errors = self.run_command(
            [
                "promote",
                "--model-id",
                "model-a",
                "--to",
                "production",
                "--approved-by",
                "reviewer",
                "--reason",
                "skipping the trial",
            ]
        )

        self.assertEqual(code, EXIT_INVALID_USAGE)
        self.assertIn("cannot become production", errors)

    def test_candidate_is_not_a_stage_a_person_can_promote_into(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(
                [
                    "promote",
                    "--model-id",
                    "model-a",
                    "--to",
                    "candidate",
                    "--approved-by",
                    "reviewer",
                    "--reason",
                    "why not",
                ]
            )


class RollbackCommandTest(LifecycleCommandTestCase):
    def test_a_rollback_still_records_who_decided_it(self) -> None:
        code, printed, _ = self.run_command(
            ["rollback", "--approved-by", "responder", "--reason", "latency regression"]
        )

        self.assertEqual(code, EXIT_SUCCESS)
        self.registry.rollback.assert_called_once_with("responder", "latency regression")
        self.assertIn("reviewer", printed)

    def test_a_rollback_with_nothing_to_go_back_to_is_a_usage_error(self) -> None:
        self.registry.rollback.side_effect = LifecycleError("no archived model is available")

        code, _, errors = self.run_command(
            ["rollback", "--approved-by", "responder", "--reason", "latency regression"]
        )

        self.assertEqual(code, EXIT_INVALID_USAGE)
        self.assertIn("no archived model", errors)


class ShowCommandTest(LifecycleCommandTestCase):
    def test_everything_recorded_about_a_model_is_printed(self) -> None:
        code, printed, _ = self.run_command(["show", "--model-id", "model-a"])

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("stage: production", printed)
        self.assertIn("dataset: 1.0.0 (dataset-id)", printed)
        self.assertIn("trained by task: train-task", printed)
        self.assertIn("promoted_by: reviewer", printed)

    def test_a_forwarded_separator_still_runs_the_command(self) -> None:
        code, _, _ = self.run_command(["--", "show", "--model-id", "model-a"])

        self.assertEqual(code, EXIT_SUCCESS)


if __name__ == "__main__":
    unittest.main()

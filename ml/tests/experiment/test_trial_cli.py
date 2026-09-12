from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from ml.experiment import trial_cli
from ml.experiment.domain import (
    OBJECTIVE_TITLE,
    TRIAL_RESULT_ARTIFACT,
    FoldScore,
    Objective,
    TrialPlan,
    TrialResult,
)
from ml.experiment.parameters import search_parameters
from ml.experiment.trial_cli import (
    EXIT_FAILURE,
    EXIT_INVALID_USAGE,
    EXIT_SUCCESS,
    THRESHOLD_TITLE,
    TrialTask,
    main,
    run_trial,
)
from ml.experiment.trials import cross_validate
from ml.pipeline.domain import DATASET_SECTION, MODEL_SECTION, PipelineError
from ml.semiconductor_quality.config import (
    DEFAULT_RANDOM_SEED,
    EstimatorConfig,
    RandomForestConfig,
)
from ml.semiconductor_quality.domain import TrainingInput
from ml.tests.experiment.test_trials import build_part


def build_result(threshold: float | None = 0.4) -> TrialResult:
    return TrialResult(
        objective_metric="f1",
        objective=0.5,
        folds=(FoldScore(fold=1, metrics={"f1": 0.5}, threshold=threshold, rows=10),),
        threshold=threshold,
    )


class FakeTask:
    """A ClearML Task, as much of one as a trial touches."""

    def __init__(self, parameters: dict[str, str]) -> None:
        self.id = "trial-task"
        self._parameters = parameters
        self.logger = mock.MagicMock(name="Logger")
        self.artifacts: dict[str, object] = {}

    def get_parameters(self) -> dict[str, str]:
        return self._parameters

    def get_logger(self) -> mock.MagicMock:
        return self.logger

    def upload_artifact(self, name: str, artifact_object: object, **_: object) -> None:
        self.artifacts[name] = artifact_object


class TrialTaskTest(unittest.TestCase):
    def setUp(self) -> None:
        self.task = FakeTask({f"{MODEL_SECTION}/n_estimators": " 300 "})
        self.trial = TrialTask(self.task)  # type: ignore[arg-type]

    def test_the_parameters_are_read_as_the_text_a_task_carries(self) -> None:
        self.assertEqual(self.trial.parameters[f"{MODEL_SECTION}/n_estimators"], " 300 ")

    def test_progress_is_reported_after_every_fold(self) -> None:
        folds = [
            FoldScore(fold=1, metrics={"f1": 0.4}, threshold=None, rows=10),
            FoldScore(fold=2, metrics={"f1": 0.6}, threshold=None, rows=10),
        ]

        self.trial.report_progress(Objective(), folds)

        reported = self.task.logger.report_scalar.call_args.kwargs
        self.assertEqual(reported["title"], OBJECTIVE_TITLE)
        self.assertEqual(reported["series"], "f1")
        self.assertAlmostEqual(reported["value"], 0.5)
        # 反復はfoldの数である。1 foldで測った候補と5 foldで測った候補を
        # 探索が取り違えないための唯一の手掛かりになる。
        self.assertEqual(reported["iteration"], 2)

    def test_the_chosen_cut_is_reported_where_a_person_can_see_it(self) -> None:
        self.trial.report_threshold(build_result(threshold=0.42))

        self.assertEqual(self.task.logger.report_scalar.call_args.kwargs["title"], THRESHOLD_TITLE)

    def test_a_trial_that_did_not_move_the_cut_reports_no_cut(self) -> None:
        self.trial.report_threshold(build_result(threshold=None))

        self.task.logger.report_scalar.assert_not_called()

    def test_the_result_is_uploaded_as_the_document_it_is(self) -> None:
        self.trial.upload_result(build_result())

        self.assertEqual(
            self.task.artifacts[TRIAL_RESULT_ARTIFACT]["objective_metric"],  # type: ignore[index]
            "f1",
        )


class RunTrialTest(unittest.TestCase):
    """One trial, with the Dataset replaced by rows this test already holds."""

    def setUp(self) -> None:
        self.part = build_part()
        parameters = {
            f"{DATASET_SECTION}/dataset_version": "2.0.0",
            f"{MODEL_SECTION}/n_estimators": "20",
            **search_parameters(TrialPlan(folds=3, threshold_folds=2), Objective()),
        }
        self.task = FakeTask(parameters)
        self.trial = TrialTask(self.task)  # type: ignore[arg-type]

        split = mock.MagicMock(name="DataSplit")
        split.train = self.part
        for name, replacement in (
            ("fetch_dataset", mock.MagicMock(name="fetch_dataset")),
            ("load_training_input", mock.MagicMock(spec=TrainingInput)),
            ("split_training_input", mock.MagicMock(return_value=split)),
        ):
            patcher = mock.patch.object(trial_cli, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_a_trial_measures_the_candidate_and_records_what_it_found(self) -> None:
        result = run_trial(self.trial)

        self.assertEqual(len(result.folds), 3)
        self.assertIn(TRIAL_RESULT_ARTIFACT, self.task.artifacts)

    def test_a_trial_reports_after_every_fold_rather_than_once_at_the_end(self) -> None:
        run_trial(self.trial)

        objective_reports = [
            call.kwargs
            for call in self.task.logger.report_scalar.call_args_list
            if call.kwargs["title"] == OBJECTIVE_TITLE
        ]
        self.assertEqual([report["iteration"] for report in objective_reports], [1, 2, 3])

    def test_the_last_report_is_the_score_the_search_decides_on(self) -> None:
        result = run_trial(self.trial)

        last = [
            call.kwargs
            for call in self.task.logger.report_scalar.call_args_list
            if call.kwargs["title"] == OBJECTIVE_TITLE
        ][-1]
        self.assertAlmostEqual(last["value"], result.objective)

    def test_a_trial_measures_exactly_what_the_same_settings_measure_offline(self) -> None:
        result = run_trial(self.trial)

        offline = cross_validate(
            self.part,
            EstimatorConfig(forest=RandomForestConfig(n_estimators=20)),
            TrialPlan(folds=3, threshold_folds=2),
            Objective(),
            DEFAULT_RANDOM_SEED,
        )
        self.assertAlmostEqual(result.objective, offline.objective)


class ExitCodeTest(unittest.TestCase):
    def carry_out(self, error: Exception | None) -> tuple[int, str]:
        task = mock.MagicMock(spec=TrialTask)
        task.id = "trial-task"
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(trial_cli, "start_trial_task", return_value=task):
            with mock.patch.object(trial_cli, "run_trial") as run:
                run.side_effect = error
                run.return_value = build_result()
                with redirect_stdout(output), redirect_stderr(errors):
                    code = main([])
        return code, output.getvalue() + errors.getvalue()

    def test_a_trial_that_measured_its_candidate_succeeds(self) -> None:
        code, printed = self.carry_out(None)

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("trial-task", printed)

    def test_a_task_that_says_something_impossible_is_a_usage_error(self) -> None:
        code, printed = self.carry_out(PipelineError("Model/n_estimators must be a whole number"))

        self.assertEqual(code, EXIT_INVALID_USAGE)
        self.assertIn("n_estimators", printed)

    def test_anything_else_is_reported_rather_than_swallowed(self) -> None:
        code, printed = self.carry_out(RuntimeError("the file server is unreachable"))

        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("unreachable", printed)

from __future__ import annotations

import unittest

from ml.experiment.domain import (
    OBJECTIVE_METRIC_PARAMETER,
    SEARCH_SECTION,
    TUNE_THRESHOLD_PARAMETER,
    ExperimentError,
    Objective,
    TrialPlan,
)
from ml.experiment.parameters import (
    read_objective,
    read_trial_plan,
    search_parameters,
    threshold_parameter,
)
from ml.pipeline.domain import MODEL_SECTION, PipelineError


class SearchParameterTest(unittest.TestCase):
    def test_what_is_written_is_what_is_read_back(self) -> None:
        plan = TrialPlan(folds=4, tune_threshold=False, threshold_folds=2)
        objective = Objective(metric="recall")

        written = search_parameters(plan, objective)

        self.assertEqual(read_trial_plan(written), plan)
        self.assertEqual(read_objective(written).metric, "recall")

    def test_a_trial_told_nothing_judges_the_way_the_project_judges(self) -> None:
        self.assertEqual(read_trial_plan({}), TrialPlan())
        self.assertEqual(read_objective({}), Objective())

    def test_a_measure_the_evaluation_does_not_report_is_refused(self) -> None:
        with self.assertRaises(ExperimentError) as raised:
            read_objective({f"{SEARCH_SECTION}/{OBJECTIVE_METRIC_PARAMETER}": "profit"})

        self.assertIn("profit", str(raised.exception))

    def test_a_setting_that_is_neither_on_nor_off_is_refused(self) -> None:
        with self.assertRaises(PipelineError) as raised:
            read_trial_plan({f"{SEARCH_SECTION}/{TUNE_THRESHOLD_PARAMETER}": "maybe"})

        self.assertIn(TUNE_THRESHOLD_PARAMETER, str(raised.exception))

    def test_the_spellings_a_person_would_write_are_all_understood(self) -> None:
        for value, expected in (("true", True), ("yes", True), ("1", True), ("false", False)):
            with self.subTest(value=value):
                plan = read_trial_plan({f"{SEARCH_SECTION}/{TUNE_THRESHOLD_PARAMETER}": value})

                self.assertEqual(plan.tune_threshold, expected)


class HandoffParameterTest(unittest.TestCase):
    def test_the_chosen_cut_is_handed_over_where_the_training_run_reads_it(self) -> None:
        written = threshold_parameter(0.42)

        self.assertEqual(written[f"{MODEL_SECTION}/decision_threshold"], "0.42")

    def test_no_cut_is_handed_over_as_the_absence_a_task_spells(self) -> None:
        self.assertEqual(threshold_parameter(None)[f"{MODEL_SECTION}/decision_threshold"], "")

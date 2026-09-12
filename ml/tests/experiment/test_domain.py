from __future__ import annotations

import unittest

from ml.experiment.domain import (
    Budget,
    ChoiceRange,
    Direction,
    Environment,
    ExecutionPlacement,
    ExperimentPlan,
    FoldScore,
    IntegerRange,
    NumberRange,
    Objective,
    SearchSpace,
    TrialPlan,
    TrialResult,
)
from ml.semiconductor_quality.config import (
    Algorithm,
    ConfigurationError,
    EstimatorConfig,
)


def build_space(**overrides: object) -> SearchSpace:
    defaults: dict[str, object] = {
        "ranges": (IntegerRange(name="n_estimators", minimum=100, maximum=600, step=50),),
    }
    defaults.update(overrides)
    return SearchSpace(**defaults)  # type: ignore[arg-type]


def build_plan(**overrides: object) -> ExperimentPlan:
    defaults: dict[str, object] = {
        "environment": Environment.DEVELOPMENT,
        "space": build_space(),
        "placement": ExecutionPlacement(trial_queue="trials", optimizer_queue="searches"),
    }
    defaults.update(overrides)
    return ExperimentPlan(**defaults)  # type: ignore[arg-type]


class ObjectiveTest(unittest.TestCase):
    def test_a_measure_the_evaluation_does_not_report_is_refused(self) -> None:
        with self.assertRaises(ConfigurationError) as raised:
            Objective(metric="profit").validate()

        self.assertIn("profit", str(raised.exception))

    def test_the_direction_is_translated_for_the_optimizer(self) -> None:
        self.assertEqual(Direction.MAXIMISE.clearml_sign, "max")
        self.assertEqual(Direction.MINIMISE.clearml_sign, "min")

    def test_the_objective_says_which_split_it_is_measured_on(self) -> None:
        self.assertIn("train", Objective().describe())


class ParameterRangeTest(unittest.TestCase):
    def test_a_range_that_does_not_go_upwards_is_refused(self) -> None:
        with self.assertRaises(ConfigurationError):
            IntegerRange(name="min_samples_leaf", minimum=20, maximum=20).validate()

    def test_a_logarithmic_range_cannot_start_at_zero(self) -> None:
        with self.assertRaises(ConfigurationError) as raised:
            NumberRange(
                name="learning_rate",
                minimum=0.0,
                maximum=0.3,
                logarithmic=True,
            ).validate()

        self.assertIn("logarithmically", str(raised.exception))

    def test_a_choice_of_one_value_is_not_a_choice(self) -> None:
        with self.assertRaises(ConfigurationError):
            ChoiceRange(name="class_weight", values=("balanced",)).validate()

    def test_the_same_choice_twice_is_refused(self) -> None:
        with self.assertRaises(ConfigurationError):
            ChoiceRange(name="class_weight", values=("none", "none")).validate()

    def test_an_empty_choice_reads_as_unset_rather_than_as_nothing(self) -> None:
        described = ChoiceRange(name="max_depth", values=("", "8")).describe()

        self.assertIn("(unset)", described)


class SearchSpaceTest(unittest.TestCase):
    def test_a_setting_the_algorithm_does_not_read_is_refused(self) -> None:
        with self.assertRaises(ConfigurationError) as raised:
            build_space(
                ranges=(NumberRange(name="learning_rate", minimum=0.1, maximum=0.3),),
            ).validate()

        self.assertIn("learning_rate", str(raised.exception))

    def test_a_setting_of_another_algorithm_is_allowed_once_that_one_is_chosen(self) -> None:
        space = build_space(
            algorithm=Algorithm.HIST_GRADIENT_BOOSTING,
            ranges=(NumberRange(name="learning_rate", minimum=0.01, maximum=0.3),),
        )

        self.assertEqual(space.validate().algorithm, Algorithm.HIST_GRADIENT_BOOSTING)

    def test_a_search_that_varies_nothing_is_refused(self) -> None:
        with self.assertRaises(ConfigurationError):
            build_space(ranges=()).validate()

    def test_varying_the_same_setting_twice_is_refused(self) -> None:
        with self.assertRaises(ConfigurationError) as raised:
            build_space(
                ranges=(
                    IntegerRange(name="min_samples_leaf", minimum=1, maximum=5),
                    IntegerRange(name="min_samples_leaf", minimum=6, maximum=9),
                ),
            ).validate()

        self.assertIn("more than once", str(raised.exception))

    def test_the_imbalance_policy_may_be_searched_for_every_algorithm(self) -> None:
        for algorithm in Algorithm:
            with self.subTest(algorithm=algorithm):
                space = build_space(
                    algorithm=algorithm,
                    ranges=(ChoiceRange(name="class_weight", values=("none", "balanced")),),
                )

                self.assertEqual(space.validate().ranges[0].name, "class_weight")


class BudgetTest(unittest.TestCase):
    def test_every_limit_has_to_be_a_limit(self) -> None:
        for field, value in (
            ("max_trials", 0),
            ("parallel_trials", 0),
            ("trial_minutes", 0.0),
            ("total_minutes", -1.0),
            ("keep_top", 0),
            ("minimum_folds", 0),
        ):
            with self.subTest(field=field), self.assertRaises(ConfigurationError):
                Budget(**{field: value}).validate()  # type: ignore[arg-type]

    def test_the_budget_says_what_it_allows_in_one_line(self) -> None:
        described = Budget(max_trials=6, parallel_trials=2).describe()

        self.assertIn("6 trials", described)
        self.assertIn("2 at a time", described)


class TrialPlanTest(unittest.TestCase):
    def test_a_single_fold_is_not_cross_validation(self) -> None:
        with self.assertRaises(ConfigurationError):
            TrialPlan(folds=1).validate()

    def test_the_inner_folds_only_matter_when_the_cut_may_move(self) -> None:
        self.assertEqual(TrialPlan(tune_threshold=False, threshold_folds=1).validate().folds, 5)

    def test_a_moving_cut_needs_something_to_choose_it_on(self) -> None:
        with self.assertRaises(ConfigurationError):
            TrialPlan(tune_threshold=True, threshold_folds=1).validate()


class ExperimentPlanTest(unittest.TestCase):
    def test_a_complete_plan_is_accepted(self) -> None:
        self.assertEqual(build_plan().validate().environment, Environment.DEVELOPMENT)

    def test_a_search_without_a_queue_to_run_on_is_refused(self) -> None:
        with self.assertRaises(ConfigurationError) as raised:
            build_plan(placement=ExecutionPlacement(trial_queue="", optimizer_queue="")).validate()

        self.assertIn("trial_queue", str(raised.exception))

    def test_settings_for_another_algorithm_than_the_one_searched_are_refused(self) -> None:
        with self.assertRaises(ConfigurationError) as raised:
            build_plan(
                estimator=EstimatorConfig(algorithm=Algorithm.LOGISTIC_REGRESSION),
            ).validate()

        self.assertIn("starts from", str(raised.exception))

    def test_the_recorded_plan_carries_the_space_the_objective_and_the_budget(self) -> None:
        document = build_plan().as_document()

        self.assertEqual(document["environment"], "dev")
        self.assertIn("search_space", document)
        self.assertIn("budget", document)
        self.assertEqual(
            document["objective"],
            {"metric": "f1", "direction": "maximise", "split": "train"},
        )

    def test_the_recorded_plan_names_the_split_the_search_may_use(self) -> None:
        objective = build_plan().as_document()["objective"]

        self.assertEqual(objective["split"], "train")  # type: ignore[index]


class TrialResultTest(unittest.TestCase):
    def test_the_folds_behind_the_mean_are_kept(self) -> None:
        result = TrialResult(
            objective_metric="f1",
            objective=0.5,
            folds=(
                FoldScore(fold=1, metrics={"f1": 0.4}, threshold=0.3, rows=10),
                FoldScore(fold=2, metrics={"f1": 0.6}, threshold=0.4, rows=10),
            ),
            threshold=0.35,
        )

        self.assertEqual(result.fold_objectives, (0.4, 0.6))
        self.assertEqual(len(result.as_document()["folds"]), 2)  # type: ignore[arg-type]
        self.assertEqual(result.as_document()["decision_threshold"], 0.35)

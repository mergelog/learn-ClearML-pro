from __future__ import annotations

import unittest

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import FixedThresholdClassifier

from ml.semiconductor_quality.algorithms import build_classifier
from ml.semiconductor_quality.config import (
    Algorithm,
    ClassWeight,
    ConfigurationError,
    EstimatorConfig,
    HistGradientBoostingConfig,
    LogisticRegressionConfig,
    RandomForestConfig,
)
from ml.semiconductor_quality.domain import POSITIVE_LABEL


SEED = 20260906


class AlgorithmTest(unittest.TestCase):
    def test_the_offered_algorithms_learn_differently(self) -> None:
        self.assertEqual(
            [algorithm.value for algorithm in Algorithm],
            ["logistic-regression", "random-forest", "hist-gradient-boosting"],
        )

    def test_an_algorithm_reads_as_its_own_name(self) -> None:
        self.assertEqual(f"{Algorithm.RANDOM_FOREST}", "random-forest")

    def test_the_project_keeps_the_model_it_started_with_as_the_default(self) -> None:
        self.assertEqual(EstimatorConfig().algorithm, Algorithm.RANDOM_FOREST)


class ActiveSettingsTest(unittest.TestCase):
    def test_every_algorithm_names_the_settings_it_reads(self) -> None:
        for algorithm in Algorithm:
            with self.subTest(algorithm=algorithm):
                self.assertIsNotNone(EstimatorConfig(algorithm=algorithm).active)

    def test_the_forest_reads_the_forest_settings(self) -> None:
        estimator = EstimatorConfig(algorithm=Algorithm.RANDOM_FOREST)

        self.assertIs(estimator.active, estimator.forest)

    def test_the_baseline_reads_the_baseline_settings(self) -> None:
        estimator = EstimatorConfig(algorithm=Algorithm.LOGISTIC_REGRESSION)

        self.assertIs(estimator.active, estimator.logistic)

    def test_the_boosting_model_reads_the_boosting_settings(self) -> None:
        estimator = EstimatorConfig(algorithm=Algorithm.HIST_GRADIENT_BOOSTING)

        self.assertIs(estimator.active, estimator.boosting)


class EstimatorValidationTest(unittest.TestCase):
    def test_only_the_settings_of_the_chosen_algorithm_are_judged(self) -> None:
        estimator = EstimatorConfig(
            algorithm=Algorithm.LOGISTIC_REGRESSION,
            forest=RandomForestConfig(n_estimators=0),
        )

        self.assertEqual(estimator.collect_errors(), ())

    def test_a_broken_setting_of_the_chosen_algorithm_is_refused(self) -> None:
        estimator = EstimatorConfig(
            algorithm=Algorithm.LOGISTIC_REGRESSION,
            logistic=LogisticRegressionConfig(regularisation=0),
        )

        with self.assertRaises(ConfigurationError) as raised:
            estimator.validate()

        self.assertIn("regularisation", str(raised.exception))

    def test_a_learning_rate_that_is_not_positive_is_refused(self) -> None:
        estimator = EstimatorConfig(
            algorithm=Algorithm.HIST_GRADIENT_BOOSTING,
            boosting=HistGradientBoostingConfig(learning_rate=-0.1),
        )

        with self.assertRaises(ConfigurationError):
            estimator.validate()

    def test_an_algorithm_this_project_does_not_offer_is_refused(self) -> None:
        estimator = EstimatorConfig(algorithm="deep-learning")  # type: ignore[arg-type]

        with self.assertRaises(ConfigurationError) as raised:
            estimator.validate()

        self.assertIn("deep-learning", str(raised.exception))


class ClassifierBuildTest(unittest.TestCase):
    def test_each_algorithm_builds_its_own_estimator(self) -> None:
        expected = {
            Algorithm.LOGISTIC_REGRESSION: LogisticRegression,
            Algorithm.RANDOM_FOREST: RandomForestClassifier,
            Algorithm.HIST_GRADIENT_BOOSTING: HistGradientBoostingClassifier,
        }

        for algorithm, kind in expected.items():
            with self.subTest(algorithm=algorithm):
                built = build_classifier(EstimatorConfig(algorithm=algorithm), SEED)

                self.assertIsInstance(built, kind)

    def test_every_algorithm_shares_the_seed_of_the_run(self) -> None:
        for algorithm in Algorithm:
            with self.subTest(algorithm=algorithm):
                built = build_classifier(EstimatorConfig(algorithm=algorithm), SEED)

                self.assertEqual(built.random_state, SEED)

    def test_the_baseline_is_built_from_its_own_settings(self) -> None:
        estimator = EstimatorConfig(
            algorithm=Algorithm.LOGISTIC_REGRESSION,
            logistic=LogisticRegressionConfig(regularisation=0.25, max_iterations=250),
        )

        built = build_classifier(estimator, SEED)

        self.assertEqual(built.C, 0.25)
        self.assertEqual(built.max_iter, 250)

    def test_the_boosting_model_is_built_from_its_own_settings(self) -> None:
        estimator = EstimatorConfig(
            algorithm=Algorithm.HIST_GRADIENT_BOOSTING,
            boosting=HistGradientBoostingConfig(learning_rate=0.05, max_iterations=300),
        )

        built = build_classifier(estimator, SEED)

        self.assertEqual(built.learning_rate, 0.05)
        self.assertEqual(built.max_iter, 300)

    def test_the_settings_of_another_algorithm_do_not_reach_the_estimator(self) -> None:
        estimator = EstimatorConfig(
            algorithm=Algorithm.LOGISTIC_REGRESSION,
            forest=RandomForestConfig(n_estimators=9_999),
        )

        built = build_classifier(estimator, SEED)

        self.assertFalse(hasattr(built, "n_estimators"))


class ImbalanceTest(unittest.TestCase):
    def test_the_rare_label_is_left_alone_unless_a_run_says_otherwise(self) -> None:
        for algorithm in Algorithm:
            with self.subTest(algorithm=algorithm):
                built = build_classifier(EstimatorConfig(algorithm=algorithm), SEED)

                self.assertIsNone(built.class_weight)

    def test_every_algorithm_weighs_the_rare_label_the_same_way(self) -> None:
        for algorithm in Algorithm:
            with self.subTest(algorithm=algorithm):
                estimator = EstimatorConfig(
                    algorithm=algorithm,
                    class_weight=ClassWeight.BALANCED,
                )

                built = build_classifier(estimator, SEED)

                self.assertEqual(built.class_weight, "balanced")


class ReproducibilityTest(unittest.TestCase):
    def test_the_forest_grows_in_one_flow_so_two_runs_predict_the_same(self) -> None:
        first = build_classifier(EstimatorConfig(), SEED)

        self.assertEqual(first.n_jobs, 1)

    def test_the_same_seed_and_rows_give_the_same_probabilities(self) -> None:
        generator = np.random.default_rng(4)
        features = generator.normal(size=(200, 5))
        targets = np.where(features[:, 0] > 0.3, "fail", "pass")

        probabilities = {
            build_classifier(EstimatorConfig(forest=RandomForestConfig(n_estimators=25)), SEED)
            .fit(features, targets)
            .predict_proba(features)
            .tobytes()
            for _ in range(4)
        }

        self.assertEqual(len(probabilities), 1)


class DecisionThresholdTest(unittest.TestCase):
    def test_a_run_that_names_no_cut_keeps_the_estimator_itself(self) -> None:
        built = build_classifier(EstimatorConfig(), SEED)

        self.assertNotIsInstance(built, FixedThresholdClassifier)

    def test_the_cut_is_part_of_the_model_rather_than_of_the_caller(self) -> None:
        built = build_classifier(EstimatorConfig(decision_threshold=0.3), SEED)

        self.assertIsInstance(built, FixedThresholdClassifier)
        self.assertEqual(built.threshold, 0.3)

    def test_the_cut_is_read_against_the_label_worth_finding(self) -> None:
        built = build_classifier(EstimatorConfig(decision_threshold=0.3), SEED)

        self.assertEqual(built.pos_label, POSITIVE_LABEL)

    def test_the_settings_of_the_algorithm_survive_the_cut(self) -> None:
        estimator = EstimatorConfig(
            forest=RandomForestConfig(n_estimators=42),
            decision_threshold=0.4,
        )

        built = build_classifier(estimator, SEED)

        self.assertEqual(built.estimator.n_estimators, 42)


if __name__ == "__main__":
    unittest.main()

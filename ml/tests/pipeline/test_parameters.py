from __future__ import annotations

import unittest

from ml.pipeline.domain import (
    DATASET_SECTION,
    EXECUTION_SECTION,
    MODEL_SECTION,
    SPLIT_SECTION,
    PipelineError,
)
from ml.pipeline.parameters import (
    RANDOM_SEED_PARAMETER,
    dataset_parameters,
    estimator_parameters,
    read_dataset,
    read_estimator,
    read_random_seed,
    read_split,
    seed_parameters,
    split_parameters,
)
from ml.semiconductor_quality.config import (
    DEFAULT_DATASET_NAME,
    DEFAULT_DATASET_PROJECT,
    Algorithm,
    ClassWeight,
    DatasetConfig,
    EstimatorConfig,
    RandomForestConfig,
    SplitConfig,
)


DATASET_PARAMETERS = {f"{DATASET_SECTION}/dataset_version": "1.0.0"}


class DatasetParameterTest(unittest.TestCase):
    def test_the_dataset_version_is_read_from_the_task(self) -> None:
        config = read_dataset(DATASET_PARAMETERS)

        self.assertEqual(config.dataset_version, "1.0.0")

    def test_the_remaining_values_fall_back_to_the_execution_contract(self) -> None:
        config = read_dataset(DATASET_PARAMETERS)

        self.assertEqual(config.dataset_project, DEFAULT_DATASET_PROJECT)
        self.assertEqual(config.dataset_name, DEFAULT_DATASET_NAME)

    def test_a_step_without_a_dataset_version_is_refused(self) -> None:
        with self.assertRaises(PipelineError) as raised:
            read_dataset({})

        self.assertIn(f"{DATASET_SECTION}/dataset_version", str(raised.exception))

    def test_a_value_cleared_in_the_web_ui_counts_as_missing(self) -> None:
        with self.assertRaises(PipelineError):
            read_dataset({f"{DATASET_SECTION}/dataset_version": "   "})

    def test_surrounding_space_is_not_part_of_the_value(self) -> None:
        config = read_dataset({f"{DATASET_SECTION}/dataset_version": " 2.0.0 "})

        self.assertEqual(config.dataset_version, "2.0.0")


class SplitParameterTest(unittest.TestCase):
    def test_the_ratios_are_read_as_numbers(self) -> None:
        config = read_split(
            {
                f"{SPLIT_SECTION}/train_ratio": "0.7",
                f"{SPLIT_SECTION}/validation_ratio": "0.2",
                f"{SPLIT_SECTION}/test_ratio": "0.1",
            }
        )

        self.assertEqual(config, SplitConfig(0.7, 0.2, 0.1))

    def test_ratios_that_were_not_given_keep_the_contract_defaults(self) -> None:
        self.assertEqual(read_split({}), SplitConfig())

    def test_a_ratio_that_is_not_a_number_is_refused_by_name(self) -> None:
        with self.assertRaises(PipelineError) as raised:
            read_split({f"{SPLIT_SECTION}/train_ratio": "most of it"})

        self.assertIn(f"{SPLIT_SECTION}/train_ratio", str(raised.exception))

    def test_ratios_that_do_not_sum_to_one_are_refused_by_the_contract(self) -> None:
        config = read_split(
            {
                f"{SPLIT_SECTION}/train_ratio": "0.7",
                f"{SPLIT_SECTION}/validation_ratio": "0.7",
                f"{SPLIT_SECTION}/test_ratio": "0.7",
            }
        )

        self.assertTrue(config.collect_errors())


class EstimatorParameterTest(unittest.TestCase):
    def test_the_algorithm_defaults_to_the_one_the_project_started_with(self) -> None:
        self.assertEqual(read_estimator({}).algorithm, Algorithm.RANDOM_FOREST)

    def test_another_algorithm_can_be_named(self) -> None:
        config = read_estimator({f"{MODEL_SECTION}/algorithm": "logistic-regression"})

        self.assertEqual(config.algorithm, Algorithm.LOGISTIC_REGRESSION)

    def test_an_algorithm_this_pipeline_does_not_offer_is_refused(self) -> None:
        with self.assertRaises(PipelineError) as raised:
            read_estimator({f"{MODEL_SECTION}/algorithm": "deep-learning"})

        self.assertIn("deep-learning", str(raised.exception))

    def test_the_forest_is_read_as_whole_numbers(self) -> None:
        config = read_estimator(
            {
                f"{MODEL_SECTION}/n_estimators": "150",
                f"{MODEL_SECTION}/max_depth": "8",
                f"{MODEL_SECTION}/min_samples_leaf": "2",
            }
        )

        self.assertEqual(
            config.forest,
            RandomForestConfig(n_estimators=150, max_depth=8, min_samples_leaf=2),
        )

    def test_an_empty_depth_means_the_trees_grow_without_a_limit(self) -> None:
        config = read_estimator({f"{MODEL_SECTION}/max_depth": ""})

        self.assertIsNone(config.forest.max_depth)

    def test_a_depth_written_as_none_also_means_no_limit(self) -> None:
        config = read_estimator({f"{MODEL_SECTION}/max_depth": "None"})

        self.assertIsNone(config.forest.max_depth)

    def test_a_forest_size_that_is_not_a_whole_number_is_refused(self) -> None:
        with self.assertRaises(PipelineError) as raised:
            read_estimator({f"{MODEL_SECTION}/n_estimators": "150.5"})

        self.assertIn(f"{MODEL_SECTION}/n_estimators", str(raised.exception))

    def test_what_was_not_given_keeps_the_contract_defaults(self) -> None:
        self.assertEqual(read_estimator({}).forest, RandomForestConfig())

    def test_the_settings_of_the_boosting_model_are_read_when_it_is_chosen(self) -> None:
        config = read_estimator(
            {
                f"{MODEL_SECTION}/algorithm": "hist-gradient-boosting",
                f"{MODEL_SECTION}/learning_rate": "0.05",
                f"{MODEL_SECTION}/max_iterations": "300",
            }
        )

        self.assertEqual(config.boosting.learning_rate, 0.05)
        self.assertEqual(config.boosting.max_iterations, 300)

    def test_the_settings_of_the_linear_baseline_are_read_when_it_is_chosen(self) -> None:
        config = read_estimator(
            {
                f"{MODEL_SECTION}/algorithm": "logistic-regression",
                f"{MODEL_SECTION}/regularisation": "0.25",
            }
        )

        self.assertEqual(config.logistic.regularisation, 0.25)

    def test_a_stale_setting_of_another_algorithm_cannot_change_the_fit(self) -> None:
        config = read_estimator(
            {
                f"{MODEL_SECTION}/algorithm": "logistic-regression",
                f"{MODEL_SECTION}/n_estimators": "9999",
            }
        )

        self.assertEqual(config.forest, RandomForestConfig())


class SharedEstimatorParameterTest(unittest.TestCase):
    """The imbalance policy and the probability cut, read for every algorithm."""

    def test_a_step_told_nothing_leaves_both_where_the_project_leaves_them(self) -> None:
        config = read_estimator({})

        self.assertEqual(config.class_weight, ClassWeight.NONE)
        self.assertIsNone(config.decision_threshold)

    def test_the_cut_a_search_chose_survives_the_trip_through_the_task(self) -> None:
        config = read_estimator({f"{MODEL_SECTION}/decision_threshold": "0.375"})

        self.assertEqual(config.decision_threshold, 0.375)

    def test_a_cut_cleared_in_the_web_ui_means_the_algorithm_decides(self) -> None:
        config = read_estimator({f"{MODEL_SECTION}/decision_threshold": "  "})

        self.assertIsNone(config.decision_threshold)

    def test_a_cut_that_is_not_a_number_is_refused(self) -> None:
        with self.assertRaises(PipelineError) as raised:
            read_estimator({f"{MODEL_SECTION}/decision_threshold": "low"})

        self.assertIn("decision_threshold", str(raised.exception))

    def test_an_imbalance_policy_this_project_does_not_have_is_refused(self) -> None:
        with self.assertRaises(PipelineError) as raised:
            read_estimator({f"{MODEL_SECTION}/class_weight": "undersample"})

        self.assertIn("undersample", str(raised.exception))

    def test_both_are_read_whichever_algorithm_the_step_fits(self) -> None:
        for algorithm in Algorithm:
            with self.subTest(algorithm=algorithm):
                config = read_estimator(
                    {
                        f"{MODEL_SECTION}/algorithm": algorithm.value,
                        f"{MODEL_SECTION}/class_weight": "balanced",
                        f"{MODEL_SECTION}/decision_threshold": "0.4",
                    }
                )

                self.assertEqual(config.class_weight, ClassWeight.BALANCED)
                self.assertEqual(config.decision_threshold, 0.4)


class WrittenParameterTest(unittest.TestCase):
    """What one side writes is what the other side reads."""

    def test_an_estimator_written_onto_a_task_is_read_back_unchanged(self) -> None:
        estimator = EstimatorConfig(
            forest=RandomForestConfig(n_estimators=250, max_depth=9, min_samples_leaf=3),
            class_weight=ClassWeight.BALANCED,
            decision_threshold=0.45,
        )

        self.assertEqual(read_estimator(estimator_parameters(estimator)), estimator)

    def test_a_split_written_onto_a_task_is_read_back_unchanged(self) -> None:
        split = SplitConfig(train_ratio=0.5, validation_ratio=0.25, test_ratio=0.25)

        self.assertEqual(read_split(split_parameters(split)), split)

    def test_a_dataset_written_onto_a_task_is_read_back_unchanged(self) -> None:
        dataset = DatasetConfig(dataset_version="3.1.0", dataset_csv_path="rows.csv")

        self.assertEqual(read_dataset(dataset_parameters(dataset)), dataset)

    def test_a_seed_written_onto_a_task_is_read_back_unchanged(self) -> None:
        self.assertEqual(read_random_seed(seed_parameters(4242), 0), 4242)

    def test_an_unlimited_depth_is_written_as_the_absence_a_task_spells(self) -> None:
        written = estimator_parameters(EstimatorConfig())

        self.assertEqual(written[f"{MODEL_SECTION}/max_depth"], "")


class RandomSeedParameterTest(unittest.TestCase):
    def test_the_seed_is_read_from_the_task(self) -> None:
        seed = read_random_seed({f"{EXECUTION_SECTION}/{RANDOM_SEED_PARAMETER}": "7"}, 1)

        self.assertEqual(seed, 7)

    def test_a_step_without_a_seed_uses_the_one_it_was_given(self) -> None:
        self.assertEqual(read_random_seed({}, 20260906), 20260906)

    def test_a_seed_that_is_not_a_whole_number_is_refused(self) -> None:
        with self.assertRaises(PipelineError):
            read_random_seed({f"{EXECUTION_SECTION}/{RANDOM_SEED_PARAMETER}": "seven"}, 1)


if __name__ == "__main__":
    unittest.main()

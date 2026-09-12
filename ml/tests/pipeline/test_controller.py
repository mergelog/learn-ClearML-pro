from __future__ import annotations

import unittest

from ml.pipeline.controller import (
    HANDOFF_SECTION,
    PipelineRequest,
    RunOrigin,
    run_overrides,
    template_parameters,
)
from ml.pipeline.domain import (
    DATASET_SECTION,
    EXECUTION_SECTION,
    INPUT_SECTION,
    MODEL_SECTION,
    SPLIT_SECTION,
    STEP_SECTION,
    StepName,
)
from ml.semiconductor_quality.config import (
    DEFAULT_TRAINING_QUEUE,
    ConfigurationError,
    DatasetConfig,
    EstimatorConfig,
    RandomForestConfig,
    SplitConfig,
)


def build_request(**overrides: object) -> PipelineRequest:
    defaults: dict[str, object] = {
        "dataset": DatasetConfig(dataset_version="1.0.0"),
        "queue": DEFAULT_TRAINING_QUEUE,
    }
    defaults.update(overrides)
    return PipelineRequest(**defaults)  # type: ignore[arg-type]


class PipelineRequestTest(unittest.TestCase):
    def test_a_run_states_what_it_computes_and_where(self) -> None:
        request = build_request()

        self.assertEqual(request.dataset.dataset_version, "1.0.0")
        self.assertEqual(request.queue, DEFAULT_TRAINING_QUEUE)

    def test_a_run_without_a_queue_is_refused(self) -> None:
        with self.assertRaises(ConfigurationError) as raised:
            build_request(queue="  ").validate()

        self.assertIn("queue", str(raised.exception))

    def test_an_unusable_split_is_refused_before_anything_is_created(self) -> None:
        with self.assertRaises(ConfigurationError):
            build_request(split=SplitConfig(0.9, 0.9, 0.9)).validate()

    def test_an_unusable_estimator_is_refused_before_anything_is_created(self) -> None:
        with self.assertRaises(ConfigurationError):
            build_request(
                estimator=EstimatorConfig(forest=RandomForestConfig(n_estimators=0))
            ).validate()


class TemplateParameterTest(unittest.TestCase):
    def test_every_step_states_which_step_it_is(self) -> None:
        for step in StepName:
            with self.subTest(step=step):
                parameters = template_parameters(step, build_request())

                self.assertEqual(parameters[f"{STEP_SECTION}/name"], step.value)

    def test_only_the_first_step_reads_the_dataset(self) -> None:
        reading_dataset = [
            step
            for step in StepName
            if any(
                name.startswith(DATASET_SECTION)
                for name in template_parameters(step, build_request())
            )
        ]

        self.assertEqual(reading_dataset, [StepName.VALIDATE])

    def test_the_step_that_divides_the_rows_reads_the_ratios_and_the_seed(self) -> None:
        parameters = template_parameters(StepName.PREPROCESS, build_request())

        self.assertIn(f"{SPLIT_SECTION}/train_ratio", parameters)
        self.assertIn(f"{EXECUTION_SECTION}/random_seed", parameters)

    def test_the_step_that_fits_the_model_reads_the_forest_and_the_seed(self) -> None:
        parameters = template_parameters(StepName.TRAIN, build_request())

        self.assertIn(f"{MODEL_SECTION}/n_estimators", parameters)
        self.assertIn(f"{EXECUTION_SECTION}/random_seed", parameters)

    def test_a_step_does_not_list_parameters_it_never_reads(self) -> None:
        parameters = template_parameters(StepName.EVALUATE, build_request())

        self.assertNotIn(f"{MODEL_SECTION}/n_estimators", parameters)
        self.assertNotIn(f"{DATASET_SECTION}/dataset_version", parameters)

    def test_an_unlimited_depth_is_left_empty_rather_than_written_as_a_number(self) -> None:
        parameters = template_parameters(StepName.TRAIN, build_request())

        self.assertEqual(parameters[f"{MODEL_SECTION}/max_depth"], "")

    def test_a_template_starts_with_its_inputs_unconnected(self) -> None:
        parameters = template_parameters(StepName.PREPROCESS, build_request())

        self.assertEqual(parameters[f"{INPUT_SECTION}/validate_task_id"], "")


class RunOverrideTest(unittest.TestCase):
    def test_a_step_is_pointed_at_the_run_it_belongs_to(self) -> None:
        overrides = run_overrides(StepName.EVALUATE, build_request())

        self.assertEqual(overrides[f"{INPUT_SECTION}/train_task_id"], "${train.id}")
        self.assertEqual(overrides[f"{INPUT_SECTION}/preprocess_task_id"], "${preprocess.id}")

    def test_the_values_of_this_run_are_written_over_the_template(self) -> None:
        request = build_request(dataset=DatasetConfig(dataset_version="2.0.0"))

        overrides = run_overrides(StepName.VALIDATE, request)

        self.assertEqual(overrides[f"{DATASET_SECTION}/dataset_version"], "2.0.0")

    def test_which_step_a_task_is_stays_as_the_template_declared_it(self) -> None:
        overrides = run_overrides(StepName.TRAIN, build_request())

        self.assertNotIn(f"{STEP_SECTION}/name", overrides)

    def test_the_forest_of_this_run_reaches_the_step_that_fits_it(self) -> None:
        request = build_request(
            estimator=EstimatorConfig(
                forest=RandomForestConfig(n_estimators=42, max_depth=5),
            )
        )

        overrides = run_overrides(StepName.TRAIN, request)

        self.assertEqual(overrides[f"{MODEL_SECTION}/n_estimators"], "42")
        self.assertEqual(overrides[f"{MODEL_SECTION}/max_depth"], "5")


if __name__ == "__main__":
    unittest.main()


class RunOriginTest(unittest.TestCase):
    """A run that a search asked for says so."""

    def test_a_run_nobody_asked_for_carries_no_origin(self) -> None:
        self.assertFalse(build_request().origin.is_known)

    def test_a_run_a_search_asked_for_names_the_search_and_the_trial(self) -> None:
        origin = RunOrigin(search_task_id="search-1", trial_task_id="trial-1")

        recorded = origin.parameters()

        self.assertTrue(origin.is_known)
        self.assertEqual(recorded[f"{HANDOFF_SECTION}/search_task_id"], "search-1")
        self.assertEqual(recorded[f"{HANDOFF_SECTION}/trial_task_id"], "trial-1")

    def test_half_an_origin_still_counts_as_one(self) -> None:
        self.assertTrue(RunOrigin(search_task_id="search-1").is_known)

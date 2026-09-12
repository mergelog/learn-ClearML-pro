from __future__ import annotations

import unittest

from ml.pipeline.domain import (
    INPUT_SECTION,
    STEP_INPUTS,
    STEP_PARAMETERS,
    PipelineError,
    StepInputs,
    StepName,
    input_placeholders,
)


class StepNameTest(unittest.TestCase):
    def test_a_step_names_the_task_that_carries_it_out(self) -> None:
        self.assertEqual(StepName.VALIDATE.task_name, "pipeline-step-validate")

    def test_the_steps_are_declared_in_the_order_they_run(self) -> None:
        self.assertEqual(
            [step.value for step in StepName],
            ["validate", "preprocess", "train", "evaluate", "register-candidate"],
        )

    def test_a_step_reads_as_its_own_name(self) -> None:
        self.assertEqual(f"{StepName.TRAIN}", "train")


class StepGraphTest(unittest.TestCase):
    def test_every_step_declares_what_it_reads(self) -> None:
        self.assertEqual(set(STEP_INPUTS), set(StepName))

    def test_the_first_step_reads_nothing_from_the_pipeline(self) -> None:
        self.assertEqual(STEP_INPUTS[StepName.VALIDATE], ())

    def test_no_step_depends_on_a_step_that_runs_after_it(self) -> None:
        order = list(StepName)
        for step, parents in STEP_INPUTS.items():
            for parent in parents:
                with self.subTest(step=step, parent=parent):
                    self.assertLess(order.index(parent), order.index(step))

    def test_every_step_that_can_be_read_has_a_parameter_to_name_it(self) -> None:
        readable = {parent for parents in STEP_INPUTS.values() for parent in parents}

        self.assertTrue(readable <= set(STEP_PARAMETERS))


class InputPlaceholderTest(unittest.TestCase):
    def test_a_step_without_inputs_needs_no_placeholder(self) -> None:
        self.assertEqual(input_placeholders(StepName.VALIDATE), {})

    def test_a_placeholder_points_at_the_run_the_step_belongs_to(self) -> None:
        placeholders = input_placeholders(StepName.PREPROCESS)

        self.assertEqual(
            placeholders,
            {f"{INPUT_SECTION}/validate_task_id": "${validate.id}"},
        )

    def test_a_step_with_two_inputs_names_both(self) -> None:
        placeholders = input_placeholders(StepName.EVALUATE)

        self.assertEqual(
            sorted(placeholders),
            [f"{INPUT_SECTION}/preprocess_task_id", f"{INPUT_SECTION}/train_task_id"],
        )


class StepInputsTest(unittest.TestCase):
    def test_the_upstream_task_of_a_step_is_read_from_its_parameters(self) -> None:
        inputs = StepInputs.from_parameters(
            {f"{INPUT_SECTION}/validate_task_id": "validate-task"}
        )

        self.assertEqual(inputs.required(StepName.VALIDATE), "validate-task")

    def test_surrounding_space_does_not_become_part_of_the_task_id(self) -> None:
        inputs = StepInputs.from_parameters(
            {f"{INPUT_SECTION}/train_task_id": "  train-task  "}
        )

        self.assertEqual(inputs.required(StepName.TRAIN), "train-task")

    def test_an_input_the_pipeline_did_not_connect_is_refused(self) -> None:
        inputs = StepInputs.from_parameters({})

        with self.assertRaises(PipelineError) as raised:
            inputs.required(StepName.PREPROCESS)

        self.assertIn("preprocess_task_id", str(raised.exception))

    def test_an_unresolved_placeholder_is_not_mistaken_for_a_task(self) -> None:
        inputs = StepInputs.from_parameters({f"{INPUT_SECTION}/validate_task_id": "   "})

        with self.assertRaises(PipelineError):
            inputs.required(StepName.VALIDATE)


if __name__ == "__main__":
    unittest.main()

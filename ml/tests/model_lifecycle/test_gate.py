from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ml.model_lifecycle.domain import LifecycleError
from ml.model_lifecycle.gate import (
    DEFAULT_CRITERIA_FILE,
    GateCriteria,
    apply_gate,
    load_criteria,
)
from ml.semiconductor_quality.domain import TEST_SPLIT, VALIDATION_SPLIT


CRITERIA = GateCriteria(split=VALIDATION_SPLIT, minimums={"recall": 0.55, "f1": 0.65})


def evaluation(**metrics: float) -> dict[str, object]:
    return {
        VALIDATION_SPLIT: {"metrics": dict(metrics)},
        TEST_SPLIT: {"metrics": {"recall": 0.99, "f1": 0.99}},
    }


class GateCriteriaTest(unittest.TestCase):
    def test_criteria_without_a_bar_would_let_everything_through(self) -> None:
        with self.assertRaises(LifecycleError) as raised:
            GateCriteria(split=VALIDATION_SPLIT, minimums={}).validate()

        self.assertIn("at least one minimum", str(raised.exception))

    def test_criteria_without_a_split_cannot_be_applied(self) -> None:
        with self.assertRaises(LifecycleError):
            GateCriteria(split="  ", minimums={"recall": 0.5}).validate()

    def test_a_bar_that_is_not_a_number_is_refused(self) -> None:
        with self.assertRaises(LifecycleError) as raised:
            GateCriteria(split=VALIDATION_SPLIT, minimums={"recall": "high"}).validate()  # type: ignore[dict-item]

        self.assertIn("recall", str(raised.exception))


class GateVerdictTest(unittest.TestCase):
    def test_a_model_that_clears_every_bar_passes(self) -> None:
        verdict = apply_gate(CRITERIA, evaluation(recall=0.60, f1=0.70))

        self.assertTrue(verdict.passed)

    def test_a_model_exactly_on_the_bar_passes(self) -> None:
        verdict = apply_gate(CRITERIA, evaluation(recall=0.55, f1=0.65))

        self.assertTrue(verdict.passed)

    def test_one_measure_below_the_bar_is_enough_to_refuse(self) -> None:
        verdict = apply_gate(CRITERIA, evaluation(recall=0.60, f1=0.40))

        self.assertFalse(verdict.passed)
        self.assertEqual([failure.measure for failure in verdict.failures], ["f1"])

    def test_the_reason_names_the_measure_and_both_numbers(self) -> None:
        verdict = apply_gate(CRITERIA, evaluation(recall=0.10, f1=0.70))

        description = verdict.describe()

        self.assertIn("recall", description)
        self.assertIn("0.1000", description)
        self.assertIn("0.55", description)

    def test_a_measure_that_was_not_reported_is_a_failure(self) -> None:
        verdict = apply_gate(CRITERIA, evaluation(f1=0.70))

        self.assertFalse(verdict.passed)
        self.assertIn("not reported", verdict.describe())

    def test_a_split_that_was_not_scored_is_a_failure(self) -> None:
        verdict = apply_gate(CRITERIA, {TEST_SPLIT: {"metrics": {"recall": 0.99, "f1": 0.99}}})

        self.assertFalse(verdict.passed)

    def test_the_split_the_model_was_chosen_on_is_the_one_judged(self) -> None:
        verdict = apply_gate(CRITERIA, evaluation(recall=0.10, f1=0.10))

        self.assertEqual(verdict.split, VALIDATION_SPLIT)
        self.assertFalse(verdict.passed)

    def test_a_value_that_is_not_a_number_counts_as_absent(self) -> None:
        broken = {VALIDATION_SPLIT: {"metrics": {"recall": "high", "f1": 0.70}}}

        verdict = apply_gate(CRITERIA, broken)

        self.assertFalse(verdict.passed)

    def test_the_decision_is_recorded_in_a_form_a_model_can_carry(self) -> None:
        verdict = apply_gate(CRITERIA, evaluation(recall=0.60, f1=0.70))

        metadata = verdict.as_metadata()

        self.assertEqual(metadata["gate_split"], VALIDATION_SPLIT)
        self.assertEqual(metadata["gate_passed"], "true")
        self.assertIn("cleared", metadata["gate_detail"])


class CriteriaFileTest(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory(prefix="model-gate-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def write(self, content: str) -> Path:
        path = self.directory / "criteria.yaml"
        path.write_text(content, encoding="utf-8")
        return path

    def test_the_criteria_the_team_edits_are_readable(self) -> None:
        criteria = load_criteria(DEFAULT_CRITERIA_FILE)

        self.assertEqual(criteria.split, VALIDATION_SPLIT)
        self.assertIn("recall", criteria.minimums)
        self.assertIn("f1", criteria.minimums)

    def test_the_bar_can_be_changed_without_changing_code(self) -> None:
        path = self.write("split: validation\nminimums:\n  recall: 0.9\n")

        criteria = load_criteria(path)

        self.assertEqual(criteria.minimums, {"recall": 0.9})

    def test_a_missing_criteria_file_is_reported_by_name(self) -> None:
        missing = self.directory / "absent.yaml"

        with self.assertRaises(LifecycleError) as raised:
            load_criteria(missing)

        self.assertIn(str(missing), str(raised.exception))

    def test_a_file_that_is_not_yaml_is_refused(self) -> None:
        path = self.write("split: [unclosed\n")

        with self.assertRaises(LifecycleError):
            load_criteria(path)

    def test_a_file_without_any_minimum_is_refused(self) -> None:
        path = self.write("split: validation\n")

        with self.assertRaises(LifecycleError) as raised:
            load_criteria(path)

        self.assertIn("at least one minimum", str(raised.exception))

    def test_minimums_that_are_not_a_mapping_are_refused(self) -> None:
        path = self.write("split: validation\nminimums:\n  - recall\n")

        with self.assertRaises(LifecycleError):
            load_criteria(path)


if __name__ == "__main__":
    unittest.main()

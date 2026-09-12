from __future__ import annotations

import unittest

from ml.data_quality.drift import DriftThresholds, compare
from ml.data_quality.profile import profile_rows
from ml.tests.data_quality.test_checks import usable_rows


def compared(reference: list[dict[str, str]], current: list[dict[str, str]], **kwargs: object):
    return compare(
        profile_rows(reference),
        profile_rows(current),
        reference_name="1.0.0",
        current_name="2.0.0",
        **kwargs,  # type: ignore[arg-type]
    )


class NoDriftTest(unittest.TestCase):
    def test_a_version_compared_with_itself_has_not_moved(self) -> None:
        report = compared(usable_rows(), usable_rows())

        self.assertFalse(report.has_drifted, report.describe())

    def test_a_report_without_drift_says_so_plainly(self) -> None:
        report = compared(usable_rows(), usable_rows())

        self.assertIn("no column moved", report.describe())

    def test_every_column_is_compared_even_when_nothing_moved(self) -> None:
        report = compared(usable_rows(), usable_rows())

        compared_columns = {drift.column for drift in report.columns}
        self.assertIn("temperature", compared_columns)
        self.assertIn("equipment_id", compared_columns)
        self.assertIn("result", compared_columns)


class NumericDriftTest(unittest.TestCase):
    def test_a_shifted_column_is_reported(self) -> None:
        moved = usable_rows()
        for one in moved:
            one["temperature"] = str(float(one["temperature"]) + 100)

        report = compared(usable_rows(), moved)

        self.assertTrue(report.has_drifted)
        self.assertIn("temperature", report.describe())

    def test_the_movement_is_measured_against_the_earlier_spread(self) -> None:
        moved = usable_rows()
        for one in moved:
            one["temperature"] = str(float(one["temperature"]) + 100)

        [drift] = [d for d in compared(usable_rows(), moved).columns if d.column == "temperature"]

        self.assertGreater(drift.measure, 1.0)
        self.assertIn("of the earlier spread", drift.detail)

    def test_a_small_shift_stays_within_the_threshold(self) -> None:
        barely_moved = usable_rows()
        for one in barely_moved:
            one["temperature"] = str(float(one["temperature"]) + 0.01)

        report = compared(usable_rows(), barely_moved)

        self.assertFalse(report.has_drifted, report.describe())

    def test_the_threshold_can_be_tightened(self) -> None:
        barely_moved = usable_rows()
        for one in barely_moved:
            one["temperature"] = str(float(one["temperature"]) + 0.5)

        report = compared(
            usable_rows(),
            barely_moved,
            thresholds=DriftThresholds(numeric=0.0001),
        )

        self.assertTrue(report.has_drifted)

    def test_a_column_that_never_varied_can_still_be_compared(self) -> None:
        flat = usable_rows()
        for one in flat:
            one["temperature"] = "400"
        moved = usable_rows()
        for one in moved:
            one["temperature"] = "500"

        [drift] = [d for d in compared(flat, moved).columns if d.column == "temperature"]

        self.assertTrue(drift.exceeded)
        self.assertIn("single value", drift.detail)


class CategoricalDriftTest(unittest.TestCase):
    def test_a_new_value_is_named_in_the_report(self) -> None:
        changed = usable_rows()
        for one in changed:
            one["equipment_id"] = "EQ-09"

        report = compared(usable_rows(), changed)

        self.assertTrue(report.has_drifted)
        self.assertIn("EQ-09", report.describe())

    def test_a_value_that_stopped_appearing_is_named(self) -> None:
        changed = usable_rows()
        for one in changed:
            one["equipment_id"] = "EQ-01"

        columns = compared(usable_rows(), changed).columns
        [drift] = [d for d in columns if d.column == "equipment_id"]

        self.assertIn("EQ-02", drift.detail)

    def test_identical_distributions_do_not_move(self) -> None:
        [drift] = [
            d for d in compared(usable_rows(), usable_rows()).columns if d.column == "equipment_id"
        ]

        self.assertEqual(drift.measure, 0.0)

    def test_distributions_with_nothing_in_common_move_the_whole_way(self) -> None:
        changed = usable_rows()
        for one in changed:
            one["equipment_id"] = "EQ-09"

        columns = compared(usable_rows(), changed).columns
        [drift] = [d for d in columns if d.column == "equipment_id"]

        self.assertAlmostEqual(drift.measure, 1.0)


class LabelDriftTest(unittest.TestCase):
    def test_a_change_in_the_balance_of_answers_is_reported(self) -> None:
        changed = usable_rows()
        for one in changed:
            one["result"] = "pass"

        report = compared(usable_rows(), changed)

        self.assertTrue(report.has_drifted)
        self.assertIn("balance of labels", report.describe())

    def test_the_balance_is_always_compared(self) -> None:
        report = compared(usable_rows(), usable_rows())

        self.assertIn("result", {drift.column for drift in report.columns})


class ReportShapeTest(unittest.TestCase):
    def test_the_report_names_both_versions(self) -> None:
        report = compared(usable_rows(), usable_rows())

        self.assertEqual(report.reference, "1.0.0")
        self.assertEqual(report.current, "2.0.0")

    def test_the_report_can_be_stored_as_plain_data(self) -> None:
        document = compared(usable_rows(), usable_rows()).as_document()

        self.assertIs(document["has_drifted"], False)
        self.assertTrue(document["columns"])


if __name__ == "__main__":
    unittest.main()

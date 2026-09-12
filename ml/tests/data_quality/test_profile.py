from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ml.data_quality.domain import DataQualityError
from ml.data_quality.profile import profile_csv, profile_rows
from ml.semiconductor_quality.domain import (
    CATEGORICAL_FEATURE_COLUMNS,
    NUMERIC_FEATURE_COLUMNS,
    REQUIRED_COLUMNS,
)


def row(**overrides: str) -> dict[str, str]:
    values = {
        "sample_id": "SAMPLE-00001",
        "temperature": "415.2",
        "pressure": "12.5",
        "process_time": "60.0",
        "gas_flow": "32.5",
        "sensor_1": "0.42",
        "sensor_2": "-0.13",
        "inspection_value": "8.75",
        "equipment_id": "EQ-01",
        "process_step": "ETCH",
        "result": "pass",
    }
    values.update(overrides)
    return values


def rows(count: int, **overrides: str) -> list[dict[str, str]]:
    return [row(sample_id=f"SAMPLE-{index:05d}", **overrides) for index in range(count)]


class ProfileShapeTest(unittest.TestCase):
    def test_every_column_of_the_contract_is_measured(self) -> None:
        profile = profile_rows(rows(3))

        self.assertEqual(sorted(profile.numeric), sorted(NUMERIC_FEATURE_COLUMNS))
        self.assertEqual(sorted(profile.categorical), sorted(CATEGORICAL_FEATURE_COLUMNS))

    def test_the_number_of_rows_is_what_was_read(self) -> None:
        self.assertEqual(profile_rows(rows(7)).row_count, 7)

    def test_the_profile_can_be_stored_as_plain_data(self) -> None:
        document = profile_rows(rows(3)).as_document()

        self.assertEqual(document["row_count"], 3)
        numeric = document["numeric"]
        assert isinstance(numeric, dict)
        self.assertIn("temperature", numeric)


class NumericMeasurementTest(unittest.TestCase):
    def test_the_range_is_what_the_rows_hold(self) -> None:
        measured = profile_rows(
            [row(temperature="10"), row(temperature="20"), row(temperature="30")]
        ).numeric["temperature"]

        self.assertEqual(measured.minimum, 10.0)
        self.assertEqual(measured.maximum, 30.0)
        self.assertEqual(measured.mean, 20.0)

    def test_a_blank_value_counts_as_missing(self) -> None:
        measured = profile_rows([row(temperature=""), row(), row()]).numeric["temperature"]

        self.assertEqual(measured.missing, 1)
        self.assertAlmostEqual(measured.missing_share, 1 / 3)

    def test_a_value_that_is_not_a_number_also_counts_as_missing(self) -> None:
        measured = profile_rows([row(temperature="warm"), row()]).numeric["temperature"]

        self.assertEqual(measured.missing, 1)

    def test_a_column_that_holds_nothing_readable_reports_no_range(self) -> None:
        measured = profile_rows([row(temperature=""), row(temperature="")]).numeric["temperature"]

        self.assertIsNone(measured.minimum)
        self.assertIsNone(measured.mean)

    def test_a_column_that_never_changes_has_no_spread(self) -> None:
        measured = profile_rows(rows(5, temperature="415.2")).numeric["temperature"]

        self.assertEqual(measured.standard_deviation, 0.0)

    def test_the_spread_is_measured_over_the_rows_that_could_be_read(self) -> None:
        measured = profile_rows(
            [row(temperature="10"), row(temperature="20"), row(temperature="")]
        ).numeric["temperature"]

        self.assertAlmostEqual(measured.mean or 0.0, 15.0)
        self.assertGreater(measured.standard_deviation or 0.0, 0.0)


class CategoricalMeasurementTest(unittest.TestCase):
    def test_every_value_is_counted(self) -> None:
        measured = profile_rows(
            [row(equipment_id="EQ-01"), row(equipment_id="EQ-01"), row(equipment_id="EQ-02")]
        ).categorical["equipment_id"]

        self.assertEqual(dict(measured.counts), {"EQ-01": 2, "EQ-02": 1})

    def test_a_blank_value_counts_as_missing_rather_than_as_a_category(self) -> None:
        measured = profile_rows([row(equipment_id=""), row()]).categorical["equipment_id"]

        self.assertEqual(measured.missing, 1)
        self.assertNotIn("", measured.counts)

    def test_how_varied_a_column_is_can_be_read(self) -> None:
        measured = profile_rows(
            [row(equipment_id="EQ-01"), row(equipment_id="EQ-02")]
        ).categorical["equipment_id"]

        self.assertEqual(measured.unique_share, 1.0)

    def test_values_nobody_declared_can_be_measured_against_the_declared_ones(self) -> None:
        measured = profile_rows(
            [row(equipment_id="EQ-01"), row(equipment_id="EQ-99")]
        ).categorical["equipment_id"]

        self.assertEqual(measured.unknown_share(["EQ-01"]), 0.5)


class IdentifierTest(unittest.TestCase):
    def test_rows_that_repeat_an_identifier_are_counted_as_surplus(self) -> None:
        profile = profile_rows(
            [row(sample_id="A"), row(sample_id="A"), row(sample_id="A"), row(sample_id="B")]
        )

        self.assertEqual(profile.duplicate_identifiers, 2)
        self.assertEqual(profile.duplicate_identifier_share, 0.5)

    def test_a_dataset_without_repeats_reports_none(self) -> None:
        self.assertEqual(profile_rows(rows(4)).duplicate_identifiers, 0)


class LabelTest(unittest.TestCase):
    def test_the_balance_of_answers_is_measured(self) -> None:
        profile = profile_rows([row(result="pass"), row(result="pass"), row(result="fail")])

        self.assertEqual(dict(profile.label_counts), {"pass": 2, "fail": 1})
        self.assertAlmostEqual(profile.label_share("fail"), 1 / 3)

    def test_a_label_that_never_appears_has_a_share_of_zero(self) -> None:
        profile = profile_rows(rows(3, result="pass"))

        self.assertEqual(profile.label_share("fail"), 0.0)


class CsvTest(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory(prefix="data-quality-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def write(self, lines: list[str]) -> Path:
        path = self.directory / "dataset.csv"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_a_csv_is_measured_the_same_way_as_rows(self) -> None:
        header = ",".join(REQUIRED_COLUMNS)
        values = ",".join(row()[column] for column in REQUIRED_COLUMNS)

        profile = profile_csv(self.write([header, values, values]))

        self.assertEqual(profile.row_count, 2)

    def test_a_csv_that_cannot_be_read_is_reported_by_name(self) -> None:
        missing = self.directory / "absent.csv"

        with self.assertRaises(DataQualityError) as raised:
            profile_csv(missing)

        self.assertIn(str(missing), str(raised.exception))

    def test_a_csv_with_no_rows_is_refused(self) -> None:
        path = self.write([",".join(REQUIRED_COLUMNS)])

        with self.assertRaises(DataQualityError):
            profile_csv(path)


if __name__ == "__main__":
    unittest.main()

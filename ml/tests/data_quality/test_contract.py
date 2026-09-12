from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ml.data_quality.contract import DEFAULT_CONTRACT_FILE, load_contract
from ml.data_quality.domain import DataQualityError
from ml.semiconductor_quality.domain import (
    CATEGORICAL_FEATURE_COLUMNS,
    NUMERIC_FEATURE_COLUMNS,
)


COMPLETE = """
numeric:
{numeric}
categorical:
  equipment_id:
    allowed: [EQ-01]
  process_step:
    allowed: [ETCH]
labels:
  minimum_share: 0.05
"""


def numeric_section(columns: tuple[str, ...]) -> str:
    return "\n".join(f"  {column}:\n    minimum: 0\n    maximum: 1000" for column in columns)


class ShippedContractTest(unittest.TestCase):
    """The file the team actually edits has to stay usable."""

    def test_the_contract_that_ships_with_the_project_can_be_read(self) -> None:
        contract = load_contract(DEFAULT_CONTRACT_FILE)

        self.assertTrue(contract.numeric)
        self.assertTrue(contract.categorical)

    def test_it_describes_exactly_the_columns_the_code_declares(self) -> None:
        contract = load_contract(DEFAULT_CONTRACT_FILE)

        self.assertEqual(sorted(contract.numeric), sorted(NUMERIC_FEATURE_COLUMNS))
        self.assertEqual(sorted(contract.categorical), sorted(CATEGORICAL_FEATURE_COLUMNS))

    def test_the_declared_equipment_covers_what_the_seed_data_holds(self) -> None:
        contract = load_contract(DEFAULT_CONTRACT_FILE)

        self.assertIn("EQ-01", contract.categorical["equipment_id"].allowed)


class ContractFileTest(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory(prefix="data-quality-contract-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def write(self, content: str) -> Path:
        path = self.directory / "data_quality.yaml"
        path.write_text(content, encoding="utf-8")
        return path

    def complete(self) -> str:
        return COMPLETE.format(numeric=numeric_section(NUMERIC_FEATURE_COLUMNS))

    def test_a_complete_file_is_accepted(self) -> None:
        contract = load_contract(self.write(self.complete()))

        self.assertEqual(sorted(contract.numeric), sorted(NUMERIC_FEATURE_COLUMNS))

    def test_a_column_the_code_declares_but_the_file_omits_is_refused(self) -> None:
        partial = COMPLETE.format(numeric=numeric_section(NUMERIC_FEATURE_COLUMNS[:-1]))

        with self.assertRaises(DataQualityError) as raised:
            load_contract(self.write(partial))

        self.assertIn(NUMERIC_FEATURE_COLUMNS[-1], str(raised.exception))

    def test_a_column_the_file_describes_but_the_code_does_not_is_refused(self) -> None:
        surplus = COMPLETE.format(
            numeric=numeric_section((*NUMERIC_FEATURE_COLUMNS, "wafer_thickness"))
        )

        with self.assertRaises(DataQualityError) as raised:
            load_contract(self.write(surplus))

        self.assertIn("wafer_thickness", str(raised.exception))

    def test_a_missing_file_is_reported_by_name(self) -> None:
        missing = self.directory / "absent.yaml"

        with self.assertRaises(DataQualityError) as raised:
            load_contract(missing)

        self.assertIn(str(missing), str(raised.exception))

    def test_a_file_that_is_not_yaml_is_refused(self) -> None:
        with self.assertRaises(DataQualityError):
            load_contract(self.write("numeric: [unclosed\n"))

    def test_a_range_that_is_inverted_is_refused(self) -> None:
        inverted = self.complete().replace(
            "    minimum: 0\n    maximum: 1000",
            "    minimum: 1000\n    maximum: 0",
            1,
        )

        with self.assertRaises(DataQualityError) as raised:
            load_contract(self.write(inverted))

        self.assertIn("minimum must be below maximum", str(raised.exception))

    def test_a_bound_that_is_not_a_number_is_refused(self) -> None:
        broken = self.complete().replace("    maximum: 1000", "    maximum: hot", 1)

        with self.assertRaises(DataQualityError) as raised:
            load_contract(self.write(broken))

        self.assertIn("must be a number", str(raised.exception))

    def test_a_categorical_column_without_allowed_values_is_refused(self) -> None:
        empty = self.complete().replace("    allowed: [EQ-01]", "    allowed: []", 1)

        with self.assertRaises(DataQualityError) as raised:
            load_contract(self.write(empty))

        self.assertIn("at least one allowed value", str(raised.exception))

    def test_a_share_outside_zero_to_one_is_refused(self) -> None:
        broken = self.complete().replace("  minimum_share: 0.05", "  minimum_share: 5", 1)

        with self.assertRaises(DataQualityError) as raised:
            load_contract(self.write(broken))

        self.assertIn("between 0 and 1", str(raised.exception))


if __name__ == "__main__":
    unittest.main()

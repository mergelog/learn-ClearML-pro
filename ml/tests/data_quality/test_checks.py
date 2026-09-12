from __future__ import annotations

import unittest

from ml.data_quality.checks import MINIMUM_ROWS, check
from ml.data_quality.domain import (
    CategoricalExpectation,
    DataQualityContract,
    LabelExpectation,
    NumericExpectation,
)
from ml.data_quality.profile import profile_rows
from ml.tests.data_quality.test_profile import rows


def build_contract(**overrides: object) -> DataQualityContract:
    defaults: dict[str, object] = {
        "numeric": {
            column: NumericExpectation(minimum=-1_000, maximum=1_000)
            for column in (
                "temperature",
                "pressure",
                "process_time",
                "gas_flow",
                "sensor_1",
                "sensor_2",
                "inspection_value",
            )
        },
        "categorical": {
            "equipment_id": CategoricalExpectation(allowed=("EQ-01", "EQ-02")),
            "process_step": CategoricalExpectation(allowed=("ETCH", "CLEAN")),
        },
        "labels": LabelExpectation(minimum_share=0.05),
    }
    defaults.update(overrides)
    return DataQualityContract(**defaults)  # type: ignore[arg-type]


# 行ごとに動く数値。「毎行同じ値」の検査に引っかからないようにするためで、
# 実データも当然ながら行ごとに違う値を持つ。
#
# 中心値は実際のseedデータに合わせ、振れ幅は小さく取る。出荷している
# config/data_quality.yaml の範囲に収まっていないと、この行を使う
# Pipelineのテストが「壊していないのに落ちる」ことになる。
TYPICAL_VALUES = {
    "temperature": 450.0,
    "pressure": 100.0,
    "process_time": 60.0,
    "gas_flow": 50.0,
    "sensor_1": 0.0,
    "sensor_2": 0.0,
    "inspection_value": 10.0,
}


def usable_rows(count: int = MINIMUM_ROWS) -> list[dict[str, str]]:
    """Rows that meet every expectation, so a test can break exactly one."""
    built = rows(count)
    for index, one in enumerate(built):
        one["result"] = "fail" if index % 4 == 0 else "pass"
        one["equipment_id"] = "EQ-01" if index % 2 == 0 else "EQ-02"
        one["process_step"] = "ETCH" if index % 3 == 0 else "CLEAN"
        for column, typical in TYPICAL_VALUES.items():
            one[column] = f"{typical + (index % 20) * 0.05:.4f}"
    return built


class UsableDatasetTest(unittest.TestCase):
    def test_a_dataset_that_meets_every_expectation_passes(self) -> None:
        report = check(build_contract(), profile_rows(usable_rows()))

        self.assertTrue(report.passed, report.describe())

    def test_a_passing_report_says_so_plainly(self) -> None:
        report = check(build_contract(), profile_rows(usable_rows()))

        self.assertIn("meets every expectation", report.describe())


class SizeTest(unittest.TestCase):
    def test_a_dataset_too_small_to_learn_from_is_refused(self) -> None:
        report = check(build_contract(), profile_rows(usable_rows(MINIMUM_ROWS - 1)))

        self.assertFalse(report.passed)
        self.assertIn("rows", report.describe())


class NumericCheckTest(unittest.TestCase):
    def test_a_value_below_the_range_is_refused(self) -> None:
        broken = usable_rows()
        broken[0]["temperature"] = "-5000"

        report = check(build_contract(), profile_rows(broken))

        self.assertFalse(report.passed)
        self.assertIn("no value below", report.describe())

    def test_a_value_above_the_range_is_refused(self) -> None:
        broken = usable_rows()
        broken[0]["temperature"] = "5000"

        report = check(build_contract(), profile_rows(broken))

        self.assertIn("no value above", report.describe())

    def test_the_violation_names_the_column_and_both_numbers(self) -> None:
        broken = usable_rows()
        broken[0]["pressure"] = "9999"

        [violation] = check(build_contract(), profile_rows(broken)).violations

        self.assertEqual(violation.column, "pressure")
        self.assertIn("1000", violation.expectation)
        self.assertIn("9999", violation.found)

    def test_a_column_that_never_changes_is_refused(self) -> None:
        stuck = usable_rows()
        for one in stuck:
            one["sensor_1"] = "0.5"

        report = check(build_contract(), profile_rows(stuck))

        self.assertFalse(report.passed)
        self.assertIn("vary between rows", report.describe())

    def test_missing_values_beyond_the_allowance_are_refused(self) -> None:
        broken = usable_rows()
        for one in broken[:10]:
            one["gas_flow"] = ""

        report = check(build_contract(), profile_rows(broken))

        self.assertIn("missing", report.describe())

    def test_missing_values_within_the_allowance_are_accepted(self) -> None:
        contract = build_contract(
            numeric={
                **build_contract().numeric,
                "gas_flow": NumericExpectation(
                    minimum=-1_000,
                    maximum=1_000,
                    maximum_missing_share=0.2,
                ),
            }
        )
        with_gaps = usable_rows()
        for one in with_gaps[:10]:
            one["gas_flow"] = ""

        report = check(contract, profile_rows(with_gaps))

        self.assertTrue(report.passed, report.describe())


class CategoricalCheckTest(unittest.TestCase):
    def test_a_value_nobody_declared_is_refused(self) -> None:
        broken = usable_rows()
        broken[0]["equipment_id"] = "EQ-99"

        report = check(build_contract(), profile_rows(broken))

        self.assertFalse(report.passed)
        self.assertIn("EQ-99", report.describe())

    def test_the_violation_says_how_much_of_the_data_is_affected(self) -> None:
        broken = usable_rows()
        for one in broken[:25]:
            one["equipment_id"] = "EQ-99"

        [violation] = check(build_contract(), profile_rows(broken)).violations

        self.assertIn("25.00%", violation.found)

    def test_unknown_values_within_the_allowance_are_accepted(self) -> None:
        contract = build_contract(
            categorical={
                **build_contract().categorical,
                "equipment_id": CategoricalExpectation(
                    allowed=("EQ-01", "EQ-02"),
                    maximum_unknown_share=0.1,
                ),
            }
        )
        tolerated = usable_rows()
        tolerated[0]["equipment_id"] = "EQ-99"

        report = check(contract, profile_rows(tolerated))

        self.assertTrue(report.passed, report.describe())


class LabelCheckTest(unittest.TestCase):
    def test_a_dataset_with_almost_no_failures_is_refused(self) -> None:
        unbalanced = usable_rows()
        for one in unbalanced[1:]:
            one["result"] = "pass"

        report = check(build_contract(), profile_rows(unbalanced))

        self.assertFalse(report.passed)
        self.assertIn("'fail'", report.describe())

    def test_a_dataset_missing_a_label_entirely_is_refused(self) -> None:
        report = check(build_contract(), profile_rows(rows(MINIMUM_ROWS, result="pass")))

        self.assertFalse(report.passed)


class IdentifierCheckTest(unittest.TestCase):
    def test_repeated_identifiers_are_refused(self) -> None:
        duplicated = usable_rows()
        duplicated[1]["sample_id"] = duplicated[0]["sample_id"]

        report = check(build_contract(), profile_rows(duplicated))

        self.assertFalse(report.passed)
        self.assertIn("sample_id", report.describe())


class MissingColumnTest(unittest.TestCase):
    def test_a_column_the_contract_expects_but_the_data_lacks_is_reported(self) -> None:
        contract = build_contract(
            numeric={
                **build_contract().numeric,
                "wafer_thickness": NumericExpectation(minimum=0, maximum=10),
            }
        )

        report = check(contract, profile_rows(usable_rows()))

        self.assertFalse(report.passed)
        self.assertIn("wafer_thickness", report.describe())


class EveryReasonTest(unittest.TestCase):
    def test_every_reason_is_reported_at_once(self) -> None:
        broken = usable_rows()
        broken[0]["temperature"] = "5000"
        broken[1]["equipment_id"] = "EQ-99"
        for one in broken[2:]:
            one["result"] = "pass"
        broken[0]["result"] = "pass"
        broken[1]["result"] = "pass"

        report = check(build_contract(), profile_rows(broken))

        columns = {violation.column for violation in report.violations}
        self.assertEqual(columns, {"temperature", "equipment_id", "result"})

    def test_a_failing_report_can_be_stored_as_plain_data(self) -> None:
        broken = usable_rows()
        broken[0]["temperature"] = "5000"

        document = check(build_contract(), profile_rows(broken)).as_document()

        self.assertIs(document["passed"], False)
        self.assertEqual(len(document["violations"]), 1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()

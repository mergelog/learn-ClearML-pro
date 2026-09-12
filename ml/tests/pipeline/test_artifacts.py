from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from ml.pipeline.artifacts import (
    SPLIT_FILE_NAME,
    describe_split,
    read_json,
    read_split,
    write_json,
    write_split,
)
from ml.pipeline.domain import PipelineError
from ml.semiconductor_quality.domain import (
    CATEGORICAL_FEATURE_COLUMNS,
    FEATURE_COLUMNS,
    NUMERIC_FEATURE_COLUMNS,
    TEST_SPLIT,
    TRAIN_SPLIT,
    VALIDATION_SPLIT,
    DataSplit,
    FeatureMatrix,
    SplitPart,
)


def build_features(row_count: int, offset: float) -> FeatureMatrix:
    """Build a feature matrix in the layout of the data contract."""
    features: FeatureMatrix = np.empty((row_count, len(FEATURE_COLUMNS)), dtype=object)
    for row in range(row_count):
        numeric = [offset + row + index / 10 for index in range(len(NUMERIC_FEATURE_COLUMNS))]
        categorical = [f"EQ-{row % 3}", f"STEP-{row % 2}"]
        features[row] = (*numeric, *categorical)
    return features


def build_part(name: str, pass_rows: int, fail_rows: int, offset: float = 0.0) -> SplitPart:
    targets = np.array(["pass"] * pass_rows + ["fail"] * fail_rows)
    return SplitPart(
        name=name,
        features=build_features(pass_rows + fail_rows, offset),
        targets=targets,
        label_counts={"pass": pass_rows, "fail": fail_rows},
    )


def build_split() -> DataSplit:
    return DataSplit(
        train=build_part(TRAIN_SPLIT, 6, 4, offset=0.0),
        validation=build_part(VALIDATION_SPLIT, 2, 2, offset=100.0),
        test=build_part(TEST_SPLIT, 3, 1, offset=200.0),
    )


class SplitArtifactTest(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory(prefix="pipeline-artifacts-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.split = build_split()
        self.path = write_split(self.directory, self.split)

    def test_the_split_is_written_where_the_next_step_looks_for_it(self) -> None:
        self.assertEqual(self.path.name, SPLIT_FILE_NAME)
        self.assertTrue(self.path.is_file())

    def test_every_part_survives_the_round_trip(self) -> None:
        restored = read_split(self.path)

        for before, after in zip(self.split.parts, restored.parts, strict=True):
            with self.subTest(part=before.name):
                self.assertEqual(after.name, before.name)
                self.assertEqual(after.row_count, before.row_count)

    def test_the_numeric_values_come_back_unchanged(self) -> None:
        restored = read_split(self.path)

        numeric_columns = len(NUMERIC_FEATURE_COLUMNS)
        before = np.asarray(self.split.train.features[:, :numeric_columns], dtype=float)
        after = np.asarray(restored.train.features[:, :numeric_columns], dtype=float)

        np.testing.assert_allclose(after, before)

    def test_the_categorical_values_come_back_unchanged(self) -> None:
        restored = read_split(self.path)

        numeric_columns = len(NUMERIC_FEATURE_COLUMNS)
        before = self.split.validation.features[:, numeric_columns:].tolist()
        after = restored.validation.features[:, numeric_columns:].tolist()

        self.assertEqual(after, before)

    def test_the_labels_come_back_unchanged(self) -> None:
        restored = read_split(self.path)

        self.assertEqual(restored.test.targets.tolist(), self.split.test.targets.tolist())

    def test_the_label_counts_are_recomputed_rather_than_trusted(self) -> None:
        restored = read_split(self.path)

        self.assertEqual(dict(restored.train.label_counts), {"pass": 6, "fail": 4})

    def test_the_restored_matrix_keeps_the_column_order_of_the_contract(self) -> None:
        restored = read_split(self.path)

        self.assertEqual(
            restored.train.features.shape[1],
            len(NUMERIC_FEATURE_COLUMNS) + len(CATEGORICAL_FEATURE_COLUMNS),
        )

    def test_nothing_in_the_artifact_can_execute_when_it_is_read(self) -> None:
        with np.load(self.path, allow_pickle=False) as stored:
            self.assertTrue(set(stored.files))

    def test_a_file_that_is_not_a_split_is_refused(self) -> None:
        broken = self.directory / "broken.npz"
        broken.write_bytes(b"this is not an archive")

        with self.assertRaises(PipelineError) as raised:
            read_split(broken)

        self.assertIn(str(broken), str(raised.exception))

    def test_a_split_missing_a_part_is_refused(self) -> None:
        partial = self.directory / "partial.npz"
        np.savez_compressed(str(partial), train_numeric=np.zeros((2, 7)))

        with self.assertRaises(PipelineError):
            read_split(partial)


class SplitSummaryTest(unittest.TestCase):
    def test_the_summary_states_the_size_and_balance_of_every_part(self) -> None:
        summary = describe_split(build_split())

        self.assertEqual(sorted(summary), sorted([TRAIN_SPLIT, VALIDATION_SPLIT, TEST_SPLIT]))
        self.assertEqual(
            summary[TRAIN_SPLIT],
            {"row_count": 10, "label_counts": {"pass": 6, "fail": 4}},
        )


class JsonArtifactTest(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory(prefix="pipeline-artifacts-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def test_a_json_artifact_survives_the_round_trip(self) -> None:
        path = write_json(self.directory, "report", {"row_count": 1200})

        self.assertEqual(read_json(path), {"row_count": 1200})

    def test_a_json_artifact_is_readable_without_this_code(self) -> None:
        path = write_json(self.directory, "report", {"row_count": 1200})

        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"row_count": 1200})

    def test_a_file_that_is_not_json_is_refused(self) -> None:
        path = self.directory / "broken.json"
        path.write_text("not json", encoding="utf-8")

        with self.assertRaises(PipelineError):
            read_json(path)

    def test_an_artifact_that_does_not_hold_an_object_is_refused(self) -> None:
        path = self.directory / "list.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")

        with self.assertRaises(PipelineError):
            read_json(path)


if __name__ == "__main__":
    unittest.main()

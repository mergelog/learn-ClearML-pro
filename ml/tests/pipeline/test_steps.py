from __future__ import annotations

import contextlib
import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import joblib
from sklearn.pipeline import Pipeline

from ml.model_lifecycle.domain import (
    METADATA_DATASET_ID,
    METADATA_DATASET_VERSION,
    METADATA_MODEL_VERSION,
    METADATA_TRAIN_TASK_ID,
    ModelStage,
)
from ml.pipeline import steps as steps_module
from ml.pipeline.artifacts import write_split
from ml.pipeline.domain import (
    DATA_DRIFT_ARTIFACT,
    DATA_PROFILE_ARTIFACT,
    DATA_QUALITY_ARTIFACT,
    DATA_QUALITY_SECTION,
    DATASET_SECTION,
    DECISION_ARTIFACT,
    EVALUATION_ARTIFACT,
    INPUT_SECTION,
    LINEAGE_ARTIFACT,
    MODEL_WEIGHTS_ARTIFACT,
    RESOLVED_DATASET_SECTION,
    SPLIT_ARTIFACT,
    SPLIT_SUMMARY_ARTIFACT,
    VALIDATION_REPORT_ARTIFACT,
    PipelineError,
    StepName,
)
from ml.pipeline.steps import DRIFT_REFERENCE_PARAMETER, StepTask, run_step
from ml.semiconductor_quality.config import EstimatorConfig, RandomForestConfig
from ml.semiconductor_quality.domain import (
    REQUIRED_COLUMNS,
    TEST_SPLIT,
    VALIDATION_SPLIT,
    FetchedDataset,
)
from ml.semiconductor_quality.train import build_contract_pipeline, fit_pipeline
from ml.tests.data_quality.test_checks import usable_rows
from ml.tests.pipeline.test_artifacts import build_split


CONNECTED_INPUTS = {
    f"{INPUT_SECTION}/validate_task_id": "validate-task",
    f"{INPUT_SECTION}/preprocess_task_id": "preprocess-task",
    f"{INPUT_SECTION}/train_task_id": "train-task",
    f"{INPUT_SECTION}/evaluate_task_id": "evaluate-task",
}


class StepTestCase(unittest.TestCase):
    """Replaces the ClearML Task a step runs as, so no server is contacted."""

    def setUp(self) -> None:
        directory = TemporaryDirectory(prefix="pipeline-step-")
        self.addCleanup(directory.cleanup)
        self.work_dir = Path(directory.name)

        self.split = build_split()
        self.split_path = write_split(self.work_dir, self.split)

        self.task = mock.MagicMock(spec=StepTask)
        self.task.id = "step-task"
        self.task.parameters = dict(CONNECTED_INPUTS)
        self.task.fetch_artifact.side_effect = self._fetch_artifact
        self.artifacts: dict[str, Path] = {SPLIT_ARTIFACT: self.split_path}

    def _fetch_artifact(self, task_id: str, name: str) -> Path:
        if name not in self.artifacts:
            raise PipelineError(f"the {name!r} artifact is missing from Task {task_id}")
        return self.artifacts[name]

    def uploaded_json(self) -> dict[str, dict[str, object]]:
        return {
            call.args[0]: call.args[1] for call in self.task.upload_json.call_args_list
        }

    def uploaded_files(self) -> dict[str, Path]:
        return {call.args[0]: call.args[1] for call in self.task.upload_file.call_args_list}

    def fit_a_model(self) -> Path:
        pipeline = build_contract_pipeline(
            EstimatorConfig(forest=RandomForestConfig(n_estimators=5)),
            1,
        )
        fit_pipeline(pipeline, self.split.train)
        weights = self.work_dir / "model.joblib"
        joblib.dump(pipeline, weights)
        return weights


class TrainStepTest(StepTestCase):
    def test_the_model_is_handed_on_under_the_name_the_next_step_reads(self) -> None:
        run_step(StepName.TRAIN, self.task, self.work_dir)

        self.assertIn(MODEL_WEIGHTS_ARTIFACT, self.uploaded_files())

    def test_the_stored_file_holds_the_preprocessing_and_the_model_together(self) -> None:
        run_step(StepName.TRAIN, self.task, self.work_dir)

        stored = joblib.load(self.uploaded_files()[MODEL_WEIGHTS_ARTIFACT])

        self.assertIsInstance(stored, Pipeline)
        self.assertEqual([name for name, _ in stored.steps], ["preprocessor", "classifier"])

    def test_the_model_is_fitted_on_the_training_rows_only(self) -> None:
        run_step(StepName.TRAIN, self.task, self.work_dir)

        stored = joblib.load(self.uploaded_files()[MODEL_WEIGHTS_ARTIFACT])
        scaler = stored.named_steps["preprocessor"].named_transformers_["numeric"]

        self.assertEqual(int(scaler.n_samples_seen_), self.split.train.row_count)

    def test_a_step_whose_input_was_not_connected_is_refused(self) -> None:
        self.task.parameters = {}

        with self.assertRaises(PipelineError) as raised:
            run_step(StepName.TRAIN, self.task, self.work_dir)

        self.assertIn("preprocess_task_id", str(raised.exception))

    def test_the_split_is_read_from_the_step_that_produced_it(self) -> None:
        run_step(StepName.TRAIN, self.task, self.work_dir)

        self.task.fetch_artifact.assert_called_once_with("preprocess-task", SPLIT_ARTIFACT)


class EvaluateStepTest(StepTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.artifacts[MODEL_WEIGHTS_ARTIFACT] = self.fit_a_model()

    def test_both_scored_splits_are_reported(self) -> None:
        run_step(StepName.EVALUATE, self.task, self.work_dir)

        reported = [call.args[0].split_name for call in self.task.report_result.call_args_list]

        self.assertEqual(reported, [VALIDATION_SPLIT, TEST_SPLIT])

    def test_the_numbers_are_kept_as_a_readable_artifact(self) -> None:
        run_step(StepName.EVALUATE, self.task, self.work_dir)

        payload = self.uploaded_json()[EVALUATION_ARTIFACT]

        self.assertEqual(sorted(payload), sorted([VALIDATION_SPLIT, TEST_SPLIT]))

    def test_every_metric_of_the_contract_is_recorded(self) -> None:
        run_step(StepName.EVALUATE, self.task, self.work_dir)

        scored = self.uploaded_json()[EVALUATION_ARTIFACT][VALIDATION_SPLIT]

        self.assertEqual(
            sorted(scored["metrics"]),  # type: ignore[index]
            ["accuracy", "f1", "precision", "recall"],
        )

    def test_a_model_artifact_that_is_not_a_pipeline_is_refused(self) -> None:
        broken = self.work_dir / "broken.joblib"
        joblib.dump({"not": "a pipeline"}, broken)
        self.artifacts[MODEL_WEIGHTS_ARTIFACT] = broken

        with self.assertRaises(PipelineError):
            run_step(StepName.EVALUATE, self.task, self.work_dir)

    def test_a_model_artifact_that_did_not_survive_the_transfer_is_refused(self) -> None:
        """途中で切れた重みは ``EOFError`` になり、ファイル名すら出ない。

        この段はagentの上で走るので、Taskのログに残る一行が全てである。
        """
        truncated = self.work_dir / "truncated.joblib"
        stored = self.fit_a_model().read_bytes()
        truncated.write_bytes(stored[: len(stored) // 2])
        self.artifacts[MODEL_WEIGHTS_ARTIFACT] = truncated

        with self.assertRaises(PipelineError) as raised:
            run_step(StepName.EVALUATE, self.task, self.work_dir)

        reported = str(raised.exception)
        self.assertIn(str(truncated), reported)
        self.assertIn("EOFError", reported)

    def test_a_model_artifact_that_is_not_a_model_at_all_is_refused(self) -> None:
        nonsense = self.work_dir / "nonsense.joblib"
        nonsense.write_bytes(b"\x00\x01 this was never a model")
        self.artifacts[MODEL_WEIGHTS_ARTIFACT] = nonsense

        with self.assertRaises(PipelineError) as raised:
            run_step(StepName.EVALUATE, self.task, self.work_dir)

        self.assertIn("cannot be read", str(raised.exception))


class RegisterCandidateStepTest(StepTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.weights = self.fit_a_model()
        self.artifacts[MODEL_WEIGHTS_ARTIFACT] = self.weights
        self.task.parameters_of.return_value = {
            f"{RESOLVED_DATASET_SECTION}/dataset_id": "dataset-id",
            f"{RESOLVED_DATASET_SECTION}/dataset_version": "1.0.0",
        }
        self.task.register_model.return_value = "model-id"
        self.write_evaluation({"recall": 0.71, "f1": 0.74})

    def write_evaluation(self, metrics: dict[str, float]) -> None:
        path = self.work_dir / "evaluation.json"
        path.write_text(json.dumps({"validation": {"metrics": metrics}}), encoding="utf-8")
        self.artifacts[EVALUATION_ARTIFACT] = path

    def test_the_model_the_training_step_produced_is_the_one_registered(self) -> None:
        run_step(StepName.REGISTER_CANDIDATE, self.task, self.work_dir)

        self.assertEqual(self.task.register_model.call_args.args[0], self.weights)

    def test_a_registered_model_starts_as_a_candidate(self) -> None:
        run_step(StepName.REGISTER_CANDIDATE, self.task, self.work_dir)

        self.assertEqual(
            self.task.register_model.call_args.kwargs["tags"],
            [ModelStage.CANDIDATE.tag],
        )

    def test_the_model_records_the_data_and_the_run_it_came_from(self) -> None:
        run_step(StepName.REGISTER_CANDIDATE, self.task, self.work_dir)

        metadata = self.task.register_model.call_args.kwargs["metadata"]

        self.assertEqual(metadata[METADATA_DATASET_ID], "dataset-id")
        self.assertEqual(metadata[METADATA_DATASET_VERSION], "1.0.0")
        self.assertEqual(metadata[METADATA_TRAIN_TASK_ID], "train-task")

    def test_the_model_version_names_the_data_and_the_run(self) -> None:
        run_step(StepName.REGISTER_CANDIDATE, self.task, self.work_dir)

        version = self.task.register_model.call_args.kwargs["metadata"][METADATA_MODEL_VERSION]

        self.assertTrue(version.startswith("1.0.0-"))
        self.assertTrue(version.endswith("-train-ta"))

    def test_the_decision_names_the_executions_it_was_based_on(self) -> None:
        run_step(StepName.REGISTER_CANDIDATE, self.task, self.work_dir)

        decision = self.uploaded_json()[DECISION_ARTIFACT]

        self.assertEqual(decision["train_task_id"], "train-task")
        self.assertEqual(decision["evaluate_task_id"], "evaluate-task")
        self.assertEqual(decision["validate_task_id"], "validate-task")

    def test_the_evaluation_it_was_based_on_is_kept_with_the_decision(self) -> None:
        run_step(StepName.REGISTER_CANDIDATE, self.task, self.work_dir)

        decision = self.uploaded_json()[DECISION_ARTIFACT]

        self.assertEqual(
            decision["evaluation"],
            {"validation": {"metrics": {"recall": 0.71, "f1": 0.74}}},
        )

    def test_a_model_below_the_bar_is_not_registered(self) -> None:
        self.write_evaluation({"recall": 0.10, "f1": 0.20})

        with self.assertRaises(PipelineError):
            run_step(StepName.REGISTER_CANDIDATE, self.task, self.work_dir)

        self.task.register_model.assert_not_called()

    def test_why_a_model_was_refused_is_still_recorded(self) -> None:
        self.write_evaluation({"recall": 0.10, "f1": 0.20})

        with contextlib.suppress(PipelineError):
            run_step(StepName.REGISTER_CANDIDATE, self.task, self.work_dir)

        decision = self.uploaded_json()[DECISION_ARTIFACT]

        self.assertIs(decision["registered"], False)
        self.assertIn("recall", str(decision["gate"]))

    def test_a_measure_the_run_did_not_report_counts_as_a_failure(self) -> None:
        self.write_evaluation({"accuracy": 0.99})

        with self.assertRaises(PipelineError) as raised:
            run_step(StepName.REGISTER_CANDIDATE, self.task, self.work_dir)

        self.assertIn("not reported", str(raised.exception))


class ApprovedDatasetTest(StepTestCase):
    def test_the_rows_that_were_approved_are_addressed_by_identifier(self) -> None:
        self.task.parameters_of.return_value = {
            f"{RESOLVED_DATASET_SECTION}/dataset_id": "dataset-id",
            f"{DATASET_SECTION}/dataset_version": "1.0.0",
        }

        approved = steps_module._approved_dataset(self.task, "validate-task")

        self.assertEqual(approved.dataset_id, "dataset-id")

    def test_a_validation_step_that_recorded_nothing_stops_the_run(self) -> None:
        self.task.parameters_of.return_value = {
            f"{DATASET_SECTION}/dataset_version": "1.0.0",
        }

        with self.assertRaises(PipelineError) as raised:
            steps_module._approved_dataset(self.task, "validate-task")

        self.assertIn("validate-task", str(raised.exception))


class ValidateStepTest(StepTestCase):
    """The validate step judges the raw Dataset before anything is fitted."""

    def setUp(self) -> None:
        super().setUp()
        self.dataset_root = self.work_dir / "dataset"
        self.dataset_root.mkdir()
        self.write_dataset(usable_rows())

        self.task.parameters = {
            **CONNECTED_INPUTS,
            f"{DATASET_SECTION}/dataset_version": "1.0.0",
        }
        self.fetch_dataset = mock.MagicMock(
            name="fetch_dataset",
            return_value=FetchedDataset(
                dataset_id="dataset-id",
                dataset_project="Semiconductor Quality Prediction",
                dataset_name="semiconductor-quality-data",
                dataset_version="1.0.0",
                local_root=self.dataset_root,
                parents=("parent-dataset-id",),
            ),
        )
        patcher = mock.patch.object(steps_module, "fetch_dataset", self.fetch_dataset)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_dataset(self, rows: list[dict[str, str]]) -> None:
        path = self.dataset_root / "semiconductor_quality.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(REQUIRED_COLUMNS))
            writer.writeheader()
            writer.writerows({column: row[column] for column in REQUIRED_COLUMNS} for row in rows)

    def test_the_dataset_that_was_approved_is_recorded_for_the_next_step(self) -> None:
        run_step(StepName.VALIDATE, self.task, self.work_dir)

        self.task.record.assert_called_once()
        section, values = self.task.record.call_args.args
        self.assertEqual(section, RESOLVED_DATASET_SECTION)
        self.assertEqual(values["dataset_id"], "dataset-id")

    def test_what_was_validated_is_kept_as_a_readable_artifact(self) -> None:
        run_step(StepName.VALIDATE, self.task, self.work_dir)

        report = self.uploaded_json()[VALIDATION_REPORT_ARTIFACT]

        self.assertEqual(report["row_count"], len(usable_rows()))

    def test_what_the_dataset_holds_is_measured_and_kept(self) -> None:
        run_step(StepName.VALIDATE, self.task, self.work_dir)

        profile = self.uploaded_json()[DATA_PROFILE_ARTIFACT]
        numeric = profile["numeric"]
        assert isinstance(numeric, dict)

        self.assertEqual(profile["row_count"], len(usable_rows()))
        self.assertIn("temperature", numeric)

    def test_the_quality_decision_is_kept_next_to_the_measurements(self) -> None:
        run_step(StepName.VALIDATE, self.task, self.work_dir)

        quality = self.uploaded_json()[DATA_QUALITY_ARTIFACT]

        self.assertIs(quality["passed"], True)

    def test_a_dataset_that_fails_the_quality_contract_stops_the_run(self) -> None:
        broken = usable_rows()
        broken[0]["equipment_id"] = "EQ-99"
        self.write_dataset(broken)

        with self.assertRaises(PipelineError) as raised:
            run_step(StepName.VALIDATE, self.task, self.work_dir)

        self.assertIn("EQ-99", str(raised.exception))

    def test_why_a_dataset_was_refused_is_still_recorded(self) -> None:
        broken = usable_rows()
        broken[0]["equipment_id"] = "EQ-99"
        self.write_dataset(broken)

        with contextlib.suppress(PipelineError):
            run_step(StepName.VALIDATE, self.task, self.work_dir)

        quality = self.uploaded_json()[DATA_QUALITY_ARTIFACT]

        self.assertIs(quality["passed"], False)

    def test_a_refused_dataset_never_reaches_the_next_step(self) -> None:
        broken = usable_rows()
        broken[0]["equipment_id"] = "EQ-99"
        self.write_dataset(broken)

        with contextlib.suppress(PipelineError):
            run_step(StepName.VALIDATE, self.task, self.work_dir)

        self.task.record.assert_not_called()

    def test_where_the_dataset_came_from_is_recorded(self) -> None:
        run_step(StepName.VALIDATE, self.task, self.work_dir)

        links = self.uploaded_json()[LINEAGE_ARTIFACT]["links"]
        assert isinstance(links, list)

        self.assertEqual([link["stage"] for link in links], ["raw", "training"])

    def test_the_training_dataset_names_the_versions_it_was_built_on(self) -> None:
        run_step(StepName.VALIDATE, self.task, self.work_dir)

        links = self.uploaded_json()[LINEAGE_ARTIFACT]["links"]
        assert isinstance(links, list)
        training = links[-1]

        self.assertEqual(training["identifier"], "dataset-id")
        self.assertEqual(training["sources"], ["parent-dataset-id"])

    def test_nothing_is_compared_when_no_earlier_version_was_named(self) -> None:
        run_step(StepName.VALIDATE, self.task, self.work_dir)

        self.assertNotIn(DATA_DRIFT_ARTIFACT, self.uploaded_json())

    def test_a_dataset_version_that_was_not_given_stops_the_run(self) -> None:
        self.task.parameters = dict(CONNECTED_INPUTS)

        with self.assertRaises(PipelineError):
            run_step(StepName.VALIDATE, self.task, self.work_dir)


class ValidateStepDriftTest(StepTestCase):
    """When an earlier version is named, the two are compared."""

    def setUp(self) -> None:
        super().setUp()
        self.roots = {
            "1.0.0": self.work_dir / "current",
            "0.9.0": self.work_dir / "reference",
        }
        for root in self.roots.values():
            root.mkdir()
        self.write("1.0.0", usable_rows())
        self.write("0.9.0", usable_rows())

        self.task.parameters = {
            **CONNECTED_INPUTS,
            f"{DATASET_SECTION}/dataset_version": "1.0.0",
            f"{DATA_QUALITY_SECTION}/{DRIFT_REFERENCE_PARAMETER}": "0.9.0",
        }
        patcher = mock.patch.object(
            steps_module,
            "fetch_dataset",
            mock.MagicMock(name="fetch_dataset", side_effect=self._fetch),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fetch(self, config: object) -> FetchedDataset:
        version = str(getattr(config, "dataset_version", "1.0.0"))
        return FetchedDataset(
            dataset_id=f"dataset-{version}",
            dataset_project="Semiconductor Quality Prediction",
            dataset_name="semiconductor-quality-data",
            dataset_version=version,
            local_root=self.roots[version],
            parents=(),
        )

    def write(self, version: str, rows: list[dict[str, str]]) -> None:
        path = self.roots[version] / "semiconductor_quality.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(REQUIRED_COLUMNS))
            writer.writeheader()
            writer.writerows({column: row[column] for column in REQUIRED_COLUMNS} for row in rows)

    def moved_rows(self) -> list[dict[str, str]]:
        moved = usable_rows()
        for row in moved:
            row["temperature"] = str(float(row["temperature"]) - 100)
        return moved

    def test_the_comparison_is_kept_as_an_artifact(self) -> None:
        run_step(StepName.VALIDATE, self.task, self.work_dir)

        self.assertIn(DATA_DRIFT_ARTIFACT, self.uploaded_json())

    def test_a_version_compared_with_itself_reports_no_drift(self) -> None:
        run_step(StepName.VALIDATE, self.task, self.work_dir)

        self.assertIs(self.uploaded_json()[DATA_DRIFT_ARTIFACT]["has_drifted"], False)

    def test_a_dataset_that_moved_is_reported(self) -> None:
        self.write("0.9.0", self.moved_rows())

        run_step(StepName.VALIDATE, self.task, self.work_dir)

        self.assertIs(self.uploaded_json()[DATA_DRIFT_ARTIFACT]["has_drifted"], True)

    def test_a_dataset_that_moved_does_not_stop_the_run(self) -> None:
        self.write("0.9.0", self.moved_rows())

        run_step(StepName.VALIDATE, self.task, self.work_dir)

        self.task.record.assert_called_once()

    def test_a_dataset_that_moved_is_marked_so_it_can_be_found_again(self) -> None:
        self.write("0.9.0", self.moved_rows())

        run_step(StepName.VALIDATE, self.task, self.work_dir)

        self.task.tag.assert_called_once_with("data-drift")
        self.task.warn.assert_called_once()

    def test_a_dataset_that_did_not_move_is_not_marked(self) -> None:
        run_step(StepName.VALIDATE, self.task, self.work_dir)

        self.task.tag.assert_not_called()


class PreprocessStepTest(StepTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.task.parameters_of.return_value = {
            f"{RESOLVED_DATASET_SECTION}/dataset_id": "dataset-id",
        }
        self.training_input = mock.MagicMock(name="training input")

        for name, replacement in (
            ("fetch_dataset_by_id", mock.MagicMock(name="fetch_dataset_by_id")),
            (
                "load_training_input",
                mock.MagicMock(name="load_training_input", return_value=self.training_input),
            ),
            (
                "split_training_input",
                mock.MagicMock(name="split_training_input", return_value=self.split),
            ),
        ):
            patcher = mock.patch.object(steps_module, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_the_rows_that_were_approved_are_the_rows_that_are_read(self) -> None:
        run_step(StepName.PREPROCESS, self.task, self.work_dir)

        steps_module.fetch_dataset_by_id.assert_called_once()  # type: ignore[attr-defined]
        self.assertEqual(
            steps_module.fetch_dataset_by_id.call_args.args[0],  # type: ignore[attr-defined]
            "dataset-id",
        )

    def test_the_split_is_handed_on_as_a_file(self) -> None:
        run_step(StepName.PREPROCESS, self.task, self.work_dir)

        self.assertIn(SPLIT_ARTIFACT, self.uploaded_files())

    def test_the_composition_of_the_split_is_readable_without_the_file(self) -> None:
        run_step(StepName.PREPROCESS, self.task, self.work_dir)

        summary = self.uploaded_json()[SPLIT_SUMMARY_ARTIFACT]

        self.assertEqual(sorted(summary), ["test", "train", "validation"])


if __name__ == "__main__":
    unittest.main()

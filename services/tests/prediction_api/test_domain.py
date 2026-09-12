from __future__ import annotations

import unittest

from ml.model_lifecycle.domain import ModelStage
from ml.semiconductor_quality.domain import FEATURE_COLUMNS
from services.prediction_api.domain import (
    MAXIMUM_BATCH_SIZE,
    SERVED_STAGE,
    ModelMismatchError,
    ModelUnavailableError,
    Prediction,
    PredictionBatch,
    ServedModel,
    feature_row,
    require_contract,
    require_labels,
    require_servable,
)


def build_model(stage: ModelStage = ModelStage.PRODUCTION) -> ServedModel:
    return ServedModel(
        model_id="model-id",
        model_version="1.0.0-20260908T043015Z-abcdef01",
        stage=stage,
        dataset_id="dataset-id",
        dataset_version="1.0.0",
        train_task_id="train-task",
        predict=lambda rows: PredictionBatch(labels=tuple("pass" for _ in rows)),
    )


class ServableStageTest(unittest.TestCase):
    def test_only_a_promoted_model_may_be_served(self) -> None:
        self.assertEqual(SERVED_STAGE, ModelStage.PRODUCTION)
        require_servable(ModelStage.PRODUCTION)

    def test_a_model_that_was_never_promoted_is_refused(self) -> None:
        for stage in (ModelStage.CANDIDATE, ModelStage.STAGING, ModelStage.ARCHIVED):
            with self.subTest(stage=stage), self.assertRaises(ModelUnavailableError) as raised:
                require_servable(stage)

            self.assertIn(str(stage), str(raised.exception))


class ContractCheckTest(unittest.TestCase):
    def test_a_model_fitted_on_the_contract_is_accepted(self) -> None:
        require_contract(FEATURE_COLUMNS)

    def test_a_model_fitted_on_other_columns_is_refused(self) -> None:
        with self.assertRaises(ModelMismatchError) as raised:
            require_contract(("temperature", "pressure"))

        self.assertIn("temperature", str(raised.exception))

    def test_a_model_whose_columns_are_in_another_order_is_refused(self) -> None:
        reordered = (FEATURE_COLUMNS[-1], *FEATURE_COLUMNS[:-1])

        with self.assertRaises(ModelMismatchError):
            require_contract(reordered)

    def test_a_model_answering_the_published_labels_is_accepted(self) -> None:
        require_labels(["pass", "fail"])

    def test_a_model_answering_something_else_is_refused(self) -> None:
        with self.assertRaises(ModelMismatchError) as raised:
            require_labels(["pass", "rework"])

        self.assertIn("rework", str(raised.exception))


class FeatureRowTest(unittest.TestCase):
    def test_a_request_is_laid_out_in_the_order_the_model_expects(self) -> None:
        values = {column: index for index, column in enumerate(FEATURE_COLUMNS)}

        self.assertEqual(feature_row(values), tuple(range(len(FEATURE_COLUMNS))))

    def test_a_request_missing_a_column_is_refused(self) -> None:
        values = dict.fromkeys(FEATURE_COLUMNS[:-1], 0)

        with self.assertRaises(KeyError):
            feature_row(values)


class ServedModelTest(unittest.TestCase):
    def test_the_answer_can_be_traced_back_to_the_model_that_gave_it(self) -> None:
        described = build_model().describe()

        self.assertEqual(
            sorted(described),
            [
                "dataset_id",
                "dataset_version",
                "model_id",
                "model_version",
                "stage",
                "train_task_id",
            ],
        )

    def test_a_batch_without_confidence_reports_none_rather_than_a_number(self) -> None:
        batch = PredictionBatch(labels=("pass", "fail"))

        self.assertIsNone(batch.confidence_at(0))

    def test_a_batch_with_confidence_reports_it_per_row(self) -> None:
        batch = PredictionBatch(labels=("pass", "fail"), confidences=(0.9, 0.7))

        self.assertEqual(batch.confidence_at(1), 0.7)


class BatchSizeTest(unittest.TestCase):
    def test_one_call_cannot_occupy_the_service_without_a_limit(self) -> None:
        self.assertGreater(MAXIMUM_BATCH_SIZE, 0)
        self.assertLessEqual(MAXIMUM_BATCH_SIZE, 1_000)


class PredictionTest(unittest.TestCase):
    def test_an_answer_names_the_product_it_is_about(self) -> None:
        prediction = Prediction(sample_id="SAMPLE-00001", label="fail", confidence=0.81)

        self.assertEqual(prediction.sample_id, "SAMPLE-00001")
        self.assertEqual(prediction.label, "fail")


if __name__ == "__main__":
    unittest.main()

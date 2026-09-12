from __future__ import annotations

import io
import json
import logging
import unittest
from collections.abc import Sequence
from unittest import mock

from fastapi.testclient import TestClient
from httpx import Response

from ml.model_lifecycle.domain import ModelStage
from ml.observability.logging import configure_logging
from ml.security.domain import Role
from services.prediction_api import app as app_module
from services.prediction_api.app import create_app
from services.prediction_api.config import ServiceConfig
from services.prediction_api.domain import (
    SERVICE_NAME,
    ModelUnavailableError,
    PredictionBatch,
    ServedModel,
)
from services.tests.credentials import access_policy, headers


VALID_MEASUREMENT = {
    "sample_id": "SAMPLE-00001",
    "equipment_id": "EQ-01",
    "process_step": "ETCH",
    "temperature": 415.2,
    "pressure": 12.5,
    "process_time": 60.0,
    "gas_flow": 32.5,
    "sensor_1": 0.42,
    "sensor_2": -0.13,
    "inspection_value": 8.75,
}


class RecordingModel:
    """A model that answers a fixed verdict and remembers what it was asked."""

    def __init__(self, labels: Sequence[str], confidences: Sequence[float] | None = None) -> None:
        self.labels = tuple(labels)
        self.confidences = tuple(confidences) if confidences is not None else None
        self.asked: list[Sequence[Sequence[object]]] = []

    def __call__(self, rows: Sequence[Sequence[object]]) -> PredictionBatch:
        self.asked.append(rows)
        return PredictionBatch(labels=self.labels, confidences=self.confidences)


def build_served(predict: object) -> ServedModel:
    return ServedModel(
        model_id="model-id",
        model_version="1.0.0-20260908T043015Z-abcdef01",
        stage=ModelStage.PRODUCTION,
        dataset_id="dataset-id",
        dataset_version="1.0.0",
        train_task_id="train-task",
        predict=predict,  # type: ignore[arg-type]
        training_failure_share=0.38,
    )


class ServiceTestCase(unittest.TestCase):
    """Replaces the registry, so no ClearML Server is contacted."""

    def setUp(self) -> None:
        # サービスは起動時にルートロガーを構造化ログへ張り替える。テストの
        # 出力を実行ログで埋めないよう、この間だけ黙らせる。
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

        self.model = RecordingModel(labels=("pass",), confidences=(0.87,))
        self.served = build_served(self.model)
        self.load = mock.MagicMock(name="load_served_model", return_value=self.served)
        patcher = mock.patch.object(app_module, "load_served_model", self.load)
        patcher.start()
        self.addCleanup(patcher.stop)

    def client(self, role: Role = Role.PREDICTOR) -> TestClient:
        """A client that already carries the credential of one caller."""
        return TestClient(
            create_app(ServiceConfig(clients=access_policy())),
            headers=headers(role),
        )


class HealthTest(ServiceTestCase):
    def test_being_alive_does_not_depend_on_the_model(self) -> None:
        with self.client() as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "alive")

    def test_being_ready_reports_the_model_that_is_serving(self) -> None:
        with self.client() as client:
            response = client.get("/ready")

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "ready")
        self.assertEqual(body["model"]["model_version"], self.served.model_version)
        self.assertEqual(body["model"]["stage"], "production")


class PredictionTest(ServiceTestCase):
    def post(self, client: TestClient, **overrides: object) -> Response:
        measurement = {**VALID_MEASUREMENT, **overrides}
        answered: Response = client.post("/predict", json={"measurements": [measurement]})
        return answered

    def test_a_valid_request_is_answered(self) -> None:
        with self.client() as client:
            response = self.post(client)

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["predictions"][0]["label"], "pass")
        self.assertEqual(body["predictions"][0]["sample_id"], "SAMPLE-00001")

    def test_every_answer_names_the_model_that_gave_it(self) -> None:
        with self.client() as client:
            response = self.post(client)

        self.assertEqual(response.json()["model"]["model_id"], "model-id")
        self.assertEqual(
            response.json()["model"]["model_version"],
            "1.0.0-20260908T043015Z-abcdef01",
        )

    def test_the_model_is_asked_in_the_column_order_of_the_contract(self) -> None:
        with self.client() as client:
            self.post(client)

        row = self.model.asked[0][0]
        self.assertEqual(row[0], VALID_MEASUREMENT["temperature"])
        self.assertEqual(row[-2], VALID_MEASUREMENT["equipment_id"])
        self.assertEqual(row[-1], VALID_MEASUREMENT["process_step"])

    def test_confidence_is_reported_when_the_model_gives_one(self) -> None:
        with self.client() as client:
            response = self.post(client)

        self.assertEqual(response.json()["predictions"][0]["confidence"], 0.87)

    def test_confidence_is_absent_rather_than_invented(self) -> None:
        self.model.confidences = None

        with self.client() as client:
            response = self.post(client)

        self.assertIsNone(response.json()["predictions"][0]["confidence"])

    def test_a_batch_is_answered_in_one_call_to_the_model(self) -> None:
        self.model.labels = ("pass", "fail")
        self.model.confidences = (0.87, 0.62)

        with self.client() as client:
            response = client.post(
                "/predict",
                json={
                    "measurements": [
                        VALID_MEASUREMENT,
                        {**VALID_MEASUREMENT, "sample_id": "SAMPLE-00002"},
                    ]
                },
            )

        self.assertEqual(len(self.model.asked), 1)
        self.assertEqual(
            [answer["label"] for answer in response.json()["predictions"]],
            ["pass", "fail"],
        )


class InvalidRequestTest(ServiceTestCase):
    def post(self, client: TestClient, **overrides: object) -> Response:
        measurement = {**VALID_MEASUREMENT, **overrides}
        answered: Response = client.post("/predict", json={"measurements": [measurement]})
        return answered

    def test_a_missing_column_is_rejected_with_a_reason(self) -> None:
        without_temperature = {
            name: value for name, value in VALID_MEASUREMENT.items() if name != "temperature"
        }

        with self.client() as client:
            response = client.post("/predict", json={"measurements": [without_temperature]})

        self.assertEqual(response.status_code, 422)
        self.assertIn("temperature", response.text)

    def test_a_value_that_cannot_be_a_measurement_is_rejected(self) -> None:
        with self.client() as client:
            response = self.post(client, pressure=-1)

        self.assertEqual(response.status_code, 422)

    def test_a_value_of_the_wrong_kind_is_rejected(self) -> None:
        with self.client() as client:
            response = self.post(client, temperature="warm")

        self.assertEqual(response.status_code, 422)

    def test_an_unexpected_column_is_rejected_rather_than_ignored(self) -> None:
        with self.client() as client:
            response = self.post(client, wafer_lot="LOT-1")

        self.assertEqual(response.status_code, 422)

    def test_an_empty_batch_is_rejected(self) -> None:
        with self.client() as client:
            response = client.post("/predict", json={"measurements": []})

        self.assertEqual(response.status_code, 422)

    def test_a_batch_beyond_the_limit_is_rejected(self) -> None:
        with self.client() as client:
            response = client.post(
                "/predict",
                json={"measurements": [VALID_MEASUREMENT] * 501},
            )

        self.assertEqual(response.status_code, 422)

    def test_a_rejected_request_never_reaches_the_model(self) -> None:
        with self.client() as client:
            self.post(client, pressure=-1)

        self.assertEqual(self.model.asked, [])


class ObservabilityTest(ServiceTestCase):
    """Every request is identifiable, and everything about it is counted."""

    def test_a_caller_is_given_something_to_quote_when_reporting_a_problem(self) -> None:
        with self.client() as client:
            response = client.get("/health")

        self.assertTrue(response.headers.get("X-Correlation-Id"))

    def test_an_identifier_the_caller_brought_is_kept(self) -> None:
        with self.client() as client:
            response = client.get("/health", headers={"X-Correlation-Id": "given-id"})

        self.assertEqual(response.headers.get("X-Correlation-Id"), "given-id")

    def test_the_numbers_are_published_in_the_format_prometheus_reads(self) -> None:
        with self.client() as client:
            client.get("/health")
            response = client.get("/metrics", headers=headers(Role.OPERATOR))

        self.assertEqual(response.status_code, 200)
        self.assertIn("prediction_requests_total", response.text)

    def test_answered_requests_are_counted_as_successes(self) -> None:
        with self.client() as client:
            client.get("/health")
            metrics = client.get("/metrics", headers=headers(Role.OPERATOR)).text

        self.assertIn('endpoint="/health",outcome="success"', metrics)

    def test_a_rejected_request_is_counted_apart_from_a_broken_service(self) -> None:
        with self.client() as client:
            client.post("/predict", json={"measurements": []})
            metrics = client.get("/metrics", headers=headers(Role.OPERATOR)).text

        self.assertIn('outcome="invalid"', metrics)
        self.assertNotIn('outcome="unavailable"', metrics)

    def test_a_service_that_cannot_answer_is_counted_as_unavailable(self) -> None:
        def failing(_rows: Sequence[Sequence[object]]) -> PredictionBatch:
            raise RuntimeError("the model ran out of memory")

        self.load.return_value = build_served(failing)

        with self.client() as client:
            client.post("/predict", json={"measurements": [VALID_MEASUREMENT]})
            metrics = client.get("/metrics", headers=headers(Role.OPERATOR)).text

        self.assertIn('outcome="unavailable"', metrics)

    def test_how_long_a_request_took_is_measured(self) -> None:
        with self.client() as client:
            client.get("/health")
            metrics = client.get("/metrics", headers=headers(Role.OPERATOR)).text

        self.assertIn("prediction_request_seconds_bucket", metrics)

    def test_what_the_model_answered_is_counted_by_label(self) -> None:
        with self.client() as client:
            client.post("/predict", json={"measurements": [VALID_MEASUREMENT]})
            metrics = client.get("/metrics", headers=headers(Role.OPERATOR)).text

        self.assertIn('predictions_total{label="pass"}', metrics)

    def test_the_share_of_failures_being_predicted_is_published(self) -> None:
        self.model.labels = ("fail",)
        self.model.confidences = (0.9,)

        with self.client() as client:
            client.post("/predict", json={"measurements": [VALID_MEASUREMENT]})
            metrics = client.get("/metrics", headers=headers(Role.OPERATOR)).text

        self.assertIn("predicted_failure_share 1.0", metrics)

    def test_what_the_model_was_trained_to_expect_is_published(self) -> None:
        with self.client() as client:
            client.get("/health")
            metrics = client.get("/metrics", headers=headers(Role.OPERATOR)).text

        self.assertIn("training_failure_share 0.38", metrics)

    def test_a_serving_process_says_so(self) -> None:
        with self.client() as client:
            client.get("/health")
            metrics = client.get("/metrics", headers=headers(Role.OPERATOR)).text

        self.assertIn("prediction_model_loaded 1.0", metrics)


class StructuredLogTest(ServiceTestCase):
    """1件の応答から、答えたモデルとそれを作った学習まで辿れる。"""

    def logged(self, send: object) -> list[dict[str, object]]:
        """Capture the lines written while the request is answered."""
        stream = io.StringIO()
        with self.client() as client:
            # 起動時のログは黙らせたまま、応答の1件だけを捕まえる。
            logging.disable(logging.NOTSET)
            configure_logging(stream=stream)
            try:
                send(client)  # type: ignore[operator]
            finally:
                logging.disable(logging.CRITICAL)
        written = [json.loads(line) for line in stream.getvalue().splitlines() if line]
        # テストクライアント自身（httpx）も同じrootロガーへ書く。サービスが
        # 書いた行だけを見る。
        return [line for line in written if line["logger"] == SERVICE_NAME]

    def test_every_line_carries_the_identifier_the_caller_was_given(self) -> None:
        lines = self.logged(
            lambda client: client.get("/health", headers={"X-Correlation-Id": "given-id"}),
        )

        self.assertTrue(lines)
        for line in lines:
            self.assertEqual(line["correlation_id"], "given-id")

    def test_a_prediction_names_the_model_and_the_task_that_produced_it(self) -> None:
        lines = self.logged(
            lambda client: client.post("/predict", json={"measurements": [VALID_MEASUREMENT]}),
        )

        [judged] = [line for line in lines if line["message"] == "products judged"]
        self.assertEqual(judged["model_version"], self.served.model_version)
        self.assertEqual(judged["dataset_version"], self.served.dataset_version)
        self.assertEqual(judged["task_id"], self.served.train_task_id)

    def test_a_line_written_before_a_model_answered_claims_no_model(self) -> None:
        """空文字で埋めると「モデルが無い」と「名前が空」が同じに見える。"""
        lines = self.logged(lambda client: client.get("/health"))

        [answered] = [line for line in lines if line["message"] == "request answered"]
        self.assertNotIn("model_version", answered)
        self.assertNotIn("task_id", answered)


class ModelFailureTest(ServiceTestCase):
    def test_a_model_that_fails_is_reported_as_unavailable(self) -> None:
        def failing(_rows: Sequence[Sequence[object]]) -> PredictionBatch:
            raise RuntimeError("the model ran out of memory")

        self.load.return_value = build_served(failing)

        with self.client() as client:
            response = client.post("/predict", json={"measurements": [VALID_MEASUREMENT]})

        self.assertEqual(response.status_code, 503)
        self.assertIn("ran out of memory", response.json()["detail"])

    def test_a_model_that_answers_the_wrong_number_of_times_is_refused(self) -> None:
        self.load.return_value = build_served(RecordingModel(labels=("pass", "fail")))

        with self.client() as client:
            response = client.post("/predict", json={"measurements": [VALID_MEASUREMENT]})

        self.assertEqual(response.status_code, 503)
        self.assertIn("answered 2 times", response.json()["detail"])

    def test_answers_and_confidences_that_do_not_line_up_are_refused(self) -> None:
        mismatched = RecordingModel(labels=("pass", "fail"), confidences=(0.9,))
        self.load.return_value = build_served(mismatched)

        with self.client() as client:
            response = client.post(
                "/predict",
                json={
                    "measurements": [
                        VALID_MEASUREMENT,
                        {**VALID_MEASUREMENT, "sample_id": "SAMPLE-00002"},
                    ]
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("confidences", response.json()["detail"])

    def test_a_process_without_a_model_never_starts_serving(self) -> None:
        self.load.side_effect = ModelUnavailableError("no model is marked production")

        with self.assertRaises(ModelUnavailableError), self.client():
            pass


if __name__ == "__main__":
    unittest.main()

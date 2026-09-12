"""Who may call which endpoint, checked through the real services.

These are the tests that answer "can we show that permissions are enforced".
They deliberately go through the HTTP layer of both services rather than
asking the policy directly: a permission that is enforced in the policy but
forgotten on a route is exactly the failure worth catching, and only a request
sees it.

The matrix is written out in full, allowed and refused alike. A table that
only lists what is allowed cannot show that anything is denied.
"""

from __future__ import annotations

import io
import json
import logging
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from unittest import mock

from fastapi.testclient import TestClient
from httpx import Response

from ml.model_lifecycle.domain import ModelStage
from ml.observability.logging import configure_logging
from ml.security.credentials import AccessPolicy, fingerprint, issue_token
from ml.security.domain import Principal, Role
from services.ops_exporter.app import create_app as create_exporter
from services.ops_exporter.config import OpsExporterConfig
from services.ops_exporter.domain import TaskOutcomes, summarise
from services.prediction_api import app as prediction_app_module
from services.prediction_api.app import create_app as create_prediction_api
from services.prediction_api.config import ServiceConfig
from services.prediction_api.domain import PredictionBatch, ServedModel
from services.security.http import AUDIT_LOGGER_NAME, AUTHENTICATE_HEADER
from services.tests.credentials import UNKNOWN_TOKEN, access_policy, headers


MEASUREMENT = {
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

ANONYMOUS: dict[str, str] = {}
UNKNOWN = {"Authorization": f"Bearer {UNKNOWN_TOKEN}"}

OK = 200
UNAUTHORIZED = 401
FORBIDDEN = 403


def served_model() -> ServedModel:
    return ServedModel(
        model_id="model-id",
        model_version="1.0.0-20260908T043015Z-abcdef01",
        stage=ModelStage.PRODUCTION,
        dataset_id="dataset-id",
        dataset_version="1.0.0",
        train_task_id="train-task",
        predict=lambda rows: PredictionBatch(labels=("pass",) * len(rows), confidences=None),
        training_failure_share=0.38,
    )


class StubOps:
    def read(self) -> object:
        return summarise(
            {"semiconductor-training": 0},
            {"semiconductor-training": 1},
            [TaskOutcomes(project="Semiconductor Quality Prediction", completed=1, failed=0)],
        )


class AuthorizationTestCase(unittest.TestCase):
    """Both services, with one caller per role and no server behind them."""

    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        patcher = mock.patch.object(
            prediction_app_module,
            "load_served_model",
            mock.MagicMock(return_value=served_model()),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def prediction_client(self, policy: AccessPolicy | None = None) -> TestClient:
        return TestClient(create_prediction_api(ServiceConfig(clients=policy or access_policy())))

    def exporter_client(self) -> TestClient:
        return TestClient(
            create_exporter(OpsExporterConfig(clients=access_policy()), source=StubOps())
        )


class PredictionServiceMatrixTest(AuthorizationTestCase):
    """すべての組み合わせを、許可も拒否も同じ表に書く。"""

    def call(self, client: TestClient, endpoint: str, sent: dict[str, str]) -> int:
        answered: Response
        if endpoint == "/predict":
            answered = client.post(
                "/predict",
                json={"measurements": [MEASUREMENT]},
                headers=sent,
            )
        else:
            answered = client.get(endpoint, headers=sent)
        return answered.status_code

    def test_every_caller_gets_exactly_what_its_role_allows(self) -> None:
        expected = {
            # 生存確認だけは資格情報を要らない。プロセスを再起動する側が
            # 資格情報の期限切れで再起動ループに入るのを避けるためである。
            ("/health", "anonymous"): OK,
            ("/health", "predictor"): OK,
            ("/ready", "anonymous"): UNAUTHORIZED,
            ("/ready", "unknown"): UNAUTHORIZED,
            ("/ready", "predictor"): OK,
            ("/ready", "operator"): OK,
            ("/ready", "scraper"): FORBIDDEN,
            ("/predict", "anonymous"): UNAUTHORIZED,
            ("/predict", "unknown"): UNAUTHORIZED,
            ("/predict", "predictor"): OK,
            ("/predict", "operator"): FORBIDDEN,
            ("/predict", "scraper"): FORBIDDEN,
            ("/metrics", "anonymous"): UNAUTHORIZED,
            ("/metrics", "unknown"): UNAUTHORIZED,
            ("/metrics", "predictor"): FORBIDDEN,
            ("/metrics", "operator"): OK,
            ("/metrics", "scraper"): OK,
        }

        with self.prediction_client() as client:
            for (endpoint, caller), status in expected.items():
                with self.subTest(endpoint=endpoint, caller=caller):
                    self.assertEqual(self.call(client, endpoint, _sent_by(caller)), status)


class OpsExporterMatrixTest(AuthorizationTestCase):
    def test_only_a_caller_granted_the_metrics_may_read_them(self) -> None:
        expected = {
            ("/health", "anonymous"): OK,
            ("/metrics", "anonymous"): UNAUTHORIZED,
            ("/metrics", "unknown"): UNAUTHORIZED,
            ("/metrics", "predictor"): FORBIDDEN,
            ("/metrics", "operator"): OK,
            ("/metrics", "scraper"): OK,
        }

        with self.exporter_client() as client:
            for (endpoint, caller), status in expected.items():
                with self.subTest(endpoint=endpoint, caller=caller):
                    response = client.get(endpoint, headers=_sent_by(caller))
                    self.assertEqual(response.status_code, status)

    def test_a_refused_reading_never_reaches_clearml(self) -> None:
        """拒否は入口で終わる。断られた呼び出しが裏側を動かしてはならない。"""
        with self.exporter_client() as client:
            response = client.get("/metrics", headers=_sent_by("predictor"))

        self.assertEqual(response.status_code, FORBIDDEN)
        self.assertNotIn("clearml_reachable", response.text)


class RefusalTest(AuthorizationTestCase):
    """断り方が、次にすべきことを語るか。"""

    def test_an_unauthenticated_caller_is_told_how_to_authenticate(self) -> None:
        with self.prediction_client() as client:
            response = client.get("/ready")

        self.assertEqual(response.status_code, UNAUTHORIZED)
        self.assertIn("Bearer", response.headers.get(AUTHENTICATE_HEADER, ""))

    def test_a_known_caller_without_the_permission_is_not_asked_to_authenticate(self) -> None:
        """403に認証の要求を返すと、資格情報の問題として調べ続けることになる。"""
        with self.prediction_client() as client:
            response = client.post(
                "/predict",
                json={"measurements": [MEASUREMENT]},
                headers=headers(Role.OPERATOR),
            )

        self.assertEqual(response.status_code, FORBIDDEN)
        self.assertNotIn(AUTHENTICATE_HEADER, response.headers)

    def test_the_reason_names_the_role_and_the_permission(self) -> None:
        with self.prediction_client() as client:
            response = client.post(
                "/predict",
                json={"measurements": [MEASUREMENT]},
                headers=headers(Role.OPERATOR),
            )

        detail = response.json()["detail"]
        self.assertIn("operator", detail)
        self.assertIn("predict", detail)

    def test_another_authentication_scheme_is_not_compared_as_a_credential(self) -> None:
        with self.prediction_client() as client:
            response = client.get("/ready", headers={"Authorization": "Basic dXNlcjpwYXNz"})

        self.assertEqual(response.status_code, UNAUTHORIZED)

    def test_a_refused_request_is_not_answered_with_the_model(self) -> None:
        with self.prediction_client() as client:
            response = client.get("/ready", headers=UNKNOWN)

        self.assertNotIn("model_version", response.text)


class CredentialRotationTest(AuthorizationTestCase):
    """入れ替えの最中に「有効な資格情報が無い瞬間」を作らない。"""

    def test_both_the_old_and_the_new_credential_work_during_a_rotation(self) -> None:
        old, new = issue_token(), issue_token()
        policy = AccessPolicy(
            principals=(
                Principal(
                    name="batch-scoring",
                    role=Role.PREDICTOR,
                    credential_fingerprints=(fingerprint(old), fingerprint(new)),
                ),
            )
        )

        with self.prediction_client(policy) as client:
            for token in (old, new):
                with self.subTest(credential="old" if token is old else "new"):
                    response = client.get("/ready", headers={"Authorization": f"Bearer {token}"})
                    self.assertEqual(response.status_code, OK)

    def test_a_withdrawn_credential_stops_working(self) -> None:
        old, new = issue_token(), issue_token()
        policy = AccessPolicy(
            principals=(
                Principal(
                    name="batch-scoring",
                    role=Role.PREDICTOR,
                    credential_fingerprints=(fingerprint(new),),
                ),
            )
        )

        with self.prediction_client(policy) as client:
            response = client.get("/ready", headers={"Authorization": f"Bearer {old}"})

        self.assertEqual(response.status_code, UNAUTHORIZED)


class AuditTrailTest(AuthorizationTestCase):
    """事故のあとに聞かれるのは「誰が止められたか」ではなく「誰がやったか」である。"""

    @contextmanager
    def recorded(self) -> Iterator[list[dict[str, object]]]:
        """Capture the audit lines written inside the block.

        The logging is configured *after* the application was built, because
        building it configures the logging itself. Capturing before that point
        would record the start up and nothing else.
        """
        stream = io.StringIO()
        lines: list[dict[str, object]] = []
        logging.disable(logging.NOTSET)
        configure_logging(stream=stream)
        try:
            yield lines
        finally:
            logging.disable(logging.CRITICAL)
            lines.extend(
                entry
                for entry in (json.loads(line) for line in stream.getvalue().splitlines() if line)
                if entry.get("logger") == AUDIT_LOGGER_NAME
            )

    def test_an_allowed_call_is_recorded_with_who_made_it(self) -> None:
        with self.prediction_client() as client:
            with self.recorded() as lines:
                client.get("/ready", headers=headers(Role.PREDICTOR))

        allowed = [line for line in lines if line["outcome"] == "allowed"]
        self.assertTrue(allowed)
        self.assertEqual(allowed[-1]["principal"], "test-predictor")
        self.assertEqual(allowed[-1]["permission"], "model:read")
        self.assertEqual(allowed[-1]["endpoint"], "/ready")

    def test_a_refusal_says_which_of_the_three_refusals_it_was(self) -> None:
        with self.prediction_client() as client:
            with self.recorded() as lines:
                client.get("/ready")
                client.get("/ready", headers=UNKNOWN)
                client.get("/metrics", headers=headers(Role.PREDICTOR))

        self.assertEqual(
            [line["outcome"] for line in lines],
            ["missing_credential", "unknown_credential", "insufficient_role"],
        )

    def test_the_credential_itself_is_never_written_down(self) -> None:
        with self.prediction_client() as client:
            with self.recorded() as lines:
                client.get("/ready", headers=headers(Role.PREDICTOR))
                client.get("/ready", headers=UNKNOWN)

        written = json.dumps(lines)
        self.assertNotIn(UNKNOWN_TOKEN, written)
        self.assertNotIn("stk_", written)


def _sent_by(caller: str) -> dict[str, str]:
    if caller == "anonymous":
        return ANONYMOUS
    if caller == "unknown":
        return UNKNOWN
    return headers(Role(caller))


if __name__ == "__main__":
    unittest.main()

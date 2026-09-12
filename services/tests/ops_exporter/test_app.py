from __future__ import annotations

import logging
import unittest

from fastapi.testclient import TestClient

from ml.security.domain import Role
from services.ops_exporter.app import create_app
from services.ops_exporter.config import OpsExporterConfig
from services.ops_exporter.domain import TaskOutcomes, summarise
from services.tests.credentials import access_policy, headers


class StubSource:
    """A reading that is decided by the test, so no server is contacted."""

    def __init__(self) -> None:
        self.snapshot = summarise(
            {"semiconductor-training": 2, "semiconductor-pipeline": 0},
            {"semiconductor-training": 1, "semiconductor-pipeline": 1},
            [TaskOutcomes(project="Semiconductor Quality Prediction", completed=4, failed=1)],
        )
        self.failure: Exception | None = None
        self.reads = 0

    def read(self) -> object:
        self.reads += 1
        if self.failure is not None:
            raise self.failure
        return self.snapshot


class ExporterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        self.source = StubSource()

    def client(self, role: Role = Role.SCRAPER) -> TestClient:
        """A client that already carries the credential Prometheus would use."""
        return TestClient(
            create_app(OpsExporterConfig(clients=access_policy()), source=self.source),
            headers=headers(role),
        )

    def metrics(self) -> str:
        with self.client() as client:
            exposed: str = client.get("/metrics").text
        return exposed


class HealthTest(ExporterTestCase):
    def test_being_alive_does_not_depend_on_clearml(self) -> None:
        with self.client() as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.source.reads, 0)


class MetricsTest(ExporterTestCase):
    def test_the_reading_is_taken_when_it_is_asked_for(self) -> None:
        self.metrics()

        self.assertEqual(self.source.reads, 1)

    def test_how_much_work_is_waiting_is_published(self) -> None:
        self.assertIn(
            'clearml_queue_pending_tasks{queue="semiconductor-training"} 2.0',
            self.metrics(),
        )

    def test_how_many_agents_are_listening_is_published(self) -> None:
        self.assertIn(
            'clearml_queue_workers{queue="semiconductor-training"} 1.0',
            self.metrics(),
        )

    def test_recent_outcomes_are_published_per_project(self) -> None:
        metrics = self.metrics()

        self.assertIn("clearml_tasks_completed_recent", metrics)
        self.assertIn("clearml_tasks_failed_recent", metrics)

    def test_a_reachable_server_says_so(self) -> None:
        self.assertIn("clearml_reachable 1.0", self.metrics())


class UnreachableServerTest(ExporterTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.source.failure = RuntimeError("the server did not answer")

    def test_the_endpoint_still_answers(self) -> None:
        with self.client() as client:
            response = client.get("/metrics")

        self.assertEqual(response.status_code, 200)

    def test_an_unreachable_server_is_reported_as_such(self) -> None:
        self.assertIn("clearml_reachable 0.0", self.metrics())

    def test_no_queue_depth_is_invented_when_nothing_could_be_read(self) -> None:
        self.assertNotIn("clearml_queue_pending_tasks", self.metrics())


if __name__ == "__main__":
    unittest.main()

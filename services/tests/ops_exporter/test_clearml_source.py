from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest import mock

from services.ops_exporter import clearml_source as source_module
from services.ops_exporter.clearml_source import MAXIMUM_TASKS, ClearmlOps


PROJECT = "Semiconductor Quality Prediction"


class FakeQueues:
    def __init__(self, queues: list[Any]) -> None:
        self._queues = queues

    def get_all(self) -> list[Any]:
        return self._queues


class FakeWorkers:
    def __init__(self, workers: list[Any]) -> None:
        self._workers = workers

    def get_all(self) -> list[Any]:
        return self._workers


class FakeProjects:
    def __init__(self, found: list[Any]) -> None:
        self._found = found
        self.asked: list[dict[str, Any]] = []

    def get_all(self, **arguments: Any) -> list[Any]:
        self.asked.append(arguments)
        return self._found


class FakeTasks:
    def __init__(self, tasks: list[Any]) -> None:
        self._tasks = tasks
        self.asked: list[dict[str, Any]] = []

    def get_all(self, **arguments: Any) -> list[Any]:
        self.asked.append(arguments)
        return self._tasks


class FakeClient:
    """A ClearML Server that answers what the test decided."""

    def __init__(
        self,
        queues: list[Any] | None = None,
        workers: list[Any] | None = None,
        projects: list[Any] | None = None,
        tasks: list[Any] | None = None,
    ) -> None:
        self.queues = FakeQueues(queues or [])
        self.workers = FakeWorkers(workers or [])
        known = projects if projects is not None else [SimpleNamespace(id="p")]
        self.projects = FakeProjects(known)
        self.tasks = FakeTasks(tasks or [])


class ClearmlSourceTestCase(unittest.TestCase):
    def read(self, client: FakeClient, **arguments: Any) -> Any:
        with mock.patch.object(source_module, "APIClient", return_value=client):
            return ClearmlOps((PROJECT,), **arguments).read()


class QueueReadingTest(ClearmlSourceTestCase):
    def test_how_much_is_waiting_is_read_from_the_entries_of_each_queue(self) -> None:
        client = FakeClient(
            queues=[
                SimpleNamespace(name="semiconductor-training", entries=["a", "b"]),
                SimpleNamespace(name="semiconductor-pipeline", entries=[]),
            ],
        )

        snapshot = self.read(client)

        depths = {queue.name: queue.queued for queue in snapshot.queues}
        self.assertEqual(depths, {"semiconductor-training": 2, "semiconductor-pipeline": 0})

    def test_a_queue_without_entries_is_empty_rather_than_unknown(self) -> None:
        client = FakeClient(queues=[SimpleNamespace(name="semiconductor-training", entries=None)])

        snapshot = self.read(client)

        self.assertEqual(snapshot.queues[0].queued, 0)

    def test_one_agent_listening_to_two_queues_counts_for_both(self) -> None:
        """次のTaskを取る者がいるかが問題であり、処理の数ではない。"""
        client = FakeClient(
            queues=[
                SimpleNamespace(name="semiconductor-training", entries=[]),
                SimpleNamespace(name="semiconductor-pipeline", entries=[]),
            ],
            workers=[
                SimpleNamespace(
                    queues=[
                        SimpleNamespace(name="semiconductor-training"),
                        SimpleNamespace(name="semiconductor-pipeline"),
                    ],
                ),
            ],
        )

        snapshot = self.read(client)

        self.assertEqual({queue.workers for queue in snapshot.queues}, {1})

    def test_an_agent_listening_to_nothing_is_not_counted_anywhere(self) -> None:
        client = FakeClient(
            queues=[SimpleNamespace(name="semiconductor-training", entries=["a"])],
            workers=[SimpleNamespace(queues=None)],
        )

        snapshot = self.read(client)

        self.assertEqual(snapshot.queues[0].workers, 0)
        self.assertEqual(snapshot.unattended_queues, snapshot.queues)


class OutcomeReadingTest(ClearmlSourceTestCase):
    def test_recently_finished_tasks_are_counted_by_how_they_ended(self) -> None:
        client = FakeClient(
            tasks=[
                SimpleNamespace(id="1", status="completed"),
                SimpleNamespace(id="2", status="failed"),
                SimpleNamespace(id="3", status="completed"),
            ],
        )

        snapshot = self.read(client)

        self.assertEqual(snapshot.outcomes[0].project, PROJECT)
        self.assertEqual(snapshot.outcomes[0].completed, 2)
        self.assertEqual(snapshot.outcomes[0].failed, 1)

    def test_a_project_that_does_not_exist_is_reported_as_no_outcomes(self) -> None:
        """名前を間違えた監視は、静かな成功と見分けが付かなければならない。"""
        client = FakeClient(projects=[])

        snapshot = self.read(client)

        self.assertEqual(snapshot.outcomes[0].total, 0)
        self.assertEqual(client.tasks.asked, [])

    def test_only_finished_tasks_of_the_watched_project_are_asked_for(self) -> None:
        client = FakeClient()

        self.read(client)

        asked = client.tasks.asked[0]
        self.assertEqual(asked["project"], ["p"])
        self.assertEqual(asked["status"], ["completed", "failed"])
        self.assertEqual(asked["page_size"], MAXIMUM_TASKS)

    def test_the_window_asked_for_is_the_one_the_exporter_was_given(self) -> None:
        client = FakeClient()

        self.read(client, recent_minutes=5)

        [condition] = client.tasks.asked[0]["status_changed"]
        self.assertTrue(condition.startswith(">="))

    def test_the_project_is_matched_by_name_rather_than_by_prefix(self) -> None:
        client = FakeClient()

        self.read(client)

        self.assertEqual(client.projects.asked[0]["name"], f"^{PROJECT}")


if __name__ == "__main__":
    unittest.main()

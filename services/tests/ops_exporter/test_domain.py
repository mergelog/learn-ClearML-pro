from __future__ import annotations

import unittest

from services.ops_exporter.domain import (
    OpsSnapshot,
    QueueDepth,
    TaskOutcomes,
    summarise,
)


class QueueDepthTest(unittest.TestCase):
    def test_a_queue_with_work_and_nobody_listening_is_unattended(self) -> None:
        self.assertTrue(QueueDepth(name="training", queued=3, workers=0).unattended)

    def test_a_queue_with_work_and_an_agent_is_merely_busy(self) -> None:
        self.assertFalse(QueueDepth(name="training", queued=3, workers=1).unattended)

    def test_an_empty_queue_without_agents_is_idle_rather_than_broken(self) -> None:
        self.assertFalse(QueueDepth(name="training", queued=0, workers=0).unattended)


class TaskOutcomeTest(unittest.TestCase):
    def test_the_share_of_failures_is_measured_over_what_finished(self) -> None:
        outcome = TaskOutcomes(project="p", completed=3, failed=1)

        self.assertEqual(outcome.total, 4)
        self.assertEqual(outcome.failure_share, 0.25)

    def test_nothing_finished_is_a_share_of_zero_rather_than_an_error(self) -> None:
        self.assertEqual(TaskOutcomes(project="p", completed=0, failed=0).failure_share, 0.0)


class SnapshotTest(unittest.TestCase):
    def test_a_queue_known_only_by_its_depth_is_still_reported(self) -> None:
        snapshot = summarise({"training": 2}, {}, [])

        self.assertEqual(snapshot.queues, (QueueDepth(name="training", queued=2, workers=0),))

    def test_a_queue_known_only_by_its_agents_is_still_reported(self) -> None:
        snapshot = summarise({}, {"training": 1}, [])

        self.assertEqual(snapshot.queues, (QueueDepth(name="training", queued=0, workers=1),))

    def test_queues_are_reported_in_a_stable_order(self) -> None:
        snapshot = summarise({"b": 1, "a": 1}, {}, [])

        self.assertEqual([queue.name for queue in snapshot.queues], ["a", "b"])

    def test_the_queues_nobody_is_listening_to_can_be_singled_out(self) -> None:
        snapshot = summarise({"training": 2, "pipeline": 1}, {"pipeline": 1}, [])

        self.assertEqual([queue.name for queue in snapshot.unattended_queues], ["training"])

    def test_a_reading_can_be_stored_as_plain_data(self) -> None:
        snapshot = summarise({"training": 2}, {"training": 1}, [TaskOutcomes("p", 3, 1)])

        document = snapshot.as_document()

        self.assertEqual(document["queues"], [{"name": "training", "queued": 2, "workers": 1}])
        self.assertEqual(document["outcomes"], [{"project": "p", "completed": 3, "failed": 1}])

    def test_an_empty_system_reads_as_empty_rather_than_as_missing(self) -> None:
        snapshot = summarise({}, {}, [])

        self.assertEqual(snapshot, OpsSnapshot(queues=(), outcomes=()))


if __name__ == "__main__":
    unittest.main()

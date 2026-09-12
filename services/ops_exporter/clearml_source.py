"""ClearML boundary of the ops exporter.

Every call into the ClearML API the exporter makes is made from here, so
:mod:`domain` decides what is worth measuring without a server.

The exporter reads and never writes. It is watching the system, and a watcher
that can change what it watches is a second way for the system to break.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from clearml.backend_api.session.client import APIClient

from .domain import DEFAULT_RECENT_MINUTES, OpsSnapshot, TaskOutcomes, summarise


COMPLETED_STATUS = "completed"
FAILED_STATUS = "failed"

# 一度に読む終了済みTaskの上限。全部読むと、履歴が伸びるほど
# 監視のほうが重くなる。
MAXIMUM_TASKS = 500


class ClearmlOps:
    """Reads how the training side of the system is doing."""

    def __init__(
        self,
        projects: Sequence[str],
        recent_minutes: int = DEFAULT_RECENT_MINUTES,
    ) -> None:
        self._projects = tuple(projects)
        self._recent_minutes = recent_minutes
        self._client = APIClient()

    def read(self) -> OpsSnapshot:
        """Take one reading of the queues and the recent outcomes."""
        return summarise(
            queued_by_queue=self._queued(),
            workers_by_queue=self._workers(),
            outcomes=self._outcomes(),
        )

    def _queued(self) -> dict[str, int]:
        """How many tasks are waiting on each queue."""
        return {
            str(queue.name): len(queue.entries or [])
            for queue in self._client.queues.get_all()
        }

    def _workers(self) -> dict[str, int]:
        """How many agents are listening to each queue.

        One agent listening to two queues counts for both. What matters is
        whether anybody would take the next task, not how many processes exist.
        """
        listening: Counter[str] = Counter()
        for worker in self._client.workers.get_all():
            for queue in worker.queues or []:
                name = getattr(queue, "name", None)
                if name:
                    listening[str(name)] += 1
        return dict(listening)

    def _outcomes(self) -> list[TaskOutcomes]:
        """How the recently finished tasks of each watched project ended."""
        since = datetime.now(timezone.utc) - timedelta(minutes=self._recent_minutes)
        return [self._outcomes_of(project, since) for project in self._projects]

    def _outcomes_of(self, project: str, since: datetime) -> TaskOutcomes:
        counted: Counter[str] = Counter()
        for task in self._finished_tasks(project, since):
            counted[str(getattr(task, "status", ""))] += 1
        return TaskOutcomes(
            project=project,
            completed=counted[COMPLETED_STATUS],
            failed=counted[FAILED_STATUS],
        )

    def _finished_tasks(self, project: str, since: datetime) -> Sequence[Any]:
        projects = self._client.projects.get_all(name=f"^{project}", only_fields=["id"])
        if not projects:
            return ()

        found: Sequence[Any] = self._client.tasks.get_all(
            project=[str(found.id) for found in projects],
            status=[COMPLETED_STATUS, FAILED_STATUS],
            only_fields=["id", "status", "last_update"],
            order_by=["-last_update"],
            page=0,
            page_size=MAXIMUM_TASKS,
            status_changed=[f">={since.strftime('%Y-%m-%dT%H:%M:%S')}"],
        )
        return found

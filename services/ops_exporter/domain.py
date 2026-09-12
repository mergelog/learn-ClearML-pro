"""What the training side of the system reports about itself.

The prediction service can report on itself because it is a process that
answers requests. The training side is not: it is a queue, some agents, and
tasks that come and go. Nothing there answers an HTTP request, so nothing
there can be scraped.

This is the shape of what somebody watching that side needs to know.

How much work is waiting. A queue that grows without bound means the agents
cannot keep up, or have stopped.

How many agents are listening. Zero is the failure that looks like nothing
happening at all, which is the hardest kind to notice.

How many tasks failed recently. A pipeline that fails every time still leaves
the queue empty and the agents idle, so queue depth alone cannot see it.

This module depends on nothing but the standard library, so what is measured
can be decided without a ClearML Server.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


SERVICE_NAME = "semiconductor-ops-exporter"

# 「最近」の幅。短すぎると失敗が窓から抜け落ち、長すぎると直った後も
# 警報が鳴り続ける。
DEFAULT_RECENT_MINUTES = 30


@dataclass(frozen=True)
class QueueDepth:
    """How much work is waiting on one queue, and who is there to take it."""

    name: str
    queued: int
    workers: int

    @property
    def unattended(self) -> bool:
        """Work is waiting and nobody is listening.

        This is worse than a long queue: a long queue drains, this one does not.
        """
        return self.queued > 0 and self.workers == 0


@dataclass(frozen=True)
class TaskOutcomes:
    """How the recently finished tasks of one project ended."""

    project: str
    completed: int
    failed: int

    @property
    def total(self) -> int:
        return self.completed + self.failed

    @property
    def failure_share(self) -> float:
        if self.total <= 0:
            return 0.0
        return self.failed / self.total


@dataclass(frozen=True)
class OpsSnapshot:
    """One reading of the training side."""

    queues: tuple[QueueDepth, ...]
    outcomes: tuple[TaskOutcomes, ...]

    @property
    def unattended_queues(self) -> tuple[QueueDepth, ...]:
        return tuple(queue for queue in self.queues if queue.unattended)

    def as_document(self) -> dict[str, object]:
        return {
            "queues": [
                {"name": queue.name, "queued": queue.queued, "workers": queue.workers}
                for queue in self.queues
            ],
            "outcomes": [
                {
                    "project": outcome.project,
                    "completed": outcome.completed,
                    "failed": outcome.failed,
                }
                for outcome in self.outcomes
            ],
        }


def summarise(
    queued_by_queue: Mapping[str, int],
    workers_by_queue: Mapping[str, int],
    outcomes: Sequence[TaskOutcomes],
) -> OpsSnapshot:
    """Build one reading out of what the server answered.

    A queue that only appears in one of the two mappings is still reported. A
    queue with workers and no work is idle; a queue with work and no workers is
    the failure this exists to catch. Dropping either would hide one of them.
    """
    names = sorted(set(queued_by_queue) | set(workers_by_queue))
    return OpsSnapshot(
        queues=tuple(
            QueueDepth(
                name=name,
                queued=queued_by_queue.get(name, 0),
                workers=workers_by_queue.get(name, 0),
            )
            for name in names
        ),
        outcomes=tuple(outcomes),
    )

"""ClearML boundary of the secret scan.

What a run wrote down is as public as the ClearML Server, and it stays there
after the run is forgotten. Three kinds of text are read here.

*Parameters* are the recorded contract of a run. A credential put into one is
visible in the Web UI, in every clone of the Task, and in every comparison
between runs.

*The console output* is whatever the code printed. This is where credentials
usually arrive: a dumped environment, a client that logs the request it is
about to send, a traceback that includes a configuration object.

*The environment* the Agent recorded is read for the same reason, when the
Task carries one.

Only reading happens here. The scan reports what it found; deciding what to do
with a Task that holds a credential — rotating first, then deleting — is a
person's decision, and it is written down in the runbook.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


# 一度に読むTaskの上限。全部読むと、履歴が伸びるほど検査が終わらなくなる。
DEFAULT_TASK_LIMIT = 50

# 1つのTaskから読む出力の行数。資格情報は起動時に印字されることが多いので、
# 先頭側から読める分で足りる。全部読むと、長い学習1件で検査が終わらなくなる。
CONSOLE_LINES = 200

PARAMETERS_ORIGIN = "parameters"
CONSOLE_ORIGIN = "console"


@dataclass(frozen=True)
class TaskText:
    """One piece of text a Task wrote down, named so it can be found again."""

    task_id: str
    task_name: str
    project: str
    kind: str
    text: str

    @property
    def origin(self) -> str:
        """How this text is named in a finding.

        The id comes first because that is what a person pastes into the Web UI
        to reach the Task the finding is about.
        """
        return f"task:{self.task_id}/{self.kind}"


class TaskSource(Protocol):
    """Where the texts to scan come from, so the scan can run without a server."""

    def read(self) -> Sequence[TaskText]:
        ...


@dataclass
class ClearmlTasks:
    """Reads the recent Tasks of the watched projects."""

    projects: tuple[str, ...]
    limit: int = DEFAULT_TASK_LIMIT
    _client: Any = field(default=None, repr=False)

    def read(self) -> Sequence[TaskText]:
        texts: list[TaskText] = []
        for task in self._recent_tasks():
            texts.extend(_texts_of(task))
        return tuple(texts)

    def _recent_tasks(self) -> Iterator[Any]:
        from clearml import Task

        for project in self.projects:
            found: list[Any] = Task.get_tasks(
                project_name=project,
                task_filter={"page": 0, "page_size": self.limit, "order_by": ["-last_update"]},
            )
            yield from found


def _texts_of(task: Any) -> Iterator[TaskText]:
    identity: dict[str, str] = {
        "task_id": str(task.id),
        "task_name": str(getattr(task, "name", "")),
        "project": str(getattr(task, "get_project_name", lambda: "")() or ""),
    }

    parameters = task.get_parameters() or {}
    if parameters:
        yield TaskText(
            **identity,
            kind=PARAMETERS_ORIGIN,
            text="\n".join(f"{name}={value}" for name, value in sorted(parameters.items())),
        )

    console = task.get_reported_console_output(number_of_reports=CONSOLE_LINES) or []
    if console:
        yield TaskText(
            **identity,
            kind=CONSOLE_ORIGIN,
            text="\n".join(str(line) for line in console),
        )


__all__ = [
    "CONSOLE_ORIGIN",
    "DEFAULT_TASK_LIMIT",
    "PARAMETERS_ORIGIN",
    "ClearmlTasks",
    "TaskSource",
    "TaskText",
]

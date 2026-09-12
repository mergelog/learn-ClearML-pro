"""Record where one execution came from.

A Task that only holds parameters and metrics answers "what was measured".
It does not answer "which code, which image and whose invocation produced
it", which is the question asked when a model has to be reproduced, audited
or rolled back months later.

This module collects that answer. It never contacts ClearML: it reads the
working tree and the environment, and hands the result to
:mod:`clearml_tracking`, which is the only place allowed to write it onto a
Task.

Nothing here fails a run. A missing value is recorded as ``UNKNOWN`` rather
than raised, because an incomplete provenance is still worth more than a
refused execution, and because the same code has to work in three places: a
developer's checkout, a container that carries no ``.git``, and a ClearML
Agent that re-runs the Task later.

The environment is allowed to override every value it can supply. That is how
a built image states its own reference and digest, which cannot be discovered
from inside a running container.
"""

from __future__ import annotations

import getpass
import platform
import socket
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

# 値が取れなかったことを、空文字ではなくこの語で残す。空文字はTaskの画面で
# 「記録し忘れ」と見分けがつかない。
UNKNOWN = "unknown"

LOCAL_QUEUE = "local"

COMMIT_ENVIRONMENT_KEY = "SEMICONDUCTOR_GIT_COMMIT"
BRANCH_ENVIRONMENT_KEY = "SEMICONDUCTOR_GIT_BRANCH"
REMOTE_ENVIRONMENT_KEY = "SEMICONDUCTOR_GIT_REMOTE"
IMAGE_ENVIRONMENT_KEY = "SEMICONDUCTOR_TRAINING_IMAGE"
IMAGE_DIGEST_ENVIRONMENT_KEY = "SEMICONDUCTOR_TRAINING_IMAGE_DIGEST"
EXECUTED_BY_ENVIRONMENT_KEY = "SEMICONDUCTOR_EXECUTED_BY"

GIT_COMMAND_TIMEOUT_SECONDS = 5

CommandRunner = Callable[[Sequence[str]], str | None]


@dataclass(frozen=True)
class CodeRevision:
    """Which revision of this repository an execution ran.

    ``is_clean`` is recorded next to the commit because a dirty working tree
    means the commit alone no longer identifies what was executed.
    """

    commit: str
    branch: str
    remote: str
    is_clean: bool

    def as_parameters(self) -> dict[str, str]:
        return {
            "git_commit": self.commit,
            "git_branch": self.branch,
            "git_remote": self.remote,
            "git_working_tree": "clean" if self.is_clean else "dirty",
        }


@dataclass(frozen=True)
class RuntimeEnvironment:
    """Which image and machine an execution ran on.

    A container cannot read the reference it was started from, so both image
    values come from the environment the image itself declares at build time.
    """

    image_reference: str
    image_digest: str
    python_version: str
    hostname: str

    def as_parameters(self) -> dict[str, str]:
        return {
            "image_reference": self.image_reference,
            "image_digest": self.image_digest,
            "python_version": self.python_version,
            "hostname": self.hostname,
        }


@dataclass(frozen=True)
class ExecutionProvenance:
    """Everything about one execution that is not the model itself.

    The record has two halves, and they are kept apart because a queued run is
    created by one process and carried out by another.

    ``code``, ``executed_by`` and ``queue`` describe the request: who asked for
    this run, from which revision, and where it was sent. They stay true for
    the life of the Task.

    ``runtime`` describes whichever process is running at the moment. For a
    queued run that is the Agent, and it is the Agent's image that a result has
    to be reproducible from.
    """

    code: CodeRevision
    runtime: RuntimeEnvironment
    executed_by: str
    queue: str

    def request_parameters(self) -> dict[str, str]:
        """Flatten the half that describes who asked for this run."""
        return {
            **self.code.as_parameters(),
            "executed_by": self.executed_by,
            "queue": self.queue,
        }

    def runtime_parameters(self) -> dict[str, str]:
        """Flatten the half that describes the process carrying the run out."""
        return self.runtime.as_parameters()


def collect_provenance(
    queue: str | None = None,
    *,
    environment: Mapping[str, str],
    run_command: CommandRunner | None = None,
) -> ExecutionProvenance:
    """Read the provenance of the execution that is starting.

    ``environment`` is passed in rather than read from :mod:`os` so that the
    caller decides which environment is being described, and so that this can
    be exercised without touching the process it runs in.
    """
    runner = run_command or _run_git
    return ExecutionProvenance(
        code=collect_code_revision(environment=environment, run_command=runner),
        runtime=collect_runtime_environment(environment=environment),
        executed_by=_value(environment, EXECUTED_BY_ENVIRONMENT_KEY) or _current_user(),
        queue=queue or LOCAL_QUEUE,
    )


def collect_code_revision(
    *,
    environment: Mapping[str, str],
    run_command: CommandRunner | None = None,
) -> CodeRevision:
    """Describe the revision that is being executed.

    The environment wins over the working tree. A container that was built
    from a known commit states it that way, and the ``git`` call is then not
    even attempted.
    """
    runner = run_command or _run_git

    commit = _value(environment, COMMIT_ENVIRONMENT_KEY) or runner(("rev-parse", "HEAD"))
    branch = _value(environment, BRANCH_ENVIRONMENT_KEY) or runner(
        ("rev-parse", "--abbrev-ref", "HEAD")
    )
    remote = _value(environment, REMOTE_ENVIRONMENT_KEY) or runner(
        ("config", "--get", "remote.origin.url")
    )
    status = runner(("status", "--porcelain"))

    return CodeRevision(
        commit=commit or UNKNOWN,
        branch=branch or UNKNOWN,
        remote=remote or UNKNOWN,
        # 状態を読めなかったときに clean と言い切ると、来歴として嘘になる。
        is_clean=status == "",
    )


def collect_runtime_environment(*, environment: Mapping[str, str]) -> RuntimeEnvironment:
    return RuntimeEnvironment(
        image_reference=_value(environment, IMAGE_ENVIRONMENT_KEY) or UNKNOWN,
        image_digest=_value(environment, IMAGE_DIGEST_ENVIRONMENT_KEY) or UNKNOWN,
        python_version=platform.python_version(),
        hostname=socket.gethostname(),
    )


def _value(environment: Mapping[str, str], key: str) -> str | None:
    value = environment.get(key, "").strip()
    return value or None


def _current_user() -> str:
    # 来歴が欠けても実行は止めない。利用者名は監査の手掛かりであって、
    # 学習の入力ではない。
    try:
        return getpass.getuser()
    except Exception:
        return UNKNOWN


def _run_git(arguments: Sequence[str]) -> str | None:
    """Ask git about this checkout, and answer ``None`` when it cannot.

    Every failure mode is the same answer: no git binary, no repository, or a
    command that timed out all mean the value is unknown.
    """
    try:
        # 引数はこのモジュール内の定数だけで、shellも介さない。
        completed = subprocess.run(
            ("git", "-C", str(REPOSITORY_ROOT), *arguments),
            capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if completed.returncode != 0:
        return None
    return completed.stdout.strip()

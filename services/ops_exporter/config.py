"""Execution contract of the ops exporter.

Who may read the metrics is part of the contract and is required. The numbers
published here say how much work is queued, how many agents are alive and how
much of the host is left; together they describe the shape of the system to
anybody who asks. The exporter therefore refuses to start without callers, in
the same way the prediction service does.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import ClassVar

from ml.security.credentials import AccessPolicy, CredentialError, parse_policy
from ml.semiconductor_quality.config import ConfigurationError, Contract, _require_text

from .domain import DEFAULT_RECENT_MINUTES


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8091
DEFAULT_PROJECTS = ("Semiconductor Quality Prediction",)

HOST_ENVIRONMENT_KEY = "OPS_EXPORTER_HOST"
PORT_ENVIRONMENT_KEY = "OPS_EXPORTER_PORT"
PROJECTS_ENVIRONMENT_KEY = "OPS_EXPORTER_PROJECTS"
RECENT_MINUTES_ENVIRONMENT_KEY = "OPS_EXPORTER_RECENT_MINUTES"
CLIENTS_ENVIRONMENT_KEY = "OPS_EXPORTER_CLIENTS"

NO_CLIENTS_MESSAGE = (
    f"no caller may read these metrics. Issue a credential with `pnpm sec:token` and put "
    f"its fingerprint into {CLIENTS_ENVIRONMENT_KEY} "
    f"(name:role:fingerprint, separated by ';')"
)


@dataclass(frozen=True)
class OpsExporterConfig(Contract):
    """Where the exporter listens, and what it watches."""

    error_heading: ClassVar[str] = "Invalid ops exporter configuration"

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    projects: tuple[str, ...] = field(default_factory=lambda: DEFAULT_PROJECTS)
    recent_minutes: int = DEFAULT_RECENT_MINUTES
    clients: AccessPolicy = field(default_factory=AccessPolicy)

    @classmethod
    def from_environment(cls) -> OpsExporterConfig:
        return cls(
            host=os.getenv(HOST_ENVIRONMENT_KEY, DEFAULT_HOST).strip() or DEFAULT_HOST,
            port=_whole(PORT_ENVIRONMENT_KEY, DEFAULT_PORT),
            projects=_projects(),
            recent_minutes=_whole(RECENT_MINUTES_ENVIRONMENT_KEY, DEFAULT_RECENT_MINUTES),
            clients=_clients_from_environment(),
        )

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = list(_require_text("host", self.host))
        if not 1 <= self.port <= 65_535:
            errors.append(f"port must be between 1 and 65535, but was {self.port}")
        if not self.projects:
            errors.append("at least one project is required, or there is nothing to watch")
        if self.recent_minutes <= 0:
            errors.append(
                f"recent_minutes must be greater than 0, but was {self.recent_minutes}"
            )
        if self.clients.is_empty:
            errors.append(NO_CLIENTS_MESSAGE)
        return tuple(errors)


def _projects() -> tuple[str, ...]:
    """Read the projects to watch, given as a comma separated list."""
    given = os.getenv(PROJECTS_ENVIRONMENT_KEY, "").strip()
    if not given:
        return DEFAULT_PROJECTS
    return tuple(part.strip() for part in given.split(",") if part.strip())


def _clients_from_environment() -> AccessPolicy:
    """Read who may read the metrics, refusing a description that cannot be used."""
    given = os.getenv(CLIENTS_ENVIRONMENT_KEY, "").strip()
    if not given:
        return AccessPolicy()
    try:
        return parse_policy(given)
    except CredentialError as error:
        raise ConfigurationError(f"{CLIENTS_ENVIRONMENT_KEY}: {error}") from error


def _whole(key: str, default: int) -> int:
    given = os.getenv(key, "").strip()
    if not given:
        return default
    try:
        return int(given)
    except ValueError:
        # 読めない値は「指示されていない」ではなく設定の誤りである。
        # 既定へ落とすと、間違った設定のまま動いていることに気付けない。
        raise ValueError(f"{key} must be a whole number, but was {given!r}") from None

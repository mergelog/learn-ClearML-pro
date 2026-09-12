"""Execution contract of the prediction service.

The service is configured entirely from the environment, because it is
deployed as a container and a container is configured by whoever starts it.

Which model is served is deliberately *not* configurable as a model id. The
service looks up whichever model currently holds production, so a promotion
takes effect by restarting the process rather than by editing a deployment.
That keeps one place — the registry — as the answer to "what is serving".

The only escape is ``PREDICTION_MODEL_ID``, which pins one model. It exists
for reproducing an incident, and the service says loudly that it is pinned.

Who may call is configured the same way, and is required. The service refuses
to start without callers rather than starting open: a prediction service that
answers anybody also tells anybody which model is in production, and the
mistake would be invisible until somebody looked.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from ml.security.credentials import AccessPolicy, CredentialError, parse_policy
from ml.semiconductor_quality.config import ConfigurationError, Contract, _require_text


# コンテナの外から届く必要があるため、ループバックではなく全インタフェースで待つ。
# 公開範囲はコンテナのポート設定側で決める。
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8090

MODEL_ID_ENVIRONMENT_KEY = "PREDICTION_MODEL_ID"
HOST_ENVIRONMENT_KEY = "PREDICTION_HOST"
PORT_ENVIRONMENT_KEY = "PREDICTION_PORT"
CLIENTS_ENVIRONMENT_KEY = "PREDICTION_API_CLIENTS"
TLS_CERTIFICATE_ENVIRONMENT_KEY = "PREDICTION_TLS_CERTIFICATE_FILE"
TLS_PRIVATE_KEY_ENVIRONMENT_KEY = "PREDICTION_TLS_PRIVATE_KEY_FILE"

NO_CLIENTS_MESSAGE = (
    f"no caller may use this service. Issue a credential with `pnpm sec:token` and put "
    f"its fingerprint into {CLIENTS_ENVIRONMENT_KEY} "
    f"(name:role:fingerprint, separated by ';')"
)


@dataclass(frozen=True)
class ServiceConfig(Contract):
    """Where the service listens, and which model it serves."""

    error_heading: ClassVar[str] = "Invalid prediction service configuration"

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    pinned_model_id: str | None = None
    clients: AccessPolicy = field(default_factory=AccessPolicy)
    tls_certificate_file: Path | None = None
    tls_private_key_file: Path | None = None

    @property
    def serves_current_production(self) -> bool:
        return self.pinned_model_id is None

    @property
    def serves_over_tls(self) -> bool:
        return self.tls_certificate_file is not None and self.tls_private_key_file is not None

    @classmethod
    def from_environment(cls) -> ServiceConfig:
        return cls(
            host=os.getenv(HOST_ENVIRONMENT_KEY, DEFAULT_HOST).strip() or DEFAULT_HOST,
            port=_port_from_environment(),
            pinned_model_id=_optional(MODEL_ID_ENVIRONMENT_KEY),
            clients=_clients_from_environment(),
            tls_certificate_file=_optional_path(TLS_CERTIFICATE_ENVIRONMENT_KEY),
            tls_private_key_file=_optional_path(TLS_PRIVATE_KEY_ENVIRONMENT_KEY),
        )

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = list(_require_text("host", self.host))
        if isinstance(self.port, bool) or not isinstance(self.port, int):
            errors.append(f"port must be a whole number, but was {self.port!r}")
        elif not 1 <= self.port <= 65_535:
            errors.append(f"port must be between 1 and 65535, but was {self.port}")
        if self.clients.is_empty:
            errors.append(NO_CLIENTS_MESSAGE)
        errors.extend(self._transport_errors())
        return tuple(errors)

    def _transport_errors(self) -> tuple[str, ...]:
        """Refuse half a TLS configuration.

        A certificate without its key, or the other way round, is the shape of
        "somebody meant to enable TLS". Starting in plain HTTP because one
        variable is missing serves traffic the operator believed was encrypted.
        """
        certificate, private_key = self.tls_certificate_file, self.tls_private_key_file
        if certificate is None and private_key is None:
            return ()
        if certificate is None or private_key is None:
            return (
                f"TLS needs both {TLS_CERTIFICATE_ENVIRONMENT_KEY} and "
                f"{TLS_PRIVATE_KEY_ENVIRONMENT_KEY}, but only one was given",
            )
        return tuple(
            f"{name} points at {path}, which does not exist"
            for name, path in (
                (TLS_CERTIFICATE_ENVIRONMENT_KEY, certificate),
                (TLS_PRIVATE_KEY_ENVIRONMENT_KEY, private_key),
            )
            if not path.is_file()
        )


def _optional(key: str) -> str | None:
    value = os.getenv(key, "").strip()
    return value or None


def _optional_path(key: str) -> Path | None:
    given = _optional(key)
    return Path(given) if given is not None else None


def _clients_from_environment() -> AccessPolicy:
    """Read who may call, and refuse a description that cannot be used.

    A malformed caller list is refused rather than skipped. Skipping it would
    start the service with fewer callers than the operator configured, and the
    first sign of that is a caller failing in production.
    """
    given = os.getenv(CLIENTS_ENVIRONMENT_KEY, "").strip()
    if not given:
        return AccessPolicy()
    try:
        return parse_policy(given)
    except CredentialError as error:
        raise ConfigurationError(f"{CLIENTS_ENVIRONMENT_KEY}: {error}") from error


def _port_from_environment() -> int:
    given = _optional(PORT_ENVIRONMENT_KEY)
    if given is None:
        return DEFAULT_PORT
    try:
        return int(given)
    except ValueError as error:
        raise ConfigurationError(
            f"{PORT_ENVIRONMENT_KEY} must be a whole number, but was {given!r}"
        ) from error

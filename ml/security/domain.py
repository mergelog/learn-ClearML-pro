"""Who may ask a service for what.

Authorization is expressed as three things, kept apart on purpose.

A *permission* names one thing a caller may do. It is stated in terms of the
work ("predict", "read the metrics"), never in terms of a route, so moving a
route does not silently move a privilege.

A *role* is a named set of permissions. Callers are granted roles rather than
permissions, because a caller is a job to be done, and the job is what a
reviewer can judge.

A *principal* is one caller: a name that appears in the audit log, the role it
was granted, and the fingerprints of the credentials it may present. It never
holds the credential itself, so neither a configuration file nor a process
memory dump hands out a working token.

The decision is a value rather than an exception, because the reason a call
was refused is worth recording even when nothing goes wrong afterwards. The
three ways to be refused are distinguished for the same reason: "no credential
was presented", "the credential is unknown" and "this caller may not do this"
lead to three different actions by whoever reads the log.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType


class Permission(Enum):
    """One thing a caller may do, named after the work and not after a route."""

    PREDICT = "predict"
    MODEL_READ = "model:read"
    METRICS_READ = "metrics:read"


class Role(Enum):
    """A named set of permissions, granted to a caller as a whole."""

    PREDICTOR = "predictor"
    OPERATOR = "operator"
    SCRAPER = "scraper"

    @property
    def permissions(self) -> frozenset[Permission]:
        return ROLE_PERMISSIONS[self]

    def may(self, permission: Permission) -> bool:
        return permission in self.permissions


# 役割は「その仕事に要る最小」で決める。
#
# predictor は答えを求める側。どのモデルが答えたかは応答の一部なので
# /ready と同じ model:read を持つが、監視の数字は業務に要らない。
# operator は運用する側。障害時に「何が提供されているか」と数字を読むが、
# 予測は業務ではない。scraper は Prometheus のための役割で、数字だけを読む。
ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]] = MappingProxyType(
    {
        Role.PREDICTOR: frozenset({Permission.PREDICT, Permission.MODEL_READ}),
        Role.OPERATOR: frozenset({Permission.MODEL_READ, Permission.METRICS_READ}),
        Role.SCRAPER: frozenset({Permission.METRICS_READ}),
    }
)


class Outcome(Enum):
    """Why a call was allowed or refused.

    The three refusals are kept apart because they ask for different actions:
    a missing credential is usually a caller that was never configured, an
    unknown one is a rotation that was not finished or an attempt, and an
    insufficient role is a caller asking for work it was not granted.
    """

    ALLOWED = "allowed"
    MISSING_CREDENTIAL = "missing_credential"
    UNKNOWN_CREDENTIAL = "unknown_credential"
    INSUFFICIENT_ROLE = "insufficient_role"

    @property
    def allowed(self) -> bool:
        return self is Outcome.ALLOWED


@dataclass(frozen=True)
class Principal:
    """One caller: a name for the audit log, its role, and its credentials.

    Several fingerprints are allowed so that a credential can be rotated
    without a moment where no valid credential exists: the new one is added,
    the callers are moved over, and the old one is removed afterwards.
    """

    name: str
    role: Role
    credential_fingerprints: tuple[str, ...] = field(default_factory=tuple)

    def may(self, permission: Permission) -> bool:
        return self.role.may(permission)


@dataclass(frozen=True)
class AccessDecision:
    """The answer to one authorization question, in a form worth logging."""

    outcome: Outcome
    permission: Permission
    principal: Principal | None = None

    @property
    def allowed(self) -> bool:
        return self.outcome.allowed

    @property
    def principal_name(self) -> str:
        # 名乗れなかった呼び出しも監査には残る。空欄ではなく、そう書く。
        return self.principal.name if self.principal is not None else "anonymous"

    @property
    def role_name(self) -> str:
        return self.principal.role.value if self.principal is not None else "none"

    def describe(self) -> str:
        """State the decision in one sentence, without naming any credential."""
        if self.outcome is Outcome.ALLOWED:
            return f"{self.principal_name} may {self.permission.value}"
        if self.outcome is Outcome.MISSING_CREDENTIAL:
            return f"{self.permission.value} requires a credential, and none was presented"
        if self.outcome is Outcome.UNKNOWN_CREDENTIAL:
            return "the presented credential belongs to no known caller"
        return (
            f"{self.principal_name} was granted {self.role_name}, "
            f"which does not include {self.permission.value}"
        )


def role_named(value: str) -> Role:
    """Read a role by name, and say which names exist when it is not one."""
    try:
        return Role(value)
    except ValueError:
        known = ", ".join(sorted(role.value for role in Role))
        raise ValueError(f"unknown role {value!r}, expected one of: {known}") from None


__all__ = [
    "ROLE_PERMISSIONS",
    "AccessDecision",
    "Outcome",
    "Permission",
    "Principal",
    "Role",
    "role_named",
]

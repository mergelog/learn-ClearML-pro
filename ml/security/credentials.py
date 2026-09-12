"""Credentials, and the decision made from one.

A credential here is a long random string ("token") that a caller presents.
The services never store it. They store its SHA-256 fingerprint, so the
configuration that describes who may call — a compose file, a `.env`, a secret
manager entry — cannot itself be used to call. Losing that configuration is a
disclosure of names and roles, not of access.

The prefix on an issued token exists for exactly one reason: a leaked
credential must be greppable. A random string is invisible in a log; a string
that starts with ``stk_`` is found by the secret scanner in this repository,
by a hosted secret scanner, and by a person reading a paste.

Rotation is expressed as several fingerprints for one caller. The new token is
added, the callers move over, the old fingerprint is removed. There is no
moment where a valid credential does not exist, which is what makes rotation
something an operator will actually do.

The policy fails closed. A service with no callers configured is not a service
that lets everyone in; it is a service that refuses to start, because "nobody
may call this" and "anybody may call this" are the two possible readings of an
empty list and only one of them is safe.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field

from .domain import AccessDecision, Outcome, Permission, Principal, role_named


# 発行したトークンだと分かる印。漏えいを見つけられるようにするためであって、
# 秘匿の役には立たない。
TOKEN_PREFIX = "stk_"

# 32バイト = 256ビット。総当たりが現実的でない幅を、乱数の側で確保する。
TOKEN_BYTES = 32

FINGERPRINT_LENGTH = 64

CLIENT_SEPARATOR = ";"
FIELD_SEPARATOR = ":"
FINGERPRINT_SEPARATOR = ","

BEARER_SCHEME = "bearer"


class CredentialError(ValueError):
    """Raised when the description of who may call cannot be used."""


def issue_token() -> str:
    """Create one credential. The only moment its plain text exists."""
    return f"{TOKEN_PREFIX}{secrets.token_urlsafe(TOKEN_BYTES)}"


def fingerprint(token: str) -> str:
    """Reduce a credential to what may be written down."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def fingerprint_hint(value: str) -> str:
    """Name a credential in a log without revealing it.

    The first bytes of the *fingerprint* are used, never of the token: a hint
    taken from the token itself would shorten the guessing work on the token.
    """
    return value[:8]


@dataclass(frozen=True)
class AccessPolicy:
    """Every caller a service accepts, and the decision made from a credential."""

    principals: tuple[Principal, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return not self.principals

    def authorize(self, credential: str | None, permission: Permission) -> AccessDecision:
        """Decide one call, and say why."""
        if credential is None or not credential.strip():
            return AccessDecision(outcome=Outcome.MISSING_CREDENTIAL, permission=permission)

        principal = self._principal_of(credential.strip())
        if principal is None:
            return AccessDecision(outcome=Outcome.UNKNOWN_CREDENTIAL, permission=permission)
        if not principal.may(permission):
            return AccessDecision(
                outcome=Outcome.INSUFFICIENT_ROLE,
                permission=permission,
                principal=principal,
            )
        return AccessDecision(
            outcome=Outcome.ALLOWED,
            permission=permission,
            principal=principal,
        )

    def _principal_of(self, credential: str) -> Principal | None:
        presented = fingerprint(credential)
        found: Principal | None = None
        for principal in self.principals:
            for known in principal.credential_fingerprints:
                # 一致した時点で抜けない。既知のトークンかどうかで応答時間が
                # 変わらないようにする。
                if hmac.compare_digest(presented, known):
                    found = principal
        return found

    def describe(self) -> str:
        """List who may call, for a startup log. Names and roles only."""
        return ", ".join(
            f"{principal.name}({principal.role.value})" for principal in self.principals
        )


def parse_policy(text: str) -> AccessPolicy:
    """Read the callers of a service from one configuration value.

    The format is ``name:role:fingerprint[,fingerprint];name:role:fingerprint``.
    It is deliberately flat: it has to survive being an environment variable in
    a compose file, and anything nested would be pasted wrongly.
    """
    entries = [part.strip() for part in text.split(CLIENT_SEPARATOR) if part.strip()]
    principals = tuple(_principal(entry) for entry in entries)
    _refuse_ambiguity(principals)
    return AccessPolicy(principals=principals)


def _principal(entry: str) -> Principal:
    fields = entry.split(FIELD_SEPARATOR)
    if len(fields) != 3:
        raise CredentialError(
            f"expected name:role:fingerprint[,fingerprint], but was {entry!r}"
        )

    name, role, fingerprints = (field_value.strip() for field_value in fields)
    if not name:
        raise CredentialError(f"a caller must be named, but was {entry!r}")

    try:
        granted = role_named(role)
    except ValueError as error:
        raise CredentialError(f"{name}: {error}") from error

    known = tuple(
        value.strip().lower()
        for value in fingerprints.split(FINGERPRINT_SEPARATOR)
        if value.strip()
    )
    if not known:
        raise CredentialError(f"{name}: no credential fingerprint was given")
    for value in known:
        _refuse_plain_token(name, value)
        if len(value) != FINGERPRINT_LENGTH or not _is_hexadecimal(value):
            raise CredentialError(
                f"{name}: a credential fingerprint is 64 hexadecimal characters "
                f"(the SHA-256 of the token), but one was {len(value)} characters long"
            )

    return Principal(name=name, role=granted, credential_fingerprints=known)


def _refuse_plain_token(name: str, value: str) -> None:
    """Refuse a token pasted where its fingerprint belongs.

    This is the mistake that turns the configuration back into a credential
    store, and it is silent: the service would start and simply never accept
    that caller. Refusing it names the mistake instead.
    """
    if value.startswith(TOKEN_PREFIX):
        raise CredentialError(
            f"{name}: a token was given where its fingerprint belongs. "
            "Configure the SHA-256 fingerprint, not the token itself"
        )


def _is_hexadecimal(value: str) -> bool:
    return all(character in "0123456789abcdef" for character in value)


def _refuse_ambiguity(principals: tuple[Principal, ...]) -> None:
    """Refuse two callers that cannot be told apart.

    Two callers sharing a name make the audit log unreadable; two sharing a
    fingerprint make the decision depend on the order of the list. Both are
    configuration mistakes, and both are invisible once the service runs.
    """
    seen_names: set[str] = set()
    seen_fingerprints: dict[str, str] = {}
    for principal in principals:
        if principal.name in seen_names:
            raise CredentialError(f"{principal.name} is described more than once")
        seen_names.add(principal.name)
        for value in principal.credential_fingerprints:
            owner = seen_fingerprints.get(value)
            if owner is not None:
                raise CredentialError(
                    f"{principal.name} and {owner} share a credential, so a call "
                    "cannot be attributed to either"
                )
            seen_fingerprints[value] = principal.name


def credential_of(authorization_header: str | None) -> str | None:
    """Take the credential out of an ``Authorization`` header.

    Only the Bearer scheme is read. A header in another scheme is treated as no
    credential at all, so a caller that authenticates the wrong way is refused
    with "none was presented" rather than being compared as a raw string.
    """
    if authorization_header is None:
        return None
    parts = authorization_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != BEARER_SCHEME:
        return None
    credential = parts[1].strip()
    return credential or None


__all__ = [
    "BEARER_SCHEME",
    "FINGERPRINT_LENGTH",
    "TOKEN_BYTES",
    "TOKEN_PREFIX",
    "AccessPolicy",
    "CredentialError",
    "credential_of",
    "fingerprint",
    "fingerprint_hint",
    "issue_token",
    "parse_policy",
]

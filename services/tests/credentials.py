"""Callers used by the service tests.

Every test that talks to a service has to present a credential, because the
services refuse to start without callers. Building them in one place keeps the
tests about what they are testing.

The tokens are issued when this module is imported rather than written down as
literals. A literal credential in a test file is indistinguishable from a real
one to anybody reading the diff — and to the secret scanner, which would have
to be taught an exception for exactly the kind of line it exists to find.
"""

from __future__ import annotations

from ml.security.credentials import AccessPolicy, fingerprint, issue_token
from ml.security.domain import Principal, Role


TOKENS: dict[Role, str] = {role: issue_token() for role in Role}

PRINCIPALS: tuple[Principal, ...] = tuple(
    Principal(
        name=f"test-{role.value}",
        role=role,
        credential_fingerprints=(fingerprint(token),),
    )
    for role, token in TOKENS.items()
)

UNKNOWN_TOKEN = issue_token()


def access_policy() -> AccessPolicy:
    """One caller per role, so a refusal can be told from a missing caller."""
    return AccessPolicy(principals=PRINCIPALS)


def headers(role: Role) -> dict[str, str]:
    """The Authorization header of the caller granted ``role``."""
    return {"Authorization": f"Bearer {TOKENS[role]}"}


__all__ = ["PRINCIPALS", "TOKENS", "UNKNOWN_TOKEN", "access_policy", "headers"]

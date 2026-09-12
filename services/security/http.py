"""Where an HTTP request meets the access policy.

This is the only place in the services that knows both about credentials and
about status codes, and it exists so that a route can say what it *needs*
(``Depends(requires(Permission.PREDICT))``) instead of how to check it. A
route that spells out the check is a route that can forget it.

The two refusals are told apart on purpose.

``401`` says "I do not know who you are": no credential, or one that belongs
to nobody. The caller can fix it by presenting a valid one, so the response
says which scheme to use.

``403`` says "I know who you are, and you may not do this". Presenting the
same credential again will not help, and answering ``401`` here would send an
operator into a credential problem that does not exist.

Every decision is written to the audit log, allowed ones included. An audit
trail that only records refusals answers "who was stopped" but not "who did
it", and the second question is the one asked after an incident.

Neither the credential nor anything derived from it beyond a short fingerprint
hint is ever logged. The hint is there to follow one caller through a log
without being enough to reconstruct what it presented.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from ml.security.credentials import AccessPolicy, credential_of, fingerprint, fingerprint_hint
from ml.security.domain import AccessDecision, Outcome, Permission, Principal


ACCESS_POLICY_STATE = "access_policy"
PRINCIPAL_STATE = "principal"

AUDIT_LOGGER_NAME = "security.access"
ACCESS_EVENT = "access.decision"

AUTHORIZATION_HEADER = "Authorization"
AUTHENTICATE_HEADER = "WWW-Authenticate"
BEARER_CHALLENGE = 'Bearer realm="semiconductor"'

audit = logging.getLogger(AUDIT_LOGGER_NAME)


class PolicyMissingError(RuntimeError):
    """Raised when an application was built without an access policy.

    Failing here rather than letting the request through is the whole point:
    an application that forgot its policy must not be an application that
    admits everybody.
    """


def requires(permission: Permission) -> Callable[[Request], Principal]:
    """Build the dependency that guards one permission."""

    def guard(request: Request) -> Principal:
        policy = policy_of(request.app)
        credential = credential_of(request.headers.get(AUTHORIZATION_HEADER))
        decision = policy.authorize(credential, permission)
        _record(decision, request, credential)

        if decision.allowed and decision.principal is not None:
            # 誰として通ったかを、この先の処理からも読めるようにする。
            setattr(request.state, PRINCIPAL_STATE, decision.principal)
            return decision.principal

        raise _refusal(decision)

    return guard


def policy_of(application: object) -> AccessPolicy:
    policy = getattr(getattr(application, "state", None), ACCESS_POLICY_STATE, None)
    if not isinstance(policy, AccessPolicy):
        raise PolicyMissingError(
            "the application was started without an access policy, so no request "
            "can be authorized"
        )
    return policy


def _record(decision: AccessDecision, request: Request, credential: str | None) -> None:
    """Write one line per decision, without writing the credential."""
    fields: dict[str, object] = {
        "event": ACCESS_EVENT,
        "principal": decision.principal_name,
        "role": decision.role_name,
        "permission": decision.permission.value,
        "outcome": decision.outcome.value,
        "endpoint": request.url.path,
        "method": request.method,
    }
    if credential is not None:
        # 提示されたものを名指しできるようにするが、再現はできないようにする。
        fields["credential"] = fingerprint_hint(fingerprint(credential))

    if decision.allowed:
        audit.info(decision.describe(), extra=fields)
    else:
        audit.warning(decision.describe(), extra=fields)


def _refusal(decision: AccessDecision) -> HTTPException:
    if decision.outcome is Outcome.INSUFFICIENT_ROLE:
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.describe())
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=decision.describe(),
        headers={AUTHENTICATE_HEADER: BEARER_CHALLENGE},
    )


__all__ = [
    "ACCESS_POLICY_STATE",
    "AUTHENTICATE_HEADER",
    "PRINCIPAL_STATE",
    "PolicyMissingError",
    "policy_of",
    "requires",
]

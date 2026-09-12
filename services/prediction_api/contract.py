"""The API this service publishes, written down so a change to it is visible.

`prediction_api` has no consumer yet. The screen does not call it; what calls
it today is a runbook's ``curl`` and the service's own tests. Writing a
consumer-provider contract test in that situation produces a test with one
side, which restates the provider and detects nothing.

What can be checked with no consumer is that **the published shape does not
change silently**. FastAPI derives the OpenAPI document from the code, so the
document is always true; it is the *change* to it that nobody notices. So the
document is committed next to the service, and a test compares the one the
code produces against it.

The committed file is also the answer to "what does this service accept",
which until now could only be learned by reading the handlers.

Any difference fails, not only a breaking one. An intentional change is one
`pnpm run serving:openapi:update` away, and the diff is then part of the
review — which is where a decision about a public API belongs. Classifying
the difference (:mod:`services.contracts.openapi`) only changes how the
failure reads, never whether it fails.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ml.security.credentials import AccessPolicy
from ml.security.domain import Principal, Role
from services.contracts.openapi import Change, breaking, changes

from .app import create_app
from .config import ServiceConfig


SNAPSHOT_PATH = Path(__file__).with_name("openapi.json")

UPDATE_COMMAND = "pnpm run serving:openapi:update"


def openapi_document() -> dict[str, Any]:
    """The document the running service publishes."""
    document: dict[str, Any] = create_app(_describable()).openapi()
    return document


def published_document() -> dict[str, Any]:
    """The document as it was last committed."""
    published: dict[str, Any] = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return published


def write_snapshot(document: dict[str, Any] | None = None) -> Path:
    """Commit the current document as the published one."""
    published = openapi_document() if document is None else document
    text = json.dumps(published, indent=2, ensure_ascii=False)
    SNAPSHOT_PATH.write_text(f"{text}\n", encoding="utf-8")
    return SNAPSHOT_PATH


def drift() -> str | None:
    """Say how the API moved away from what is published, or nothing.

    The comparison for *whether* it moved is the whole document; the
    classification is only there so that the reader of a red build knows
    whether callers are about to break.
    """
    published, current = published_document(), openapi_document()
    if published == current:
        return None

    found = changes(published, current)
    lines = [
        f"公開しているAPIが {SNAPSHOT_PATH} と違う。",
        "",
        *_section("呼び出し側が壊れる変更", breaking(found)),
        *_section("互換の変更", tuple(change for change in found if not change.breaking)),
        *_unclassified(found),
        f"意図した変更であれば `{UPDATE_COMMAND}` で更新し、差分をレビューに載せる。",
    ]
    return "\n".join(lines)


def _section(heading: str, found: tuple[Change, ...]) -> tuple[str, ...]:
    if not found:
        return ()
    return (heading, *(f"  - {change.describe()}" for change in found), "")


def _unclassified(found: tuple[Change, ...]) -> tuple[str, ...]:
    """Say so when the document moved in a way the comparison cannot name.

    A tightened bound or a narrowed enum is a real change to the promise that
    :mod:`services.contracts.openapi` does not read yet. It still has to be
    looked at, so it is reported as itself rather than as nothing.
    """
    if found:
        return ()
    return (
        "操作・要求・応答の形は変わっていない。説明文や制約など、",
        "呼び出し可能な形以外のどこかが動いている。差分を読むこと。",
        "",
    )


def _describable() -> ServiceConfig:
    """A configuration that can describe the service without being able to serve.

    The service refuses to start without callers, and the document does not
    depend on who they are. So it is built with one caller that holds no
    credential: enough to assemble the application, and unable to answer
    anybody even if this ever reached a socket.
    """
    return ServiceConfig(
        clients=AccessPolicy(principals=(Principal(name="openapi", role=Role.PREDICTOR),))
    )


__all__ = [
    "SNAPSHOT_PATH",
    "UPDATE_COMMAND",
    "drift",
    "openapi_document",
    "published_document",
    "write_snapshot",
]

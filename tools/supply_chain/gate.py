"""The decision a release is allowed to depend on.

The gate does not look for vulnerabilities. Scanners do that, and there is
more than one of them: the dependency database answers about the locks, an
image scanner answers about what else is in the container. The gate reads what
they found and decides one thing — may this be released — so that the decision
lives in one place instead of being spelled out again in every pipeline.

Two rules make it usable rather than merely strict.

An exemption expires. "We accepted this in March" stops being true in June,
and an allowlist without dates becomes the list of things nobody looks at
again. An expired exemption stops excusing its advisory and is reported as
expired, so the deadline arrives as a failure rather than as silence.

An unrated advisory is reported rather than blocking, by default. Rating is
what the databases are slow at, and a gate that blocks on every unrated
advisory teaches people to bypass it. The default is a choice, and it is
written in the policy file where it can be changed to blocking for an
environment that needs it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from .domain import Severity, Vulnerability, severity_named


DEFAULT_POLICY_FILE = Path(__file__).resolve().parents[2] / "config" / "supply_chain.yaml"

RELEASE_GATE_SECTION = "release_gate"
BLOCK_KEY = "block"
UNKNOWN_KEY = "unknown"
EXEMPTIONS_KEY = "exemptions"

REPORT_UNKNOWN = "report"
BLOCK_UNKNOWN = "block"

DEFAULT_BLOCKED = (Severity.CRITICAL,)


class PolicyError(ValueError):
    """Raised when the policy cannot be read."""


@dataclass(frozen=True)
class Exemption:
    """One advisory that is accepted for now, by somebody, until a date."""

    identifier: str
    reason: str
    until: date

    def applies_on(self, today: date) -> bool:
        return today <= self.until


@dataclass(frozen=True)
class Policy:
    """What blocks a release, and what is merely reported."""

    blocked: tuple[Severity, ...] = DEFAULT_BLOCKED
    unknown: str = REPORT_UNKNOWN
    exemptions: tuple[Exemption, ...] = field(default_factory=tuple)

    def blocks(self, severity: Severity) -> bool:
        if severity is Severity.UNKNOWN:
            return self.unknown == BLOCK_UNKNOWN
        return any(severity.at_least(blocked) for blocked in self.blocked)

    def exemption_for(self, identifier: str) -> Exemption | None:
        for exemption in self.exemptions:
            if exemption.identifier == identifier:
                return exemption
        return None


@dataclass(frozen=True)
class Decision:
    """What the gate concluded, in the words a failing build should use."""

    blocking: tuple[Vulnerability, ...] = field(default_factory=tuple)
    excused: tuple[tuple[Vulnerability, Exemption], ...] = field(default_factory=tuple)
    expired: tuple[tuple[Vulnerability, Exemption], ...] = field(default_factory=tuple)
    reported: tuple[Vulnerability, ...] = field(default_factory=tuple)

    @property
    def allowed(self) -> bool:
        return not self.blocking


def decide(
    vulnerabilities: tuple[Vulnerability, ...],
    policy: Policy,
    today: date,
) -> Decision:
    """Sort what was found into what stops a release and what does not."""
    blocking: list[Vulnerability] = []
    excused: list[tuple[Vulnerability, Exemption]] = []
    expired: list[tuple[Vulnerability, Exemption]] = []
    reported: list[Vulnerability] = []

    for vulnerability in vulnerabilities:
        if not policy.blocks(vulnerability.severity):
            reported.append(vulnerability)
            continue

        exemption = policy.exemption_for(vulnerability.identifier)
        if exemption is None:
            blocking.append(vulnerability)
        elif exemption.applies_on(today):
            excused.append((vulnerability, exemption))
        else:
            # 期限切れは「まだ許されている」でも「新しく見つかった」でもない。
            # 決めた日から時間が経ったという事実そのものを報告する。
            expired.append((vulnerability, exemption))
            blocking.append(vulnerability)

    return Decision(
        blocking=tuple(blocking),
        excused=tuple(excused),
        expired=tuple(expired),
        reported=tuple(reported),
    )


def load_policy(path: Path = DEFAULT_POLICY_FILE) -> Policy:
    """Read the policy, refusing anything that would silently weaken it."""
    if not path.is_file():
        raise PolicyError(f"{path} does not exist, and the gate has no policy to apply")

    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    section = document.get(RELEASE_GATE_SECTION)
    if not isinstance(section, dict):
        raise PolicyError(f"{path}: {RELEASE_GATE_SECTION} must be a mapping")

    blocked = tuple(_severity(value, path) for value in section.get(BLOCK_KEY, ["critical"]))
    if not blocked:
        raise PolicyError(f"{path}: a gate that blocks nothing is not a gate")

    unknown = str(section.get(UNKNOWN_KEY, REPORT_UNKNOWN)).strip().lower()
    if unknown not in (REPORT_UNKNOWN, BLOCK_UNKNOWN):
        raise PolicyError(
            f"{path}: {UNKNOWN_KEY} must be {REPORT_UNKNOWN!r} or {BLOCK_UNKNOWN!r}"
        )

    return Policy(
        blocked=blocked,
        unknown=unknown,
        exemptions=tuple(
            _exemption(entry, path) for entry in section.get(EXEMPTIONS_KEY) or []
        ),
    )


def _severity(value: object, path: Path) -> Severity:
    severity = severity_named(str(value))
    if severity is Severity.UNKNOWN:
        raise PolicyError(f"{path}: {value!r} is not a severity")
    return severity


def _exemption(entry: object, path: Path) -> Exemption:
    if not isinstance(entry, dict):
        raise PolicyError(f"{path}: each exemption must be a mapping, but one was {entry!r}")

    identifier = str(entry.get("id", "")).strip()
    reason = str(entry.get("reason", "")).strip()
    until = entry.get("until")
    if not identifier:
        raise PolicyError(f"{path}: an exemption must name the advisory it accepts")
    if not reason:
        raise PolicyError(f"{path}: the exemption for {identifier} does not say why")
    if not isinstance(until, date):
        raise PolicyError(
            f"{path}: the exemption for {identifier} needs an expiry date (YYYY-MM-DD). "
            "An exemption without one is never looked at again"
        )
    return Exemption(identifier=identifier, reason=reason, until=until)


__all__ = [
    "BLOCK_UNKNOWN",
    "DEFAULT_POLICY_FILE",
    "REPORT_UNKNOWN",
    "Decision",
    "Exemption",
    "Policy",
    "PolicyError",
    "decide",
    "load_policy",
]

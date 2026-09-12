"""Ask a vulnerability database about the components that were found.

OSV is used because it is the one database that answers for both ecosystems
this repository depends on, with one query shape and no account. The query is
built from the SBOM, so what is asked about is exactly what is locked.

The advisory carries a CVSS vector rather than a band, so the band is computed
here from the vector. A database that only says "moderate" is believed as a
fallback; a database that says nothing at all leaves the severity unknown, and
unknown is reported as unknown. Guessing "low" for an advisory nobody has rated
is the one answer that is certainly wrong.

Being unable to reach the database is a failure, not a clean result. A gate
that passes when the network is down is a gate that passes when it matters.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from .domain import (
    Component,
    CvssError,
    Severity,
    Vulnerability,
    cvss_base_score,
    severity_named,
    severity_of_score,
)


OSV_QUERY_BATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_VULNERABILITY_URL = "https://api.osv.dev/v1/vulns"

SOURCE = "osv"

# 1回のバッチで問い合わせる件数。APIの上限は1000で、半分にしているのは
# 失敗したときに再送する量を小さくするためである。
BATCH_SIZE = 500

REQUEST_TIMEOUT_SECONDS = 30

CVSS_V3_TYPES = ("CVSS_V3", "CVSS_V3.1", "CVSS_V3.0")

Transport = Callable[[str, dict[str, Any] | None], dict[str, Any]]


class OsvUnavailableError(RuntimeError):
    """Raised when the database could not be asked."""


def http_transport(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send one request, and refuse to turn a failure into an empty answer."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            answered: dict[str, Any] = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise OsvUnavailableError(f"{url} could not be asked: {error}") from error
    return answered


@dataclass
class OsvDatabase:
    """The advisories that apply to a set of components."""

    transport: Transport = http_transport
    _details: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)

    def vulnerabilities(self, components: Sequence[Component]) -> tuple[Vulnerability, ...]:
        found: list[Vulnerability] = []
        for batch in _batched(components, BATCH_SIZE):
            found.extend(self._batch(batch))
        return tuple(sorted(found, key=lambda item: (-item.severity.rank, item.identifier)))

    def _batch(self, components: Sequence[Component]) -> list[Vulnerability]:
        answered = self.transport(
            OSV_QUERY_BATCH_URL,
            {
                "queries": [
                    {
                        "package": {"name": component.name, "ecosystem": component.ecosystem},
                        "version": component.version,
                    }
                    for component in components
                ]
            },
        )
        results = answered.get("results", [])
        found: list[Vulnerability] = []
        # 問い合わせと答えは同じ数で並ぶ。ずれたら、どの部品の話かが
        # 分からなくなるので、黙って短いほうに合わせない。
        for component, result in zip(components, results, strict=True):
            for listed in result.get("vulns", []) or []:
                found.append(self._advisory(str(listed["id"]), component))
        return found

    def _advisory(self, identifier: str, component: Component) -> Vulnerability:
        record = self._detail(identifier)
        severity, score = severity_of(record)
        return Vulnerability(
            identifier=identifier,
            component=component,
            severity=severity,
            score=score,
            summary=str(record.get("summary", "")),
            fixed_in=fixed_versions(record, component),
            source=SOURCE,
        )

    def _detail(self, identifier: str) -> dict[str, Any]:
        # 同じ助言が複数の依存に当たることは普通にある。取りに行くのは一度でよい。
        if identifier not in self._details:
            self._details[identifier] = self.transport(
                f"{OSV_VULNERABILITY_URL}/{identifier}",
                None,
            )
        return self._details[identifier]


def severity_of(record: dict[str, Any]) -> tuple[Severity, float | None]:
    """Decide the band of one advisory, and say what it was decided from."""
    scores = []
    for entry in record.get("severity", []) or []:
        if str(entry.get("type", "")) in CVSS_V3_TYPES:
            try:
                scores.append(cvss_base_score(str(entry.get("score", ""))))
            except CvssError:
                continue
    if scores:
        highest = max(scores)
        return severity_of_score(highest), highest

    named = record.get("database_specific", {}).get("severity")
    if named:
        return severity_named(str(named)), None
    return Severity.UNKNOWN, None


def fixed_versions(record: dict[str, Any], component: Component) -> tuple[str, ...]:
    """List the versions that carry the fix, for the component that was asked about."""
    fixed: list[str] = []
    for affected in record.get("affected", []) or []:
        package = affected.get("package", {})
        if str(package.get("name", "")).lower() != component.name.lower():
            continue
        for interval in affected.get("ranges", []) or []:
            for event in interval.get("events", []) or []:
                if "fixed" in event:
                    fixed.append(str(event["fixed"]))
    return tuple(sorted(set(fixed)))


def _batched(components: Sequence[Component], size: int) -> Iterable[Sequence[Component]]:
    for start in range(0, len(components), size):
        yield components[start : start + size]


__all__ = [
    "BATCH_SIZE",
    "OSV_QUERY_BATCH_URL",
    "OSV_VULNERABILITY_URL",
    "SOURCE",
    "OsvDatabase",
    "OsvUnavailableError",
    "Transport",
    "fixed_versions",
    "http_transport",
    "severity_of",
]

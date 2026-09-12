"""Reading what the scanners found, whatever shape they wrote it in.

Two report shapes are read. The first is the one written here, from the
dependency database. The second is Trivy's, because container scanning is the
part of the supply chain that is not described by any lock file: the base
image, the system packages inside it, the things a Dockerfile installed.

Both are turned into the same record before the gate sees them. The gate
decides on severity and identity, and it must not have to know which tool
found what — otherwise adding a third scanner means changing the decision.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .domain import PYPI, Component, Severity, Vulnerability, severity_named


REPORT_VERSION = 1

OWN_FORMAT_KEY = "vulnerabilities"
TRIVY_RESULTS_KEY = "Results"

TRIVY_SOURCE = "trivy"


class ReportError(ValueError):
    """Raised when a report cannot be read."""


def write_report(path: Path, vulnerabilities: tuple[Vulnerability, ...], source: str) -> None:
    """Write what one scanner found, in the shape the gate reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": REPORT_VERSION,
                "source": source,
                OWN_FORMAT_KEY: [
                    {
                        "id": vulnerability.identifier,
                        "package": vulnerability.component.name,
                        "version": vulnerability.component.version,
                        "ecosystem": vulnerability.component.ecosystem,
                        "severity": vulnerability.severity.value,
                        "score": vulnerability.score,
                        "summary": vulnerability.summary,
                        "fixed_in": list(vulnerability.fixed_in),
                        "source": vulnerability.source,
                    }
                    for vulnerability in vulnerabilities
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def read_report(path: Path) -> tuple[Vulnerability, ...]:
    """Read one report, in either shape."""
    if not path.is_file():
        raise ReportError(f"{path} does not exist")

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ReportError(f"{path} is not readable as JSON: {error}") from error

    if isinstance(document, dict) and TRIVY_RESULTS_KEY in document:
        return _read_trivy(document)
    if isinstance(document, dict) and OWN_FORMAT_KEY in document:
        return _read_own(document)
    raise ReportError(
        f"{path} is in no shape this gate reads "
        f"(expected {OWN_FORMAT_KEY!r} or {TRIVY_RESULTS_KEY!r})"
    )


def _read_own(document: dict[str, Any]) -> tuple[Vulnerability, ...]:
    return tuple(
        Vulnerability(
            identifier=str(entry["id"]),
            component=Component(
                name=str(entry["package"]),
                version=str(entry["version"]),
                ecosystem=str(entry.get("ecosystem", PYPI)),
            ),
            severity=severity_named(str(entry.get("severity", ""))),
            score=entry.get("score"),
            summary=str(entry.get("summary", "")),
            fixed_in=tuple(entry.get("fixed_in") or ()),
            source=str(entry.get("source", document.get("source", ""))),
        )
        for entry in document.get(OWN_FORMAT_KEY, [])
    )


def _read_trivy(document: dict[str, Any]) -> tuple[Vulnerability, ...]:
    """Read Trivy's report of what is inside an image."""
    found: list[Vulnerability] = []
    for result in document.get(TRIVY_RESULTS_KEY) or []:
        ecosystem = str(result.get("Type", "container"))
        for entry in result.get("Vulnerabilities") or []:
            fixed = str(entry.get("FixedVersion", "")).strip()
            found.append(
                Vulnerability(
                    identifier=str(entry.get("VulnerabilityID", "")),
                    component=Component(
                        name=str(entry.get("PkgName", "")),
                        version=str(entry.get("InstalledVersion", "")),
                        ecosystem=ecosystem,
                    ),
                    severity=_trivy_severity(entry),
                    summary=str(entry.get("Title", "")),
                    fixed_in=tuple(part.strip() for part in fixed.split(",") if part.strip()),
                    source=TRIVY_SOURCE,
                )
            )
    return tuple(found)


def _trivy_severity(entry: dict[str, Any]) -> Severity:
    return severity_named(str(entry.get("Severity", "")))


__all__ = ["REPORT_VERSION", "TRIVY_SOURCE", "ReportError", "read_report", "write_report"]

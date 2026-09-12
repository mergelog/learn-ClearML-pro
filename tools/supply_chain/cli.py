"""Command line contract of the supply chain checks.

Three commands, in the order they are used.

``sbom`` writes down what the system is made of, from the locks. It is the
input of everything else, and it is worth keeping as an artifact of a release:
a question asked six months later ("were we running the version with that
advisory?") is answerable only if somebody wrote down the answer at the time.

``audit`` asks the vulnerability database about that bill of materials and
writes what it found. It is the only command that needs a network.

``gate`` reads what the scanners found and decides whether this may be
released. It needs no network, so a release decision does not depend on a
service being up at that moment — and the audit that produced the report is
where a network failure is reported, loudly.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from .domain import Vulnerability
from .gate import DEFAULT_POLICY_FILE, Decision, PolicyError, decide, load_policy
from .osv import SOURCE, OsvDatabase, OsvUnavailableError
from .reports import ReportError, read_report, write_report
from .sbom import build_document, collect, read_document


EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_INVALID_USAGE = 2

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SBOM_FILE = REPOSITORY_ROOT / ".generated" / "security" / "sbom.json"
DEFAULT_AUDIT_FILE = REPOSITORY_ROOT / ".generated" / "security" / "dependencies.json"

PYTHON_LOCKS = (
    REPOSITORY_ROOT / "requirements" / "training.txt",
    REPOSITORY_ROOT / "requirements" / "serving.txt",
    REPOSITORY_ROOT / "requirements" / "agent.txt",
    REPOSITORY_ROOT / "requirements" / "dev.txt",
)
PNPM_LOCK = REPOSITORY_ROOT / "pnpm-lock.yaml"

PROJECT_NAME = "stackup"
PROJECT_VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Write the bill of materials, ask what is known about it, and "
            "decide whether it may be released."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    sbom = commands.add_parser("sbom", help="Write the bill of materials from the locks.")
    sbom.add_argument("--output", type=Path, default=DEFAULT_SBOM_FILE)

    audit = commands.add_parser("audit", help="Ask the vulnerability database about it.")
    audit.add_argument("--sbom", type=Path, default=DEFAULT_SBOM_FILE)
    audit.add_argument("--output", type=Path, default=DEFAULT_AUDIT_FILE)

    gate = commands.add_parser("gate", help="Decide whether what was found blocks a release.")
    gate.add_argument(
        "--report",
        action="append",
        dest="reports",
        type=Path,
        default=None,
        help="A scanner report to judge. May be given more than once.",
    )
    gate.add_argument("--policy", type=Path, default=DEFAULT_POLICY_FILE)
    return parser


def main(argv: Sequence[str] | None = None, database: OsvDatabase | None = None) -> int:
    arguments = build_parser().parse_args(argv)

    if arguments.command == "sbom":
        return _write_sbom(arguments.output)
    if arguments.command == "audit":
        return _audit(arguments.sbom, arguments.output, database or OsvDatabase())
    return _gate(arguments.reports or [DEFAULT_AUDIT_FILE], arguments.policy)


def _write_sbom(output: Path) -> int:
    components = collect(PYTHON_LOCKS, PNPM_LOCK)
    document = build_document(components, name=PROJECT_NAME, version=PROJECT_VERSION)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    python = sum(1 for component in components if component.ecosystem == "PyPI")
    print(f"{len(components)} components ({python} PyPI, {len(components) - python} npm)")
    print(f"written to {output}")
    return EXIT_SUCCESS


def _audit(sbom: Path, output: Path, database: OsvDatabase) -> int:
    if not sbom.is_file():
        print(f"{sbom} does not exist. Write it first with `sbom`.", file=sys.stderr)
        return EXIT_INVALID_USAGE

    components = read_document(json.loads(sbom.read_text(encoding="utf-8")))
    try:
        found = database.vulnerabilities(components)
    except OsvUnavailableError as error:
        # 届かなかったことを「何も無かった」と書くと、次に読む人が
        # 「調べた結果、無かった」と読む。書かずに失敗する。
        print(error, file=sys.stderr)
        return EXIT_FAILURE

    write_report(output, found, source=SOURCE)
    print(f"{len(components)} components asked about, {len(found)} advisories found")
    for vulnerability in found:
        print(f"  {vulnerability.describe()}")
    print(f"written to {output}")
    return EXIT_SUCCESS


def _gate(reports: Sequence[Path], policy_file: Path) -> int:
    try:
        policy = load_policy(policy_file)
    except PolicyError as error:
        print(error, file=sys.stderr)
        return EXIT_INVALID_USAGE

    found: list[Vulnerability] = []
    for report in reports:
        try:
            found.extend(read_report(report))
        except ReportError as error:
            print(error, file=sys.stderr)
            return EXIT_INVALID_USAGE

    decision = decide(tuple(found), policy, today=datetime.now(timezone.utc).date())
    _print(decision, len(reports))
    return EXIT_SUCCESS if decision.allowed else EXIT_FAILURE


def _print(decision: Decision, reports: int) -> None:
    print(f"{reports} report(s) judged.")

    for vulnerability, exemption in decision.excused:
        print(f"  accepted until {exemption.until}: {vulnerability.describe()}")
        print(f"    {exemption.reason}")

    for vulnerability, exemption in decision.expired:
        print(f"  the exemption for {vulnerability.identifier} expired on {exemption.until}")

    reported = [item for item in decision.reported if item.severity.value != "none"]
    if reported:
        print(f"  {len(reported)} advisory(ies) below the blocking level:")
        for vulnerability in reported[:20]:
            print(f"    {vulnerability.describe()}")
        if len(reported) > 20:
            print(f"    ... and {len(reported) - 20} more, in the reports")

    if not decision.blocking:
        print("Nothing blocks a release.")
        return

    print("")
    print("A release is blocked by:")
    for vulnerability in decision.blocking:
        print(f"  {vulnerability.describe()}")
        if vulnerability.summary:
            print(f"    {vulnerability.summary}")


if __name__ == "__main__":
    raise SystemExit(main())

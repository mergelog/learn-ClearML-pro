"""Command line contract of the security checks.

Four things can be asked, and they are separate because they are asked at
different moments.

``token`` issues one credential. It is the only command that prints a secret,
and it prints it once: there is nowhere to look it up afterwards, by design.

``repository`` searches what a clone would contain. It runs before a change is
shared, and in CI on every change.

``paths`` searches something that is not tracked — a build artifact, an export,
a directory somebody is about to attach to a ticket.

``clearml`` searches what runs wrote down: Task Parameters and console output.
It answers the question the other two cannot, because a credential can reach
the Server without ever being in a file.

Every search answers with an exit code, so it can be a gate rather than a
report somebody remembers to read.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ml.security.credentials import fingerprint, issue_token
from ml.security.domain import Role, role_named
from ml.security.secrets import Allowlist, SecretFinding, scan_files, scan_text

from .allowlist import DEFAULT_ALLOWLIST_FILE, AllowlistError, load_allowlist
from .clearml_tasks import DEFAULT_TASK_LIMIT, ClearmlTasks, TaskSource
from .sources import REPOSITORY_ROOT, RepositoryError, files_below, tracked_files


EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_INVALID_USAGE = 2

DEFAULT_PROJECT = "Semiconductor Quality Prediction"

TEXT_FORMAT = "text"
JSON_FORMAT = "json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Issue a service credential, or search the repository, a build "
            "artifact or the recorded Tasks for credentials."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    token = commands.add_parser("token", help="Issue one credential for one caller.")
    token.add_argument("--name", required=True, help="How this caller appears in the audit log.")
    token.add_argument(
        "--role",
        required=True,
        choices=sorted(role.value for role in Role),
        help="What this caller is allowed to do.",
    )
    token.add_argument("--format", choices=(TEXT_FORMAT, JSON_FORMAT), default=TEXT_FORMAT)

    repository = commands.add_parser("repository", help="Search the tracked files.")
    _add_allowlist_argument(repository)

    paths = commands.add_parser("paths", help="Search files that are not tracked.")
    paths.add_argument("paths", nargs="+", type=Path, help="Files or directories to search.")
    _add_allowlist_argument(paths)

    tasks = commands.add_parser("clearml", help="Search what recent Tasks wrote down.")
    tasks.add_argument(
        "--project",
        action="append",
        dest="projects",
        default=None,
        help="A ClearML project to search. May be given more than once.",
    )
    tasks.add_argument("--limit", type=int, default=DEFAULT_TASK_LIMIT)
    _add_allowlist_argument(tasks)
    return parser


def _add_allowlist_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=DEFAULT_ALLOWLIST_FILE,
        help="The exemptions to honour, each with the reason it exists.",
    )


def main(argv: Sequence[str] | None = None, source: TaskSource | None = None) -> int:
    arguments = build_parser().parse_args(argv)

    if arguments.command == "token":
        return _issue(arguments.name, arguments.role, arguments.format)

    try:
        allowlist = load_allowlist(arguments.allowlist)
    except AllowlistError as error:
        print(error, file=sys.stderr)
        return EXIT_INVALID_USAGE

    if arguments.command == "repository":
        return _report(_search_repository(allowlist), "the tracked files")
    if arguments.command == "paths":
        return _report(_search_paths(arguments.paths, allowlist), "the given paths")
    return _report(
        _search_tasks(arguments, allowlist, source),
        "the recorded Tasks",
    )


def _issue(name: str, role: str, output_format: str) -> int:
    """Print one credential, once.

    Nothing writes it down. The caller that will present it has to be given it
    now, and the service is configured with the fingerprint instead — which is
    what makes a copy of the configuration useless to whoever finds it.
    """
    try:
        granted = role_named(role)
    except ValueError as error:
        print(error, file=sys.stderr)
        return EXIT_INVALID_USAGE

    token = issue_token()
    entry = f"{name}:{granted.value}:{fingerprint(token)}"

    if output_format == JSON_FORMAT:
        print(json.dumps({"name": name, "role": granted.value, "token": token, "client": entry}))
        return EXIT_SUCCESS

    print(f"caller:      {name}")
    print(f"role:        {granted.value}")
    print(f"permissions: {', '.join(sorted(p.value for p in granted.permissions))}")
    print("")
    print("Give this to the caller. It is not stored, and cannot be shown again:")
    print(f"  {token}")
    print("")
    print("Add this to PREDICTION_API_CLIENTS or OPS_EXPORTER_CLIENTS (';' separated):")
    print(f"  {entry}")
    return EXIT_SUCCESS


def _search_repository(allowlist: Allowlist) -> tuple[SecretFinding, ...]:
    try:
        tracked = tracked_files()
    except RepositoryError as error:
        raise SystemExit(str(error)) from error
    return scan_files(tracked, root=REPOSITORY_ROOT, allowlist=allowlist)


def _search_paths(paths: Sequence[Path], allowlist: Allowlist) -> tuple[SecretFinding, ...]:
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise SystemExit(f"nothing to search at: {', '.join(str(path) for path in missing)}")
    # 相対で渡されたパスをそのまま歩くと、報告の名前が呼び出した場所によって
    # 変わる。除外はパスで書かれているので、先に絶対パスへ揃える。
    given = tuple(path.resolve() for path in paths)
    return scan_files(files_below(given), root=_common_root(given), allowlist=allowlist)


def _common_root(paths: Sequence[Path]) -> Path | None:
    """Name the findings the way the exemptions are written.

    A generated file inside the repository is named relative to it, so one
    exemption covers both the source it was built from and the build output.
    Something outside the repository is named in full, because there is no
    shorter name that stays unambiguous.
    """
    inside = all(path.is_relative_to(REPOSITORY_ROOT) for path in paths)
    return REPOSITORY_ROOT if inside else None


def _search_tasks(
    arguments: argparse.Namespace,
    allowlist: Allowlist,
    source: TaskSource | None,
) -> tuple[SecretFinding, ...]:
    projects = tuple(arguments.projects or (DEFAULT_PROJECT,))
    reader = source or ClearmlTasks(projects=projects, limit=arguments.limit)
    findings: list[SecretFinding] = []
    for recorded in reader.read():
        findings.extend(scan_text(recorded.text, recorded.origin, allowlist=allowlist))
    return tuple(findings)


def _report(findings: Sequence[SecretFinding], searched: str) -> int:
    """Say what was found, and answer with an exit code."""
    if not findings:
        print(f"No credential was found in {searched}.")
        return EXIT_SUCCESS

    print(f"Credentials appear to be written down in {searched}:")
    for finding in findings:
        print(f"  {finding.describe()}")
    print("")
    print(f"{len(findings)} finding(s). Rotate what leaked before removing it: a credential")
    print("that was written down is compromised whether or not the file is deleted.")
    return EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())

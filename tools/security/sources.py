"""Where the secret scan looks.

Three places are worth searching, and they are different enough to be listed
separately.

The *repository* is what everybody gets by cloning. Only tracked files are
scanned, which is what "the repository contains no secret" means: an ignored
``clearml.conf`` on one machine holds real credentials on purpose, and
reporting it every time would train whoever runs the scan to ignore it.

A *build artifact* is what leaves the machine. It is not tracked, so it has to
be pointed at, and it is worth pointing at: a bundle can carry a credential
that never appeared in a source file, because the build put it there.

A *Task* is what a run wrote down. Parameters and console output are read by
everybody with access to the ClearML Server, and a credential printed there
outlives the run that printed it.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

# 中身が資格情報そのものである作業ファイル。追跡されていないので通常は
# 現れないが、パス指定で走査したときに毎回挙がると報告が読まれなくなる。
LIST_TRACKED_COMMAND = ("git", "ls-files", "-z")

# 走査しても意味が無いもの。バイナリは読めず、依存の塊は自分の資産ではない。
SKIPPED_DIRECTORIES = frozenset(
    {
        ".angular",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "node_modules",
    }
)


class RepositoryError(RuntimeError):
    """Raised when the tracked files cannot be listed."""


def tracked_files(root: Path = REPOSITORY_ROOT) -> tuple[Path, ...]:
    """List what a clone would contain.

    ``git`` is asked rather than the filesystem, because the question is about
    what is shared, and only git knows that.
    """
    try:
        listed = subprocess.run(
            LIST_TRACKED_COMMAND,
            cwd=root,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RepositoryError(
            f"the tracked files of {root} could not be listed: {error}"
        ) from error

    names = listed.stdout.decode("utf-8").split("\0")
    return tuple(root / name for name in names if name)


def files_below(paths: Iterable[Path]) -> tuple[Path, ...]:
    """List the files under the given paths, skipping what cannot hold a secret."""
    found: list[Path] = []
    for path in paths:
        if path.is_file():
            found.append(path)
            continue
        found.extend(_walk(path))
    return tuple(found)


def _walk(directory: Path) -> Iterator[Path]:
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if SKIPPED_DIRECTORIES.intersection(path.parts):
            continue
        yield path


__all__ = [
    "REPOSITORY_ROOT",
    "SKIPPED_DIRECTORIES",
    "RepositoryError",
    "files_below",
    "tracked_files",
]

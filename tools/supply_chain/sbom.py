"""What this system is made of, read from the locks that decide it.

The bill of materials is built from the lock files rather than from an
installed environment, for the same reason the locks exist: the answer must be
the same on a laptop, in CI and inside an image. An SBOM produced by looking at
one machine describes that machine.

It is written in CycloneDX because that is what the tools around it read, and
it is deterministic — sorted, with no timestamp — so that two builds of the
same commit produce the same document and a difference in the file means a
difference in the dependencies.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import yaml

from .domain import NPM, PYPI, Component


SBOM_FORMAT = "CycloneDX"
SBOM_SPECIFICATION = "1.5"
SBOM_VERSION = 1

COMPONENT_TYPE = "library"
APPLICATION_TYPE = "application"

# `name==version` の行だけを見る。`-r other.txt` や `--hash=...`、
# 環境マーカー付きの行は、それぞれ別の意味を持つので取り違えない。
PINNED_REQUIREMENT = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)==(?P<version>[^\s;#]+)")

# pnpm の lock は `packages:` の下に `name@version` を鍵として並べる。
# scope 付き (`@angular/core@22.0.0`) があるため、最後の `@` で切る。
# peer 依存を含む鍵 (`react@18.0.0(typescript@5.0.0)`) は括弧から前だけ見る。
PNPM_PACKAGE = re.compile(r"^(?P<name>.+)@(?P<version>[^@]+)$")

PACKAGES_KEY = "packages"
SNAPSHOTS_KEY = "snapshots"


def read_python_lock(path: Path) -> tuple[Component, ...]:
    """Read the pinned versions out of one compiled requirements file."""
    components = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "-")):
            continue
        match = PINNED_REQUIREMENT.match(stripped)
        if match:
            components.append(
                Component(
                    name=match.group("name").lower(),
                    version=match.group("version"),
                    ecosystem=PYPI,
                )
            )
    return tuple(components)


def read_pnpm_lock(path: Path) -> tuple[Component, ...]:
    """Read the resolved versions out of the pnpm lock file."""
    document: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    packages = document.get(PACKAGES_KEY) or document.get(SNAPSHOTS_KEY) or {}
    components = []
    for key in packages:
        component = _npm_component(str(key))
        if component is not None:
            components.append(component)
    return tuple(components)


def _npm_component(key: str) -> Component | None:
    # v6 の lock は `/name/version`、v9 は `name@version`。どちらも来うる。
    identifier = key.split("(", 1)[0]
    if identifier.startswith("/"):
        identifier = identifier[1:]
    match = PNPM_PACKAGE.match(identifier)
    if not match:
        return None
    version = match.group("version")
    if not version or not version[0].isdigit():
        return None
    return Component(name=match.group("name"), version=version, ecosystem=NPM)


def collect(python_locks: Iterable[Path], pnpm_lock: Path | None) -> tuple[Component, ...]:
    """Read every lock, and keep one entry per component."""
    components: set[Component] = set()
    for lock in python_locks:
        components.update(read_python_lock(lock))
    if pnpm_lock is not None and pnpm_lock.is_file():
        components.update(read_pnpm_lock(pnpm_lock))
    return _sorted(components)


def _sorted(components: Iterable[Component]) -> tuple[Component, ...]:
    return tuple(sorted(components, key=lambda item: (item.ecosystem, item.name, item.version)))


def build_document(
    components: Sequence[Component],
    name: str,
    version: str,
) -> dict[str, Any]:
    """Render the components as a CycloneDX document.

    No timestamp is written. A document that differs between two builds of the
    same commit cannot be compared, and comparing them is the point.
    """
    return {
        "bomFormat": SBOM_FORMAT,
        "specVersion": SBOM_SPECIFICATION,
        "version": SBOM_VERSION,
        "metadata": {
            "component": {
                "type": APPLICATION_TYPE,
                "name": name,
                "version": version,
            }
        },
        "components": [
            {
                "type": COMPONENT_TYPE,
                "name": component.name,
                "version": component.version,
                "purl": component.purl,
            }
            for component in _sorted(components)
        ],
    }


def read_document(document: dict[str, Any]) -> tuple[Component, ...]:
    """Read the components back out of a CycloneDX document."""
    components = []
    for entry in document.get("components", []):
        purl = str(entry.get("purl", ""))
        ecosystem = PYPI if purl.startswith("pkg:pypi/") else NPM
        components.append(
            Component(
                name=str(entry["name"]),
                version=str(entry["version"]),
                ecosystem=ecosystem,
            )
        )
    return _sorted(components)


__all__ = [
    "SBOM_FORMAT",
    "SBOM_SPECIFICATION",
    "build_document",
    "collect",
    "read_document",
    "read_pnpm_lock",
    "read_python_lock",
]

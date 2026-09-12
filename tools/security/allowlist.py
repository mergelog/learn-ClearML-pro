"""What the secret scan is allowed to see, and why.

An exemption is a decision, not a setting: somebody looked at a match and
judged it not to be a credential. So each one carries a reason, and the file
that holds them is reviewed like code.

The file is optional. A repository without it is scanned with every rule
everywhere, which is the safe default: forgetting the file cannot quieten the
scan.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ml.security.secrets import Allowlist, Exemption


DEFAULT_ALLOWLIST_FILE = Path(__file__).resolve().parents[2] / "config" / "security.yaml"

SECRET_SCAN_SECTION = "secret_scan"
EXEMPTIONS_KEY = "exemptions"

PATH_KEY = "path"
RULES_KEY = "rules"
REASON_KEY = "reason"


class AllowlistError(ValueError):
    """Raised when the exemptions cannot be read."""


def load_allowlist(path: Path = DEFAULT_ALLOWLIST_FILE) -> Allowlist:
    """Read the exemptions, refusing any that does not say why it exists."""
    if not path.is_file():
        return Allowlist()

    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, dict):
        raise AllowlistError(f"{path} must contain a mapping")

    section = document.get(SECRET_SCAN_SECTION) or {}
    entries = section.get(EXEMPTIONS_KEY) or []
    if not isinstance(entries, list):
        raise AllowlistError(f"{path}: {SECRET_SCAN_SECTION}.{EXEMPTIONS_KEY} must be a list")

    return Allowlist(exemptions=tuple(_exemption(entry, path) for entry in entries))


def _exemption(entry: object, path: Path) -> Exemption:
    if not isinstance(entry, dict):
        raise AllowlistError(f"{path}: each exemption must be a mapping, but one was {entry!r}")

    where = str(entry.get(PATH_KEY, "")).strip()
    reason = str(entry.get(REASON_KEY, "")).strip()
    if not where:
        raise AllowlistError(f"{path}: an exemption without a path excuses everything")
    if not reason:
        # 理由の無い除外は、次にこの行を読む人が判断できない。
        raise AllowlistError(f"{path}: the exemption for {where} does not say why it exists")

    rules = entry.get(RULES_KEY) or ()
    if isinstance(rules, str):
        rules = [rules]
    return Exemption(path=where, rules=tuple(str(rule) for rule in rules), reason=reason)


__all__ = ["DEFAULT_ALLOWLIST_FILE", "AllowlistError", "load_allowlist"]

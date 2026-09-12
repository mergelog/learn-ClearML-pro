"""Find credentials in text that was never meant to hold one.

A secret does not leak by being stolen. It leaks by being written down: into a
committed file, into a Task Parameter that the whole team can read, into a
build artifact that is copied to a laptop, into a log line that is shipped to
a search index. All of those are text, so all of them are searched the same
way here.

The detection is deliberately conservative in one direction and loud in the
other. A rule that never fires is worse than a rule that fires twice, because
the first is discovered after the disclosure. False positives are handled by
naming them — an allowlist entry with a reason — rather than by weakening the
rule.

Two kinds of rule are used together. A *shaped* rule knows what a particular
credential looks like (an issued token of this repository, an AWS key id, a
PEM block) and needs no further judgement. A *contextual* rule looks for a
name that promises a secret ("password", "token", "secret_key") next to a
value, and then asks whether the value looks random enough to be one. Without
the entropy test, the second kind flags every documented placeholder; with it,
``password = "changeme"`` is quiet and ``password = "9fbc1a…"`` is not.

Nothing in this module ever puts a matched value into its output. A report
that quotes the secret it found is a second copy of the secret, in a file that
is usually more widely readable than the first.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from re import Pattern


# 検査から外したい行に書く印。理由まで書かせるのは、印だけが増えて
# 誰も理由を知らない状態を避けるためである。
ALLOW_MARKER = "secret-scan:allow"

# 値がどれだけ「乱数らしいか」の下限。英単語は2.5前後、base64の乱数は4を超える。
# 3.2 は、この境目を実際のリポジトリで確かめて選んだ値である。
MINIMUM_ENTROPY = 3.2

# 文脈規則が値とみなす最短の長さ。これより短い値は、秘密であっても
# 秘密として機能しない。
MINIMUM_VALUE_LENGTH = 12

REDACTED_PREFIX_LENGTH = 4

# 値そのものではなく、値の置き場所。設定を組み立てる側が後から埋める。
PLACEHOLDER_SHAPES = (
    re.compile(r"^\$\{[^}]*\}$"),
    re.compile(r"^\{\{[^}]*\}\}$"),
    re.compile(r"^<[^>]*>$"),
)

# 明らかに人が書いた見本。乱数らしさの前に、名前で落とす。
PLACEHOLDER_WORDS = (
    "change",
    "dummy",
    "example",
    "fake",
    "placeholder",
    "redacted",
    "sample",
    "secret",
    "todo",
    "xxx",
    "your",
)


@dataclass(frozen=True)
class SecretRule:
    """One way a credential shows itself in text."""

    name: str
    pattern: Pattern[str]
    explanation: str
    value_group: int = 0
    entropy_required: bool = False

    def findings(self, line: str) -> Iterator[str]:
        """Yield the candidate values this rule sees in one line."""
        for match in self.pattern.finditer(line):
            value = match.group(self.value_group)
            if self.entropy_required and not looks_random(value):
                continue
            yield value


def looks_random(value: str) -> bool:
    """Judge whether a value could be a credential rather than a word.

    Length alone is not enough (``"this-is-the-default"`` is long) and entropy
    alone is not enough (a short hash-looking word is not a secret). Both are
    required; a value that names itself an example is never one, and neither is
    a placeholder that something else fills in (``${TOKEN}``, ``<token>``) nor
    an identifier that happens to sit next to a promising name.
    """
    if len(value) < MINIMUM_VALUE_LENGTH:
        return False
    if any(shape.match(value) for shape in PLACEHOLDER_SHAPES):
        return False
    if not any(character.isdigit() for character in value):
        # 生成された資格情報はほぼ確実に数字を含み、`bucketCredentials` の
        # ような識別子は含まない。文字だけの秘密を取り逃す代わりに、
        # コードの定数を秘密と読み違えなくなる取引である。
        return False
    lowered = value.lower()
    if any(word in lowered for word in PLACEHOLDER_WORDS):
        return False
    return shannon_entropy(value) >= MINIMUM_ENTROPY


def shannon_entropy(value: str) -> float:
    """Bits of information per character, the usual measure of randomness."""
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum(
        (count / length) * math.log2(count / length) for count in counts.values()
    )


def redact(value: str) -> str:
    """Name a value without repeating it."""
    return f"{value[:REDACTED_PREFIX_LENGTH]}…({len(value)} characters)"


RULES: tuple[SecretRule, ...] = (
    SecretRule(
        name="issued-token",
        pattern=re.compile(r"stk_[A-Za-z0-9_-]{20,}"),
        explanation="a service token issued by this repository",
    ),
    SecretRule(
        name="private-key",
        pattern=re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
        explanation="the beginning of a private key",
    ),
    SecretRule(
        name="aws-access-key-id",
        pattern=re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        explanation="an AWS access key id",
    ),
    SecretRule(
        name="json-web-token",
        pattern=re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+"),
        explanation="a signed JSON Web Token",
    ),
    SecretRule(
        name="credential-in-url",
        pattern=re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s/:@]+:([^\s/:@]{6,})@"),
        explanation="a password inside a URL",
        value_group=1,
        entropy_required=True,
    ),
    SecretRule(
        # ClearML の資格情報は access_key / secret_key という名前で書かれ、
        # 設定ファイルでは必ず引用符が付く。引用符を必須にしているのは、
        # `access_key=_read_environment(...)` のような「読む側のコード」を
        # 資格情報と読み違えないためである。
        name="clearml-credential",
        pattern=re.compile(
            r"(?i)\b(?:access_key|secret_key)\s*[=:]\s*[\"']([^\"'\s]{16,})[\"']"
        ),
        explanation="a ClearML access key or secret key",
        value_group=1,
        entropy_required=True,
    ),
    SecretRule(
        # `.env` や compose、シェルの export の形。1行がまるごと代入に
        # なっているときだけ見る。名前は大文字の環境変数に限る。
        name="environment-credential",
        pattern=re.compile(
            r"^\s*(?:export\s+)?[A-Z][A-Z0-9_]*"
            r"(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)S?\s*=\s*([^\s\"'#]{12,})\s*$"
        ),
        explanation="a credential assigned in an environment file",
        value_group=1,
        entropy_required=True,
    ),
    SecretRule(
        # 名前は `secret_key` とも `userSecret` とも `"apiToken"` とも書かれる。
        # 語の前を許して、語の直後で切ることで、書き方の違いを1つの規則で見る。
        name="named-secret",
        pattern=re.compile(
            r"(?i)[A-Za-z0-9_\-]*(?:passwd|password|secret|token|api[_-]?key|credential)s?"
            r"[\"']?\s*[=:]\s*[\"']([^\"'\s]{12,})[\"']"
        ),
        explanation="a value assigned to a name that promises a secret",
        value_group=1,
        entropy_required=True,
    ),
)


@dataclass(frozen=True)
class SecretFinding:
    """One place where a credential appears to have been written down."""

    origin: str
    line_number: int
    rule: SecretRule
    excerpt: str

    def describe(self) -> str:
        return (
            f"{self.origin}:{self.line_number}: {self.rule.name}: "
            f"{self.rule.explanation} ({self.excerpt})"
        )


@dataclass(frozen=True)
class Exemption:
    """One place that is allowed to match, and why."""

    path: str
    rules: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""

    def covers(self, origin: str, rule: SecretRule) -> bool:
        if self.rules and rule.name not in self.rules:
            return False
        return _matches_glob(origin, self.path)


@dataclass(frozen=True)
class Allowlist:
    """Everything that may match without being a leak."""

    exemptions: tuple[Exemption, ...] = field(default_factory=tuple)

    def excuses(self, origin: str, rule: SecretRule) -> bool:
        return any(exemption.covers(origin, rule) for exemption in self.exemptions)


EMPTY_ALLOWLIST = Allowlist()


def _matches_glob(origin: str, pattern: str) -> bool:
    """Match an origin against a glob, with ``**`` crossing directories.

    ``Path.match`` cannot express "anywhere below this directory", and an
    origin is not always a filesystem path — a Task log is one too. Translating
    the glob ourselves keeps both cases on the same rule.
    """
    return re.fullmatch(_glob_expression(pattern), origin) is not None


@cache
def _glob_expression(pattern: str) -> str:
    expression: list[str] = []
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if pattern.startswith("**/", index):
            expression.append("(?:.*/)?")
            index += 3
            continue
        if pattern.startswith("**", index):
            expression.append(".*")
            index += 2
            continue
        if character == "*":
            expression.append("[^/]*")
        elif character == "?":
            expression.append("[^/]")
        else:
            expression.append(re.escape(character))
        index += 1
    return "".join(expression)


def scan_text(
    text: str,
    origin: str,
    allowlist: Allowlist = EMPTY_ALLOWLIST,
    rules: Sequence[SecretRule] = RULES,
) -> tuple[SecretFinding, ...]:
    """Search one piece of text, line by line."""
    findings: list[SecretFinding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        for rule in rules:
            if allowlist.excuses(origin, rule):
                continue
            findings.extend(
                SecretFinding(
                    origin=origin,
                    line_number=number,
                    rule=rule,
                    excerpt=redact(value),
                )
                for value in rule.findings(line)
            )
    return tuple(findings)


class SecretLeakError(RuntimeError):
    """Raised when something about to be written down holds a credential."""


def refuse_secrets(
    fields: Mapping[str, object],
    origin: str,
    allowlist: Allowlist = EMPTY_ALLOWLIST,
) -> None:
    """Refuse to record a mapping that carries a credential.

    Detection after the fact tells you that a credential is on a server that
    many people can read; refusing at the moment of writing is what keeps it
    from getting there. The check runs on the rendered ``name=value`` text, so
    a credential is caught whether it sits in the value or in the name.
    """
    rendered = "\n".join(f"{name}={value}" for name, value in sorted(fields.items()))
    findings = scan_text(rendered, origin, allowlist=allowlist)
    if not findings:
        return
    raise SecretLeakError(
        f"{origin} would record a credential, and was not written:\n"
        + "\n".join(f"- {finding.describe()}" for finding in findings)
    )


def scan_file(
    path: Path,
    origin: str | None = None,
    allowlist: Allowlist = EMPTY_ALLOWLIST,
    rules: Sequence[SecretRule] = RULES,
) -> tuple[SecretFinding, ...]:
    """Search one file, skipping what cannot be read as text.

    Binary content is skipped rather than decoded with replacements: a
    credential inside a compiled artifact is not found by this kind of search,
    and pretending otherwise would report a clean scan that never looked.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ()
    return scan_text(text, origin or str(path), allowlist=allowlist, rules=rules)


def scan_files(
    paths: Iterable[Path],
    root: Path | None = None,
    allowlist: Allowlist = EMPTY_ALLOWLIST,
    rules: Sequence[SecretRule] = RULES,
) -> tuple[SecretFinding, ...]:
    """Search many files, naming each one relative to the root that was given."""
    findings: list[SecretFinding] = []
    for path in paths:
        origin = str(path.relative_to(root)) if root is not None else str(path)
        findings.extend(scan_file(path, origin=origin, allowlist=allowlist, rules=rules))
    return tuple(findings)


__all__ = [
    "ALLOW_MARKER",
    "MINIMUM_ENTROPY",
    "RULES",
    "Allowlist",
    "Exemption",
    "SecretFinding",
    "SecretLeakError",
    "SecretRule",
    "looks_random",
    "redact",
    "refuse_secrets",
    "scan_file",
    "scan_files",
    "scan_text",
    "shannon_entropy",
]

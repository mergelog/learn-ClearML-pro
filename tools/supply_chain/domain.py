"""What is depended on, what is wrong with it, and how bad that is.

Three ideas live here, and none of them talks to a network or a file.

A *component* is one third-party thing the system runs on, named the way the
ecosystem names it. The identifier is a package URL, because that is what both
the SBOM and the vulnerability database understand, and translating names in
two places is how a dependency quietly stops being checked.

A *vulnerability* is one advisory about one component. It keeps the report it
came from, so a finding can be traced back to the tool that produced it rather
than being argued about in the abstract.

A *severity* is a band, not a score. A release gate is a decision, and a
decision needs categories: "critical" and "everything else" is a policy people
can hold, while "7.4" is not. The score is kept alongside for whoever wants to
know why the band is what it is.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum


PYPI = "PyPI"
NPM = "npm"

# CycloneDX と OSV が共通で読む名前空間。
PURL_TYPE = {PYPI: "pypi", NPM: "npm"}


class Severity(Enum):
    """How bad an advisory is, in the bands a policy is written in."""

    UNKNOWN = "unknown"
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _SEVERITY_ORDER.index(self)

    def at_least(self, other: Severity) -> bool:
        return self.rank >= other.rank


# 低いものから。unknown は「まだ分からない」であって「無害」ではないため、
# none と low のあいだではなく、比較から外れる位置に置いてある。
_SEVERITY_ORDER: tuple[Severity, ...] = (
    Severity.UNKNOWN,
    Severity.NONE,
    Severity.LOW,
    Severity.MEDIUM,
    Severity.HIGH,
    Severity.CRITICAL,
)

SEVERITY_BANDS: tuple[tuple[float, Severity], ...] = (
    (9.0, Severity.CRITICAL),
    (7.0, Severity.HIGH),
    (4.0, Severity.MEDIUM),
    (0.1, Severity.LOW),
)

# 助言データベースが自分で付けている言葉。CVSSが無いときはこれを使う。
NAMED_SEVERITIES = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "moderate": Severity.MEDIUM,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "none": Severity.NONE,
}


@dataclass(frozen=True)
class Component:
    """One third-party thing the system runs on."""

    name: str
    version: str
    ecosystem: str

    @property
    def purl(self) -> str:
        # イメージの走査は debian や alpine といった生態系も返す。名前を
        # 知らないものは、そのまま小文字にして通す。取り違えるより素通りが良い。
        namespace = PURL_TYPE.get(self.ecosystem, self.ecosystem.lower())
        return f"pkg:{namespace}/{self.name}@{self.version}"

    @property
    def coordinates(self) -> str:
        return f"{self.name}@{self.version}"


@dataclass(frozen=True)
class Vulnerability:
    """One advisory about one component, and where it was reported from."""

    identifier: str
    component: Component
    severity: Severity
    summary: str = ""
    fixed_in: tuple[str, ...] = field(default_factory=tuple)
    source: str = ""
    score: float | None = None

    def describe(self) -> str:
        fix = f", fixed in {', '.join(self.fixed_in)}" if self.fixed_in else ", no fix published"
        return (
            f"[{self.severity.value}] {self.identifier} in "
            f"{self.component.coordinates}{fix} ({self.source})"
        )


def severity_of_score(score: float) -> Severity:
    """Put a CVSS base score into the band a policy is written in."""
    for threshold, severity in SEVERITY_BANDS:
        if score >= threshold:
            return severity
    return Severity.NONE


def severity_named(value: str) -> Severity:
    return NAMED_SEVERITIES.get(value.strip().lower(), Severity.UNKNOWN)


# --- CVSS v3 -----------------------------------------------------------------
#
# 助言に付いてくるのはベクタ文字列であって点数ではない。点数にするのは公式の
# 計算式で、実装しているのは基本評価値だけである。時間・環境の評価は、この
# リポジトリの運用に合わせて誰かが決める値であり、機械が埋めるものではない。

_ATTACK_VECTOR = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
_ATTACK_COMPLEXITY = {"L": 0.77, "H": 0.44}
_PRIVILEGES_UNCHANGED = {"N": 0.85, "L": 0.62, "H": 0.27}
_PRIVILEGES_CHANGED = {"N": 0.85, "L": 0.68, "H": 0.50}
_USER_INTERACTION = {"N": 0.85, "R": 0.62}
_IMPACT = {"H": 0.56, "L": 0.22, "N": 0.0}

_VECTOR_PATTERN = re.compile(r"^CVSS:3\.[01]/")


class CvssError(ValueError):
    """Raised when a vector cannot be scored."""


def cvss_base_score(vector: str) -> float:
    """Score a CVSS v3 vector the way the specification defines it."""
    if not _VECTOR_PATTERN.match(vector.strip()):
        raise CvssError(f"not a CVSS v3 vector: {vector!r}")

    metrics = dict(
        part.split(":", 1)
        for part in vector.strip().split("/")[1:]
        if ":" in part
    )
    try:
        changed = metrics["S"] == "C"
        privileges = _PRIVILEGES_CHANGED if changed else _PRIVILEGES_UNCHANGED
        exploitability = (
            8.22
            * _ATTACK_VECTOR[metrics["AV"]]
            * _ATTACK_COMPLEXITY[metrics["AC"]]
            * privileges[metrics["PR"]]
            * _USER_INTERACTION[metrics["UI"]]
        )
        subscore = 1 - (
            (1 - _IMPACT[metrics["C"]])
            * (1 - _IMPACT[metrics["I"]])
            * (1 - _IMPACT[metrics["A"]])
        )
    except KeyError as error:
        raise CvssError(f"{vector!r} is missing or misspells {error}") from error

    if changed:
        impact = 7.52 * (subscore - 0.029) - 3.25 * (subscore - 0.02) ** 15
    else:
        impact = 6.42 * subscore

    if impact <= 0:
        return 0.0
    combined = 1.08 * (impact + exploitability) if changed else impact + exploitability
    return _round_up(min(combined, 10.0))


def _round_up(value: float) -> float:
    """Round up to one decimal, as the CVSS specification requires."""
    # 浮動小数の誤差で 7.0 が 7.000000001 になると、切り上げで 7.1 になる。
    # 1000倍の整数で見てから丸める。
    scaled = round(value * 100_000)
    if scaled % 10_000 == 0:
        return scaled / 100_000
    return (math.floor(scaled / 10_000) + 1) / 10.0


__all__ = [
    "NPM",
    "PYPI",
    "Component",
    "CvssError",
    "Severity",
    "Vulnerability",
    "cvss_base_score",
    "severity_named",
    "severity_of_score",
]

"""Decide whether a trained model is allowed to become a candidate.

Without a gate, "the run finished" and "the model is good enough" are the same
event, and the only thing standing between a bad model and production is
whoever happens to look at the numbers.

This module makes the criteria a file and the decision a value. It never
contacts ClearML and never reads a model: it is handed the metrics a run
produced and answers whether they clear the bar, naming every measure that did
not.

Two decisions are deliberate.

The gate reads the validation split, not the test split. The test split is the
final evaluation of a model that was already chosen; using it to choose would
spend it and leave nothing to confirm the choice with.

A measure the criteria name but the run did not report is a failure, not a
pass. A missing number is not evidence of quality.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from ml.semiconductor_quality.domain import VALIDATION_SPLIT

from .domain import LifecycleError


DEFAULT_CRITERIA_FILE = Path(__file__).resolve().parents[2] / "config" / "model_gate.yaml"

CRITERIA_SPLIT_KEY = "split"
CRITERIA_MINIMUMS_KEY = "minimums"


@dataclass(frozen=True)
class GateCriteria:
    """The bar a model has to clear before it may be registered.

    ``minimums`` maps a measure to the lowest value that is still acceptable.
    Only the measures named here are checked, so adding one is a change to this
    file rather than to the code that applies it.
    """

    split: str = VALIDATION_SPLIT
    minimums: Mapping[str, float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.minimums is None:
            object.__setattr__(self, "minimums", {})

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.split.strip():
            errors.append("split is required, so it is clear which numbers are judged")
        if not self.minimums:
            errors.append("at least one minimum is required, or the gate lets everything through")
        for measure, minimum in self.minimums.items():
            if isinstance(minimum, bool) or not isinstance(minimum, (int, float)):
                errors.append(f"the minimum for {measure!r} must be a number, but was {minimum!r}")
        return tuple(errors)

    def validate(self) -> GateCriteria:
        errors = self.collect_errors()
        if errors:
            raise LifecycleError(
                "Invalid model gate criteria:\n"
                + "\n".join(f"- {message}" for message in errors)
            )
        return self


@dataclass(frozen=True)
class MeasureVerdict:
    """One measure, the bar it had to clear, and whether it did."""

    measure: str
    minimum: float
    value: float | None

    @property
    def passed(self) -> bool:
        return self.value is not None and self.value >= self.minimum

    def describe(self) -> str:
        if self.value is None:
            return f"{self.measure} was not reported, but the gate requires at least {self.minimum}"
        return (
            f"{self.measure} was {self.value:.4f}, but the gate requires at least {self.minimum}"
        )


@dataclass(frozen=True)
class GateVerdict:
    """The decision about one model, with the reason for it kept."""

    split: str
    verdicts: tuple[MeasureVerdict, ...]

    @property
    def passed(self) -> bool:
        return all(verdict.passed for verdict in self.verdicts)

    @property
    def failures(self) -> tuple[MeasureVerdict, ...]:
        return tuple(verdict for verdict in self.verdicts if not verdict.passed)

    def describe(self) -> str:
        if self.passed:
            cleared = ", ".join(
                f"{verdict.measure}>={verdict.minimum}" for verdict in self.verdicts
            )
            return f"the {self.split} split cleared the gate ({cleared})"
        return f"the {self.split} split did not clear the gate: " + "; ".join(
            verdict.describe() for verdict in self.failures
        )

    def as_metadata(self) -> dict[str, str]:
        return {
            "gate_split": self.split,
            "gate_passed": "true" if self.passed else "false",
            "gate_detail": self.describe(),
        }


def load_criteria(path: Path | None = None) -> GateCriteria:
    """Read the criteria from the file the team edits.

    The criteria live outside the code because changing the bar is an
    operational decision, and the file is read at decision time so that a
    change does not need a release.
    """
    criteria_file = path or DEFAULT_CRITERIA_FILE
    try:
        content = yaml.safe_load(criteria_file.read_text(encoding="utf-8"))
    except OSError as error:
        raise LifecycleError(
            f"the model gate criteria at {criteria_file} cannot be read: {error}"
        ) from error
    except yaml.YAMLError as error:
        raise LifecycleError(
            f"the model gate criteria at {criteria_file} are not valid YAML: {error}"
        ) from error

    if not isinstance(content, dict):
        raise LifecycleError(f"the model gate criteria at {criteria_file} do not hold a mapping")

    minimums = content.get(CRITERIA_MINIMUMS_KEY, {})
    if not isinstance(minimums, dict):
        raise LifecycleError(
            f"{CRITERIA_MINIMUMS_KEY} in {criteria_file} must map a measure to a number"
        )

    return GateCriteria(
        split=str(content.get(CRITERIA_SPLIT_KEY, VALIDATION_SPLIT)),
        minimums=dict(minimums),
    ).validate()


def apply_gate(criteria: GateCriteria, evaluation: Mapping[str, object]) -> GateVerdict:
    """Judge one evaluation against the criteria.

    ``evaluation`` is the artifact shape a run produces: a mapping from split
    name to a mapping that holds ``metrics``.
    """
    measured = _metrics_of(criteria.split, evaluation)
    return GateVerdict(
        split=criteria.split,
        verdicts=tuple(
            MeasureVerdict(
                measure=measure,
                minimum=float(minimum),
                value=measured.get(measure),
            )
            for measure, minimum in sorted(criteria.minimums.items())
        ),
    )


def _metrics_of(split: str, evaluation: Mapping[str, object]) -> dict[str, float]:
    """Read the numbers of one split, treating anything unreadable as absent."""
    scored = evaluation.get(split)
    if not isinstance(scored, Mapping):
        return {}

    metrics = scored.get("metrics")
    if not isinstance(metrics, Mapping):
        return {}

    readable: dict[str, float] = {}
    for measure, value in metrics.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        readable[str(measure)] = float(value)
    return readable


def describe_failures(verdicts: Sequence[MeasureVerdict]) -> str:
    return "; ".join(verdict.describe() for verdict in verdicts)

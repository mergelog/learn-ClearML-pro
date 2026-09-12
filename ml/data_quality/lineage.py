"""Record where a training Dataset came from.

A Dataset version answers "these are the rows". It does not answer "these rows
were produced from those rows by that program on that day", which is the
question asked when a model behaves oddly and somebody has to decide whether
the data or the code changed.

The chain this project has is three links long.

``raw`` is what arrives from the process: the measurements as recorded, before
anybody touched them.

``curated`` is what a person or a program decided to keep: rows dropped,
columns renamed, units normalised.

``training`` is the Dataset a model may be fitted on, which is the one ClearML
holds a version of.

Each link records what it was made from, what made it, and when. That is
enough to walk backwards from a model to the rows it learned from, without
anybody having to remember.

This module never contacts ClearML. It builds the record; writing it onto a
Dataset belongs to the code that owns that boundary.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .domain import DataQualityError


class LineageStage(str, Enum):
    """The three forms the data takes on its way to a model."""

    RAW = "raw"
    CURATED = "curated"
    TRAINING = "training"

    def __str__(self) -> str:
        return self.value


# どの段階が、どの段階から作られてよいか。ここに無い組み合わせは拒否される。
# raw に上流が無いのは、そこが記録の始まりだからである。
ALLOWED_SOURCES = {
    LineageStage.RAW: (),
    LineageStage.CURATED: (LineageStage.RAW,),
    LineageStage.TRAINING: (LineageStage.CURATED, LineageStage.RAW),
}


@dataclass(frozen=True)
class Producer:
    """What made one link of the chain.

    ``name`` is the program or the person, ``version`` is which revision of it.
    Both are recorded because "the seeding script" is not an answer once the
    seeding script has changed.
    """

    name: str
    version: str
    executed_by: str

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.name.strip():
            errors.append("the producer needs a name")
        if not self.version.strip():
            errors.append("the producer needs a version, so two runs of it can be told apart")
        return tuple(errors)


@dataclass(frozen=True)
class LineageLink:
    """One step of the chain: what was produced, from what, by what."""

    stage: LineageStage
    identifier: str
    produced_at: str
    producer: Producer
    sources: tuple[str, ...] = ()
    source_stage: LineageStage | None = None
    row_count: int | None = None
    notes: str = ""

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = list(self.producer.collect_errors())
        if not self.identifier.strip():
            errors.append(f"the {self.stage} link needs an identifier")

        allowed = ALLOWED_SOURCES[self.stage]
        if not allowed:
            if self.sources:
                errors.append(f"a {self.stage} link is where the record starts and has no sources")
            return tuple(errors)

        if not self.sources:
            errors.append(f"a {self.stage} link has to say what it was produced from")
        if self.source_stage is None:
            errors.append(f"a {self.stage} link has to say which stage it was produced from")
        elif self.source_stage not in allowed:
            readable = ", ".join(str(stage) for stage in allowed)
            errors.append(
                f"a {self.stage} link cannot be produced from {self.source_stage}. "
                f"It can only come from: {readable}"
            )
        return tuple(errors)

    def as_document(self) -> dict[str, object]:
        return {
            "stage": self.stage.value,
            "identifier": self.identifier,
            "produced_at": self.produced_at,
            "producer": {
                "name": self.producer.name,
                "version": self.producer.version,
                "executed_by": self.producer.executed_by,
            },
            "sources": list(self.sources),
            "source_stage": None if self.source_stage is None else self.source_stage.value,
            "row_count": self.row_count,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class LineageRecord:
    """The whole chain, from the rows that arrived to the Dataset a model uses."""

    links: tuple[LineageLink, ...] = field(default_factory=tuple)

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        for link in self.links:
            errors.extend(link.collect_errors())

        known = {link.identifier for link in self.links}
        for link in self.links:
            unknown = [source for source in link.sources if source not in known]
            if unknown:
                errors.append(
                    f"the {link.stage} link names sources that are not part of this record: "
                    f"{', '.join(unknown)}"
                )

        if not any(link.stage is LineageStage.TRAINING for link in self.links):
            errors.append("a lineage record has to end at a training dataset")
        return tuple(errors)

    def validate(self) -> LineageRecord:
        errors = self.collect_errors()
        if errors:
            raise DataQualityError(
                "Invalid lineage record:\n" + "\n".join(f"- {message}" for message in errors)
            )
        return self

    def trace(self, identifier: str) -> tuple[LineageLink, ...]:
        """Walk backwards from one link to everything it was made from.

        The answer is ordered from the link itself towards the raw data, which
        is the direction somebody investigating reads in.
        """
        by_identifier = {link.identifier: link for link in self.links}
        start = by_identifier.get(identifier)
        if start is None:
            raise DataQualityError(f"{identifier!r} is not part of this lineage record")

        walked: list[LineageLink] = []
        pending: list[str] = [identifier]
        seen: set[str] = set()

        while pending:
            current = pending.pop(0)
            if current in seen:
                continue
            seen.add(current)
            link = by_identifier.get(current)
            if link is None:
                continue
            walked.append(link)
            pending.extend(link.sources)

        return tuple(walked)

    def as_document(self) -> dict[str, object]:
        return {"links": [link.as_document() for link in self.links]}


def build_link(
    stage: LineageStage,
    identifier: str,
    producer: Producer,
    *,
    sources: Sequence[str] = (),
    source_stage: LineageStage | None = None,
    row_count: int | None = None,
    notes: str = "",
    produced_at: str | None = None,
) -> LineageLink:
    """Build one link, stamped with the moment it was produced."""
    return LineageLink(
        stage=stage,
        identifier=identifier,
        produced_at=produced_at or _now(),
        producer=producer,
        sources=tuple(sources),
        source_stage=source_stage,
        row_count=row_count,
        notes=notes,
    )


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

"""Contracts of the model lifecycle.

A run that saves an Output Model answers "a model exists". It does not answer
the questions asked when something goes wrong in production: which model is
serving, was it allowed to get there, who allowed it, and what does it go back
to.

This module states the vocabulary for those answers. It depends on nothing but
the standard library, so a promotion can be decided and refused without a
ClearML Server.

Three rules shape it.

A model is in exactly one stage. The stage is a fact about the model, not a
description of what somebody intends to do with it.

Only declared transitions are possible. A candidate cannot become production
without passing through staging, and a model that failed the gate cannot move
at all. Refusing an undeclared move is what stops an unreviewed model from
being served.

Every move is recorded with who made it and why. A stage without that record
answers "what" but not "on whose authority", which is the question an audit
actually asks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from ml.semiconductor_quality.domain import MODEL_NAME


# ClearMLのタグは検索の単位なので、段階もタグとして持つ。metadataだけだと
# 「いまproductionはどれか」を一覧から絞り込めない。
STAGE_TAG_PREFIX = "stage"

METADATA_STAGE = "stage"
METADATA_MODEL_VERSION = "model_version"
METADATA_DATASET_ID = "dataset_id"
METADATA_DATASET_VERSION = "dataset_version"
METADATA_TRAIN_TASK_ID = "train_task_id"
# 学習時に見た不良の割合。推論側が「いま返している割合」と比べる相手になる。
METADATA_TRAINING_FAILURE_SHARE = "training_failure_share"
METADATA_EVALUATE_TASK_ID = "evaluate_task_id"
METADATA_REGISTER_TASK_ID = "register_task_id"
METADATA_PROMOTED_BY = "promoted_by"
METADATA_PROMOTED_AT = "promoted_at"
METADATA_PROMOTION_REASON = "promotion_reason"
METADATA_PREVIOUS_STAGE = "previous_stage"



class LifecycleError(RuntimeError):
    """Raised when a model cannot move the way it was asked to."""


class ModelStage(str, Enum):
    """Where a model stands, as a fact rather than an intention.

    There is no stage for a model that failed the gate, because such a model is
    never registered. Keeping it out of the registry entirely is a stronger
    guarantee than marking it, and what it was measured on is still readable
    from the run that produced it.
    """

    CANDIDATE = "candidate"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"

    @property
    def tag(self) -> str:
        return f"{STAGE_TAG_PREFIX}:{self.value}"

    def __str__(self) -> str:
        return self.value


# 許される遷移だけを書く。ここに無い移動は拒否される。
# candidate から production へ直接行けないのは、staging での確認を飛ばさない
# ため。archived -> production があるのは、rollbackが「戻す」ことだからである。
ALLOWED_TRANSITIONS: Mapping[ModelStage, tuple[ModelStage, ...]] = {
    ModelStage.CANDIDATE: (ModelStage.STAGING, ModelStage.ARCHIVED),
    ModelStage.STAGING: (ModelStage.PRODUCTION, ModelStage.ARCHIVED),
    ModelStage.PRODUCTION: (ModelStage.ARCHIVED,),
    ModelStage.ARCHIVED: (ModelStage.PRODUCTION,),
}

# 同時に1つしか存在してはいけない段階。昇格すると、いまの持ち主が退く。
EXCLUSIVE_STAGES = (ModelStage.PRODUCTION,)

ALL_STAGE_TAGS = tuple(stage.tag for stage in ModelStage)


@dataclass(frozen=True)
class ModelIdentity:
    """What a model is, in terms a person can act on.

    ``model_id`` is what ClearML addresses and never changes. ``model_version``
    is what a person reads in a runbook, and is built so that it names the data
    it learned from and the execution that produced it. Both are recorded,
    because a rollback is decided by reading and carried out by addressing.
    """

    model_id: str
    model_version: str
    stage: ModelStage
    dataset_id: str
    dataset_version: str
    train_task_id: str

    @property
    def name(self) -> str:
        return MODEL_NAME


@dataclass(frozen=True)
class PromotionRequest:
    """One asked-for move of one model, with the authority behind it."""

    model_id: str
    target: ModelStage
    approved_by: str
    reason: str

    def collect_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.model_id.strip():
            errors.append("model_id is required")
        if not self.approved_by.strip():
            errors.append("approved_by is required, because a stage records whose decision it was")
        if not self.reason.strip():
            errors.append("reason is required, because a stage without a reason cannot be reviewed")
        return tuple(errors)

    def validate(self) -> PromotionRequest:
        errors = self.collect_errors()
        if errors:
            raise LifecycleError(
                "Invalid promotion request:\n"
                + "\n".join(f"- {message}" for message in errors)
            )
        return self


@dataclass(frozen=True)
class PromotionRecord:
    """What one move of one model looked like once it was carried out."""

    model_id: str
    model_version: str
    previous_stage: ModelStage
    stage: ModelStage
    approved_by: str
    reason: str
    promoted_at: str
    demoted: tuple[str, ...] = ()

    def as_metadata(self) -> dict[str, str]:
        return {
            METADATA_STAGE: self.stage.value,
            METADATA_PREVIOUS_STAGE: self.previous_stage.value,
            METADATA_PROMOTED_BY: self.approved_by,
            METADATA_PROMOTED_AT: self.promoted_at,
            METADATA_PROMOTION_REASON: self.reason,
        }


def build_model_version(dataset_version: str, train_task_id: str, created_at: datetime) -> str:
    """Name a model so that a person can tell two of them apart.

    The name carries the data it learned from and the execution that produced
    it, in that order, because a rollback starts from "which data was this" and
    ends at "which run do I go back to". The timestamp is UTC so that versions
    from two machines still sort against each other.
    """
    stamp = created_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{dataset_version}-{stamp}-{train_task_id[:8]}"


def require_transition(current: ModelStage, target: ModelStage) -> None:
    """Refuse a move that the lifecycle does not declare."""
    if target == current:
        raise LifecycleError(f"the model is already {current}")

    allowed = ALLOWED_TRANSITIONS[current]
    if target not in allowed:
        readable = ", ".join(str(stage) for stage in allowed) or "nothing"
        raise LifecycleError(
            f"a {current} model cannot become {target}. From {current} it can only "
            f"become {readable}"
        )


def stage_of(tags: Sequence[str]) -> ModelStage:
    """Read the stage a model carries, and refuse an ambiguous one.

    Two stage tags on one model means two people decided different things, and
    guessing which one wins is exactly the mistake this refuses to make.
    """
    found = [stage for stage in ModelStage if stage.tag in tags]
    if not found:
        raise LifecycleError(
            f"the model carries no stage tag. Expected one of: {', '.join(ALL_STAGE_TAGS)}"
        )
    if len(found) > 1:
        carried = ", ".join(str(stage) for stage in found)
        raise LifecycleError(f"the model carries more than one stage tag: {carried}")
    return found[0]


def replace_stage_tag(tags: Sequence[str], stage: ModelStage) -> list[str]:
    """Put one stage tag on a model, keeping every tag that means something else."""
    kept = [tag for tag in tags if tag not in ALL_STAGE_TAGS]
    return [*kept, stage.tag]


def utc_now() -> str:
    """The moment a decision was made, written the same way everywhere."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

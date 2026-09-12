"""ClearML boundary of the model lifecycle.

Every call into the ClearML SDK that a promotion makes is made from here, so
:mod:`domain` and :mod:`gate` decide without a server and can be exercised
without one.

The stage of a model is written twice, on purpose.

As a tag, because tags are what ClearML searches by, and "which model is in
production" has to be answerable from a list rather than by opening models one
at a time.

As metadata, together with who decided it, when, and why. A tag says what is
true now; the metadata says how it became true, which is what an audit and a
rollback both read.

Promoting into an exclusive stage moves whoever held it out of the way in the
same operation, so there is never a moment with two production models, and the
model that stepped aside records what replaced it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from clearml import Model

from ml.semiconductor_quality.domain import MODEL_NAME

from .domain import (
    EXCLUSIVE_STAGES,
    METADATA_DATASET_ID,
    METADATA_DATASET_VERSION,
    METADATA_MODEL_VERSION,
    METADATA_PREVIOUS_STAGE,
    METADATA_PROMOTED_AT,
    METADATA_PROMOTED_BY,
    METADATA_PROMOTION_REASON,
    METADATA_STAGE,
    METADATA_TRAIN_TASK_ID,
    LifecycleError,
    ModelIdentity,
    ModelStage,
    PromotionRecord,
    PromotionRequest,
    replace_stage_tag,
    require_transition,
    stage_of,
    utc_now,
)


# metadataは文字列で持つ。段階も承認者も理由も、後から機械が計算し直せる値では
# なく、そのとき決めたことの記録だからである。
METADATA_TYPE = "str"

DEMOTED_BY_METADATA = "replaced_by"


@dataclass(frozen=True)
class RegisteredModel:
    """One model as the registry sees it: its identity and its raw record."""

    identity: ModelIdentity
    tags: tuple[str, ...]
    metadata: dict[str, str]


class ModelRegistry:
    """Reads and moves models, and refuses moves the lifecycle does not allow."""

    def __init__(self, model_name: str = MODEL_NAME, project_name: str | None = None) -> None:
        # 既定でプロジェクトを絞らないのは、同じモデルが単発学習の
        # プロジェクトからもPipelineのステップからも登録されるためである。
        # 「いまproductionはどれか」は、どこで作られたかに依らず1つでなければ
        # ならない。
        self._model_name = model_name
        self._project_name = project_name

    def find(self, model_id: str) -> RegisteredModel:
        """Read one model by the identifier that never changes."""
        return _describe(_model(model_id))

    def in_stage(self, stage: ModelStage) -> tuple[RegisteredModel, ...]:
        """List the models that currently carry one stage."""
        models: Sequence[Model] = Model.query_models(
            project_name=self._project_name,
            model_name=self._model_name,
            tags=[stage.tag],
            include_archived=True,
        )
        return tuple(_describe(model) for model in models)

    def current(self, stage: ModelStage) -> RegisteredModel | None:
        """The single model holding an exclusive stage, or nothing.

        More than one is refused rather than resolved, because picking one
        would hide that two promotions disagreed.
        """
        holders = self.in_stage(stage)
        if not holders:
            return None
        if len(holders) > 1:
            versions = ", ".join(held.identity.model_version for held in holders)
            raise LifecycleError(
                f"{len(holders)} models are marked {stage}, which cannot be true: {versions}"
            )
        return holders[0]

    def promote(self, request: PromotionRequest) -> PromotionRecord:
        """Move one model to another stage, with the decision recorded.

        The move is refused before anything is written when the lifecycle does
        not declare it, so a rejected model cannot reach production by way of a
        second attempt.
        """
        request.validate()
        model = _model(request.model_id)
        described = _describe(model)
        current = described.identity.stage

        require_transition(current, request.target)

        demoted = self._clear_exclusive_stage(request)
        record = PromotionRecord(
            model_id=described.identity.model_id,
            model_version=described.identity.model_version,
            previous_stage=current,
            stage=request.target,
            approved_by=request.approved_by.strip(),
            reason=request.reason.strip(),
            promoted_at=utc_now(),
            demoted=demoted,
        )
        _apply(model, record)
        return record

    def rollback(self, approved_by: str, reason: str) -> PromotionRecord:
        """Put the model that production replaced back into production.

        The candidate is the most recently archived model, which is the one the
        current production model displaced. Rolling back is therefore an
        ordinary promotion, and is recorded as one.
        """
        replaced = self._most_recently_archived()
        if replaced is None:
            raise LifecycleError(
                "no archived model is available to roll back to. A rollback "
                "restores the model that production replaced, and nothing has "
                "been replaced yet"
            )

        return self.promote(
            PromotionRequest(
                model_id=replaced.identity.model_id,
                target=ModelStage.PRODUCTION,
                approved_by=approved_by,
                reason=reason,
            )
        )

    def _clear_exclusive_stage(self, request: PromotionRequest) -> tuple[str, ...]:
        """Move whoever holds an exclusive stage out of the way."""
        if request.target not in EXCLUSIVE_STAGES:
            return ()

        holder = self.current(request.target)
        if holder is None or holder.identity.model_id == request.model_id:
            return ()

        demotion = PromotionRecord(
            model_id=holder.identity.model_id,
            model_version=holder.identity.model_version,
            previous_stage=holder.identity.stage,
            stage=ModelStage.ARCHIVED,
            approved_by=request.approved_by.strip(),
            reason=f"replaced in {request.target} by {request.model_id}",
            promoted_at=utc_now(),
        )
        demoted_model = _model(holder.identity.model_id)
        _apply(demoted_model, demotion)
        demoted_model.set_metadata(DEMOTED_BY_METADATA, request.model_id, METADATA_TYPE)
        return (holder.identity.model_id,)

    def _most_recently_archived(self) -> RegisteredModel | None:
        archived = self.in_stage(ModelStage.ARCHIVED)
        if not archived:
            return None
        return max(archived, key=lambda model: model.metadata.get(METADATA_PROMOTED_AT, ""))


def _model(model_id: str) -> Model:
    if not model_id.strip():
        raise LifecycleError("a model id is required")
    try:
        return Model(model_id=model_id)
    except Exception as error:
        raise LifecycleError(f"model {model_id} cannot be read: {error}") from error


def _describe(model: Model) -> RegisteredModel:
    tags = tuple(str(tag) for tag in (model.tags or ()))
    metadata = {
        name: str(entry.get("value", ""))
        for name, entry in (model.get_all_metadata() or {}).items()
    }
    identity = ModelIdentity(
        model_id=str(model.id),
        model_version=metadata.get(METADATA_MODEL_VERSION, str(model.id)),
        stage=stage_of(tags),
        dataset_id=metadata.get(METADATA_DATASET_ID, ""),
        dataset_version=metadata.get(METADATA_DATASET_VERSION, ""),
        train_task_id=metadata.get(METADATA_TRAIN_TASK_ID, ""),
    )
    return RegisteredModel(identity=identity, tags=tags, metadata=metadata)


def _apply(model: Model, record: PromotionRecord) -> None:
    """Write one decision onto a model: first the record, then the tag.

    The metadata is written before the tag, so a failure halfway leaves a model
    whose tag still says the old stage rather than one that claims a stage
    nobody can account for.
    """
    for name, value in record.as_metadata().items():
        model.set_metadata(name, value, METADATA_TYPE)
    model.tags = replace_stage_tag(model.tags or (), record.stage)


def describe_record(record: PromotionRecord) -> str:
    lines = [
        f"{record.model_version} ({record.model_id})",
        f"  {record.previous_stage} -> {record.stage}",
        f"  approved by {record.approved_by} at {record.promoted_at}",
        f"  reason: {record.reason}",
    ]
    lines.extend(f"  archived: {model_id}" for model_id in record.demoted)
    return "\n".join(lines)


__all__ = [
    "METADATA_PREVIOUS_STAGE",
    "METADATA_PROMOTED_BY",
    "METADATA_PROMOTION_REASON",
    "METADATA_STAGE",
    "ModelRegistry",
    "RegisteredModel",
    "describe_record",
]

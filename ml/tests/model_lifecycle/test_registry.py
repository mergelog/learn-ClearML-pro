from __future__ import annotations

import unittest
from collections.abc import Iterable
from unittest import mock

from ml.model_lifecycle import registry as registry_module
from ml.model_lifecycle.domain import (
    METADATA_MODEL_VERSION,
    METADATA_PROMOTED_AT,
    METADATA_PROMOTED_BY,
    METADATA_PROMOTION_REASON,
    METADATA_STAGE,
    LifecycleError,
    ModelStage,
    PromotionRequest,
)
from ml.model_lifecycle.registry import DEMOTED_BY_METADATA, ModelRegistry


class FakeModel:
    """A ClearML Model that lives in memory, so no server is contacted."""

    def __init__(self, model_id: str, stage: ModelStage, **metadata: str) -> None:
        self.id = model_id
        self.tags: list[str] = [stage.tag]
        self._metadata: dict[str, str] = {
            METADATA_MODEL_VERSION: f"1.0.0-{model_id}",
            METADATA_STAGE: stage.value,
            **metadata,
        }

    def get_all_metadata(self) -> dict[str, dict[str, str]]:
        return {name: {"value": value} for name, value in self._metadata.items()}

    def set_metadata(self, key: str, value: str, _type: str | None = None) -> bool:
        self._metadata[key] = value
        return True

    @property
    def stage(self) -> str:
        return self._metadata[METADATA_STAGE]


class RegistryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.models: dict[str, FakeModel] = {}
        self.sdk = mock.MagicMock(name="Model")
        self.sdk.side_effect = lambda model_id: self._model(model_id)
        self.sdk.query_models.side_effect = self._query
        patcher = mock.patch.object(registry_module, "Model", self.sdk)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.registry = ModelRegistry()

    def add(self, model_id: str, stage: ModelStage, **metadata: str) -> FakeModel:
        model = FakeModel(model_id, stage, **metadata)
        self.models[model_id] = model
        return model

    def _model(self, model_id: str) -> FakeModel:
        if model_id not in self.models:
            raise ValueError(f"no such model: {model_id}")
        return self.models[model_id]

    def _query(self, **keywords: object) -> list[FakeModel]:
        requested = keywords.get("tags")
        wanted = set(requested) if isinstance(requested, Iterable) else set()
        return [model for model in self.models.values() if wanted <= set(model.tags)]

    def promote(self, model_id: str, target: ModelStage, **overrides: str) -> object:
        request = PromotionRequest(
            model_id=model_id,
            target=target,
            approved_by=overrides.get("approved_by", "reviewer"),
            reason=overrides.get("reason", "the trial ran without regressions"),
        )
        return self.registry.promote(request)


class ReadingTest(RegistryTestCase):
    def test_a_model_is_read_by_the_identifier_that_never_changes(self) -> None:
        self.add("model-a", ModelStage.CANDIDATE)

        found = self.registry.find("model-a")

        self.assertEqual(found.identity.model_id, "model-a")
        self.assertEqual(found.identity.stage, ModelStage.CANDIDATE)

    def test_a_model_that_does_not_exist_is_reported_by_name(self) -> None:
        with self.assertRaises(LifecycleError) as raised:
            self.registry.find("absent")

        self.assertIn("absent", str(raised.exception))

    def test_an_empty_identifier_is_refused_before_anything_is_read(self) -> None:
        with self.assertRaises(LifecycleError):
            self.registry.find("  ")

    def test_the_models_holding_a_stage_can_be_listed(self) -> None:
        self.add("model-a", ModelStage.CANDIDATE)
        self.add("model-b", ModelStage.CANDIDATE)
        self.add("model-c", ModelStage.PRODUCTION)

        held = self.registry.in_stage(ModelStage.CANDIDATE)

        self.assertEqual(sorted(model.identity.model_id for model in held), ["model-a", "model-b"])

    def test_nothing_serves_when_nothing_was_promoted(self) -> None:
        self.assertIsNone(self.registry.current(ModelStage.PRODUCTION))

    def test_two_models_claiming_to_serve_is_refused_rather_than_resolved(self) -> None:
        self.add("model-a", ModelStage.PRODUCTION)
        self.add("model-b", ModelStage.PRODUCTION)

        with self.assertRaises(LifecycleError) as raised:
            self.registry.current(ModelStage.PRODUCTION)

        self.assertIn("cannot be true", str(raised.exception))


class PromotionTest(RegistryTestCase):
    def test_a_candidate_moves_to_staging(self) -> None:
        model = self.add("model-a", ModelStage.CANDIDATE)

        self.promote("model-a", ModelStage.STAGING)

        self.assertEqual(model.tags, [ModelStage.STAGING.tag])
        self.assertEqual(model.stage, "staging")

    def test_the_decision_is_recorded_with_the_model(self) -> None:
        model = self.add("model-a", ModelStage.CANDIDATE)

        self.promote("model-a", ModelStage.STAGING, approved_by="reviewer", reason="looks good")

        self.assertEqual(model._metadata[METADATA_PROMOTED_BY], "reviewer")
        self.assertEqual(model._metadata[METADATA_PROMOTION_REASON], "looks good")
        self.assertTrue(model._metadata[METADATA_PROMOTED_AT])

    def test_a_candidate_cannot_reach_production_without_review(self) -> None:
        model = self.add("model-a", ModelStage.CANDIDATE)

        with self.assertRaises(LifecycleError):
            self.promote("model-a", ModelStage.PRODUCTION)

        self.assertEqual(model.tags, [ModelStage.CANDIDATE.tag])

    def test_a_move_without_an_approver_changes_nothing(self) -> None:
        model = self.add("model-a", ModelStage.CANDIDATE)

        with self.assertRaises(LifecycleError):
            self.promote("model-a", ModelStage.STAGING, approved_by="")

        self.assertEqual(model.tags, [ModelStage.CANDIDATE.tag])

    def test_promoting_into_production_moves_the_previous_one_aside(self) -> None:
        serving = self.add("model-old", ModelStage.PRODUCTION)
        self.add("model-new", ModelStage.STAGING)

        record = self.promote("model-new", ModelStage.PRODUCTION)

        self.assertEqual(serving.tags, [ModelStage.ARCHIVED.tag])
        self.assertEqual(record.demoted, ("model-old",))  # type: ignore[attr-defined]

    def test_the_model_that_stepped_aside_records_what_replaced_it(self) -> None:
        serving = self.add("model-old", ModelStage.PRODUCTION)
        self.add("model-new", ModelStage.STAGING)

        self.promote("model-new", ModelStage.PRODUCTION)

        self.assertEqual(serving._metadata[DEMOTED_BY_METADATA], "model-new")

    def test_only_one_model_serves_after_a_promotion(self) -> None:
        self.add("model-old", ModelStage.PRODUCTION)
        self.add("model-new", ModelStage.STAGING)

        self.promote("model-new", ModelStage.PRODUCTION)

        serving = self.registry.current(ModelStage.PRODUCTION)
        self.assertIsNotNone(serving)
        self.assertEqual(serving.identity.model_id, "model-new")  # type: ignore[union-attr]

    def test_the_record_says_where_the_model_came_from(self) -> None:
        self.add("model-a", ModelStage.STAGING)

        record = self.promote("model-a", ModelStage.PRODUCTION)

        self.assertEqual(record.previous_stage, ModelStage.STAGING)  # type: ignore[attr-defined]
        self.assertEqual(record.stage, ModelStage.PRODUCTION)  # type: ignore[attr-defined]


class RollbackTest(RegistryTestCase):
    def test_the_model_production_replaced_goes_back(self) -> None:
        self.add(
            "model-old",
            ModelStage.ARCHIVED,
            **{METADATA_PROMOTED_AT: "2026-09-08T04:00:00Z"},
        )
        self.add("model-new", ModelStage.PRODUCTION)

        record = self.registry.rollback("responder", "the new model started rejecting good wafers")

        self.assertEqual(record.model_id, "model-old")
        self.assertEqual(record.stage, ModelStage.PRODUCTION)

    def test_the_model_that_was_serving_steps_aside(self) -> None:
        self.add(
            "model-old",
            ModelStage.ARCHIVED,
            **{METADATA_PROMOTED_AT: "2026-09-08T04:00:00Z"},
        )
        serving = self.add("model-new", ModelStage.PRODUCTION)

        self.registry.rollback("responder", "the new model started rejecting good wafers")

        self.assertEqual(serving.tags, [ModelStage.ARCHIVED.tag])

    def test_the_most_recently_replaced_model_is_the_one_restored(self) -> None:
        self.add(
            "model-older",
            ModelStage.ARCHIVED,
            **{METADATA_PROMOTED_AT: "2026-09-01T04:00:00Z"},
        )
        self.add(
            "model-recent",
            ModelStage.ARCHIVED,
            **{METADATA_PROMOTED_AT: "2026-09-08T04:00:00Z"},
        )
        self.add("model-new", ModelStage.PRODUCTION)

        record = self.registry.rollback("responder", "latency regression")

        self.assertEqual(record.model_id, "model-recent")

    def test_a_rollback_with_nothing_to_go_back_to_is_refused(self) -> None:
        self.add("model-new", ModelStage.PRODUCTION)

        with self.assertRaises(LifecycleError) as raised:
            self.registry.rollback("responder", "latency regression")

        self.assertIn("nothing has been replaced", str(raised.exception))

    def test_a_rollback_still_records_who_decided_it(self) -> None:
        model = self.add(
            "model-old",
            ModelStage.ARCHIVED,
            **{METADATA_PROMOTED_AT: "2026-09-08T04:00:00Z"},
        )
        self.add("model-new", ModelStage.PRODUCTION)

        self.registry.rollback("responder", "latency regression")

        self.assertEqual(model._metadata[METADATA_PROMOTED_BY], "responder")
        self.assertEqual(model._metadata[METADATA_PROMOTION_REASON], "latency regression")


if __name__ == "__main__":
    unittest.main()

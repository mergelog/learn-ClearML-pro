from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from ml.model_lifecycle.domain import (
    ALL_STAGE_TAGS,
    ALLOWED_TRANSITIONS,
    EXCLUSIVE_STAGES,
    LifecycleError,
    ModelStage,
    PromotionRecord,
    PromotionRequest,
    build_model_version,
    replace_stage_tag,
    require_transition,
    stage_of,
)


class ModelStageTest(unittest.TestCase):
    def test_a_stage_is_searchable_as_a_tag(self) -> None:
        self.assertEqual(ModelStage.PRODUCTION.tag, "stage:production")

    def test_a_stage_reads_as_its_own_name(self) -> None:
        self.assertEqual(f"{ModelStage.CANDIDATE}", "candidate")

    def test_every_stage_has_a_tag_of_its_own(self) -> None:
        self.assertEqual(len(set(ALL_STAGE_TAGS)), len(ModelStage))


class TransitionTest(unittest.TestCase):
    def test_every_stage_declares_where_it_can_go(self) -> None:
        self.assertEqual(set(ALLOWED_TRANSITIONS), set(ModelStage))

    def test_a_candidate_is_reviewed_before_it_serves(self) -> None:
        require_transition(ModelStage.CANDIDATE, ModelStage.STAGING)

        with self.assertRaises(LifecycleError) as raised:
            require_transition(ModelStage.CANDIDATE, ModelStage.PRODUCTION)

        self.assertIn("staging", str(raised.exception))

    def test_a_model_can_be_put_back_into_production(self) -> None:
        require_transition(ModelStage.ARCHIVED, ModelStage.PRODUCTION)

    def test_production_is_only_left_by_being_replaced(self) -> None:
        self.assertEqual(ALLOWED_TRANSITIONS[ModelStage.PRODUCTION], (ModelStage.ARCHIVED,))

    def test_moving_a_model_to_where_it_already_is_is_refused(self) -> None:
        with self.assertRaises(LifecycleError) as raised:
            require_transition(ModelStage.PRODUCTION, ModelStage.PRODUCTION)

        self.assertIn("already", str(raised.exception))

    def test_only_one_model_may_serve_at_a_time(self) -> None:
        self.assertEqual(EXCLUSIVE_STAGES, (ModelStage.PRODUCTION,))


class StageTagTest(unittest.TestCase):
    def test_the_stage_a_model_carries_is_read_from_its_tags(self) -> None:
        self.assertEqual(stage_of(["framework:sklearn", "stage:staging"]), ModelStage.STAGING)

    def test_a_model_without_a_stage_is_refused(self) -> None:
        with self.assertRaises(LifecycleError) as raised:
            stage_of(["framework:sklearn"])

        self.assertIn("stage:candidate", str(raised.exception))

    def test_a_model_with_two_stages_is_refused_rather_than_resolved(self) -> None:
        with self.assertRaises(LifecycleError) as raised:
            stage_of(["stage:staging", "stage:production"])

        self.assertIn("more than one", str(raised.exception))

    def test_changing_the_stage_keeps_every_other_tag(self) -> None:
        tags = replace_stage_tag(["framework:sklearn", "stage:candidate"], ModelStage.STAGING)

        self.assertEqual(tags, ["framework:sklearn", "stage:staging"])

    def test_a_model_never_ends_up_with_two_stage_tags(self) -> None:
        tags = replace_stage_tag(["stage:candidate", "stage:staging"], ModelStage.PRODUCTION)

        self.assertEqual(tags, ["stage:production"])


class ModelVersionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.moment = datetime(2026, 9, 8, 4, 30, 15, tzinfo=timezone.utc)

    def test_a_version_names_the_data_it_learned_from(self) -> None:
        version = build_model_version("1.0.0", "abcdef0123456789", self.moment)

        self.assertTrue(version.startswith("1.0.0-"))

    def test_a_version_names_the_execution_that_produced_it(self) -> None:
        version = build_model_version("1.0.0", "abcdef0123456789", self.moment)

        self.assertTrue(version.endswith("-abcdef01"))

    def test_two_runs_of_the_same_data_produce_different_versions(self) -> None:
        first = build_model_version("1.0.0", "abcdef0123456789", self.moment)
        second = build_model_version(
            "1.0.0",
            "abcdef0123456789",
            self.moment + timedelta(seconds=1),
        )

        self.assertNotEqual(first, second)

    def test_versions_from_two_machines_still_sort_against_each_other(self) -> None:
        earlier = build_model_version(
            "1.0.0",
            "aaaaaaaa",
            self.moment.astimezone(timezone(timedelta(hours=9))),
        )
        later = build_model_version(
            "1.0.0",
            "bbbbbbbb",
            self.moment + timedelta(minutes=1),
        )

        self.assertLess(earlier, later)


class PromotionRequestTest(unittest.TestCase):
    def build(self, **overrides: str) -> PromotionRequest:
        values: dict[str, object] = {
            "model_id": "model-id",
            "target": ModelStage.STAGING,
            "approved_by": "reviewer",
            "reason": "validation recall is high enough for a trial",
        }
        values.update(overrides)
        return PromotionRequest(**values)  # type: ignore[arg-type]

    def test_a_complete_request_is_accepted(self) -> None:
        request = self.build()

        self.assertIs(request.validate(), request)

    def test_a_move_without_an_approver_is_refused(self) -> None:
        with self.assertRaises(LifecycleError) as raised:
            self.build(approved_by="  ").validate()

        self.assertIn("approved_by", str(raised.exception))

    def test_a_move_without_a_reason_is_refused(self) -> None:
        with self.assertRaises(LifecycleError) as raised:
            self.build(reason="").validate()

        self.assertIn("reason", str(raised.exception))

    def test_every_reason_a_request_is_unusable_is_reported_at_once(self) -> None:
        with self.assertRaises(LifecycleError) as raised:
            self.build(approved_by="", reason="").validate()

        message = str(raised.exception)
        self.assertIn("approved_by", message)
        self.assertIn("reason", message)


class PromotionRecordTest(unittest.TestCase):
    def test_the_record_answers_who_decided_and_why(self) -> None:
        record = PromotionRecord(
            model_id="model-id",
            model_version="1.0.0-20260908T043015Z-abcdef01",
            previous_stage=ModelStage.STAGING,
            stage=ModelStage.PRODUCTION,
            approved_by="reviewer",
            reason="the trial ran for a week without regressions",
            promoted_at="2026-09-08T04:30:15Z",
        )

        metadata = record.as_metadata()

        self.assertEqual(metadata["stage"], "production")
        self.assertEqual(metadata["previous_stage"], "staging")
        self.assertEqual(metadata["promoted_by"], "reviewer")
        self.assertEqual(metadata["promotion_reason"], record.reason)
        self.assertEqual(metadata["promoted_at"], "2026-09-08T04:30:15Z")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from ml.data_quality.domain import DataQualityError
from ml.data_quality.lineage import (
    LineageLink,
    LineageRecord,
    LineageStage,
    Producer,
    build_link,
)


PRODUCER = Producer(name="semiconductor-seed", version="1.0.0", executed_by="test-user")


def raw(identifier: str = "raw-001") -> LineageLink:
    return build_link(LineageStage.RAW, identifier, PRODUCER, row_count=1_500)


def curated(
    identifier: str = "curated-001",
    sources: tuple[str, ...] = ("raw-001",),
) -> LineageLink:
    return build_link(
        LineageStage.CURATED,
        identifier,
        PRODUCER,
        sources=sources,
        source_stage=LineageStage.RAW,
        row_count=1_200,
    )


def training(
    identifier: str = "dataset-001",
    sources: tuple[str, ...] = ("curated-001",),
) -> LineageLink:
    return build_link(
        LineageStage.TRAINING,
        identifier,
        PRODUCER,
        sources=sources,
        source_stage=LineageStage.CURATED,
        row_count=1_200,
    )


def complete() -> LineageRecord:
    return LineageRecord(links=(raw(), curated(), training()))


class LinkTest(unittest.TestCase):
    def test_a_link_is_stamped_with_when_it_was_produced(self) -> None:
        link = raw()

        self.assertRegex(link.produced_at, r"^\d{4}-\d{2}-\d{2}T")

    def test_the_start_of_the_chain_has_no_sources(self) -> None:
        self.assertEqual(raw().collect_errors(), ())

    def test_a_raw_link_that_claims_sources_is_refused(self) -> None:
        link = build_link(LineageStage.RAW, "raw-001", PRODUCER, sources=("something",))

        self.assertTrue(link.collect_errors())

    def test_a_curated_link_has_to_say_what_it_came_from(self) -> None:
        link = build_link(LineageStage.CURATED, "curated-001", PRODUCER)

        self.assertTrue(link.collect_errors())

    def test_a_link_cannot_come_from_a_stage_further_down_the_chain(self) -> None:
        link = build_link(
            LineageStage.CURATED,
            "curated-001",
            PRODUCER,
            sources=("dataset-001",),
            source_stage=LineageStage.TRAINING,
        )

        self.assertTrue(link.collect_errors())

    def test_a_training_dataset_may_come_straight_from_raw_data(self) -> None:
        link = build_link(
            LineageStage.TRAINING,
            "dataset-001",
            PRODUCER,
            sources=("raw-001",),
            source_stage=LineageStage.RAW,
        )

        self.assertEqual(link.collect_errors(), ())

    def test_a_producer_without_a_version_is_refused(self) -> None:
        link = build_link(
            LineageStage.RAW,
            "raw-001",
            Producer(name="seed", version="", executed_by="test-user"),
        )

        self.assertTrue(link.collect_errors())

    def test_a_link_can_be_stored_as_plain_data(self) -> None:
        document = training().as_document()

        self.assertEqual(document["stage"], "training")
        self.assertEqual(document["sources"], ["curated-001"])


class RecordTest(unittest.TestCase):
    def test_a_complete_chain_is_accepted(self) -> None:
        record = complete()

        self.assertIs(record.validate(), record)

    def test_a_record_that_never_reaches_a_training_dataset_is_refused(self) -> None:
        record = LineageRecord(links=(raw(), curated()))

        with self.assertRaises(DataQualityError) as raised:
            record.validate()

        self.assertIn("training dataset", str(raised.exception))

    def test_a_source_that_is_not_part_of_the_record_is_refused(self) -> None:
        record = LineageRecord(links=(raw(), training(sources=("curated-999",))))

        with self.assertRaises(DataQualityError) as raised:
            record.validate()

        self.assertIn("curated-999", str(raised.exception))

    def test_walking_backwards_reaches_the_raw_data(self) -> None:
        walked = complete().trace("dataset-001")

        self.assertEqual(
            [link.identifier for link in walked],
            ["dataset-001", "curated-001", "raw-001"],
        )

    def test_walking_starts_at_the_link_that_was_asked_about(self) -> None:
        walked = complete().trace("curated-001")

        self.assertEqual([link.identifier for link in walked], ["curated-001", "raw-001"])

    def test_walking_from_something_unknown_is_refused(self) -> None:
        with self.assertRaises(DataQualityError):
            complete().trace("dataset-999")

    def test_a_record_can_be_stored_as_plain_data(self) -> None:
        document = complete().as_document()

        self.assertEqual(len(document["links"]), 3)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()

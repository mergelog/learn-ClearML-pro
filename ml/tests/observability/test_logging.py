from __future__ import annotations

import io
import json
import logging
import unittest

from ml.observability.logging import (
    CORRELATION_ID_HEADER,
    LogContext,
    configure_logging,
    current_context,
    extended_context,
    log_context,
    new_correlation_id,
)


class CorrelationIdTest(unittest.TestCase):
    def test_two_units_of_work_get_different_identifiers(self) -> None:
        self.assertNotEqual(new_correlation_id(), new_correlation_id())

    def test_the_header_a_caller_quotes_is_named_once(self) -> None:
        self.assertEqual(CORRELATION_ID_HEADER, "X-Correlation-Id")


class ContextTest(unittest.TestCase):
    def build(self, **overrides: str | None) -> LogContext:
        values: dict[str, str | None] = {
            "correlation_id": "abc",
            "service": "prediction",
        }
        values.update(overrides)
        return LogContext(**values)  # type: ignore[arg-type]

    def test_nothing_is_attached_outside_a_unit_of_work(self) -> None:
        self.assertIsNone(current_context())

    def test_the_context_is_attached_inside_the_block(self) -> None:
        with log_context(self.build()):
            attached = current_context()

        self.assertIsNotNone(attached)
        self.assertEqual(attached.correlation_id, "abc")  # type: ignore[union-attr]

    def test_the_context_is_removed_on_the_way_out(self) -> None:
        with log_context(self.build()):
            pass

        self.assertIsNone(current_context())

    def test_a_failed_block_does_not_leave_its_identifiers_behind(self) -> None:
        with self.assertRaises(RuntimeError), log_context(self.build()):
            raise RuntimeError("something went wrong")

        self.assertIsNone(current_context())

    def test_a_value_that_is_not_known_yet_is_absent_rather_than_empty(self) -> None:
        fields = self.build().as_fields()

        self.assertNotIn("model_version", fields)

    def test_a_value_that_is_known_is_carried(self) -> None:
        fields = self.build(model_version="1.0.0-abc").as_fields()

        self.assertEqual(fields["model_version"], "1.0.0-abc")

    def test_what_becomes_known_later_can_be_added(self) -> None:
        with log_context(self.build()), extended_context(model_version="1.0.0-abc"):
            attached = current_context()

        self.assertEqual(attached.model_version, "1.0.0-abc")  # type: ignore[union-attr]

    def test_the_original_context_comes_back_afterwards(self) -> None:
        with log_context(self.build()):
            with extended_context(model_version="1.0.0-abc"):
                pass
            attached = current_context()

        self.assertIsNone(attached.model_version)  # type: ignore[union-attr]

    def test_extending_outside_a_unit_of_work_does_nothing(self) -> None:
        with extended_context(model_version="1.0.0-abc") as extended:
            self.assertIsNone(extended)


class StructuredOutputTest(unittest.TestCase):
    def setUp(self) -> None:
        self.stream = io.StringIO()
        configure_logging(stream=self.stream)
        self.addCleanup(logging.getLogger().handlers.clear)
        self.logger = logging.getLogger("test-logger")

    def written(self) -> list[dict[str, object]]:
        return [json.loads(line) for line in self.stream.getvalue().splitlines() if line]

    def test_every_line_is_one_json_object(self) -> None:
        self.logger.info("something happened")

        self.assertEqual(len(self.written()), 1)

    def test_a_line_says_when_at_what_level_and_what(self) -> None:
        self.logger.warning("something happened")

        [line] = self.written()
        self.assertEqual(line["level"], "warning")
        self.assertEqual(line["message"], "something happened")
        self.assertEqual(line["logger"], "test-logger")
        self.assertIn("timestamp", line)

    def test_the_identifiers_of_the_unit_of_work_are_on_every_line(self) -> None:
        with log_context(LogContext(correlation_id="abc", service="prediction")):
            self.logger.info("first")
            self.logger.info("second")

        for line in self.written():
            self.assertEqual(line["correlation_id"], "abc")
            self.assertEqual(line["service"], "prediction")

    def test_values_the_caller_attached_stay_values(self) -> None:
        self.logger.info("request answered", extra={"status": 200, "endpoint": "/predict"})

        [line] = self.written()
        self.assertEqual(line["status"], 200)
        self.assertEqual(line["endpoint"], "/predict")

    def test_a_failure_is_written_into_the_same_object(self) -> None:
        try:
            raise ValueError("the model could not be read")
        except ValueError as error:
            self.logger.error("the service could not answer", exc_info=error)

        [line] = self.written()
        self.assertIn("the model could not be read", str(line["error"]))

    def test_configuring_twice_does_not_write_every_line_twice(self) -> None:
        configure_logging(stream=self.stream)
        self.logger.info("something happened")

        self.assertEqual(len(self.written()), 1)

    def test_something_that_cannot_be_serialised_does_not_lose_the_line(self) -> None:
        self.logger.info("something happened", extra={"weird": object()})

        [line] = self.written()
        self.assertEqual(line["message"], "something happened")


if __name__ == "__main__":
    unittest.main()

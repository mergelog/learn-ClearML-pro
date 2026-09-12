from __future__ import annotations

import unittest

from ml.observability.metrics import (
    OUTCOME_INVALID,
    OUTCOME_SUCCESS,
    OUTCOME_UNAVAILABLE,
    PredictionMetrics,
)


class RequestMetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.metrics = PredictionMetrics()

    def exposed(self) -> str:
        return self.metrics.expose().decode("utf-8")

    def test_requests_are_counted_by_endpoint_and_outcome(self) -> None:
        self.metrics.record_request("/predict", OUTCOME_SUCCESS, 0.01)

        self.assertIn('endpoint="/predict",outcome="success"', self.exposed())

    def test_a_caller_error_is_counted_apart_from_a_service_error(self) -> None:
        self.metrics.record_request("/predict", OUTCOME_INVALID, 0.01)
        self.metrics.record_request("/predict", OUTCOME_UNAVAILABLE, 0.01)

        exposed = self.exposed()
        self.assertIn('outcome="invalid"', exposed)
        self.assertIn('outcome="unavailable"', exposed)

    def test_how_long_requests_took_is_kept_as_a_distribution(self) -> None:
        self.metrics.record_request("/predict", OUTCOME_SUCCESS, 0.3)

        self.assertIn("prediction_request_seconds_bucket", self.exposed())

    def test_two_services_do_not_see_each_other_numbers(self) -> None:
        other = PredictionMetrics()
        self.metrics.record_request("/predict", OUTCOME_SUCCESS, 0.01)

        self.assertNotIn('endpoint="/predict"', other.expose().decode("utf-8"))


class PredictionMetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.metrics = PredictionMetrics()

    def test_answers_are_counted_by_label(self) -> None:
        self.metrics.record_predictions(["pass", "fail", "pass"], failure_label="fail")

        exposed = self.metrics.expose().decode("utf-8")
        self.assertIn('predictions_total{label="pass"} 2.0', exposed)
        self.assertIn('predictions_total{label="fail"} 1.0', exposed)

    def test_the_share_of_failures_is_measured_over_recent_answers(self) -> None:
        self.metrics.record_predictions(["fail", "pass", "pass", "pass"], failure_label="fail")

        self.assertEqual(self.metrics.recent_failure_share, 0.25)

    def test_nothing_answered_yet_is_a_share_of_zero(self) -> None:
        self.assertEqual(self.metrics.recent_failure_share, 0.0)

    def test_only_recent_answers_count(self) -> None:
        metrics = PredictionMetrics(drift_window=4)
        metrics.record_predictions(["fail", "fail", "fail", "fail"], failure_label="fail")
        metrics.record_predictions(["pass", "pass", "pass", "pass"], failure_label="fail")

        self.assertEqual(metrics.recent_failure_share, 0.0)

    def test_how_much_the_share_is_based_on_can_be_read(self) -> None:
        metrics = PredictionMetrics(drift_window=4)
        metrics.record_predictions(["pass", "pass"], failure_label="fail")

        self.assertEqual(metrics.observed_predictions, 2)

    def test_the_window_does_not_grow_past_its_size(self) -> None:
        metrics = PredictionMetrics(drift_window=3)
        metrics.record_predictions(["pass"] * 10, failure_label="fail")

        self.assertEqual(metrics.observed_predictions, 3)


class ModelMetricsTest(unittest.TestCase):
    def test_a_serving_process_says_so(self) -> None:
        metrics = PredictionMetrics()
        metrics.record_model(0.38)

        exposed = metrics.expose().decode("utf-8")
        self.assertIn("prediction_model_loaded 1.0", exposed)
        self.assertIn("training_failure_share 0.38", exposed)

    def test_a_model_that_never_recorded_its_balance_publishes_none(self) -> None:
        metrics = PredictionMetrics()
        metrics.record_model(None)

        self.assertIn("training_failure_share 0.0", metrics.expose().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()

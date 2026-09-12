"""What the prediction service reports about itself.

Logs answer "what happened to this one request". Metrics answer "what is
happening to all of them", which is the question an alert can be built on.

Four things are measured, and each exists because a specific failure would
otherwise go unnoticed.

Requests, counted by outcome. An error rate is the first thing anyone asks
for, and it cannot be derived from a total alone.

Latency, as a histogram rather than an average. An average hides the tail, and
the tail is what callers actually experience.

Predictions, counted by label. A model that quietly starts answering "pass" to
everything keeps a perfect error rate while being useless.

The share of failures predicted, as a gauge. This is prediction drift: it is
compared against the share the model saw while training, and a gap means the
world moved even though nothing broke.

Every metric is registered on a registry this module owns, so a test can build
a fresh one and two tests cannot see each other's numbers.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import CollectorRegistry as Registry


METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

# 応答時間の区切り。上端を大きく取るのは、遅い応答が「一番上の箱」に
# まとめて入ってしまうと、悪化していることが分からなくなるためである。
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# 予測の偏りを見る窓の大きさ。小さすぎると数件の偶然で警報が鳴り、
# 大きすぎると変化に気付くのが遅れる。
DEFAULT_DRIFT_WINDOW = 500

OUTCOME_SUCCESS = "success"
OUTCOME_INVALID = "invalid"
OUTCOME_UNAVAILABLE = "unavailable"


@dataclass
class PredictionMetrics:
    """The numbers one prediction service reports.

    The registry is held rather than global, so a test builds its own and the
    numbers of one test never reach another.
    """

    registry: Registry = field(default_factory=CollectorRegistry)
    drift_window: int = DEFAULT_DRIFT_WINDOW

    def __post_init__(self) -> None:
        self.requests = Counter(
            "prediction_requests_total",
            "Requests answered, by endpoint and outcome.",
            labelnames=("endpoint", "outcome"),
            registry=self.registry,
        )
        self.latency = Histogram(
            "prediction_request_seconds",
            "How long a request took to answer, by endpoint.",
            labelnames=("endpoint",),
            buckets=LATENCY_BUCKETS,
            registry=self.registry,
        )
        self.predictions = Counter(
            "predictions_total",
            "Products judged, by the label they were given.",
            labelnames=("label",),
            registry=self.registry,
        )
        self.predicted_failure_share = Gauge(
            "predicted_failure_share",
            "Share of recent predictions that said the product fails.",
            registry=self.registry,
        )
        self.training_failure_share = Gauge(
            "training_failure_share",
            "Share of failures the serving model saw while it was trained.",
            registry=self.registry,
        )
        self.model_loaded = Gauge(
            "prediction_model_loaded",
            "1 when a model is loaded and the service can answer.",
            registry=self.registry,
        )
        self._recent: deque[bool] = deque(maxlen=self.drift_window)

    def record_request(self, endpoint: str, outcome: str, seconds: float) -> None:
        self.requests.labels(endpoint=endpoint, outcome=outcome).inc()
        self.latency.labels(endpoint=endpoint).observe(seconds)

    def record_predictions(self, labels: Iterable[str], failure_label: str) -> None:
        """Count what was answered, and keep the recent balance up to date."""
        for label in labels:
            self.predictions.labels(label=label).inc()
            self._recent.append(label == failure_label)
        self.predicted_failure_share.set(self.recent_failure_share)

    def record_model(self, training_failure_share: float | None) -> None:
        """Note that a model is serving, and what it was trained to expect."""
        self.model_loaded.set(1)
        if training_failure_share is not None:
            self.training_failure_share.set(training_failure_share)

    @property
    def recent_failure_share(self) -> float:
        if not self._recent:
            return 0.0
        return sum(self._recent) / len(self._recent)

    @property
    def observed_predictions(self) -> int:
        """How many predictions the recent share is based on.

        An alert should not fire on three requests. Whoever reads the share
        needs to know how much is behind it.
        """
        return len(self._recent)

    def expose(self) -> bytes:
        """The current numbers, in the format Prometheus reads."""
        return generate_latest(self.registry)

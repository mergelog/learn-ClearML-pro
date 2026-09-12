"""The shape of what the service accepts and answers.

The request schema is the data contract, restated for a caller who has never
read the training code. Every field the model was fitted on is required and
every one is bounded, so a caller learns what is wrong from a 422 rather than
from an answer that quietly means nothing.

The bounds are deliberately generous. They exist to reject values that cannot
be a measurement — a negative pressure, a temperature in the thousands — and
not to reject unusual products. Deciding what is unusual is the model's job.

The response always names the model. A caller that stores predictions can then
answer, later, which model produced which answer.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ml.semiconductor_quality.domain import LABELS

from .domain import MAXIMUM_BATCH_SIZE


IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"


class Measurement(BaseModel):
    """One product, described by the columns the model was fitted on."""

    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(
        pattern=IDENTIFIER_PATTERN,
        description="Identifies the product. Echoed back so answers can be matched up.",
    )
    equipment_id: str = Field(
        min_length=1,
        max_length=64,
        description="Which machine produced it.",
    )
    process_step: str = Field(
        min_length=1,
        max_length=64,
        description="Which step of the process it came from.",
    )
    temperature: float = Field(ge=-273.15, le=5_000)
    pressure: float = Field(ge=0, le=100_000)
    process_time: float = Field(ge=0, le=100_000)
    gas_flow: float = Field(ge=0, le=100_000)
    sensor_1: float = Field(ge=-1_000_000, le=1_000_000)
    sensor_2: float = Field(ge=-1_000_000, le=1_000_000)
    inspection_value: float = Field(ge=-1_000_000, le=1_000_000)


class PredictionRequest(BaseModel):
    """A batch of products to judge.

    The batch is bounded so that one call cannot occupy the service for an
    unbounded time. A caller with more rows makes more calls.
    """

    model_config = ConfigDict(extra="forbid")

    measurements: list[Measurement] = Field(
        min_length=1,
        max_length=MAXIMUM_BATCH_SIZE,
        description="Between one and 500 products.",
    )


class PredictedSample(BaseModel):
    """The answer for one product."""

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    label: str = Field(description=f"One of: {', '.join(LABELS)}.")
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "How sure the model is, when the algorithm reports it. "
            "Absent when it does not."
        ),
    )


class ModelDescription(BaseModel):
    """Which model answered."""

    model_config = ConfigDict(extra="forbid")

    model_id: str
    model_version: str
    stage: str
    dataset_id: str
    dataset_version: str
    train_task_id: str


class PredictionResponse(BaseModel):
    """The answers, and the model that gave them."""

    model_config = ConfigDict(extra="forbid")

    model: ModelDescription
    predictions: list[PredictedSample]


class HealthResponse(BaseModel):
    """Whether the process is alive."""

    model_config = ConfigDict(extra="forbid")

    service: str
    status: str


class ReadinessResponse(BaseModel):
    """Whether the process can actually answer, and with which model."""

    model_config = ConfigDict(extra="forbid")

    service: str
    status: str
    model: ModelDescription


class ErrorResponse(BaseModel):
    """Why the service refused."""

    model_config = ConfigDict(extra="forbid")

    detail: str

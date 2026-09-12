"""Fit the RandomForest of one execution.

This module never contacts ClearML. It holds the training use case: split the
validated input, build one pipeline out of the preprocessing and the estimator,
fit it, and confirm the settings of the run on the validation part.

Two boundaries are deliberate. The pipeline is fitted on the training rows
only, so neither the validation nor the test part can leak into what the model
learned. And the test part is not predicted here at all: it stays untouched
until the final evaluation, which uses it exactly once. A validation result
that looks wrong is a reason to start another Task with other parameters, not
to refit inside this one.

Storing the fitted pipeline lives here as well, because what is stored is the
model of this module: the preprocessing and the estimator as one unit. Handing
the stored file to an experiment tracker is somebody else's job.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from .algorithms import build_classifier
from .config import EstimatorConfig, TrainingConfig
from .domain import (
    DatasetValidationReport,
    DataSplit,
    LabelVector,
    ModelCost,
    SplitPart,
    TrainingInput,
)
from .preprocess import (
    build_contract_preprocessor,
    build_preprocessor,
    split_training_input,
)


PREPROCESSOR_STEP = "preprocessor"
CLASSIFIER_STEP = "classifier"

MODEL_FILE_NAME = "semiconductor_quality_pipeline.joblib"


@dataclass(frozen=True)
class TrainedModel:
    """Outcome of one fit: what it learned from, and what it predicted so far."""

    report: DatasetValidationReport
    split: DataSplit
    pipeline: Pipeline
    validation_predictions: LabelVector
    training_seconds: float = 0.0

    def predict(self, part: SplitPart) -> LabelVector:
        """Predict one part with the fitted pipeline, preprocessing included."""
        return predict_part(self.pipeline, part)


def train_classifier(training_input: TrainingInput, config: TrainingConfig) -> TrainedModel:
    """Split the validated input, fit the estimator, and confirm it on validation."""
    split = split_training_input(training_input, config.split, config.random_seed)
    pipeline = build_pipeline(training_input.report, config.estimator, config.random_seed)

    # 学習にかかった時間は、精度と並べて初めて「どれを採用するか」を判断できる。
    started = time.perf_counter()
    fit_pipeline(pipeline, split.train)
    training_seconds = time.perf_counter() - started

    return TrainedModel(
        report=training_input.report,
        split=split,
        pipeline=pipeline,
        validation_predictions=predict_part(pipeline, split.validation),
        training_seconds=training_seconds,
    )


def build_pipeline(
    report: DatasetValidationReport,
    estimator: EstimatorConfig,
    random_seed: int,
) -> Pipeline:
    """Put the preprocessing and the estimator into a single fitted unit.

    Keeping both in one pipeline means the preprocessing is fitted on the
    training rows only, and that a stored model carries the preprocessing it
    was fitted with.
    """
    return _pipeline_of(build_preprocessor(report), estimator, random_seed)


def build_contract_pipeline(estimator: EstimatorConfig, random_seed: int) -> Pipeline:
    """Build the same unit for an input that was validated somewhere else.

    A pipeline step receives a split another step already validated, so it has
    the rows but not the report they were validated from. The column layout is
    part of the data contract, so the preprocessing can still be rebuilt
    exactly.
    """
    return _pipeline_of(build_contract_preprocessor(), estimator, random_seed)


def _pipeline_of(
    preprocessor: ColumnTransformer,
    estimator: EstimatorConfig,
    random_seed: int,
) -> Pipeline:
    return Pipeline(
        steps=[
            (PREPROCESSOR_STEP, preprocessor),
            (CLASSIFIER_STEP, build_classifier(estimator, random_seed)),
        ]
    )


def fit_pipeline(pipeline: Pipeline, train: SplitPart) -> Pipeline:
    """Fit the pipeline on the training part, and on nothing else."""
    return pipeline.fit(train.features, train.targets)


def measure_cost(model: TrainedModel, weights: Path) -> ModelCost:
    """Measure what a fitted model costs to use, next to what it cost to fit.

    Inference is timed on the validation part, which is the part the model was
    chosen on, so the measurement belongs to the same comparison as the scores.
    The prediction is thrown away: what is wanted here is the duration.
    """
    started = time.perf_counter()
    predict_part(model.pipeline, model.split.validation)
    inference_seconds = time.perf_counter() - started

    return ModelCost(
        training_seconds=model.training_seconds,
        inference_seconds=inference_seconds,
        inference_rows=model.split.validation.row_count,
        model_bytes=weights.stat().st_size,
    )


def predict_part(pipeline: Pipeline, part: SplitPart) -> LabelVector:
    predictions: LabelVector = np.asarray(pipeline.predict(part.features))
    return predictions


@contextmanager
def saved_pipeline(pipeline: Pipeline, file_name: str = MODEL_FILE_NAME) -> Iterator[Path]:
    """Write the fitted pipeline to a file for as long as a caller needs it.

    The preprocessing is stored together with the estimator, so the file is the
    whole model and not the classifier alone. It is written into a temporary
    directory because it exists only to be handed over, and whoever receives it
    is expected to have taken its copy before this context closes.
    """
    with TemporaryDirectory(prefix="semiconductor-quality-") as directory:
        path = Path(directory) / file_name
        joblib.dump(pipeline, path)
        yield path

from __future__ import annotations

import unittest

import numpy as np

from ml.experiment.domain import ExperimentError, Objective, TrialPlan
from ml.experiment.trials import (
    build_trial_pipeline,
    cross_validate,
    iter_folds,
    running_objective,
    summarise,
)
from ml.semiconductor_quality.config import (
    ClassWeight,
    EstimatorConfig,
    RandomForestConfig,
)
from ml.semiconductor_quality.domain import (
    CATEGORICAL_FEATURE_COLUMNS,
    NUMERIC_FEATURE_COLUMNS,
    SplitPart,
)
from ml.semiconductor_quality.train import CLASSIFIER_STEP


FAST_FOREST = EstimatorConfig(forest=RandomForestConfig(n_estimators=20, min_samples_leaf=2))
FAST_PLAN = TrialPlan(folds=3, threshold_folds=2)


def build_part(name: str = "train", rows: int = 240, seed: int = 11) -> SplitPart:
    """Rows shaped like the data contract, with a learnable signal in them."""
    generator = np.random.default_rng(seed)
    numeric = generator.normal(size=(rows, len(NUMERIC_FEATURE_COLUMNS)))
    categorical = np.array(
        [["EQ-01", "CLEAN"] for _ in range(rows)],
        dtype=object,
    )
    features = np.hstack([numeric.astype(object), categorical])
    assert features.shape[1] == len(NUMERIC_FEATURE_COLUMNS) + len(CATEGORICAL_FEATURE_COLUMNS)

    noise = generator.normal(scale=0.6, size=rows)
    targets = np.where(numeric[:, 0] + noise > 0.7, "fail", "pass")
    labels = {"pass": int((targets == "pass").sum()), "fail": int((targets == "fail").sum())}
    return SplitPart(name=name, features=features, targets=targets, label_counts=labels)


class SearchBoundaryTest(unittest.TestCase):
    def test_a_search_may_only_be_measured_on_the_training_rows(self) -> None:
        for name in ("validation", "test"):
            with self.subTest(split=name), self.assertRaises(ExperimentError) as raised:
                cross_validate(build_part(name), FAST_FOREST, FAST_PLAN, Objective(), 3)

            self.assertIn(name, str(raised.exception))

    def test_rows_too_few_to_divide_twice_are_refused_before_any_fit(self) -> None:
        part = build_part(rows=30)
        plan = TrialPlan(folds=8, threshold_folds=4)

        with self.assertRaises(ExperimentError) as raised:
            cross_validate(part, FAST_FOREST, plan, Objective(), 3)

        self.assertIn("rarest label", str(raised.exception))


class CrossValidationTest(unittest.TestCase):
    def test_every_fold_is_measured_and_the_mean_is_reported(self) -> None:
        result = cross_validate(build_part(), FAST_FOREST, FAST_PLAN, Objective(), 3)

        self.assertEqual(len(result.folds), FAST_PLAN.folds)
        self.assertAlmostEqual(result.objective, float(np.mean(result.fold_objectives)))

    def test_the_same_seed_measures_the_same_candidate_the_same_way(self) -> None:
        first = cross_validate(build_part(), FAST_FOREST, FAST_PLAN, Objective(), 3)
        again = cross_validate(build_part(), FAST_FOREST, FAST_PLAN, Objective(), 3)

        self.assertEqual(first.objective, again.objective)
        self.assertEqual(first.threshold, again.threshold)

    def test_every_row_of_the_part_is_scored_exactly_once(self) -> None:
        part = build_part()

        result = cross_validate(part, FAST_FOREST, FAST_PLAN, Objective(), 3)

        self.assertEqual(sum(fold.rows for fold in result.folds), part.row_count)

    def test_the_objective_names_the_measure_it_was_taken_from(self) -> None:
        result = cross_validate(build_part(), FAST_FOREST, FAST_PLAN, Objective(metric="recall"), 3)

        self.assertEqual(result.objective_metric, "recall")
        self.assertAlmostEqual(
            result.objective,
            float(np.mean([fold.metrics["recall"] for fold in result.folds])),
        )

    def test_a_progress_report_means_the_same_as_the_final_one(self) -> None:
        folds = list(iter_folds(build_part(), FAST_FOREST, FAST_PLAN, Objective(), 3))

        self.assertAlmostEqual(
            running_objective(folds, "f1"),
            summarise(folds, Objective()).objective,
        )

    def test_a_trial_that_measured_nothing_cannot_be_judged(self) -> None:
        with self.assertRaises(ExperimentError):
            summarise((), Objective())


class ThresholdTest(unittest.TestCase):
    def test_each_fold_chooses_a_cut_and_the_folds_agree_on_one(self) -> None:
        result = cross_validate(build_part(), FAST_FOREST, FAST_PLAN, Objective(), 3)

        self.assertIsNotNone(result.threshold)
        chosen = [fold.threshold for fold in result.folds]
        self.assertTrue(all(value is not None for value in chosen))
        agreed = result.threshold
        assert agreed is not None
        self.assertGreaterEqual(agreed, min(value for value in chosen if value is not None))
        self.assertLessEqual(agreed, max(value for value in chosen if value is not None))

    def test_a_trial_that_may_not_move_the_cut_reports_none(self) -> None:
        plan = TrialPlan(folds=3, tune_threshold=False)

        result = cross_validate(build_part(), FAST_FOREST, plan, Objective(), 3)

        self.assertIsNone(result.threshold)
        self.assertTrue(all(fold.threshold is None for fold in result.folds))

    def test_a_candidate_carrying_a_cut_is_still_measured_by_the_search(self) -> None:
        carried = EstimatorConfig(
            forest=RandomForestConfig(n_estimators=20),
            decision_threshold=0.9,
        )

        pipeline = build_trial_pipeline(carried, FAST_PLAN, Objective(), 3)

        self.assertNotIn("FixedThreshold", type(pipeline.named_steps[CLASSIFIER_STEP]).__name__)


class ImbalanceTest(unittest.TestCase):
    def test_weighing_the_rare_label_changes_what_is_measured(self) -> None:
        plain = cross_validate(build_part(), FAST_FOREST, FAST_PLAN, Objective(), 3)
        balanced = cross_validate(
            build_part(),
            EstimatorConfig(
                forest=RandomForestConfig(n_estimators=20, min_samples_leaf=2),
                class_weight=ClassWeight.BALANCED,
            ),
            FAST_PLAN,
            Objective(),
            3,
        )

        self.assertNotEqual(plain.objective, balanced.objective)

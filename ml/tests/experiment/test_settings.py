from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from ml.experiment.domain import (
    ChoiceRange,
    Direction,
    Environment,
    ExperimentError,
    IntegerRange,
    NumberRange,
)
from ml.experiment.settings import (
    DEFAULT_SETTINGS_DIRECTORY,
    ENVIRONMENT_VARIABLE,
    load_plan,
    resolve_environment,
    settings_files,
)
from ml.semiconductor_quality.config import Algorithm, ClassWeight


BASE = """
objective:
  metric: f1
  direction: maximise

search:
  algorithm: random-forest
  parameters:
    n_estimators:
      integer:
        minimum: 100
        maximum: 600
        step: 50
  defaults:
    min_samples_leaf: 6

trial:
  folds: 4
  tune_threshold: true
  threshold_folds: 2
"""

OVERLAY = """
budget:
  max_trials: 3
  parallel_trials: 1
  trial_minutes: 2
  total_minutes: 5
  keep_top: 2
  minimum_folds: 2

execution:
  trial_queue: trials
  optimizer_queue: searches
"""


CONFUSED_PARAMETER = """
objective:
  metric: f1

search:
  algorithm: random-forest
  parameters:
    n_estimators:
      integer:
        minimum: 100
        maximum: 600
      choice: [100, 200]
"""

EVERY_KIND = """
objective:
  metric: f1

search:
  algorithm: random-forest
  parameters:
    n_estimators:
      integer:
        minimum: 100
        maximum: 600
        step: 50
    max_depth:
      choice: [null, 8]
    class_weight:
      choice: [none, balanced]
"""

LOGARITHMIC = """
objective:
  metric: recall

search:
  algorithm: hist-gradient-boosting
  parameters:
    learning_rate:
      number:
        minimum: 0.01
        maximum: 0.3
        logarithmic: true
"""


class SettingsDirectory:
    """A pair of settings files on disk, for one test."""

    def __init__(self, base: str = BASE, overlay: str = OVERLAY) -> None:
        self._directory = TemporaryDirectory(prefix="experiment-settings-")
        self.path = Path(self._directory.name)
        (self.path / "base.yaml").write_text(base, encoding="utf-8")
        (self.path / "dev.yaml").write_text(overlay, encoding="utf-8")

    def close(self) -> None:
        self._directory.cleanup()


class EnvironmentTest(unittest.TestCase):
    def test_an_unnamed_environment_is_the_development_one(self) -> None:
        self.assertEqual(resolve_environment(None), Environment.DEVELOPMENT)

    def test_the_name_given_wins_over_the_environment_variable(self) -> None:
        with mock.patch.dict("os.environ", {ENVIRONMENT_VARIABLE: "staging"}):
            self.assertEqual(resolve_environment("production"), Environment.PRODUCTION)

    def test_the_environment_variable_is_read_when_nothing_is_named(self) -> None:
        with mock.patch.dict("os.environ", {ENVIRONMENT_VARIABLE: "staging"}):
            self.assertEqual(resolve_environment(None), Environment.STAGING)

    def test_an_unknown_environment_is_refused_rather_than_guessed(self) -> None:
        with self.assertRaises(ExperimentError) as raised:
            resolve_environment("prod")

        self.assertIn("prod", str(raised.exception))

    def test_each_environment_is_read_from_the_shared_file_and_its_own(self) -> None:
        base, overlay = settings_files(Environment.PRODUCTION)

        self.assertEqual(base.name, "base.yaml")
        self.assertEqual(overlay.name, "production.yaml")


class LayeringTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = SettingsDirectory()
        self.addCleanup(self.settings.close)

    def test_the_shared_meaning_and_this_environment_s_limits_are_both_read(self) -> None:
        plan = load_plan(Environment.DEVELOPMENT, self.settings.path)

        self.assertEqual(plan.objective.metric, "f1")
        self.assertEqual(plan.trial.folds, 4)
        self.assertEqual(plan.budget.max_trials, 3)
        self.assertEqual(plan.placement.trial_queue, "trials")

    def test_an_environment_may_change_one_limit_without_repeating_the_rest(self) -> None:
        overlay = OVERLAY + "\ntrial:\n  folds: 2\n"
        settings = SettingsDirectory(overlay=overlay)
        self.addCleanup(settings.close)

        plan = load_plan(Environment.DEVELOPMENT, settings.path)

        self.assertEqual(plan.trial.folds, 2)
        self.assertTrue(plan.trial.tune_threshold)

    def test_the_settings_a_search_does_not_vary_start_from_the_file(self) -> None:
        plan = load_plan(Environment.DEVELOPMENT, self.settings.path)

        self.assertEqual(plan.estimator.forest.min_samples_leaf, 6)
        self.assertEqual(plan.estimator.algorithm, Algorithm.RANDOM_FOREST)

    def test_a_missing_file_is_reported_with_its_path(self) -> None:
        with self.assertRaises(ExperimentError) as raised:
            load_plan(Environment.PRODUCTION, self.settings.path)

        self.assertIn("production.yaml", str(raised.exception))


class RefusalTest(unittest.TestCase):
    def test_a_setting_this_project_does_not_read_is_refused(self) -> None:
        settings = SettingsDirectory(base=BASE + "\nsampling:\n  strategy: grid\n")
        self.addCleanup(settings.close)

        with self.assertRaises(ExperimentError) as raised:
            load_plan(Environment.DEVELOPMENT, settings.path)

        self.assertIn("sampling", str(raised.exception))

    def test_a_misspelled_budget_limit_is_refused_rather_than_ignored(self) -> None:
        settings = SettingsDirectory(overlay=OVERLAY + "\n  max_trial: 40\n")
        self.addCleanup(settings.close)

        with self.assertRaises(ExperimentError) as raised:
            load_plan(Environment.DEVELOPMENT, settings.path)

        self.assertIn("max_trial", str(raised.exception))

    def test_a_credential_in_a_settings_file_is_refused(self) -> None:
        # 検出器そのものの題材である。その場で考えた乱数列で、実在しない。
        leaked = BASE + '\nexecution:\n  api_token: "8fA3kd92Lm04Qz71pR6t"\n'  # secret-scan:allow
        settings = SettingsDirectory(base=leaked)
        self.addCleanup(settings.close)

        with self.assertRaises(ExperimentError) as raised:
            load_plan(Environment.DEVELOPMENT, settings.path)

        self.assertIn("credential", str(raised.exception))

    def test_a_parameter_that_declares_two_kinds_is_refused(self) -> None:
        settings = SettingsDirectory(base=CONFUSED_PARAMETER)
        self.addCleanup(settings.close)

        with self.assertRaises(ExperimentError) as raised:
            load_plan(Environment.DEVELOPMENT, settings.path)

        self.assertIn("exactly one", str(raised.exception))

    def test_a_budget_that_is_not_a_number_is_refused(self) -> None:
        settings = SettingsDirectory(overlay=OVERLAY.replace("max_trials: 3", "max_trials: many"))
        self.addCleanup(settings.close)

        with self.assertRaises(ExperimentError) as raised:
            load_plan(Environment.DEVELOPMENT, settings.path)

        self.assertIn("max_trials", str(raised.exception))


class RangeShapeTest(unittest.TestCase):
    def test_the_three_kinds_are_read_as_the_ranges_they_declare(self) -> None:
        settings = SettingsDirectory(base=EVERY_KIND)
        self.addCleanup(settings.close)

        ranges = {
            parameter.name: parameter
            for parameter in load_plan(Environment.DEVELOPMENT, settings.path).space.ranges
        }

        self.assertIsInstance(ranges["n_estimators"], IntegerRange)
        self.assertIsInstance(ranges["max_depth"], ChoiceRange)
        self.assertEqual(ranges["max_depth"].values, ("", "8"))  # type: ignore[attr-defined]
        self.assertEqual(
            ranges["class_weight"].values,  # type: ignore[attr-defined]
            ("none", "balanced"),
        )

    def test_an_empty_choice_is_carried_as_the_absence_a_task_spells(self) -> None:
        settings = SettingsDirectory(base=EVERY_KIND)
        self.addCleanup(settings.close)

        depth = load_plan(Environment.DEVELOPMENT, settings.path).space.ranges[1]

        self.assertEqual(depth.values[0], "")  # type: ignore[attr-defined]

    def test_a_number_may_be_drawn_on_a_logarithmic_scale(self) -> None:
        settings = SettingsDirectory(base=LOGARITHMIC)
        self.addCleanup(settings.close)

        parameter = load_plan(Environment.DEVELOPMENT, settings.path).space.ranges[0]

        self.assertIsInstance(parameter, NumberRange)
        self.assertTrue(parameter.logarithmic)  # type: ignore[attr-defined]


class ShippedSettingsTest(unittest.TestCase):
    """The files this repository ships have to be readable, in every environment."""

    def test_every_environment_of_this_repository_can_be_read(self) -> None:
        for environment in Environment:
            with self.subTest(environment=environment):
                plan = load_plan(environment, DEFAULT_SETTINGS_DIRECTORY)

                self.assertEqual(plan.environment, environment)
                self.assertEqual(plan.objective.direction, Direction.MAXIMISE)
                self.assertTrue(plan.space.ranges)

    def test_a_larger_environment_is_allowed_to_spend_more(self) -> None:
        budgets = {
            environment: load_plan(environment, DEFAULT_SETTINGS_DIRECTORY).budget
            for environment in Environment
        }

        self.assertLess(
            budgets[Environment.DEVELOPMENT].max_trials,
            budgets[Environment.PRODUCTION].max_trials,
        )

    def test_the_imbalance_policy_is_part_of_what_the_shipped_search_varies(self) -> None:
        plan = load_plan(Environment.DEVELOPMENT, DEFAULT_SETTINGS_DIRECTORY)
        names = {parameter.name for parameter in plan.space.ranges}

        self.assertIn("class_weight", names)
        self.assertEqual(plan.estimator.class_weight, ClassWeight.NONE)

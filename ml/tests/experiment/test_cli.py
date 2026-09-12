from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from ml.experiment.cli import (
    CLEARML_PROCESS_VARIABLES,
    EXIT_INVALID_USAGE,
    EXIT_SUCCESS,
    independent_environment,
    main,
    parse_arguments,
)
from ml.experiment.domain import Environment
from ml.experiment.settings import ENVIRONMENT_VARIABLE


BASE_ARGUMENTS = ("--dataset-version", "2.0.0")


class ParsingTest(unittest.TestCase):
    def test_a_search_runs_under_the_development_budget_unless_told_otherwise(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=False):
            request, _, _ = parse_arguments(BASE_ARGUMENTS)

        self.assertEqual(request.plan.environment, Environment.DEVELOPMENT)

    def test_the_environment_decides_the_budget_and_the_queues(self) -> None:
        development, _, _ = parse_arguments((*BASE_ARGUMENTS, "--environment", "dev"))
        production, _, _ = parse_arguments((*BASE_ARGUMENTS, "--environment", "production"))

        self.assertLess(
            development.plan.budget.max_trials,
            production.plan.budget.max_trials,
        )
        self.assertTrue(production.plan.placement.trial_queue)

    def test_the_environment_variable_is_read_when_none_is_named(self) -> None:
        with mock.patch.dict("os.environ", {ENVIRONMENT_VARIABLE: "staging"}):
            request, _, _ = parse_arguments(BASE_ARGUMENTS)

        self.assertEqual(request.plan.environment, Environment.STAGING)

    def test_the_search_and_the_run_that_follows_it_share_one_seed(self) -> None:
        request, _, _ = parse_arguments((*BASE_ARGUMENTS, "--random-seed", "7"))

        self.assertEqual(request.random_seed, 7)

    def test_handing_the_winner_on_is_asked_for_rather_than_assumed(self) -> None:
        _, handoff, _ = parse_arguments(BASE_ARGUMENTS)
        _, asked, _ = parse_arguments((*BASE_ARGUMENTS, "--handoff"))

        self.assertFalse(handoff)
        self.assertTrue(asked)

    def test_a_search_without_a_dataset_version_is_refused(self) -> None:
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            parse_arguments(())


class DryRunTest(unittest.TestCase):
    def test_the_search_can_be_read_before_it_is_allowed_to_spend_anything(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            code = main([*BASE_ARGUMENTS, "--dry-run"])

        printed = output.getvalue()
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("Objective:", printed)
        self.assertIn("Budget:", printed)
        self.assertIn("n_estimators", printed)

    def test_a_dry_run_names_the_dataset_every_trial_would_read(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            main([*BASE_ARGUMENTS, "--dry-run"])

        self.assertIn("2.0.0", output.getvalue())

    def test_an_unknown_environment_is_refused_before_anything_is_created(self) -> None:
        errors = io.StringIO()

        with redirect_stderr(errors), self.assertRaises(SystemExit):
            main([*BASE_ARGUMENTS, "--environment", "prod", "--dry-run"])

    def test_the_package_manager_separator_is_not_read_as_an_argument(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            code = main(["--", *BASE_ARGUMENTS, "--dry-run"])

        self.assertEqual(code, EXIT_SUCCESS)


class RefusalTest(unittest.TestCase):
    def test_a_split_that_does_not_add_up_is_refused_without_contacting_clearml(self) -> None:
        errors = io.StringIO()

        with redirect_stderr(errors):
            code = main([*BASE_ARGUMENTS, "--train-ratio", "0.9", "--dry-run"])

        self.assertEqual(code, EXIT_INVALID_USAGE)
        self.assertIn("sum to 1.0", errors.getvalue())


class HandoffProcessTest(unittest.TestCase):
    """The run a search asks for is a run of its own, not part of the search."""

    def test_the_child_is_not_told_it_belongs_to_the_search_task(self) -> None:
        linked = dict.fromkeys(CLEARML_PROCESS_VARIABLES, "1234:abcd")

        with mock.patch.dict("os.environ", linked):
            environment = independent_environment()

        for name in CLEARML_PROCESS_VARIABLES:
            with self.subTest(variable=name):
                self.assertNotIn(name, environment)

    def test_everything_else_about_the_environment_is_inherited(self) -> None:
        with mock.patch.dict("os.environ", {"CLEARML_API_HOST": "http://localhost:8008"}):
            environment = independent_environment()

        self.assertEqual(environment["CLEARML_API_HOST"], "http://localhost:8008")

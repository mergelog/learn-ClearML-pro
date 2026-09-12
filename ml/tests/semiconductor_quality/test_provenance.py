from __future__ import annotations

import subprocess
import unittest
from collections.abc import Mapping, Sequence
from typing import Any
from unittest import mock

from ml.semiconductor_quality import provenance as provenance_module
from ml.semiconductor_quality.provenance import (
    BRANCH_ENVIRONMENT_KEY,
    COMMIT_ENVIRONMENT_KEY,
    EXECUTED_BY_ENVIRONMENT_KEY,
    GIT_COMMAND_TIMEOUT_SECONDS,
    IMAGE_DIGEST_ENVIRONMENT_KEY,
    IMAGE_ENVIRONMENT_KEY,
    LOCAL_QUEUE,
    REMOTE_ENVIRONMENT_KEY,
    UNKNOWN,
    CodeRevision,
    CommandRunner,
    RuntimeEnvironment,
    collect_code_revision,
    collect_provenance,
    collect_runtime_environment,
)


CLEAN_CHECKOUT: Mapping[tuple[str, ...], str | None] = {
    ("rev-parse", "HEAD"): "0123456789abcdef",
    ("rev-parse", "--abbrev-ref", "HEAD"): "main",
    ("config", "--get", "remote.origin.url"): "git@example.invalid:team/repository.git",
    ("status", "--porcelain"): "",
}


def answering(answers: Mapping[tuple[str, ...], str | None]) -> CommandRunner:
    """Build a git stand-in that answers only the questions it was given."""

    def run_command(arguments: Sequence[str]) -> str | None:
        return answers.get(tuple(arguments))

    return run_command


def silent(_arguments: Sequence[str]) -> str | None:
    """A checkout that answers nothing, as in a container without git."""
    return None


class CodeRevisionTest(unittest.TestCase):
    def test_the_working_tree_answers_the_revision(self) -> None:
        revision = collect_code_revision(
            environment={},
            run_command=answering(CLEAN_CHECKOUT),
        )

        self.assertEqual(revision.commit, "0123456789abcdef")
        self.assertEqual(revision.branch, "main")
        self.assertEqual(revision.remote, "git@example.invalid:team/repository.git")
        self.assertTrue(revision.is_clean)

    def test_uncommitted_changes_are_recorded_next_to_the_commit(self) -> None:
        revision = collect_code_revision(
            environment={},
            run_command=answering(
                {**CLEAN_CHECKOUT, ("status", "--porcelain"): " M ml/cli.py"}
            ),
        )

        self.assertEqual(revision.commit, "0123456789abcdef")
        self.assertFalse(revision.is_clean)

    def test_the_environment_states_the_revision_of_a_built_image(self) -> None:
        environment = {
            COMMIT_ENVIRONMENT_KEY: "fedcba9876543210",
            BRANCH_ENVIRONMENT_KEY: "release",
            REMOTE_ENVIRONMENT_KEY: "https://example.invalid/team/repository.git",
        }

        revision = collect_code_revision(environment=environment, run_command=silent)

        self.assertEqual(revision.commit, "fedcba9876543210")
        self.assertEqual(revision.branch, "release")
        self.assertEqual(revision.remote, "https://example.invalid/team/repository.git")

    def test_the_environment_wins_over_the_working_tree(self) -> None:
        revision = collect_code_revision(
            environment={COMMIT_ENVIRONMENT_KEY: "fedcba9876543210"},
            run_command=answering(CLEAN_CHECKOUT),
        )

        self.assertEqual(revision.commit, "fedcba9876543210")

    def test_a_checkout_that_cannot_be_read_is_recorded_as_unknown(self) -> None:
        revision = collect_code_revision(environment={}, run_command=silent)

        self.assertEqual(revision.commit, UNKNOWN)
        self.assertEqual(revision.branch, UNKNOWN)
        self.assertEqual(revision.remote, UNKNOWN)

    def test_an_unreadable_checkout_is_not_claimed_to_be_clean(self) -> None:
        revision = collect_code_revision(environment={}, run_command=silent)

        self.assertFalse(revision.is_clean)

    def test_blank_environment_values_are_treated_as_absent(self) -> None:
        revision = collect_code_revision(
            environment={COMMIT_ENVIRONMENT_KEY: "   "},
            run_command=answering(CLEAN_CHECKOUT),
        )

        self.assertEqual(revision.commit, "0123456789abcdef")


class GitCommandTest(unittest.TestCase):
    """The real reader of the working tree, rather than a stand-in for it.

    Every other test in this file injects ``run_command``. That leaves the one
    thing the module actually promises — that nothing here fails a run —
    resting on a function no test calls. A git that hangs is the realistic way
    to break it: the value is not missing, the call never comes back.
    """

    def run_git(self, **behaviour: Any) -> str | None:
        with mock.patch.object(subprocess, "run", **behaviour):
            return provenance_module._run_git(("rev-parse", "HEAD"))

    def test_a_git_that_never_answers_is_given_a_deadline(self) -> None:
        with mock.patch.object(subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "0123456789abcdef", "")
            provenance_module._run_git(("rev-parse", "HEAD"))

        self.assertEqual(run.call_args.kwargs["timeout"], GIT_COMMAND_TIMEOUT_SECONDS)

    def test_a_command_that_timed_out_is_answered_as_unknown(self) -> None:
        answered = self.run_git(
            side_effect=subprocess.TimeoutExpired(("git",), GIT_COMMAND_TIMEOUT_SECONDS)
        )

        self.assertIsNone(answered)

    def test_a_checkout_without_git_installed_is_answered_as_unknown(self) -> None:
        answered = self.run_git(side_effect=FileNotFoundError("git"))

        self.assertIsNone(answered)

    def test_a_directory_that_is_not_a_repository_is_answered_as_unknown(self) -> None:
        answered = self.run_git(
            return_value=subprocess.CompletedProcess([], 128, "", "not a git repository")
        )

        self.assertIsNone(answered)

    def test_a_hanging_git_does_not_stop_the_run_it_was_describing(self) -> None:
        """来歴が取れないことと、学習が走らないことは別である。"""
        with mock.patch.object(
            subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(("git",), GIT_COMMAND_TIMEOUT_SECONDS),
        ):
            revision = collect_code_revision(environment={})

        self.assertEqual(revision.commit, UNKNOWN)
        self.assertFalse(revision.is_clean)


class RuntimeEnvironmentTest(unittest.TestCase):
    def test_the_image_names_itself_through_the_environment(self) -> None:
        environment = {
            IMAGE_ENVIRONMENT_KEY: "stackup/semiconductor-agent:0.1.0",
            IMAGE_DIGEST_ENVIRONMENT_KEY: "sha256:abc",
        }

        runtime = collect_runtime_environment(environment=environment)

        self.assertEqual(runtime.image_reference, "stackup/semiconductor-agent:0.1.0")
        self.assertEqual(runtime.image_digest, "sha256:abc")

    def test_a_run_outside_a_container_records_no_image(self) -> None:
        runtime = collect_runtime_environment(environment={})

        self.assertEqual(runtime.image_reference, UNKNOWN)
        self.assertEqual(runtime.image_digest, UNKNOWN)

    def test_the_interpreter_and_machine_are_always_recorded(self) -> None:
        runtime = collect_runtime_environment(environment={})

        self.assertRegex(runtime.python_version, r"^\d+\.\d+\.\d+")
        self.assertTrue(runtime.hostname)


class ExecutionProvenanceTest(unittest.TestCase):
    def test_a_run_without_a_queue_is_recorded_as_local(self) -> None:
        provenance = collect_provenance(None, environment={}, run_command=silent)

        self.assertEqual(provenance.queue, LOCAL_QUEUE)

    def test_the_queue_a_run_was_handed_to_is_recorded(self) -> None:
        provenance = collect_provenance(
            "semiconductor-training",
            environment={},
            run_command=silent,
        )

        self.assertEqual(provenance.queue, "semiconductor-training")

    def test_the_person_who_asked_for_the_run_can_be_stated(self) -> None:
        provenance = collect_provenance(
            None,
            environment={EXECUTED_BY_ENVIRONMENT_KEY: "release-bot"},
            run_command=silent,
        )

        self.assertEqual(provenance.executed_by, "release-bot")

    def test_the_person_is_recorded_even_without_an_override(self) -> None:
        provenance = collect_provenance(None, environment={}, run_command=silent)

        self.assertTrue(provenance.executed_by)


class ProvenanceParametersTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provenance = collect_provenance(
            "semiconductor-training",
            environment={
                EXECUTED_BY_ENVIRONMENT_KEY: "release-bot",
                IMAGE_ENVIRONMENT_KEY: "stackup/semiconductor-agent:0.1.0",
                IMAGE_DIGEST_ENVIRONMENT_KEY: "sha256:abc",
            },
            run_command=answering(CLEAN_CHECKOUT),
        )

    def test_every_recorded_value_is_flat_text(self) -> None:
        parameters = {
            **self.provenance.request_parameters(),
            **self.provenance.runtime_parameters(),
        }

        self.assertTrue(parameters)
        for name, value in parameters.items():
            with self.subTest(parameter=name):
                self.assertIsInstance(value, str)

    def test_the_request_records_who_asked_for_the_run_and_from_where(self) -> None:
        self.assertEqual(
            sorted(self.provenance.request_parameters()),
            [
                "executed_by",
                "git_branch",
                "git_commit",
                "git_remote",
                "git_working_tree",
                "queue",
            ],
        )

    def test_the_runtime_records_the_environment_that_carries_the_run_out(self) -> None:
        self.assertEqual(
            sorted(self.provenance.runtime_parameters()),
            ["hostname", "image_digest", "image_reference", "python_version"],
        )

    def test_the_two_halves_do_not_overlap(self) -> None:
        request = set(self.provenance.request_parameters())
        runtime = set(self.provenance.runtime_parameters())

        self.assertEqual(request & runtime, set())

    def test_a_dirty_working_tree_is_readable_in_the_recorded_values(self) -> None:
        dirty = CodeRevision(
            commit="0123456789abcdef",
            branch="main",
            remote=UNKNOWN,
            is_clean=False,
        )

        self.assertEqual(dirty.as_parameters()["git_working_tree"], "dirty")

    def test_a_clean_working_tree_is_readable_in_the_recorded_values(self) -> None:
        clean = CodeRevision(
            commit="0123456789abcdef",
            branch="main",
            remote=UNKNOWN,
            is_clean=True,
        )

        self.assertEqual(clean.as_parameters()["git_working_tree"], "clean")

    def test_the_image_is_readable_in_the_recorded_values(self) -> None:
        runtime = RuntimeEnvironment(
            image_reference="stackup/semiconductor-agent:0.1.0",
            image_digest="sha256:abc",
            python_version="3.10.12",
            hostname="builder",
        )

        parameters = runtime.as_parameters()

        self.assertEqual(parameters["image_reference"], "stackup/semiconductor-agent:0.1.0")
        self.assertEqual(parameters["image_digest"], "sha256:abc")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from ml.security.credentials import TOKEN_PREFIX, fingerprint, issue_token, parse_policy
from tools.security.allowlist import AllowlistError, load_allowlist
from tools.security.clearml_tasks import TaskText
from tools.security.cli import EXIT_FAILURE, EXIT_INVALID_USAGE, EXIT_SUCCESS, main
from tools.security.sources import files_below


class RecordedTasks:
    """What some Tasks wrote down, decided by the test."""

    def __init__(self, texts: tuple[TaskText, ...]) -> None:
        self.texts = texts

    def read(self) -> tuple[TaskText, ...]:
        return self.texts


def run(argv: list[str], source: object = None) -> tuple[int, str]:
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        code = main(argv, source=source)  # type: ignore[arg-type]
    return code, output.getvalue()


class IssuedCredentialTest(unittest.TestCase):
    def test_a_credential_is_issued_with_its_fingerprint_ready_to_configure(self) -> None:
        code, printed = run(["token", "--name", "batch-scoring", "--role", "predictor"])

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn(TOKEN_PREFIX, printed)
        self.assertIn("batch-scoring:predictor:", printed)

    def test_the_printed_entry_is_what_a_service_can_actually_read(self) -> None:
        """出力をそのまま貼れること。貼れない出力は、貼り間違いを誘う。"""
        _, printed = run(
            ["token", "--name", "batch-scoring", "--role", "operator", "--format", "json"]
        )

        issued = json.loads(printed)
        policy = parse_policy(issued["client"])
        self.assertEqual(policy.principals[0].name, "batch-scoring")
        self.assertEqual(
            policy.principals[0].credential_fingerprints,
            (fingerprint(issued["token"]),),
        )

    def test_a_role_that_does_not_exist_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            run(["token", "--name", "batch-scoring", "--role", "administrator"])

        self.assertEqual(raised.exception.code, EXIT_INVALID_USAGE)


class ScannedPathTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.allowlist = self.root / "security.yaml"
        self.allowlist.write_text("secret_scan:\n  exemptions: []\n", encoding="utf-8")

    def scan(self, target: Path) -> tuple[int, str]:
        return run(["paths", str(target), "--allowlist", str(self.allowlist)])

    def test_a_credential_in_a_generated_file_is_reported(self) -> None:
        self.token = issue_token()
        (self.root / "bundle.js").write_text(f"const t = '{self.token}'", encoding="utf-8")

        code, printed = self.scan(self.root)

        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("issued-token", printed)

    def test_the_report_does_not_repeat_what_it_found(self) -> None:
        token = issue_token()
        (self.root / "bundle.js").write_text(f"const t = '{token}'", encoding="utf-8")

        _, printed = self.scan(self.root)

        self.assertNotIn(token, printed)

    def test_a_clean_directory_says_so(self) -> None:
        (self.root / "bundle.js").write_text("const t = readToken()", encoding="utf-8")

        code, printed = self.scan(self.root)

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("No credential", printed)

    def test_a_path_that_is_not_there_is_a_usage_error_and_not_a_pass(self) -> None:
        with self.assertRaises(SystemExit):
            self.scan(self.root / "absent")

    def test_dependencies_and_caches_are_not_walked(self) -> None:
        """走査すべきでない場所に時間を使うと、走査そのものが行われなくなる。"""
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "index.js").write_text("x", encoding="utf-8")
        (self.root / "app.js").write_text("y", encoding="utf-8")

        found = files_below([self.root])

        self.assertIn("app.js", [path.name for path in found])
        self.assertNotIn("index.js", [path.name for path in found])


class ScannedTaskTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.allowlist = Path(self.directory.name) / "security.yaml"
        self.allowlist.write_text("secret_scan:\n  exemptions: []\n", encoding="utf-8")

    def scan(self, texts: tuple[TaskText, ...]) -> tuple[int, str]:
        return run(
            ["clearml", "--allowlist", str(self.allowlist)],
            source=RecordedTasks(texts),
        )

    def test_a_credential_in_a_task_parameter_is_reported_with_the_task(self) -> None:
        recorded = TaskText(
            task_id="9f2c1b",
            task_name="random-forest",
            project="Semiconductor Quality Prediction",
            kind="parameters",
            text=f"Execution/command_line=--token {issue_token()}",
        )

        code, printed = self.scan((recorded,))

        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("task:9f2c1b/parameters", printed)

    def test_a_task_that_wrote_nothing_secret_is_reported_as_clean(self) -> None:
        recorded = TaskText(
            task_id="9f2c1b",
            task_name="random-forest",
            project="Semiconductor Quality Prediction",
            kind="console",
            text="fitting the model\nreporting the evaluation",
        )

        code, _ = self.scan((recorded,))

        self.assertEqual(code, EXIT_SUCCESS)


class AllowlistFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "security.yaml"

    def test_an_exemption_without_a_reason_is_refused(self) -> None:
        """理由の無い除外は、次に読む人が判断できない。"""
        self.path.write_text(
            "secret_scan:\n  exemptions:\n    - path: 'docs/**'\n",
            encoding="utf-8",
        )

        with self.assertRaises(AllowlistError):
            load_allowlist(self.path)

    def test_an_exemption_without_a_path_would_excuse_everything(self) -> None:
        self.path.write_text(
            "secret_scan:\n  exemptions:\n    - reason: 'because'\n",
            encoding="utf-8",
        )

        with self.assertRaises(AllowlistError):
            load_allowlist(self.path)

    def test_a_missing_file_scans_with_every_rule(self) -> None:
        self.assertEqual(load_allowlist(self.path).exemptions, ())

    def test_one_rule_may_be_named_as_a_single_value(self) -> None:
        self.path.write_text(
            "secret_scan:\n"
            "  exemptions:\n"
            "    - path: 'docs/**'\n"
            "      rules: named-secret\n"
            "      reason: 'the runbook shows the shape of a configuration entry'\n",
            encoding="utf-8",
        )

        exemption = load_allowlist(self.path).exemptions[0]

        self.assertEqual(exemption.rules, ("named-secret",))


if __name__ == "__main__":
    unittest.main()

"""The published API, and what happens when it moves."""

from __future__ import annotations

import copy
import io
import json
import logging
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import mock

from services.prediction_api import contract, contract_cli


class ContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # 文書を組み立てるにはアプリを作る必要があり、その過程で構造化ログが
        # 有効になる。テストの出力を起動ログで埋めないよう黙らせる。
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)


class PublishedDocumentTest(ContractTestCase):
    def test_the_committed_document_is_what_the_service_publishes(self) -> None:
        """The one check with a consumer-less API: it must not move silently.

        When this fails, read the report it prints. An intentional change is
        committed with `pnpm run serving:openapi:update`.
        """
        report = contract.drift()

        # 差し替えず fail へ渡すのは、報告が複数行だからである。
        # assertIsNone は repr で潰すので、読ませたい文面が1行に畳まれる。
        if report is not None:
            self.fail(f"\n\n{report}\n")

    def test_every_endpoint_the_service_answers_is_written_down(self) -> None:
        published = contract.published_document()

        self.assertEqual(sorted(published["paths"]), ["/health", "/predict", "/ready"])

    def test_the_document_is_produced_without_a_usable_caller(self) -> None:
        """Describing the service must not need a credential to exist."""
        document = contract.openapi_document()

        self.assertEqual(document["info"]["version"], "1.0.0")


class DriftTest(ContractTestCase):
    """The report a developer reads when the code moved away from the file.

    The service's own document stands in for "what the code says now", edited
    one promise at a time, so the report is exercised against the real shapes
    rather than against an invented service.
    """

    def report_after(self, change: Any) -> str:
        document = copy.deepcopy(contract.published_document())
        change(document)
        with mock.patch.object(contract, "openapi_document", return_value=document):
            report = contract.drift()

        self.assertIsNotNone(report)
        return str(report)

    def test_a_document_that_did_not_move_reports_nothing(self) -> None:
        with mock.patch.object(
            contract, "openapi_document", return_value=contract.published_document()
        ):
            self.assertIsNone(contract.drift())

    def test_an_endpoint_that_disappeared_is_reported_as_breaking(self) -> None:
        report = self.report_after(lambda document: document["paths"].pop("/ready"))

        self.assertIn("呼び出し側が壊れる変更", report)
        self.assertIn("GET /ready: この操作が無くなった", report)

    def test_a_new_endpoint_is_reported_as_compatible(self) -> None:
        def add(document: dict[str, Any]) -> None:
            document["paths"]["/drain"] = copy.deepcopy(document["paths"]["/health"])

        report = self.report_after(add)

        self.assertNotIn("呼び出し側が壊れる変更", report)
        self.assertIn("GET /drain: この操作が増えた", report)

    def test_a_value_that_callers_must_start_sending_is_reported_as_breaking(self) -> None:
        def require(document: dict[str, Any]) -> None:
            measurement = document["components"]["schemas"]["Measurement"]
            measurement["properties"]["lot_id"] = {"type": "string"}
            measurement["required"].append("lot_id")

        report = self.report_after(require)

        self.assertIn("要求に必須の measurements[].lot_id が増えた", report)

    def test_a_change_the_comparison_cannot_name_is_still_reported(self) -> None:
        """A tightened bound moves the promise without moving the shape."""

        def tighten(document: dict[str, Any]) -> None:
            temperature = document["components"]["schemas"]["Measurement"]["properties"][
                "temperature"
            ]
            temperature["maximum"] = 1_000

        report = self.report_after(tighten)

        self.assertIn("差分を読むこと", report)

    def test_the_report_says_how_to_accept_the_change(self) -> None:
        report = self.report_after(lambda document: document["paths"].pop("/ready"))

        self.assertIn(contract.UPDATE_COMMAND, report)


class SnapshotTest(ContractTestCase):
    def test_writing_the_snapshot_leaves_a_document_that_reads_back(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "openapi.json"
            with mock.patch.object(contract, "SNAPSHOT_PATH", path):
                written = contract.write_snapshot()
                published = contract.published_document()

            self.assertEqual(written, path)
            self.assertEqual(published, contract.openapi_document())
            self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), published)


class CommandTest(ContractTestCase):
    """The one command that writes the file."""

    def run_command(self, *arguments: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = contract_cli.main(list(arguments))
        return code, out.getvalue(), err.getvalue()

    def test_running_it_writes_the_document_and_says_where(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "openapi.json"
            with mock.patch.object(contract, "SNAPSHOT_PATH", path):
                code, written, _ = self.run_command()

            self.assertEqual(code, contract_cli.EXIT_SUCCESS)
            self.assertIn(str(path), written)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["openapi"][:1], "3")

    def test_an_argument_it_does_not_understand_writes_nothing(self) -> None:
        """The command has no options. A typo must not be taken as one."""
        with mock.patch.object(contract_cli, "write_snapshot") as write:
            code, _, refused = self.run_command("check")

        self.assertEqual(code, contract_cli.EXIT_INVALID_USAGE)
        self.assertIn("usage:", refused)
        write.assert_not_called()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tools.supply_chain.cli import EXIT_FAILURE, EXIT_INVALID_USAGE, EXIT_SUCCESS, main
from tools.supply_chain.domain import (
    NPM,
    PYPI,
    Component,
    CvssError,
    Severity,
    Vulnerability,
    cvss_base_score,
    severity_of_score,
)
from tools.supply_chain.gate import (
    Exemption,
    Policy,
    PolicyError,
    decide,
    load_policy,
)
from tools.supply_chain.osv import (
    OSV_QUERY_BATCH_URL,
    OsvDatabase,
    OsvUnavailableError,
    fixed_versions,
    severity_of,
)
from tools.supply_chain.reports import ReportError, read_report, write_report
from tools.supply_chain.sbom import build_document, read_document, read_pnpm_lock, read_python_lock


TODAY = date(2026, 9, 8)

REQUESTS = Component(name="requests", version="2.32.5", ecosystem=PYPI)


def vulnerability(identifier: str, severity: Severity) -> Vulnerability:
    return Vulnerability(
        identifier=identifier,
        component=REQUESTS,
        severity=severity,
        summary="something is wrong",
        fixed_in=("2.33.0",),
        source="osv",
    )


def run(argv: list[str], database: object = None) -> tuple[int, str]:
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        code = main(argv, database=database)  # type: ignore[arg-type]
    return code, output.getvalue()


class CvssTest(unittest.TestCase):
    """点数は助言に付いてこない。ベクタから計算する。"""

    def test_the_published_examples_score_the_way_the_specification_says(self) -> None:
        for vector, expected in (
            ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8),
            ("CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:U/C:H/I:N/A:N", 5.3),
            ("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N", 6.1),
            ("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H", 7.5),
            ("CVSS:3.1/AV:P/AC:H/PR:H/UI:R/S:U/C:N/I:N/A:N", 0.0),
        ):
            with self.subTest(vector=vector):
                self.assertEqual(cvss_base_score(vector), expected)

    def test_a_vector_of_another_version_is_not_scored_as_if_it_were_v3(self) -> None:
        with self.assertRaises(CvssError):
            cvss_base_score("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H")

    def test_a_vector_missing_a_metric_is_refused(self) -> None:
        with self.assertRaises(CvssError):
            cvss_base_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H")

    def test_the_bands_are_the_ones_a_policy_is_written_in(self) -> None:
        self.assertEqual(severity_of_score(9.8), Severity.CRITICAL)
        self.assertEqual(severity_of_score(7.0), Severity.HIGH)
        self.assertEqual(severity_of_score(6.9), Severity.MEDIUM)
        self.assertEqual(severity_of_score(0.0), Severity.NONE)


class SbomTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_only_pinned_requirements_become_components(self) -> None:
        lock = self.root / "training.txt"
        lock.write_text(
            "# comment\n-c serving.txt\nscikit-learn==1.7.2\nnumpy==2.3.5\n    \n",
            encoding="utf-8",
        )

        components = read_python_lock(lock)

        self.assertEqual(
            [component.coordinates for component in components],
            ["scikit-learn@1.7.2", "numpy@2.3.5"],
        )

    def test_a_scoped_npm_package_keeps_its_scope(self) -> None:
        lock = self.root / "pnpm-lock.yaml"
        lock.write_text(
            "packages:\n"
            "  '@angular/core@22.0.0':\n    resolution: {integrity: sha512-x}\n"
            "  rxjs@7.8.1:\n    resolution: {integrity: sha512-y}\n",
            encoding="utf-8",
        )

        components = read_pnpm_lock(lock)

        self.assertEqual(
            sorted(component.coordinates for component in components),
            ["@angular/core@22.0.0", "rxjs@7.8.1"],
        )

    def test_a_peer_dependency_suffix_is_not_part_of_the_version(self) -> None:
        lock = self.root / "pnpm-lock.yaml"
        lock.write_text(
            "packages:\n  'ngrx@19.0.0(rxjs@7.8.1)':\n    resolution: {integrity: sha512-z}\n",
            encoding="utf-8",
        )

        self.assertEqual(read_pnpm_lock(lock)[0].coordinates, "ngrx@19.0.0")

    def test_the_document_is_the_same_for_the_same_dependencies(self) -> None:
        """2回作って違うなら、差分は依存の変化を意味しなくなる。"""
        components = (
            Component(name="rxjs", version="7.8.1", ecosystem=NPM),
            REQUESTS,
        )

        first = build_document(components, name="stackup", version="0.1.0")
        second = build_document(tuple(reversed(components)), name="stackup", version="0.1.0")

        self.assertEqual(first, second)

    def test_the_components_can_be_read_back_with_their_ecosystem(self) -> None:
        document = build_document(
            (REQUESTS, Component(name="rxjs", version="7.8.1", ecosystem=NPM)),
            name="stackup",
            version="0.1.0",
        )

        self.assertEqual(
            [(item.name, item.ecosystem) for item in read_document(document)],
            [("requests", PYPI), ("rxjs", NPM)],
        )

    def test_a_package_url_names_the_ecosystem_the_database_expects(self) -> None:
        self.assertEqual(REQUESTS.purl, "pkg:pypi/requests@2.32.5")


class FakeOsv:
    """Answers the queries the test decided on, without a network."""

    def __init__(self, results: dict[str, Any], details: dict[str, Any]) -> None:
        self.results = results
        self.details = details
        self.asked: list[str] = []

    def __call__(self, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self.asked.append(url)
        if url == OSV_QUERY_BATCH_URL:
            return self.results
        detail: dict[str, Any] = self.details[url.rsplit("/", 1)[-1]]
        return detail


class OsvTest(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = FakeOsv(
            results={"results": [{"vulns": [{"id": "GHSA-1111"}]}]},
            details={
                "GHSA-1111": {
                    "summary": "credentials leak",
                    "severity": [
                        {
                            "type": "CVSS_V3",
                            "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                        }
                    ],
                    "affected": [
                        {
                            "package": {"name": "requests", "ecosystem": PYPI},
                            "ranges": [
                                {"events": [{"introduced": "0"}, {"fixed": "2.33.0"}]}
                            ],
                        }
                    ],
                }
            },
        )

    def test_an_advisory_is_reported_against_the_component_that_was_asked_about(self) -> None:
        found = OsvDatabase(transport=self.transport).vulnerabilities([REQUESTS])

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].identifier, "GHSA-1111")
        self.assertEqual(found[0].component, REQUESTS)
        self.assertEqual(found[0].severity, Severity.CRITICAL)
        self.assertEqual(found[0].fixed_in, ("2.33.0",))

    def test_the_same_advisory_is_only_looked_up_once(self) -> None:
        self.transport.results = {
            "results": [{"vulns": [{"id": "GHSA-1111"}]}, {"vulns": [{"id": "GHSA-1111"}]}]
        }
        other = Component(name="requests", version="2.32.4", ecosystem=PYPI)

        OsvDatabase(transport=self.transport).vulnerabilities([REQUESTS, other])

        self.assertEqual(self.transport.asked.count("https://api.osv.dev/v1/vulns/GHSA-1111"), 1)

    def test_a_database_that_only_names_the_severity_is_believed(self) -> None:
        severity, score = severity_of({"database_specific": {"severity": "MODERATE"}})

        self.assertEqual(severity, Severity.MEDIUM)
        self.assertIsNone(score)

    def test_an_unrated_advisory_stays_unknown_rather_than_becoming_low(self) -> None:
        self.assertEqual(severity_of({"summary": "no rating"})[0], Severity.UNKNOWN)

    def test_a_vector_this_scorer_cannot_read_falls_back_instead_of_crashing(self) -> None:
        record = {
            "severity": [{"type": "CVSS_V4", "score": "CVSS:4.0/AV:N"}],
            "database_specific": {"severity": "HIGH"},
        }

        self.assertEqual(severity_of(record)[0], Severity.HIGH)

    def test_a_fix_for_another_package_is_not_reported_as_this_one_s_fix(self) -> None:
        record = {
            "affected": [
                {
                    "package": {"name": "urllib3"},
                    "ranges": [{"events": [{"fixed": "2.0.0"}]}],
                }
            ]
        }

        self.assertEqual(fixed_versions(record, REQUESTS), ())

    def test_a_database_that_cannot_be_reached_is_not_an_empty_result(self) -> None:
        def refuse(_url: str, _payload: dict[str, Any] | None = None) -> dict[str, Any]:
            raise OsvUnavailableError("the network is down")

        with self.assertRaises(OsvUnavailableError):
            OsvDatabase(transport=refuse).vulnerabilities([REQUESTS])


class GateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = Policy(blocked=(Severity.CRITICAL,))

    def test_a_critical_advisory_blocks_a_release(self) -> None:
        decision = decide((vulnerability("GHSA-1111", Severity.CRITICAL),), self.policy, TODAY)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.blocking[0].identifier, "GHSA-1111")

    def test_what_is_below_the_line_is_reported_and_does_not_block(self) -> None:
        decision = decide((vulnerability("GHSA-2222", Severity.HIGH),), self.policy, TODAY)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reported[0].identifier, "GHSA-2222")

    def test_a_stricter_policy_blocks_what_the_looser_one_reported(self) -> None:
        stricter = Policy(blocked=(Severity.HIGH,))

        decision = decide((vulnerability("GHSA-2222", Severity.HIGH),), stricter, TODAY)

        self.assertFalse(decision.allowed)

    def test_an_accepted_advisory_is_named_together_with_the_reason(self) -> None:
        policy = Policy(
            blocked=(Severity.CRITICAL,),
            exemptions=(
                Exemption(
                    identifier="GHSA-1111",
                    reason="no fix published; the affected path is not reachable",
                    until=date(2026, 10, 31),
                ),
            ),
        )

        decision = decide((vulnerability("GHSA-1111", Severity.CRITICAL),), policy, TODAY)

        self.assertTrue(decision.allowed)
        self.assertIn("no fix published", decision.excused[0][1].reason)

    def test_an_exemption_stops_excusing_when_it_expires(self) -> None:
        """期限の無い受け入れは、二度と見直されない一覧になる。"""
        policy = Policy(
            blocked=(Severity.CRITICAL,),
            exemptions=(
                Exemption(
                    identifier="GHSA-1111",
                    reason="waiting for the fix",
                    until=date(2026, 8, 31),
                ),
            ),
        )

        decision = decide((vulnerability("GHSA-1111", Severity.CRITICAL),), policy, TODAY)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.expired[0][0].identifier, "GHSA-1111")

    def test_an_unrated_advisory_is_reported_by_default(self) -> None:
        decision = decide((vulnerability("GHSA-3333", Severity.UNKNOWN),), self.policy, TODAY)

        self.assertTrue(decision.allowed)

    def test_an_environment_may_choose_to_block_on_unrated_advisories(self) -> None:
        policy = Policy(blocked=(Severity.CRITICAL,), unknown="block")

        decision = decide((vulnerability("GHSA-3333", Severity.UNKNOWN),), policy, TODAY)

        self.assertFalse(decision.allowed)


class PolicyFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "supply_chain.yaml"

    def write(self, body: str) -> Path:
        self.path.write_text(body, encoding="utf-8")
        return self.path

    def test_the_repository_policy_is_readable(self) -> None:
        policy = load_policy()

        self.assertIn(Severity.CRITICAL, policy.blocked)

    def test_an_exemption_without_an_expiry_is_refused(self) -> None:
        path = self.write(
            "release_gate:\n"
            "  block: [critical]\n"
            "  exemptions:\n"
            "    - id: GHSA-1111\n"
            "      reason: waiting for the fix\n"
        )

        with self.assertRaises(PolicyError) as raised:
            load_policy(path)

        self.assertIn("expiry", str(raised.exception))

    def test_an_exemption_without_a_reason_is_refused(self) -> None:
        path = self.write(
            "release_gate:\n"
            "  block: [critical]\n"
            "  exemptions:\n"
            "    - id: GHSA-1111\n"
            "      until: 2026-10-31\n"
        )

        with self.assertRaises(PolicyError):
            load_policy(path)

    def test_a_policy_that_blocks_nothing_is_refused(self) -> None:
        with self.assertRaises(PolicyError):
            load_policy(self.write("release_gate:\n  block: []\n"))

    def test_a_severity_that_does_not_exist_is_refused(self) -> None:
        with self.assertRaises(PolicyError):
            load_policy(self.write("release_gate:\n  block: [catastrophic]\n"))

    def test_a_missing_policy_is_not_treated_as_an_empty_one(self) -> None:
        with self.assertRaises(PolicyError):
            load_policy(Path(self.directory.name) / "absent.yaml")


class ReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_what_was_written_can_be_read_back(self) -> None:
        path = self.root / "dependencies.json"

        write_report(path, (vulnerability("GHSA-1111", Severity.CRITICAL),), source="osv")

        read = read_report(path)
        self.assertEqual(read[0].identifier, "GHSA-1111")
        self.assertEqual(read[0].severity, Severity.CRITICAL)
        self.assertEqual(read[0].component.coordinates, "requests@2.32.5")

    def test_an_image_scan_is_read_into_the_same_shape(self) -> None:
        path = self.root / "image.json"
        path.write_text(
            json.dumps(
                {
                    "Results": [
                        {
                            "Type": "debian",
                            "Vulnerabilities": [
                                {
                                    "VulnerabilityID": "CVE-2026-1234",
                                    "PkgName": "libssl3",
                                    "InstalledVersion": "3.0.11-1",
                                    "FixedVersion": "3.0.13-1",
                                    "Severity": "CRITICAL",
                                    "Title": "openssl is vulnerable",
                                }
                            ],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        found = read_report(path)

        self.assertEqual(found[0].severity, Severity.CRITICAL)
        self.assertEqual(found[0].source, "trivy")
        self.assertEqual(found[0].fixed_in, ("3.0.13-1",))

    def test_a_report_in_an_unknown_shape_is_refused_rather_than_read_as_empty(self) -> None:
        path = self.root / "other.json"
        path.write_text('{"findings": []}', encoding="utf-8")

        with self.assertRaises(ReportError):
            read_report(path)


class CommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.policy = self.root / "supply_chain.yaml"
        self.policy.write_text("release_gate:\n  block: [critical]\n", encoding="utf-8")

    def test_the_gate_fails_the_build_on_a_critical_advisory(self) -> None:
        report = self.root / "dependencies.json"
        write_report(report, (vulnerability("GHSA-1111", Severity.CRITICAL),), source="osv")

        code, printed = run(
            ["gate", "--report", str(report), "--policy", str(self.policy)]
        )

        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("A release is blocked by", printed)
        self.assertIn("GHSA-1111", printed)

    def test_the_gate_passes_when_nothing_reaches_the_line(self) -> None:
        report = self.root / "dependencies.json"
        write_report(report, (vulnerability("GHSA-2222", Severity.MEDIUM),), source="osv")

        code, printed = run(
            ["gate", "--report", str(report), "--policy", str(self.policy)]
        )

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("Nothing blocks a release", printed)

    def test_a_report_that_is_not_there_is_a_usage_error_and_not_a_pass(self) -> None:
        code, _ = run(
            ["gate", "--report", str(self.root / "absent.json"), "--policy", str(self.policy)]
        )

        self.assertEqual(code, EXIT_INVALID_USAGE)

    def test_an_audit_without_a_bill_of_materials_says_what_to_do_first(self) -> None:
        code, printed = run(["audit", "--sbom", str(self.root / "absent.json")])

        self.assertEqual(code, EXIT_INVALID_USAGE)
        self.assertIn("sbom", printed)

    def test_an_unreachable_database_fails_instead_of_writing_an_empty_report(self) -> None:
        sbom = self.root / "sbom.json"
        sbom.write_text(
            json.dumps(build_document((REQUESTS,), name="stackup", version="0.1.0")),
            encoding="utf-8",
        )
        output = self.root / "dependencies.json"

        def refuse(_url: str, _payload: dict[str, Any] | None = None) -> dict[str, Any]:
            raise OsvUnavailableError("the network is down")

        code, _ = run(
            ["audit", "--sbom", str(sbom), "--output", str(output)],
            database=OsvDatabase(transport=refuse),
        )

        self.assertEqual(code, EXIT_FAILURE)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()

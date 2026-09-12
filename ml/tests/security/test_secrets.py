from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ml.security.credentials import issue_token
from ml.security.secrets import (
    ALLOW_MARKER,
    Allowlist,
    Exemption,
    looks_random,
    redact,
    scan_file,
    scan_files,
    scan_text,
    shannon_entropy,
)


def rules_that_fired(text: str, origin: str = "example.py") -> list[str]:
    return [finding.rule.name for finding in scan_text(text, origin)]


class ShapedSecretTest(unittest.TestCase):
    """形で分かる資格情報は、文脈が無くても見つかること。"""

    def test_a_token_issued_by_this_repository_is_found(self) -> None:
        self.assertIn("issued-token", rules_that_fired(f"const token = '{issue_token()}'"))

    def test_a_private_key_is_found_by_its_first_line(self) -> None:
        self.assertIn("private-key", rules_that_fired("-----BEGIN RSA PRIVATE KEY-----"))

    def test_an_aws_access_key_id_is_found(self) -> None:
        self.assertIn("aws-access-key-id", rules_that_fired("aws_key: AKIAIOSFODNN7EXAMPLE"))

    def test_a_signed_json_web_token_is_found(self) -> None:
        token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r"

        self.assertIn("json-web-token", rules_that_fired(f"Authorization: Bearer {token}"))

    def test_a_password_inside_a_url_is_found(self) -> None:
        connection = "mongodb://service:8Fq2xVn4Lp7Tz@mongo:27017/clearml"

        self.assertIn("credential-in-url", rules_that_fired(connection))


class ContextualSecretTest(unittest.TestCase):
    """名前が秘密を約束している行は、値が乱数らしいときだけ挙げること。"""

    def test_a_clearml_credential_is_found(self) -> None:
        line = 'access_key = "Q7HXV2K9WPL3ZB8NRT4M"'

        self.assertIn("clearml-credential", rules_that_fired(line))

    def test_a_random_value_behind_a_promising_name_is_found(self) -> None:
        line = "password: 'j8Kq2Wm5Vz9Rb7Tx'"

        self.assertIn("named-secret", rules_that_fired(line))

    def test_a_documented_placeholder_is_not_a_finding(self) -> None:
        """見本まで挙げると、報告そのものが読まれなくなる。"""
        for line in (
            'password = "your-password-here"',
            'api_key = "changeme-changeme"',
            "PREDICTION_API_CLIENTS=name:role:fingerprint",
            'token = "${PREDICTION_TOKEN}"',
        ):
            with self.subTest(line=line):
                self.assertEqual(rules_that_fired(line), [])

    def test_a_short_value_is_not_treated_as_a_credential(self) -> None:
        self.assertEqual(rules_that_fired('password = "hunter2"'), [])

    def test_an_identifier_next_to_a_promising_name_is_not_a_credential(self) -> None:
        """`BUCKET_CREDENTIALS = 'bucketCredentials'` は定数であって秘密ではない。"""
        self.assertEqual(rules_that_fired("BUCKET_CREDENTIALS = 'bucketCredentials'"), [])

    def test_a_credential_in_an_environment_file_is_found(self) -> None:
        self.assertIn(
            "environment-credential",
            rules_that_fired("PREDICTION_API_TOKEN=9fbc1a7d4e2b8c6a5031", ".env"),
        )

    def test_an_environment_variable_holding_a_name_is_not_a_credential(self) -> None:
        self.assertEqual(rules_that_fired("CLEARML_TRAINING_QUEUE=semiconductor-training"), [])


class EntropyTest(unittest.TestCase):
    def test_a_word_is_less_random_than_a_generated_token(self) -> None:
        self.assertLess(shannon_entropy("passwordpassword"), shannon_entropy(issue_token()))

    def test_an_empty_value_has_no_entropy(self) -> None:
        self.assertEqual(shannon_entropy(""), 0.0)

    def test_a_value_that_names_itself_an_example_is_never_random_enough(self) -> None:
        self.assertFalse(looks_random("example-8Fq2xVn4Lp7Tz"))

    def test_a_generated_token_looks_random(self) -> None:
        self.assertTrue(looks_random(issue_token()))


class ReportTest(unittest.TestCase):
    """報告そのものが2つ目の漏えいにならないこと。"""

    def test_the_value_is_never_repeated_in_the_finding(self) -> None:
        token = issue_token()

        findings = scan_text(f"token = '{token}'", "example.py")

        self.assertTrue(findings)
        for finding in findings:
            self.assertNotIn(token, finding.describe())

    def test_the_finding_says_where_it_was_and_what_it_is(self) -> None:
        described = scan_text(f"\n\nsecret = '{issue_token()}'", "config/app.py")[0].describe()

        self.assertIn("config/app.py:3", described)
        self.assertIn("issued-token", described)

    def test_a_redacted_value_keeps_only_its_beginning_and_its_length(self) -> None:
        self.assertEqual(redact("abcdefghij"), "abcd…(10 characters)")


class AllowlistTest(unittest.TestCase):
    def test_a_named_exemption_silences_one_rule_in_one_place(self) -> None:
        allowlist = Allowlist(
            exemptions=(
                Exemption(
                    path="docs/**",
                    rules=("issued-token",),
                    reason="the runbook shows what an issued token looks like",
                ),
            )
        )
        line = f"    {issue_token()}"

        self.assertEqual(scan_text(line, "docs/runbooks/007.md", allowlist=allowlist), ())
        self.assertTrue(scan_text(line, "ml/security/example.py", allowlist=allowlist))

    def test_an_exemption_without_rules_covers_the_whole_file(self) -> None:
        allowlist = Allowlist(exemptions=(Exemption(path="pnpm-lock.yaml", reason="hashes"),))

        self.assertEqual(scan_text("-----BEGIN PRIVATE KEY-----", "pnpm-lock.yaml", allowlist), ())

    def test_a_line_may_excuse_itself_where_the_reason_is_visible(self) -> None:
        line = f"token = '{issue_token()}'  # {ALLOW_MARKER}: this is a generated example"

        self.assertEqual(scan_text(line, "example.py"), ())


class ScannedFileTest(unittest.TestCase):
    def test_a_file_is_named_relative_to_the_root_it_was_scanned_from(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            path = root / "nested" / "settings.py"
            path.write_text(f"token = '{issue_token()}'", encoding="utf-8")

            findings = scan_files([path], root=root)

        self.assertEqual(findings[0].origin, "nested/settings.py")

    def test_content_that_is_not_text_is_skipped_rather_than_guessed(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "model.joblib"
            path.write_bytes(b"\x00\x01\x02\xff")

            self.assertEqual(scan_file(path), ())

    def test_a_file_that_cannot_be_read_is_not_reported_as_clean_by_crashing(self) -> None:
        with TemporaryDirectory() as directory:
            self.assertEqual(scan_file(Path(directory) / "absent.py"), ())


if __name__ == "__main__":
    unittest.main()

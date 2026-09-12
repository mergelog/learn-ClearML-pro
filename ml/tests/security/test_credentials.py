from __future__ import annotations

import unittest

from ml.security.credentials import (
    TOKEN_PREFIX,
    AccessPolicy,
    CredentialError,
    credential_of,
    fingerprint,
    fingerprint_hint,
    issue_token,
    parse_policy,
)
from ml.security.domain import Outcome, Permission, Principal, Role


class IssuedTokenTest(unittest.TestCase):
    def test_an_issued_token_is_recognisable(self) -> None:
        """漏えいは、探せる形をしているときだけ見つかる。"""
        self.assertTrue(issue_token().startswith(TOKEN_PREFIX))

    def test_two_tokens_are_never_the_same(self) -> None:
        self.assertNotEqual(issue_token(), issue_token())

    def test_a_fingerprint_does_not_contain_the_token(self) -> None:
        token = issue_token()

        self.assertNotIn(token, fingerprint(token))
        self.assertEqual(len(fingerprint(token)), 64)

    def test_the_same_token_always_has_the_same_fingerprint(self) -> None:
        token = issue_token()

        self.assertEqual(fingerprint(token), fingerprint(token))

    def test_the_hint_is_taken_from_the_fingerprint_and_not_from_the_token(self) -> None:
        token = issue_token()

        hint = fingerprint_hint(fingerprint(token))
        self.assertNotIn(hint, token)
        self.assertTrue(fingerprint(token).startswith(hint))


class ParsedPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.token = issue_token()
        self.other = issue_token()

    def test_one_caller_is_read_with_its_role(self) -> None:
        policy = parse_policy(f"batch-scoring:predictor:{fingerprint(self.token)}")

        self.assertEqual(len(policy.principals), 1)
        self.assertEqual(policy.principals[0].name, "batch-scoring")
        self.assertEqual(policy.principals[0].role, Role.PREDICTOR)

    def test_several_callers_are_separated_by_semicolons(self) -> None:
        policy = parse_policy(
            f"batch-scoring:predictor:{fingerprint(self.token)};"
            f"prometheus:scraper:{fingerprint(self.other)}"
        )

        self.assertEqual(
            [(caller.name, caller.role) for caller in policy.principals],
            [("batch-scoring", Role.PREDICTOR), ("prometheus", Role.SCRAPER)],
        )

    def test_a_caller_may_hold_two_credentials_while_one_is_replaced(self) -> None:
        policy = parse_policy(
            f"batch-scoring:predictor:{fingerprint(self.token)},{fingerprint(self.other)}"
        )

        self.assertEqual(len(policy.principals[0].credential_fingerprints), 2)

    def test_an_empty_description_allows_nobody(self) -> None:
        self.assertTrue(parse_policy("   ").is_empty)

    def test_a_token_pasted_instead_of_its_fingerprint_is_named_as_the_mistake(self) -> None:
        """黙って通すと、そのcallerだけが静かに認証できない状態になる。"""
        with self.assertRaises(CredentialError) as raised:
            parse_policy(f"batch-scoring:predictor:{self.token}")

        self.assertIn("fingerprint", str(raised.exception))

    def test_an_unknown_role_is_refused(self) -> None:
        with self.assertRaises(CredentialError):
            parse_policy(f"batch-scoring:administrator:{fingerprint(self.token)}")

    def test_a_missing_field_is_refused(self) -> None:
        with self.assertRaises(CredentialError):
            parse_policy("batch-scoring:predictor")

    def test_a_fingerprint_of_the_wrong_shape_is_refused(self) -> None:
        with self.assertRaises(CredentialError):
            parse_policy("batch-scoring:predictor:not-a-fingerprint")

    def test_two_callers_with_the_same_name_cannot_be_told_apart(self) -> None:
        with self.assertRaises(CredentialError):
            parse_policy(
                f"batch-scoring:predictor:{fingerprint(self.token)};"
                f"batch-scoring:operator:{fingerprint(self.other)}"
            )

    def test_a_shared_credential_makes_a_call_unattributable(self) -> None:
        with self.assertRaises(CredentialError) as raised:
            parse_policy(
                f"batch-scoring:predictor:{fingerprint(self.token)};"
                f"nightly-report:operator:{fingerprint(self.token)}"
            )

        self.assertIn("attributed", str(raised.exception))


class AuthorizationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.token = issue_token()
        self.policy = AccessPolicy(
            principals=(
                Principal(
                    name="batch-scoring",
                    role=Role.PREDICTOR,
                    credential_fingerprints=(fingerprint(self.token),),
                ),
            )
        )

    def test_a_known_caller_may_do_what_its_role_allows(self) -> None:
        decision = self.policy.authorize(self.token, Permission.PREDICT)

        self.assertTrue(decision.allowed)
        self.assertIsNotNone(decision.principal)
        self.assertEqual(decision.principal_name, "batch-scoring")

    def test_a_known_caller_is_refused_what_its_role_does_not_include(self) -> None:
        decision = self.policy.authorize(self.token, Permission.METRICS_READ)

        self.assertEqual(decision.outcome, Outcome.INSUFFICIENT_ROLE)

    def test_no_credential_is_told_apart_from_an_unknown_one(self) -> None:
        self.assertEqual(
            self.policy.authorize(None, Permission.PREDICT).outcome,
            Outcome.MISSING_CREDENTIAL,
        )
        self.assertEqual(
            self.policy.authorize(issue_token(), Permission.PREDICT).outcome,
            Outcome.UNKNOWN_CREDENTIAL,
        )

    def test_a_blank_credential_is_no_credential(self) -> None:
        self.assertEqual(
            self.policy.authorize("   ", Permission.PREDICT).outcome,
            Outcome.MISSING_CREDENTIAL,
        )

    def test_a_policy_without_callers_allows_nobody(self) -> None:
        empty = AccessPolicy()

        self.assertTrue(empty.is_empty)
        self.assertFalse(empty.authorize(self.token, Permission.PREDICT).allowed)

    def test_the_description_names_callers_and_roles_only(self) -> None:
        described = self.policy.describe()

        self.assertIn("batch-scoring(predictor)", described)
        self.assertNotIn(self.token, described)
        self.assertNotIn(fingerprint(self.token), described)


class AuthorizationHeaderTest(unittest.TestCase):
    def test_a_bearer_credential_is_taken_out_of_the_header(self) -> None:
        self.assertEqual(credential_of("Bearer abc123"), "abc123")

    def test_the_scheme_is_read_regardless_of_how_it_was_written(self) -> None:
        self.assertEqual(credential_of("bearer abc123"), "abc123")

    def test_another_scheme_is_not_mistaken_for_a_credential(self) -> None:
        self.assertIsNone(credential_of("Basic dXNlcjpwYXNz"))

    def test_a_header_without_a_credential_is_no_credential(self) -> None:
        self.assertIsNone(credential_of("Bearer"))
        self.assertIsNone(credential_of("Bearer    "))
        self.assertIsNone(credential_of(None))


if __name__ == "__main__":
    unittest.main()

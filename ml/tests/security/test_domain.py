from __future__ import annotations

import unittest

from ml.security.domain import (
    ROLE_PERMISSIONS,
    AccessDecision,
    Outcome,
    Permission,
    Principal,
    Role,
    role_named,
)


class RoleTest(unittest.TestCase):
    """役割は「その仕事に要る最小」であること。"""

    def test_answering_predictions_does_not_include_reading_the_metrics(self) -> None:
        self.assertTrue(Role.PREDICTOR.may(Permission.PREDICT))
        self.assertFalse(Role.PREDICTOR.may(Permission.METRICS_READ))

    def test_operating_the_system_does_not_include_asking_for_predictions(self) -> None:
        self.assertTrue(Role.OPERATOR.may(Permission.METRICS_READ))
        self.assertFalse(Role.OPERATOR.may(Permission.PREDICT))

    def test_the_scraper_may_read_the_numbers_and_nothing_else(self) -> None:
        self.assertEqual(Role.SCRAPER.permissions, frozenset({Permission.METRICS_READ}))

    def test_every_role_is_described(self) -> None:
        """許可の表に無い役割は、何も許されていないのか、書き忘れかが分からない。"""
        self.assertEqual(set(ROLE_PERMISSIONS), set(Role))

    def test_an_unknown_role_says_which_roles_exist(self) -> None:
        with self.assertRaises(ValueError) as raised:
            role_named("administrator")

        for role in Role:
            self.assertIn(role.value, str(raised.exception))


class DecisionTest(unittest.TestCase):
    """断った理由が、そのまま監査の1行になること。"""

    def setUp(self) -> None:
        self.principal = Principal(name="batch-scoring", role=Role.OPERATOR)

    def test_a_caller_that_never_named_itself_is_recorded_as_anonymous(self) -> None:
        decision = AccessDecision(
            outcome=Outcome.MISSING_CREDENTIAL,
            permission=Permission.PREDICT,
        )

        self.assertEqual(decision.principal_name, "anonymous")
        self.assertEqual(decision.role_name, "none")
        self.assertFalse(decision.allowed)

    def test_a_refusal_by_role_names_both_the_role_and_what_was_asked(self) -> None:
        decision = AccessDecision(
            outcome=Outcome.INSUFFICIENT_ROLE,
            permission=Permission.PREDICT,
            principal=self.principal,
        )

        described = decision.describe()
        self.assertIn("batch-scoring", described)
        self.assertIn("operator", described)
        self.assertIn("predict", described)

    def test_an_unknown_credential_is_not_attributed_to_anybody(self) -> None:
        decision = AccessDecision(
            outcome=Outcome.UNKNOWN_CREDENTIAL,
            permission=Permission.METRICS_READ,
        )

        self.assertIn("no known caller", decision.describe())

    def test_an_allowed_call_still_says_who_made_it(self) -> None:
        decision = AccessDecision(
            outcome=Outcome.ALLOWED,
            permission=Permission.METRICS_READ,
            principal=self.principal,
        )

        self.assertTrue(decision.allowed)
        self.assertIn("batch-scoring", decision.describe())


if __name__ == "__main__":
    unittest.main()

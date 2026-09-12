from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from ml.security.credentials import fingerprint, issue_token
from ml.semiconductor_quality.config import ConfigurationError
from services.prediction_api.config import (
    CLIENTS_ENVIRONMENT_KEY,
    DEFAULT_HOST,
    DEFAULT_PORT,
    HOST_ENVIRONMENT_KEY,
    MODEL_ID_ENVIRONMENT_KEY,
    PORT_ENVIRONMENT_KEY,
    TLS_CERTIFICATE_ENVIRONMENT_KEY,
    TLS_PRIVATE_KEY_ENVIRONMENT_KEY,
    ServiceConfig,
)
from services.tests.credentials import access_policy


class DefaultConfigTest(unittest.TestCase):
    def test_a_service_without_configuration_serves_what_is_in_production(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            config = ServiceConfig.from_environment()

        self.assertTrue(config.serves_current_production)
        self.assertEqual(config.host, DEFAULT_HOST)
        self.assertEqual(config.port, DEFAULT_PORT)

    def test_the_service_listens_where_the_container_says(self) -> None:
        environment = {HOST_ENVIRONMENT_KEY: "127.0.0.1", PORT_ENVIRONMENT_KEY: "9000"}

        with mock.patch.dict("os.environ", environment, clear=True):
            config = ServiceConfig.from_environment()

        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 9000)

    def test_a_pinned_model_is_an_exception_and_says_so(self) -> None:
        with mock.patch.dict("os.environ", {MODEL_ID_ENVIRONMENT_KEY: "model-id"}, clear=True):
            config = ServiceConfig.from_environment()

        self.assertFalse(config.serves_current_production)
        self.assertEqual(config.pinned_model_id, "model-id")

    def test_a_blank_pin_is_the_same_as_no_pin(self) -> None:
        with mock.patch.dict("os.environ", {MODEL_ID_ENVIRONMENT_KEY: "  "}, clear=True):
            config = ServiceConfig.from_environment()

        self.assertTrue(config.serves_current_production)


class InvalidConfigTest(unittest.TestCase):
    def test_a_port_that_is_not_a_number_is_refused_before_start_up(self) -> None:
        with mock.patch.dict("os.environ", {PORT_ENVIRONMENT_KEY: "http"}, clear=True):
            with self.assertRaises(ConfigurationError) as raised:
                ServiceConfig.from_environment()

        self.assertIn(PORT_ENVIRONMENT_KEY, str(raised.exception))

    def test_a_port_outside_the_usable_range_is_refused(self) -> None:
        for port in (0, 70_000):
            with self.subTest(port=port), self.assertRaises(ConfigurationError):
                ServiceConfig(port=port).validate()

    def test_a_service_without_a_host_is_refused(self) -> None:
        with self.assertRaises(ConfigurationError):
            ServiceConfig(host="  ").validate()

    def test_a_usable_configuration_is_accepted(self) -> None:
        config = ServiceConfig(clients=access_policy())

        self.assertIs(config.validate(), config)

    def test_a_service_nobody_may_call_does_not_start(self) -> None:
        """開いたまま起動するより、起動しないほうが安全側である。"""
        with self.assertRaises(ConfigurationError) as raised:
            ServiceConfig().validate()

        self.assertIn(CLIENTS_ENVIRONMENT_KEY, str(raised.exception))

    def test_the_callers_are_read_from_the_environment(self) -> None:
        token = issue_token()
        given = {CLIENTS_ENVIRONMENT_KEY: f"batch-scoring:predictor:{fingerprint(token)}"}

        with mock.patch.dict("os.environ", given, clear=True):
            config = ServiceConfig.from_environment()

        self.assertEqual([caller.name for caller in config.clients.principals], ["batch-scoring"])
        self.assertIs(config.validate(), config)

    def test_a_caller_list_that_cannot_be_read_is_refused_before_start_up(self) -> None:
        given = {CLIENTS_ENVIRONMENT_KEY: "batch-scoring:predictor"}

        with mock.patch.dict("os.environ", given, clear=True):
            with self.assertRaises(ConfigurationError) as raised:
                ServiceConfig.from_environment()

        self.assertIn(CLIENTS_ENVIRONMENT_KEY, str(raised.exception))


class TransportSecurityTest(unittest.TestCase):
    """TLSは「半分だけ設定されている」が最も危ない状態である。"""

    def test_plain_http_is_the_local_default(self) -> None:
        self.assertFalse(ServiceConfig(clients=access_policy()).serves_over_tls)

    def test_a_certificate_without_its_key_is_refused(self) -> None:
        config = ServiceConfig(
            clients=access_policy(),
            tls_certificate_file=Path("/etc/tls/serving.crt"),
        )

        with self.assertRaises(ConfigurationError) as raised:
            config.validate()

        self.assertIn(TLS_PRIVATE_KEY_ENVIRONMENT_KEY, str(raised.exception))

    def test_a_certificate_that_is_not_there_is_refused(self) -> None:
        missing = Path("/nonexistent/serving.crt")
        config = ServiceConfig(
            clients=access_policy(),
            tls_certificate_file=missing,
            tls_private_key_file=missing,
        )

        with self.assertRaises(ConfigurationError) as raised:
            config.validate()

        self.assertIn(TLS_CERTIFICATE_ENVIRONMENT_KEY, str(raised.exception))

    def test_a_certificate_and_its_key_are_served_over_tls(self) -> None:
        with TemporaryDirectory() as directory:
            certificate = Path(directory) / "serving.crt"
            private_key = Path(directory) / "serving.key"
            certificate.write_text("certificate", encoding="utf-8")
            private_key.write_text("key", encoding="utf-8")
            config = ServiceConfig(
                clients=access_policy(),
                tls_certificate_file=certificate,
                tls_private_key_file=private_key,
            ).validate()

        self.assertTrue(config.serves_over_tls)


if __name__ == "__main__":
    unittest.main()

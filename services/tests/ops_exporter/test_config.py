from __future__ import annotations

import unittest
from unittest import mock

from ml.security.credentials import fingerprint, issue_token
from ml.semiconductor_quality.config import ConfigurationError
from services.ops_exporter.config import (
    CLIENTS_ENVIRONMENT_KEY,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_PROJECTS,
    HOST_ENVIRONMENT_KEY,
    PORT_ENVIRONMENT_KEY,
    PROJECTS_ENVIRONMENT_KEY,
    RECENT_MINUTES_ENVIRONMENT_KEY,
    OpsExporterConfig,
)
from services.ops_exporter.domain import DEFAULT_RECENT_MINUTES
from services.tests.credentials import access_policy


class DefaultConfigTest(unittest.TestCase):
    def test_an_exporter_without_configuration_watches_the_known_project(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            config = OpsExporterConfig.from_environment()

        self.assertEqual(config.host, DEFAULT_HOST)
        self.assertEqual(config.port, DEFAULT_PORT)
        self.assertEqual(config.projects, DEFAULT_PROJECTS)
        self.assertEqual(config.recent_minutes, DEFAULT_RECENT_MINUTES)

    def test_the_exporter_listens_where_the_container_says(self) -> None:
        environment = {HOST_ENVIRONMENT_KEY: "127.0.0.1", PORT_ENVIRONMENT_KEY: "9100"}

        with mock.patch.dict("os.environ", environment, clear=True):
            config = OpsExporterConfig.from_environment()

        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 9100)

    def test_several_projects_can_be_watched_by_one_exporter(self) -> None:
        given = {PROJECTS_ENVIRONMENT_KEY: "Semiconductor Quality Prediction, Spare Project"}

        with mock.patch.dict("os.environ", given, clear=True):
            config = OpsExporterConfig.from_environment()

        self.assertEqual(config.projects, ("Semiconductor Quality Prediction", "Spare Project"))

    def test_an_unset_project_list_falls_back_to_what_is_known(self) -> None:
        with mock.patch.dict("os.environ", {PROJECTS_ENVIRONMENT_KEY: "   "}, clear=True):
            config = OpsExporterConfig.from_environment()

        self.assertEqual(config.projects, DEFAULT_PROJECTS)

    def test_a_list_of_only_separators_is_a_mistake_and_is_not_guessed(self) -> None:
        """設定はされているが、中身が無い。既定へ落とすと誤りに気付けない。"""
        with mock.patch.dict("os.environ", {PROJECTS_ENVIRONMENT_KEY: " , "}, clear=True):
            config = OpsExporterConfig.from_environment()

        self.assertEqual(config.projects, ())
        with self.assertRaises(ConfigurationError):
            config.validate()

    def test_how_far_back_recent_reaches_can_be_changed(self) -> None:
        with mock.patch.dict("os.environ", {RECENT_MINUTES_ENVIRONMENT_KEY: "5"}, clear=True):
            config = OpsExporterConfig.from_environment()

        self.assertEqual(config.recent_minutes, 5)


class InvalidConfigTest(unittest.TestCase):
    def test_a_port_that_is_not_a_number_is_refused_before_start_up(self) -> None:
        with mock.patch.dict("os.environ", {PORT_ENVIRONMENT_KEY: "metrics"}, clear=True):
            with self.assertRaises(ValueError) as raised:
                OpsExporterConfig.from_environment()

        self.assertIn(PORT_ENVIRONMENT_KEY, str(raised.exception))

    def test_a_port_outside_the_usable_range_is_refused(self) -> None:
        for port in (0, 70_000):
            with self.subTest(port=port), self.assertRaises(ConfigurationError):
                OpsExporterConfig(port=port).validate()

    def test_an_exporter_without_a_host_is_refused(self) -> None:
        with self.assertRaises(ConfigurationError):
            OpsExporterConfig(host="  ").validate()

    def test_watching_nothing_is_refused_rather_than_started(self) -> None:
        with self.assertRaises(ConfigurationError) as raised:
            OpsExporterConfig(projects=()).validate()

        self.assertIn("at least one project", str(raised.exception))

    def test_a_window_that_reaches_nowhere_is_refused(self) -> None:
        with self.assertRaises(ConfigurationError):
            OpsExporterConfig(recent_minutes=0).validate()

    def test_a_usable_configuration_is_accepted(self) -> None:
        config = OpsExporterConfig(clients=access_policy())

        self.assertIs(config.validate(), config)

    def test_an_exporter_nobody_may_read_does_not_start(self) -> None:
        """数字は「このシステムがいまどうなっているか」そのものである。"""
        with self.assertRaises(ConfigurationError) as raised:
            OpsExporterConfig().validate()

        self.assertIn(CLIENTS_ENVIRONMENT_KEY, str(raised.exception))

    def test_the_readers_are_read_from_the_environment(self) -> None:
        token = issue_token()
        given = {CLIENTS_ENVIRONMENT_KEY: f"prometheus:scraper:{fingerprint(token)}"}

        with mock.patch.dict("os.environ", given, clear=True):
            config = OpsExporterConfig.from_environment()

        self.assertEqual([reader.name for reader in config.clients.principals], ["prometheus"])


if __name__ == "__main__":
    unittest.main()

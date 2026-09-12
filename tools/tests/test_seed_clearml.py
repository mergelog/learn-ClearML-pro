from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from tools import seed_clearml


class SeedClearmlCredentialsTest(unittest.TestCase):
    def test_credentials_are_optional(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(seed_clearml.get_credentials())

    def test_credentials_are_read_from_environment(self):
        environment = {
            "CLEARML_API_ACCESS_KEY": "access-key",
            "CLEARML_API_SECRET_KEY": "secret-key",
        }

        with patch.dict("os.environ", environment, clear=True):
            self.assertEqual(
                seed_clearml.get_credentials(),
                ("access-key", "secret-key"),
            )

    def test_incomplete_credentials_are_rejected(self):
        environment = {"CLEARML_API_ACCESS_KEY": "access-key"}

        with patch.dict("os.environ", environment, clear=True):
            with self.assertRaisesRegex(RuntimeError, "must be set together"):
                seed_clearml.get_credentials()


class SeedClearmlTest(unittest.TestCase):
    @patch("tools.seed_clearml.call")
    def test_existing_project_is_reused(self, call_mock):
        call_mock.return_value = {
            "data": {"projects": [{"id": "project-1", "name": "stackup/test"}]}
        }

        self.assertEqual(seed_clearml.ensure_project(), "project-1")
        call_mock.assert_called_once_with(
            "projects.get_all",
            {"name": "stackup/test", "only_fields": ["id", "name"]},
        )

    @patch("tools.seed_clearml.call")
    def test_missing_task_is_created(self, call_mock):
        call_mock.side_effect = [
            {"data": {"tasks": []}},
            {"data": {"id": "task-1"}},
        ]

        self.assertEqual(seed_clearml.ensure_task("project-1"), "task-1")
        create_endpoint, create_payload = call_mock.call_args_list[1].args
        self.assertEqual(create_endpoint, "tasks.create")
        self.assertEqual(create_payload["project"], "project-1")
        self.assertEqual(create_payload["type"], "testing")


class WaitUntilReadyTest(unittest.TestCase):
    """The one place in this repository that retries.

    Seeding runs right after `backend:up`, when the ClearML Server is still
    starting: a first attempt that fails is the normal case, not the broken
    one. Everything else in the system is allowed to fail at once and be
    restarted, so this is the only retry there is — and it was the only one
    with no test.
    """

    def setUp(self) -> None:
        # 本物の待ち時間をテストに持ち込まない。確かめたいのは待つ回数と
        # 止め方であって、2分かかること自体ではない。
        sleep = patch("tools.seed_clearml.time.sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    @patch("tools.seed_clearml.call")
    def test_a_server_that_answers_at_once_is_not_waited_for(self, call_mock):
        seed_clearml.wait_until_ready()

        call_mock.assert_called_once_with("debug.ping")
        self.sleep.assert_not_called()

    @patch("tools.seed_clearml.call")
    def test_a_server_that_is_still_starting_is_waited_for(self, call_mock):
        # 立ち上がりかけのサーバは「繋がらない」から始まる。
        call_mock.side_effect = [URLError("connection refused"), {"data": {}}]

        seed_clearml.wait_until_ready()

        self.assertEqual(call_mock.call_count, 2)
        self.sleep.assert_called_once_with(2)

    @patch("tools.seed_clearml.call")
    def test_waiting_stops_as_soon_as_the_server_answers(self, call_mock):
        call_mock.side_effect = [TimeoutError(), URLError("refused"), {"data": {}}]

        seed_clearml.wait_until_ready()

        # 答えたあとも待ち続けると、seed全体が無駄に遅くなる。
        self.assertEqual(call_mock.call_count, 3)
        self.assertEqual(self.sleep.call_count, 2)

    @patch("tools.seed_clearml.call")
    def test_a_server_that_never_answers_is_given_up_on_with_a_reason(self, call_mock):
        call_mock.side_effect = URLError("connection refused")

        with self.assertRaises(RuntimeError) as raised:
            seed_clearml.wait_until_ready()

        # 黙って諦めると、次に落ちるのは無関係な行になる。
        self.assertIn(seed_clearml.API_HOST, str(raised.exception))
        self.assertEqual(call_mock.call_count, 60)

    @patch("tools.seed_clearml.call")
    def test_a_server_that_answers_with_an_error_is_also_waited_for(self, call_mock):
        # 起動途中のClearMLは 500 を返すことがある。繋がらないのと同じ扱いにする。
        error = HTTPError("http://localhost:8008", 500, "Internal", {}, None)  # type: ignore[arg-type]
        call_mock.side_effect = [error, {"data": {}}]

        seed_clearml.wait_until_ready()

        self.assertEqual(call_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from unittest.mock import patch
from urllib.error import URLError

import numpy as np

from tools.semiconductor_seed import clearml_gateway, dataset_cli, server_health
from tools.semiconductor_seed.clearml_gateway import ClearmlGateway
from tools.semiconductor_seed.config import Settings
from tools.semiconductor_seed.dataset_seeding import seed_datasets
from tools.semiconductor_seed.domain import DatasetVersion, GeneratedDataset
from tools.semiconductor_seed.generator import generate_dataset
from tools.semiconductor_seed.scenarios import experiment_specs


class RecordingDatasetGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[GeneratedDataset, str | None]] = []

    def ensure_dataset(
        self,
        dataset: GeneratedDataset,
        parent_id: str | None = None,
    ) -> str:
        self.calls.append((dataset, parent_id))
        return f"dataset-{dataset.definition.version}"


class SemiconductorDatasetGeneratorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.definition = DatasetVersion(
            version="test",
            row_count=200,
            random_seed_offset=0,
            description="Test data",
        )

    def test_generation_is_reproducible(self) -> None:
        with (
            tempfile.TemporaryDirectory() as first_dir,
            tempfile.TemporaryDirectory() as second_dir,
        ):
            first = generate_dataset(self.definition, Path(first_dir), base_seed=123)
            second = generate_dataset(self.definition, Path(second_dir), base_seed=123)

            np.testing.assert_array_equal(first.features, second.features)
            np.testing.assert_array_equal(first.targets, second.targets)
            self.assertEqual(first.csv_path.read_bytes(), second.csv_path.read_bytes())

    def test_dataset_contains_both_classes(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            generated = generate_dataset(self.definition, Path(output_dir), base_seed=123)

            labels, counts = np.unique(generated.targets, return_counts=True)
            distribution = dict(zip(labels, counts / counts.sum(), strict=True))

            self.assertEqual(set(distribution), {"pass", "fail"})
            self.assertGreater(distribution["pass"], 0.55)
            self.assertGreater(distribution["fail"], 0.30)


class SemiconductorDatasetSeedingTest(unittest.TestCase):
    def test_registers_only_versioned_datasets_in_parent_order(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            settings = Settings(
                api_host="http://localhost:8008",
                web_host="http://localhost:8080",
                files_host="http://localhost:8081",
                access_key="test-access-key",
                secret_key="test-secret-key",
                output_dir=Path(output_dir),
                random_seed=123,
            )
            gateway = RecordingDatasetGateway()

            datasets, dataset_ids = seed_datasets(settings, gateway)

            self.assertEqual(list(datasets), ["1.0.0", "2.0.0"])
            self.assertEqual(
                dataset_ids,
                {
                    "1.0.0": "dataset-1.0.0",
                    "2.0.0": "dataset-2.0.0",
                },
            )
            self.assertEqual(
                [
                    (dataset.definition.version, parent_id)
                    for dataset, parent_id in gateway.calls
                ],
                [
                    ("1.0.0", None),
                    ("2.0.0", "dataset-1.0.0"),
                ],
            )


class SemiconductorScenarioTest(unittest.TestCase):
    def test_twenty_unique_experiments_are_defined(self) -> None:
        specs = experiment_specs()

        self.assertEqual(len(specs), 20)
        self.assertEqual(len({spec.name for spec in specs}), 20)
        self.assertEqual(sum(spec.final_status == "failed" for spec in specs), 1)
        self.assertEqual(sum(spec.final_status == "aborted" for spec in specs), 1)


if __name__ == "__main__":
    unittest.main()


class SemiconductorSeedSettingsTest(unittest.TestCase):
    def test_credentials_are_optional(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings.from_environment()

        self.assertIsNone(settings.access_key)
        self.assertIsNone(settings.secret_key)

    def test_credentials_are_read_from_environment(self) -> None:
        environment = {
            "CLEARML_API_ACCESS_KEY": "access-key",
            "CLEARML_API_SECRET_KEY": "secret-key",
        }

        with patch.dict("os.environ", environment, clear=True):
            settings = Settings.from_environment()

        self.assertEqual(settings.access_key, "access-key")
        self.assertEqual(settings.secret_key, "secret-key")
        self.assertNotIn("access-key", repr(settings))
        self.assertNotIn("secret-key", repr(settings))

    def test_incomplete_credentials_are_rejected(self) -> None:
        environment = {"CLEARML_API_ACCESS_KEY": "access-key"}

        with patch.dict("os.environ", environment, clear=True):
            with self.assertRaisesRegex(ValueError, "must be set together"):
                Settings.from_environment()


class SemiconductorDatasetLookupTest(unittest.TestCase):
    """A Dataset version is identified by project, name and version alone."""

    @staticmethod
    def _settings() -> Settings:
        return Settings(
            api_host="http://localhost:8008",
            web_host="http://localhost:8080",
            files_host="http://localhost:8081",
            access_key=None,
            secret_key=None,
            output_dir=Path(),
            random_seed=123,
        )

    def test_lookup_does_not_filter_on_the_seed_tag(self) -> None:
        with patch.object(clearml_gateway, "Task"):
            with patch.object(clearml_gateway, "Dataset") as dataset:
                gateway = ClearmlGateway(self._settings())

                gateway._find_dataset("2.0.0")

        self.assertNotIn("dataset_tags", dataset.get.call_args.kwargs)

    def test_untagged_existing_version_is_reused(self) -> None:
        generated = GeneratedDataset(
            definition=DatasetVersion(
                version="2.0.0",
                row_count=1,
                random_seed_offset=0,
                description="",
            ),
            csv_path=Path("unused.csv"),
            features=np.zeros((1, 1), dtype=object),
            targets=np.array(["pass"]),
        )

        with patch.object(clearml_gateway, "Task"):
            with patch.object(clearml_gateway, "Dataset") as dataset:
                dataset.get.return_value = SimpleNamespace(id="existing-id")
                gateway = ClearmlGateway(self._settings())

                dataset_id = gateway.ensure_dataset(generated)

        self.assertEqual(dataset_id, "existing-id")
        dataset.create.assert_not_called()


class ServerReadinessTest(unittest.TestCase):
    """What seeding does when the ClearML Server is not there.

    This is the first call both seed commands make, and it is the realistic
    failure: the containers are still starting, or were never started. What
    matters is that it says so in one line, and that nothing is created on a
    server that could not be reached.
    """

    def answering(self, status: int) -> object:
        response = mock.MagicMock()
        response.status = status
        response.__enter__ = lambda _self: response
        response.__exit__ = lambda *_: False
        return response

    def test_a_server_that_answers_is_accepted(self) -> None:
        with patch.object(server_health, "urlopen", return_value=self.answering(200)):
            server_health.ensure_server_is_ready("http://localhost:8008")

    def test_the_readiness_of_the_api_is_asked_with_a_deadline(self) -> None:
        # 期限を付けずに尋ねると、落ちているサーバの前で止まったままになる。
        with patch.object(server_health, "urlopen", return_value=self.answering(200)) as opened:
            server_health.ensure_server_is_ready("http://localhost:8008")

        self.assertEqual(opened.call_args.kwargs["timeout"], 10)
        self.assertIn("debug.ping", opened.call_args.args[0])

    def test_a_server_that_answers_something_else_is_refused_by_host(self) -> None:
        with patch.object(server_health, "urlopen", return_value=self.answering(503)):
            with self.assertRaises(RuntimeError) as raised:
                server_health.ensure_server_is_ready("http://localhost:8008")

        self.assertIn("http://localhost:8008", str(raised.exception))


class DatasetSeedCommandTest(unittest.TestCase):
    """The command's own failure path, not the gateway's."""

    def run_main(self) -> tuple[int, str]:
        errors = io.StringIO()
        with patch("sys.stderr", errors):
            code = dataset_cli.main()
        return code, errors.getvalue()

    def test_a_server_that_is_not_there_fails_the_command_with_a_reason(self) -> None:
        with (
            patch.object(
                dataset_cli,
                "ensure_server_is_ready",
                side_effect=URLError("connection refused"),
            ),
            patch.object(dataset_cli, "ClearmlGateway") as gateway,
        ):
            code, reported = self.run_main()

        self.assertEqual(code, 1)
        self.assertIn("connection refused", reported)
        # 繋がらなかったサーバに対して、続きを始めない。
        gateway.assert_not_called()

    def test_a_server_that_never_answers_fails_the_command(self) -> None:
        # TimeoutError は OSError なので、落ちているのと同じ扱いで拾われる。
        with (
            patch.object(dataset_cli, "ensure_server_is_ready", side_effect=TimeoutError()),
            patch.object(dataset_cli, "ClearmlGateway") as gateway,
        ):
            code, reported = self.run_main()

        self.assertEqual(code, 1)
        self.assertIn("Semiconductor dataset seed failed", reported)
        gateway.assert_not_called()

    def test_a_server_that_is_not_ready_fails_the_command(self) -> None:
        with (
            patch.object(
                dataset_cli,
                "ensure_server_is_ready",
                side_effect=RuntimeError("ClearML API is not ready at http://localhost:8008"),
            ),
            patch.object(dataset_cli, "ClearmlGateway"),
        ):
            code, reported = self.run_main()

        self.assertEqual(code, 1)
        self.assertIn("is not ready", reported)


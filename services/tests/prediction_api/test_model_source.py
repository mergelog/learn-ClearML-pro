from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import joblib

from ml.model_lifecycle.domain import (
    METADATA_DATASET_ID,
    METADATA_DATASET_VERSION,
    METADATA_MODEL_VERSION,
    METADATA_TRAIN_TASK_ID,
    LifecycleError,
    ModelStage,
)
from ml.semiconductor_quality.config import EstimatorConfig, RandomForestConfig
from ml.semiconductor_quality.train import build_contract_pipeline, fit_pipeline
from ml.tests.pipeline.test_artifacts import build_split
from services.prediction_api import model_source
from services.prediction_api.config import ServiceConfig
from services.prediction_api.domain import (
    ModelMismatchError,
    ModelUnavailableError,
)
from services.prediction_api.model_source import load_served_model


class FakeModel:
    """A registered model that lives in memory, so no server is contacted."""

    def __init__(self, model_id: str, stage: ModelStage, weights: Path | None) -> None:
        self.id = model_id
        self.tags = [stage.tag]
        self.url = "http://localhost:8081/models/model.joblib"
        self._weights = weights
        self._metadata = {
            METADATA_MODEL_VERSION: f"1.0.0-{model_id}",
            METADATA_DATASET_ID: "dataset-id",
            METADATA_DATASET_VERSION: "1.0.0",
            METADATA_TRAIN_TASK_ID: "train-task",
        }

    def get_all_metadata(self) -> dict[str, dict[str, str]]:
        return {name: {"value": value} for name, value in self._metadata.items()}

    def get_local_copy(self) -> str | None:
        return None if self._weights is None else str(self._weights)


class ModelSourceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory(prefix="prediction-model-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.weights = self.fit_a_model()

        self.registry: dict[str, FakeModel] = {}
        self.sdk = mock.MagicMock(name="Model")
        self.sdk.side_effect = lambda model_id: self._by_id(model_id)
        self.sdk.query_models.side_effect = self._query

        for name, replacement in (
            ("Model", self.sdk),
            ("connected_settings", mock.MagicMock(name="connected_settings")),
        ):
            patcher = mock.patch.object(model_source, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def fit_a_model(self) -> Path:
        split = build_split()
        pipeline = build_contract_pipeline(
            EstimatorConfig(forest=RandomForestConfig(n_estimators=5)),
            1,
        )
        fit_pipeline(pipeline, split.train)
        weights = self.directory / "model.joblib"
        joblib.dump(pipeline, weights)
        return weights

    def add(self, model_id: str, stage: ModelStage, weights: Path | None = None) -> FakeModel:
        model = FakeModel(model_id, stage, self.weights if weights is None else weights)
        self.registry[model_id] = model
        return model

    def _by_id(self, model_id: str) -> FakeModel:
        if model_id not in self.registry:
            raise ValueError(f"no such model: {model_id}")
        return self.registry[model_id]

    def _query(self, **keywords: object) -> list[FakeModel]:
        requested = keywords.get("tags") or []
        wanted = set(requested) if isinstance(requested, list) else set()
        return [model for model in self.registry.values() if wanted <= set(model.tags)]


class LoadingTest(ModelSourceTestCase):
    def test_the_model_in_production_is_the_one_served(self) -> None:
        self.add("model-a", ModelStage.PRODUCTION)
        self.add("model-b", ModelStage.STAGING)

        served = load_served_model(ServiceConfig())

        self.assertEqual(served.model_id, "model-a")
        self.assertEqual(served.stage, ModelStage.PRODUCTION)

    def test_the_served_model_carries_what_it_learned_from(self) -> None:
        self.add("model-a", ModelStage.PRODUCTION)

        served = load_served_model(ServiceConfig())

        self.assertEqual(served.dataset_version, "1.0.0")
        self.assertEqual(served.train_task_id, "train-task")

    def test_the_loaded_model_actually_answers(self) -> None:
        self.add("model-a", ModelStage.PRODUCTION)
        served = load_served_model(ServiceConfig())

        answered = served.predict([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, "EQ-0", "STEP-0"]])

        self.assertEqual(len(answered.labels), 1)
        self.assertIn(answered.labels[0], ("pass", "fail"))

    def test_a_forest_reports_how_sure_it_is(self) -> None:
        self.add("model-a", ModelStage.PRODUCTION)
        served = load_served_model(ServiceConfig())

        answered = served.predict([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, "EQ-0", "STEP-0"]])

        self.assertIsNotNone(answered.confidences)


class TunedThresholdModelTest(ModelSourceTestCase):
    """A model whose probability cut was chosen by a search is still a model.

    A search hands over the cut inside the fitted pipeline, so what reaches
    the registry is a classifier wrapped in one more layer. The service must
    not need to know that: it asks for labels and for how sure the model is,
    and both answers have to keep working.
    """

    def fit_a_model(self) -> Path:
        split = build_split()
        pipeline = build_contract_pipeline(
            EstimatorConfig(
                forest=RandomForestConfig(n_estimators=5),
                decision_threshold=0.4,
            ),
            1,
        )
        fit_pipeline(pipeline, split.train)
        weights = self.directory / "model.joblib"
        joblib.dump(pipeline, weights)
        return weights

    def test_a_model_cut_where_a_search_chose_is_served(self) -> None:
        self.add("model-a", ModelStage.PRODUCTION)

        served = load_served_model(ServiceConfig())

        self.assertEqual(served.model_id, "model-a")

    def test_it_answers_labels_and_says_how_sure_it_is(self) -> None:
        self.add("model-a", ModelStage.PRODUCTION)
        served = load_served_model(ServiceConfig())

        answered = served.predict([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, "EQ-0", "STEP-0"]])

        self.assertIn(answered.labels[0], ("pass", "fail"))
        self.assertIsNotNone(answered.confidences)


class RefusalTest(ModelSourceTestCase):
    def test_a_service_with_nothing_in_production_refuses_to_start(self) -> None:
        self.add("model-a", ModelStage.CANDIDATE)

        with self.assertRaises(ModelUnavailableError) as raised:
            load_served_model(ServiceConfig())

        self.assertIn("nothing to serve", str(raised.exception))

    def test_two_models_claiming_production_stop_the_start_up(self) -> None:
        self.add("model-a", ModelStage.PRODUCTION)
        self.add("model-b", ModelStage.PRODUCTION)

        with self.assertRaises(ModelUnavailableError) as raised:
            load_served_model(ServiceConfig())

        self.assertIn("cannot be true", str(raised.exception))

    def test_a_pinned_model_that_was_never_promoted_is_refused(self) -> None:
        self.add("model-a", ModelStage.CANDIDATE)

        with self.assertRaises(ModelUnavailableError) as raised:
            load_served_model(ServiceConfig(pinned_model_id="model-a"))

        self.assertIn("candidate", str(raised.exception))

    def test_a_pinned_model_that_does_not_exist_is_reported_by_name(self) -> None:
        with self.assertRaises(ModelUnavailableError) as raised:
            load_served_model(ServiceConfig(pinned_model_id="absent"))

        self.assertIn("absent", str(raised.exception))

    def test_a_model_whose_weights_cannot_be_fetched_stops_the_start_up(self) -> None:
        self.add("model-a", ModelStage.PRODUCTION, weights=Path("/nowhere/model.joblib"))

        with self.assertRaises(ModelUnavailableError) as raised:
            load_served_model(ServiceConfig())

        # 起動時の失敗はコンテナの再起動ループの中で読まれる。どのモデルの
        # どのファイルが読めなかったのかが、そこに書いてある必要がある。
        self.assertIn("model-a", str(raised.exception))
        self.assertIn("cannot be read", str(raised.exception))

    def test_a_registry_that_cannot_be_reached_stops_the_start_up(self) -> None:
        """ClearMLが止まっているとき、起動しない理由がそう読めること。

        SDKは自分の内部の型で失敗する。そのまま外に出ると、モデルの問題と
        サーバの問題が同じに見える。停止と再起動のどちらで直るかが変わるので、
        見分けられないと運用の判断ができない。
        """
        self.sdk.query_models.side_effect = ConnectionError("connection refused")

        with self.assertRaises(ModelUnavailableError) as raised:
            load_served_model(ServiceConfig())

        reported = str(raised.exception)
        self.assertIn("registry cannot be read", reported)
        self.assertIn("connection refused", reported)

    def test_weights_that_were_cut_off_are_refused_by_name(self) -> None:
        """途中で切れた重みは ``EOFError`` になる。原因を何も語らない。"""
        truncated = self.directory / "truncated.joblib"
        stored = self.weights.read_bytes()
        truncated.write_bytes(stored[: len(stored) // 2])
        self.add("model-a", ModelStage.PRODUCTION, weights=truncated)

        with self.assertRaises(ModelUnavailableError) as raised:
            load_served_model(ServiceConfig())

        reported = str(raised.exception)
        self.assertIn("model-a", reported)
        self.assertIn("EOFError", reported)
        self.assertIn("damaged", reported)

    def test_a_file_that_is_not_a_model_at_all_is_refused_by_name(self) -> None:
        """joblib以外のファイルは ``KeyError: 0`` になる。同じく何も語らない。"""
        nonsense = self.directory / "nonsense.joblib"
        nonsense.write_bytes(b"\x00\x01 this was never a model")
        self.add("model-a", ModelStage.PRODUCTION, weights=nonsense)

        with self.assertRaises(ModelUnavailableError) as raised:
            load_served_model(ServiceConfig())

        self.assertIn(str(nonsense), str(raised.exception))

    def test_a_model_that_only_exists_on_another_machine_is_reported_clearly(self) -> None:
        model = self.add("model-a", ModelStage.PRODUCTION)
        model.get_local_copy = lambda: None  # type: ignore[method-assign]
        model.url = "file:///home/app/.clearml/model.joblib"  # type: ignore[attr-defined]

        with self.assertRaises(ModelUnavailableError) as raised:
            load_served_model(ServiceConfig())

        self.assertIn("cannot be downloaded", str(raised.exception))

    def test_a_model_that_is_not_a_pipeline_is_refused(self) -> None:
        broken = self.directory / "broken.joblib"
        joblib.dump({"not": "a pipeline"}, broken)
        self.add("model-a", ModelStage.PRODUCTION, weights=broken)

        with self.assertRaises(ModelUnavailableError) as raised:
            load_served_model(ServiceConfig())

        self.assertIn("fitted pipeline", str(raised.exception))

    def test_a_model_without_a_stage_stops_the_start_up(self) -> None:
        model = self.add("model-a", ModelStage.PRODUCTION)
        model.tags = ["framework:sklearn"]

        with self.assertRaises(LifecycleError):
            load_served_model(ServiceConfig(pinned_model_id="model-a"))

    def test_a_model_fitted_on_other_columns_is_refused(self) -> None:
        self.add("model-a", ModelStage.PRODUCTION)

        with mock.patch.object(model_source, "_feature_names", return_value=("temperature",)):
            with self.assertRaises(ModelMismatchError) as raised:
                load_served_model(ServiceConfig())

        self.assertIn("temperature", str(raised.exception))


if __name__ == "__main__":
    unittest.main()

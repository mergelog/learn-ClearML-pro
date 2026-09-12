from __future__ import annotations

import math
import unittest
from typing import Any

from clearml.automation import (
    DiscreteParameterRange,
    LogUniformParameterRange,
    UniformIntegerParameterRange,
    UniformParameterRange,
)

from ml.experiment.domain import (
    SEARCH_PLAN_ARTIFACT,
    TRIAL_RESULT_ARTIFACT,
    ChoiceRange,
    Environment,
    ExecutionPlacement,
    ExperimentError,
    ExperimentPlan,
    IntegerRange,
    NumberRange,
    SearchSpace,
)
from ml.experiment.optimizer import (
    BUDGET_SECTION,
    OBJECTIVE_SECTION,
    PLACEMENT_SECTION,
    SPACE_SECTION,
    TRIAL_SECTION,
    BestTrial,
    SearchRequest,
    estimator_parameter_name,
    handoff_arguments,
    hyper_parameters,
    read_trial,
    record_plan,
    trial_parameters,
)
from ml.pipeline.cli import parse_arguments as parse_pipeline_arguments
from ml.pipeline.domain import DATASET_SECTION, MODEL_SECTION, SPLIT_SECTION
from ml.semiconductor_quality.clearml_tracking import model_parameters
from ml.semiconductor_quality.config import (
    Algorithm,
    ClassWeight,
    ConfigurationError,
    DatasetConfig,
    EstimatorConfig,
    HistGradientBoostingConfig,
    LogisticRegressionConfig,
    RandomForestConfig,
    SplitConfig,
)


def build_request(**overrides: object) -> SearchRequest:
    plan = ExperimentPlan(
        environment=Environment.DEVELOPMENT,
        space=SearchSpace(
            ranges=(
                IntegerRange(name="n_estimators", minimum=100, maximum=600, step=50),
                ChoiceRange(name="class_weight", values=("none", "balanced")),
            ),
        ),
        placement=ExecutionPlacement(trial_queue="trials", optimizer_queue="searches"),
    )
    defaults: dict[str, object] = {
        "plan": plan,
        "dataset": DatasetConfig(dataset_version="2.0.0"),
    }
    defaults.update(overrides)
    return SearchRequest(**defaults)  # type: ignore[arg-type]


class FakeArtifact:
    def __init__(self, content: object) -> None:
        self._content = content

    def get(self) -> object:
        return self._content


class FakeTask:
    """A Task that has run, as much of one as reading a trial back needs."""

    def __init__(self, parameters: dict[str, str], result: object) -> None:
        self.id = "trial-1"
        self._parameters = parameters
        self.artifacts: dict[str, Any] = (
            {} if result is None else {TRIAL_RESULT_ARTIFACT: FakeArtifact(result)}
        )

    def get_parameters(self) -> dict[str, str]:
        return self._parameters


class SearchRequestTest(unittest.TestCase):
    def test_a_search_states_the_rows_it_searches_on(self) -> None:
        request = build_request().validate()

        self.assertEqual(request.dataset.dataset_version, "2.0.0")

    def test_a_search_without_a_dataset_version_is_refused(self) -> None:
        with self.assertRaises(ConfigurationError):
            build_request(dataset=DatasetConfig(dataset_version="")).validate()

    def test_ratios_that_do_not_divide_the_rows_are_refused(self) -> None:
        with self.assertRaises(ConfigurationError):
            build_request(split=SplitConfig(train_ratio=0.9, validation_ratio=0.9)).validate()


class TrialTemplateTest(unittest.TestCase):
    def test_a_trial_is_told_everything_it_needs_to_run_on_its_own(self) -> None:
        parameters = trial_parameters(build_request())

        self.assertEqual(parameters[f"{DATASET_SECTION}/dataset_version"], "2.0.0")
        self.assertEqual(parameters[f"{SPLIT_SECTION}/train_ratio"], "0.6")
        self.assertEqual(parameters[f"{MODEL_SECTION}/algorithm"], "random-forest")
        self.assertIn("Search/cross_validation_folds", parameters)

    def test_the_template_starts_without_a_cut_because_each_trial_chooses_one(self) -> None:
        parameters = trial_parameters(build_request())

        self.assertEqual(parameters[f"{MODEL_SECTION}/decision_threshold"], "")


class SearchSpaceTranslationTest(unittest.TestCase):
    def test_a_searched_setting_is_addressed_where_a_trial_reads_it(self) -> None:
        self.assertEqual(
            estimator_parameter_name("n_estimators"),
            f"{MODEL_SECTION}/n_estimators",
        )

    def test_each_kind_becomes_the_range_the_optimizer_samples(self) -> None:
        space = SearchSpace(
            algorithm=Algorithm.HIST_GRADIENT_BOOSTING,
            ranges=(
                IntegerRange(name="max_iterations", minimum=50, maximum=200, step=10),
                NumberRange(name="learning_rate", minimum=0.05, maximum=0.5),
                ChoiceRange(name="class_weight", values=("none", "balanced")),
            ),
        )

        translated = hyper_parameters(space)

        self.assertIsInstance(translated[0], UniformIntegerParameterRange)
        self.assertIsInstance(translated[1], UniformParameterRange)
        self.assertIsInstance(translated[2], DiscreteParameterRange)

    def test_a_logarithmic_range_is_handed_over_as_the_exponents_clearml_expects(self) -> None:
        space = SearchSpace(
            algorithm=Algorithm.HIST_GRADIENT_BOOSTING,
            ranges=(
                NumberRange(name="learning_rate", minimum=0.01, maximum=0.1, logarithmic=True),
            ),
        )

        translated = hyper_parameters(space)[0]

        self.assertIsInstance(translated, LogUniformParameterRange)
        assert isinstance(translated, LogUniformParameterRange)
        self.assertAlmostEqual(translated.min_value, math.log10(0.01))
        self.assertAlmostEqual(translated.max_value, math.log10(0.1))
        self.assertAlmostEqual(translated.base**translated.min_value, 0.01)


class ReadingTheWinnerTest(unittest.TestCase):
    def test_the_winner_is_read_from_what_its_task_actually_ran(self) -> None:
        task = FakeTask(
            {
                f"{MODEL_SECTION}/algorithm": "random-forest",
                f"{MODEL_SECTION}/n_estimators": "450",
                f"{MODEL_SECTION}/class_weight": "balanced",
            },
            {"objective_metric": "f1", "objective": 0.72, "decision_threshold": 0.38},
        )

        winner = read_trial(task, "f1")  # type: ignore[arg-type]

        self.assertEqual(winner.estimator.forest.n_estimators, 450)
        self.assertEqual(winner.estimator.class_weight, ClassWeight.BALANCED)
        self.assertEqual(winner.estimator.decision_threshold, 0.38)
        self.assertEqual(winner.objective, 0.72)

    def test_the_cut_the_trial_chose_travels_with_the_settings(self) -> None:
        task = FakeTask(
            {f"{MODEL_SECTION}/algorithm": "random-forest"},
            {"objective": 0.5, "decision_threshold": None},
        )

        winner = read_trial(task, "f1")  # type: ignore[arg-type]

        self.assertIsNone(winner.estimator.decision_threshold)

    def test_a_trial_that_recorded_no_score_cannot_be_the_winner(self) -> None:
        task = FakeTask({}, {"decision_threshold": 0.4})

        with self.assertRaises(ExperimentError):
            read_trial(task, "f1")  # type: ignore[arg-type]

    def test_a_trial_that_uploaded_no_result_cannot_be_the_winner(self) -> None:
        task = FakeTask({}, None)

        with self.assertRaises(ExperimentError) as raised:
            read_trial(task, "f1")  # type: ignore[arg-type]

        self.assertIn(TRIAL_RESULT_ARTIFACT, str(raised.exception))

    def test_the_recorded_winner_carries_the_settings_a_run_can_be_started_from(self) -> None:
        task = FakeTask(
            {f"{MODEL_SECTION}/algorithm": "random-forest", f"{MODEL_SECTION}/n_estimators": "200"},
            {"objective": 0.6, "decision_threshold": 0.3},
        )

        document = read_trial(task, "f1").as_document()  # type: ignore[arg-type]

        self.assertEqual(document["split"], "train")
        estimator = document["estimator"]
        self.assertEqual(estimator[f"{MODEL_SECTION}/n_estimators"], "200")  # type: ignore[index]


class HandoffTest(unittest.TestCase):
    """What the search hands over has to arrive as what it chose."""

    def build_winner(self, **overrides: object) -> BestTrial:
        defaults: dict[str, object] = {
            "task_id": "trial-1",
            "objective_metric": "f1",
            "objective": 0.78,
            "estimator": EstimatorConfig(
                forest=RandomForestConfig(n_estimators=450, max_depth=16, min_samples_leaf=11),
                class_weight=ClassWeight.BALANCED,
                decision_threshold=0.42,
            ),
        }
        defaults.update(overrides)
        return BestTrial(**defaults)  # type: ignore[arg-type]

    def test_the_settings_survive_the_trip_through_the_command_line(self) -> None:
        request = build_request()
        winner = self.build_winner()

        handed = parse_pipeline_arguments(handoff_arguments(request, winner, "search-1"))

        # 比べるのは、その実行が実際に読む設定である。選ばれなかった
        # アルゴリズムの設定は、どちらの側でも結果に影響しない。
        self.assertEqual(
            model_parameters(handed.estimator),
            model_parameters(winner.estimator),
        )

    def test_the_rows_and_the_seed_are_the_ones_the_search_used(self) -> None:
        request = build_request(random_seed=77)
        handed = parse_pipeline_arguments(
            handoff_arguments(request, self.build_winner(), "search-1")
        )

        self.assertEqual(handed.dataset, request.dataset)
        self.assertEqual(handed.split, request.split)
        self.assertEqual(handed.random_seed, 77)

    def test_the_run_says_which_search_and_which_trial_asked_for_it(self) -> None:
        handed = parse_pipeline_arguments(
            handoff_arguments(build_request(), self.build_winner(), "search-1")
        )

        self.assertEqual(handed.origin.search_task_id, "search-1")
        self.assertEqual(handed.origin.trial_task_id, "trial-1")

    def test_a_setting_that_was_not_instructed_is_not_handed_over(self) -> None:
        winner = self.build_winner(
            estimator=EstimatorConfig(forest=RandomForestConfig(max_depth=None)),
        )

        handed = handoff_arguments(build_request(), winner, "search-1")

        self.assertNotIn("--max-depth", handed)
        self.assertNotIn("--decision-threshold", handed)

    def test_every_algorithm_hands_over_its_own_settings(self) -> None:
        for algorithm, estimator in (
            (
                Algorithm.LOGISTIC_REGRESSION,
                EstimatorConfig(
                    algorithm=Algorithm.LOGISTIC_REGRESSION,
                    logistic=LogisticRegressionConfig(regularisation=0.25, max_iterations=800),
                ),
            ),
            (
                Algorithm.HIST_GRADIENT_BOOSTING,
                EstimatorConfig(
                    algorithm=Algorithm.HIST_GRADIENT_BOOSTING,
                    boosting=HistGradientBoostingConfig(learning_rate=0.05, max_iterations=120),
                ),
            ),
        ):
            with self.subTest(algorithm=algorithm):
                winner = self.build_winner(estimator=estimator)

                handed = parse_pipeline_arguments(
                    handoff_arguments(build_request(), winner, "search-1")
                )

                self.assertEqual(
                    model_parameters(handed.estimator),
                    model_parameters(estimator),
                )

    def test_the_run_is_placed_on_the_queues_the_environment_names(self) -> None:
        request = build_request()

        handed = parse_pipeline_arguments(
            handoff_arguments(request, self.build_winner(), "search-1")
        )

        self.assertEqual(handed.queue, request.plan.placement.trial_queue)
        self.assertEqual(handed.pipeline_queue, request.plan.placement.optimizer_queue)


class RecordedPlanTest(unittest.TestCase):
    """A search says what it is allowed to do, before it does any of it."""

    class FakeTask:
        def __init__(self) -> None:
            self.id = "search-1"
            self.sections: dict[str, dict[str, object]] = {}
            self.artifacts_uploaded: dict[str, object] = {}

        def connect(self, values: dict[str, object], name: str) -> dict[str, object]:
            self.sections[name] = dict(values)
            return values

        def upload_artifact(self, name: str, artifact_object: object, **_: object) -> None:
            self.artifacts_uploaded[name] = artifact_object

    def setUp(self) -> None:
        self.task = self.FakeTask()
        record_plan(self.task, build_request())  # type: ignore[arg-type]

    def test_the_objective_is_readable_from_the_task(self) -> None:
        self.assertEqual(self.task.sections[OBJECTIVE_SECTION]["metric"], "f1")
        self.assertEqual(self.task.sections[OBJECTIVE_SECTION]["split"], "train")

    def test_the_budget_is_readable_from_the_task(self) -> None:
        self.assertIn("max_trials", self.task.sections[BUDGET_SECTION])
        self.assertIn("total_minutes", self.task.sections[BUDGET_SECTION])

    def test_the_search_space_is_readable_from_the_task(self) -> None:
        space = self.task.sections[SPACE_SECTION]

        self.assertIn("n_estimators", space)
        self.assertIn("class_weight", space)

    def test_the_whole_plan_is_kept_as_one_document(self) -> None:
        document = self.task.artifacts_uploaded[SEARCH_PLAN_ARTIFACT]
        assert isinstance(document, dict)

        self.assertEqual(document["environment"], "dev")
        self.assertIn("search_space", document)

    def test_how_a_candidate_is_judged_is_readable_from_the_task(self) -> None:
        self.assertEqual(self.task.sections[TRIAL_SECTION]["folds"], 5)
        self.assertTrue(self.task.sections[TRIAL_SECTION]["tune_threshold"])

    def test_where_it_runs_is_readable_from_the_task(self) -> None:
        self.assertEqual(self.task.sections[PLACEMENT_SECTION]["trial_queue"], "trials")

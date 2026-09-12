from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from ml.semiconductor_quality import cli
from ml.semiconductor_quality.cli import (
    EXIT_FAILURE,
    EXIT_INTERRUPTED,
    EXIT_INVALID_USAGE,
    EXIT_SUCCESS,
    QueuedTraining,
    build_command,
    carry_out,
    enqueue_training,
    main,
    parse_arguments,
    run_training,
)
from ml.semiconductor_quality.config import (
    DEFAULT_DATASET_ALIAS,
    DEFAULT_DATASET_CSV_PATH,
    DEFAULT_DATASET_NAME,
    DEFAULT_DATASET_PROJECT,
    DEFAULT_RANDOM_SEED,
    DEFAULT_TASK_NAME,
    DEFAULT_TASK_PROJECT,
    DEFAULT_TRAINING_QUEUE,
    Algorithm,
    ClassWeight,
    ConfigurationError,
    EstimatorConfig,
    ExecutionPlan,
    HistGradientBoostingConfig,
    LogisticRegressionConfig,
    RandomForestConfig,
    SplitConfig,
)
from ml.semiconductor_quality.dataset import DatasetValidationError
from ml.semiconductor_quality.domain import (
    CATEGORICAL_FEATURE_COLUMNS,
    FEATURE_COLUMNS,
    NUMERIC_FEATURE_COLUMNS,
    TEST_SPLIT,
    VALIDATION_SPLIT,
    DatasetSource,
    DatasetValidationReport,
    DataSplit,
    EvaluationResult,
    FetchedDataset,
    ModelCost,
    SplitPart,
    TrainingEvaluation,
    TrainingInput,
)
from ml.semiconductor_quality.preprocess import PreprocessingError
from ml.semiconductor_quality.train import TrainedModel


ARGUMENTS = ["--dataset-version", "1.0.0"]


def build_report() -> DatasetValidationReport:
    return DatasetValidationReport(
        source=DatasetSource(
            dataset_id="dataset-id",
            dataset_project=DEFAULT_DATASET_PROJECT,
            dataset_name=DEFAULT_DATASET_NAME,
            dataset_version="1.0.0",
            csv_path=Path("/cache/datasets/dataset-id/semiconductor_quality.csv"),
        ),
        row_count=1_200,
        feature_names=FEATURE_COLUMNS,
        numeric_feature_names=NUMERIC_FEATURE_COLUMNS,
        categorical_feature_names=CATEGORICAL_FEATURE_COLUMNS,
        label_counts={"pass": 700, "fail": 500},
    )


def build_part(name: str, pass_rows: int, fail_rows: int) -> SplitPart:
    targets = np.array(["pass"] * pass_rows + ["fail"] * fail_rows)
    return SplitPart(
        name=name,
        features=np.zeros((targets.size, len(FEATURE_COLUMNS)), dtype=object),
        targets=targets,
        label_counts={"pass": pass_rows, "fail": fail_rows},
    )


def build_trained_model(report: DatasetValidationReport) -> TrainedModel:
    validation = build_part(VALIDATION_SPLIT, 140, 100)
    return TrainedModel(
        report=report,
        split=DataSplit(
            train=build_part("train", 420, 300),
            validation=validation,
            test=build_part(TEST_SPLIT, 140, 100),
        ),
        pipeline=mock.sentinel.pipeline,
        validation_predictions=validation.targets,
    )


def build_evaluation() -> TrainingEvaluation:
    return TrainingEvaluation(
        validation=build_result(VALIDATION_SPLIT, 0.8125),
        test=build_result(TEST_SPLIT, 0.7917),
    )


def build_result(split_name: str, accuracy: float) -> EvaluationResult:
    return EvaluationResult(
        split_name=split_name,
        metrics={"accuracy": accuracy, "precision": 0.75, "recall": 0.7, "f1": 0.724},
        confusion_matrix=np.array([[120, 20], [25, 75]]),
    )


def parse_failure(argv: list[str]) -> str:
    """Parse an invalid invocation and return what the parser wrote to stderr."""
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        with unittest.TestCase().assertRaises(SystemExit) as raised:
            parse_arguments(argv)
    assert raised.exception.code == 2
    return stderr.getvalue()


class DatasetArgumentTest(unittest.TestCase):
    def test_the_dataset_version_is_required(self) -> None:
        message = parse_failure([])

        self.assertIn("--dataset-version", message)

    def test_the_dataset_defaults_match_the_registered_seed_dataset(self) -> None:
        dataset = parse_arguments(["--dataset-version", "1.0.0"]).config.dataset

        self.assertEqual(dataset.dataset_version, "1.0.0")
        self.assertEqual(dataset.dataset_project, DEFAULT_DATASET_PROJECT)
        self.assertEqual(dataset.dataset_name, DEFAULT_DATASET_NAME)
        self.assertEqual(dataset.dataset_csv_path, DEFAULT_DATASET_CSV_PATH)
        self.assertEqual(dataset.dataset_alias, DEFAULT_DATASET_ALIAS)

    def test_the_dataset_can_be_selected_explicitly(self) -> None:
        dataset = parse_arguments(
            [
                "--dataset-version",
                "2.0.0",
                "--dataset-project",
                "Other Project",
                "--dataset-name",
                "other-data",
                "--dataset-csv-path",
                "v2/quality.csv",
            ]
        ).config.dataset

        self.assertEqual(dataset.dataset_version, "2.0.0")
        self.assertEqual(dataset.dataset_project, "Other Project")
        self.assertEqual(dataset.dataset_name, "other-data")
        self.assertEqual(dataset.dataset_csv_path, "v2/quality.csv")

    def test_a_csv_path_outside_the_dataset_root_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError) as raised:
            parse_arguments(["--dataset-version", "1.0.0", "--dataset-csv-path", "../quality.csv"])

        self.assertIn("dataset_csv_path", str(raised.exception))


class TaskArgumentTest(unittest.TestCase):
    def test_the_task_defaults_are_separated_from_the_dataset_project(self) -> None:
        task = parse_arguments(["--dataset-version", "1.0.0"]).config.task

        self.assertEqual(task.task_project, DEFAULT_TASK_PROJECT)
        self.assertEqual(task.task_name, DEFAULT_TASK_NAME)

    def test_the_task_can_be_named_per_run(self) -> None:
        task = parse_arguments(
            [
                "--dataset-version",
                "1.0.0",
                "--task-project",
                "Semiconductor Quality Prediction/Experiments",
                "--task-name",
                "deeper-forest",
            ]
        ).config.task

        self.assertEqual(task.task_project, "Semiconductor Quality Prediction/Experiments")
        self.assertEqual(task.task_name, "deeper-forest")


class TrainingParameterArgumentTest(unittest.TestCase):
    def test_the_defaults_come_from_the_execution_contract(self) -> None:
        config = parse_arguments(["--dataset-version", "1.0.0"]).config

        self.assertEqual(config.split, SplitConfig())
        self.assertEqual(config.estimator, EstimatorConfig())
        self.assertEqual(config.random_seed, DEFAULT_RANDOM_SEED)

    def test_the_forest_can_be_varied_to_create_another_task(self) -> None:
        config = parse_arguments(
            [
                "--dataset-version",
                "1.0.0",
                "--n-estimators",
                "150",
                "--max-depth",
                "8",
                "--min-samples-leaf",
                "2",
                "--random-seed",
                "7",
            ]
        ).config

        self.assertEqual(
            config.estimator.forest,
            RandomForestConfig(n_estimators=150, max_depth=8, min_samples_leaf=2),
        )
        self.assertEqual(config.random_seed, 7)

    def test_the_depth_is_unlimited_unless_it_is_given(self) -> None:
        config = parse_arguments(["--dataset-version", "1.0.0"]).config

        self.assertIsNone(config.estimator.forest.max_depth)


class AlgorithmArgumentTest(unittest.TestCase):
    """One invocation names the algorithm; everything else stays the same."""

    def test_the_project_keeps_the_model_it_started_with_by_default(self) -> None:
        config = parse_arguments(ARGUMENTS).config

        self.assertEqual(config.estimator.algorithm, Algorithm.RANDOM_FOREST)

    def test_another_algorithm_can_be_chosen(self) -> None:
        config = parse_arguments([*ARGUMENTS, "--algorithm", "logistic-regression"]).config

        self.assertEqual(config.estimator.algorithm, Algorithm.LOGISTIC_REGRESSION)

    def test_an_algorithm_this_project_does_not_offer_is_rejected(self) -> None:
        message = parse_failure([*ARGUMENTS, "--algorithm", "deep-learning"])

        self.assertIn("deep-learning", message)

    def test_the_baseline_reads_its_own_settings(self) -> None:
        config = parse_arguments(
            [*ARGUMENTS, "--algorithm", "logistic-regression", "--regularisation", "0.25"]
        ).config

        self.assertEqual(config.estimator.logistic.regularisation, 0.25)

    def test_the_boosting_model_reads_its_own_settings(self) -> None:
        config = parse_arguments(
            [*ARGUMENTS, "--algorithm", "hist-gradient-boosting", "--learning-rate", "0.05"]
        ).config

        self.assertEqual(config.estimator.boosting.learning_rate, 0.05)

    def test_a_shared_setting_that_was_not_given_leaves_each_algorithm_on_its_own(self) -> None:
        config = parse_arguments(ARGUMENTS).config

        self.assertEqual(
            config.estimator.forest.min_samples_leaf,
            RandomForestConfig().min_samples_leaf,
        )
        self.assertEqual(
            config.estimator.boosting.min_samples_leaf,
            HistGradientBoostingConfig().min_samples_leaf,
        )

    def test_a_shared_setting_that_was_given_reaches_every_algorithm(self) -> None:
        config = parse_arguments([*ARGUMENTS, "--min-samples-leaf", "7"]).config

        self.assertEqual(config.estimator.forest.min_samples_leaf, 7)
        self.assertEqual(config.estimator.boosting.min_samples_leaf, 7)

    def test_an_iteration_budget_that_was_not_given_leaves_each_algorithm_on_its_own(self) -> None:
        config = parse_arguments(ARGUMENTS).config

        self.assertEqual(
            config.estimator.logistic.max_iterations,
            LogisticRegressionConfig().max_iterations,
        )
        self.assertEqual(
            config.estimator.boosting.max_iterations,
            HistGradientBoostingConfig().max_iterations,
        )

    def test_a_setting_that_the_chosen_algorithm_ignores_is_not_a_usage_error(self) -> None:
        config = parse_arguments(
            [*ARGUMENTS, "--algorithm", "logistic-regression", "--n-estimators", "150"]
        ).config

        self.assertEqual(config.estimator.algorithm, Algorithm.LOGISTIC_REGRESSION)
        self.assertEqual(config.estimator.forest.n_estimators, 150)

    def test_the_split_can_be_changed_as_a_whole(self) -> None:
        config = parse_arguments(
            [
                "--dataset-version",
                "1.0.0",
                "--train-ratio",
                "0.5",
                "--validation-ratio",
                "0.25",
                "--test-ratio",
                "0.25",
            ]
        ).config

        self.assertEqual(config.split, SplitConfig(0.5, 0.25, 0.25))

    def test_a_split_that_does_not_sum_to_one_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError) as raised:
            parse_arguments(["--dataset-version", "1.0.0", "--train-ratio", "0.8"])

        self.assertIn("must sum to 1.0", str(raised.exception))

    def test_a_non_numeric_ratio_is_rejected_by_the_parser(self) -> None:
        message = parse_failure(["--dataset-version", "1.0.0", "--train-ratio", "half"])

        self.assertIn("--train-ratio", message)


class SharedModelArgumentTest(unittest.TestCase):
    """The two settings that mean the same thing whichever algorithm is fitted."""

    def test_a_run_leaves_the_rare_label_alone_unless_it_is_asked_to_weigh_it(self) -> None:
        config = parse_arguments(ARGUMENTS).config

        self.assertEqual(config.estimator.class_weight, ClassWeight.NONE)

    def test_the_rare_label_can_be_weighed_by_how_rare_it_is(self) -> None:
        config = parse_arguments([*ARGUMENTS, "--class-weight", "balanced"]).config

        self.assertEqual(config.estimator.class_weight, ClassWeight.BALANCED)

    def test_an_imbalance_policy_this_project_does_not_have_is_rejected(self) -> None:
        message = parse_failure([*ARGUMENTS, "--class-weight", "undersample"])

        self.assertIn("undersample", message)

    def test_a_run_cuts_where_the_algorithm_does_unless_it_is_told_otherwise(self) -> None:
        config = parse_arguments(ARGUMENTS).config

        self.assertIsNone(config.estimator.decision_threshold)

    def test_the_cut_a_search_chose_can_be_handed_to_a_run(self) -> None:
        config = parse_arguments([*ARGUMENTS, "--decision-threshold", "0.35"]).config

        self.assertEqual(config.estimator.decision_threshold, 0.35)

    def test_a_cut_that_is_not_a_probability_is_refused_before_a_task_is_created(self) -> None:
        with self.assertRaises(ConfigurationError):
            parse_arguments([*ARGUMENTS, "--decision-threshold", "1.4"])

    def test_the_policy_is_read_whichever_algorithm_is_fitted(self) -> None:
        for algorithm in Algorithm:
            with self.subTest(algorithm=algorithm):
                config = parse_arguments(
                    [*ARGUMENTS, "--algorithm", algorithm.value, "--class-weight", "balanced"]
                ).config

                self.assertEqual(config.estimator.class_weight, ClassWeight.BALANCED)


class CommandLineTrackingTest(unittest.TestCase):
    def test_the_arguments_are_kept_for_the_task_record(self) -> None:
        argv = ["--dataset-version", "1.0.0", "--n-estimators", "150"]

        command = parse_arguments(argv)

        self.assertEqual(command.command_line, tuple(argv))

    def test_an_unknown_argument_is_rejected(self) -> None:
        message = parse_failure(["--dataset-version", "1.0.0", "--epochs", "10"])

        self.assertIn("--epochs", message)


class TrainingRunTestCase(unittest.TestCase):
    """Replaces the ClearML boundary and the input reader of the composition root."""

    def setUp(self) -> None:
        self.report = build_report()
        self.training_input = TrainingInput(
            report=self.report,
            features=mock.sentinel.features,
            targets=mock.sentinel.targets,
        )
        self.task = mock.MagicMock(name="training_task")
        self.boundary = mock.MagicMock(name="training_task_boundary")
        self.boundary.return_value.__enter__.return_value = self.task
        self.boundary.return_value.__exit__.return_value = False
        self.fetch_dataset = mock.MagicMock(
            name="fetch_dataset",
            return_value=FetchedDataset(
                dataset_id="dataset-id",
                dataset_project=DEFAULT_DATASET_PROJECT,
                dataset_name=DEFAULT_DATASET_NAME,
                dataset_version="1.0.0",
                local_root=Path("/cache/datasets/dataset-id"),
            ),
        )
        self.load_training_input = mock.MagicMock(
            name="load_training_input",
            return_value=self.training_input,
        )
        self.model = build_trained_model(self.report)
        self.train_classifier = mock.MagicMock(
            name="train_classifier",
            return_value=self.model,
        )
        self.evaluation = build_evaluation()
        self.evaluate_model = mock.MagicMock(
            name="evaluate_model",
            return_value=self.evaluation,
        )
        self.weights = Path("/tmp/run/semiconductor_quality_pipeline.joblib")
        self.cost = ModelCost(
            training_seconds=1.5,
            inference_seconds=0.01,
            inference_rows=240,
            model_bytes=204_800,
        )
        self.measure_cost = mock.MagicMock(name="measure_cost", return_value=self.cost)
        self.saved_pipeline = mock.MagicMock(name="saved_pipeline")
        self.saved_pipeline.return_value.__enter__.return_value = self.weights
        self.saved_pipeline.return_value.__exit__.return_value = False

        # The order the boundary is left in matters as much as what is recorded,
        # so every step of the composition reports when it ran.
        self.events: list[str] = []
        self.task.register_model.side_effect = lambda *_: self.events.append("register-model")
        self.boundary.return_value.__exit__.side_effect = self._record_leaving_boundary

        # 既定ではAgentではなく人がこのプロセスを起動した、という前提で走らせる。
        self.running_under_agent = mock.MagicMock(
            name="running_under_agent",
            return_value=False,
        )
        self.queued_command_line = mock.MagicMock(
            name="queued_command_line",
            return_value=tuple(ARGUMENTS),
        )
        self.started_task = mock.MagicMock(name="started_task")
        self.started_task.id = "queued-task-id"
        self.start_training_task = mock.MagicMock(
            name="start_training_task",
            return_value=self.started_task,
        )

        for name, replacement in (
            ("training_task", self.boundary),
            ("fetch_dataset", self.fetch_dataset),
            ("load_training_input", self.load_training_input),
            ("train_classifier", self.train_classifier),
            ("evaluate_model", self.evaluate_model),
            ("saved_pipeline", self.saved_pipeline),
            ("measure_cost", self.measure_cost),
            ("running_under_agent", self.running_under_agent),
            ("queued_command_line", self.queued_command_line),
            ("start_training_task", self.start_training_task),
        ):
            patcher = mock.patch.object(cli, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _record_leaving_boundary(self, *_arguments: object) -> bool:
        """Note that the Task boundary was left, and let the exception through."""
        self.events.append("leave-boundary")
        return False


class RunTrainingTest(TrainingRunTestCase):
    def test_the_dataset_is_read_inside_the_task_boundary(self) -> None:
        run_training(parse_arguments(ARGUMENTS))

        self.boundary.assert_called_once()
        self.fetch_dataset.assert_called_once()
        self.assertEqual(
            self.fetch_dataset.call_args.args[0],
            parse_arguments(ARGUMENTS).config.dataset,
        )

    def test_the_invocation_is_recorded_with_the_task(self) -> None:
        run_training(parse_arguments(ARGUMENTS))

        self.assertEqual(self.boundary.call_args.kwargs["command_line"], tuple(ARGUMENTS))

    def test_the_configured_csv_of_the_fetched_dataset_is_read(self) -> None:
        run_training(parse_arguments([*ARGUMENTS, "--dataset-csv-path", "v1/quality.csv"]))

        self.assertEqual(
            self.load_training_input.call_args.args,
            (self.fetch_dataset.return_value, "v1/quality.csv"),
        )

    def test_the_resolved_dataset_is_recorded_on_the_task(self) -> None:
        run_training(parse_arguments(ARGUMENTS))

        self.task.record_dataset_source.assert_called_once_with(self.report.source)

    def test_the_model_is_fitted_from_the_validated_input(self) -> None:
        outcome = run_training(parse_arguments(ARGUMENTS))

        self.train_classifier.assert_called_once_with(
            self.training_input,
            parse_arguments(ARGUMENTS).config,
        )
        self.assertIs(outcome.model, self.model)

    def test_the_run_reports_the_task_it_was_recorded_on(self) -> None:
        outcome = run_training(parse_arguments(ARGUMENTS))

        self.assertEqual(outcome.task_id, self.task.id)

    def test_the_input_and_its_split_are_recorded_on_the_task(self) -> None:
        run_training(parse_arguments(ARGUMENTS))

        self.task.record_input.assert_called_once_with(self.model.report, self.model.split)

    def test_the_fitted_model_is_scored_once_and_recorded(self) -> None:
        outcome = run_training(parse_arguments(ARGUMENTS))

        self.evaluate_model.assert_called_once_with(self.model)
        self.task.record_evaluation.assert_called_once_with(self.evaluation)
        self.assertIs(outcome.evaluation, self.evaluation)

    def test_the_registered_model_is_the_pipeline_that_was_saved(self) -> None:
        run_training(parse_arguments(ARGUMENTS))

        self.saved_pipeline.assert_called_once_with(self.model.pipeline)
        self.task.register_model.assert_called_once_with(self.weights)

    def test_the_model_is_registered_before_the_task_is_left(self) -> None:
        run_training(parse_arguments(ARGUMENTS))

        self.assertEqual(self.events, ["register-model", "leave-boundary"])


class ExitCodeTest(TrainingRunTestCase):
    def test_a_completed_run_reports_success(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = main(ARGUMENTS)

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("dataset-id", stdout.getvalue())
        self.assertIn("1200 rows", stdout.getvalue())
        self.assertIn("train=720", stdout.getvalue())
        self.assertIn("test=240", stdout.getvalue())

    def test_a_completed_run_reports_both_scored_splits(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            main(ARGUMENTS)

        printed = stdout.getvalue()
        self.assertIn("validation: accuracy=0.8125", printed)
        self.assertIn("test: accuracy=0.7917", printed)
        self.assertIn("f1=0.7240", printed)

    def test_a_completed_run_names_the_task_it_can_be_reviewed_on(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            main(ARGUMENTS)

        self.assertIn(f"ClearML Task {self.task.id}", stdout.getvalue())

    def test_an_evaluation_that_fails_is_reported_as_a_failure(self) -> None:
        self.evaluate_model.side_effect = ValueError("240 predictions were made for it")

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = main(ARGUMENTS)

        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("240 predictions", stderr.getvalue())
        self.task.register_model.assert_not_called()

    def test_an_unsatisfiable_contract_is_reported_as_a_usage_error(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = main([*ARGUMENTS, "--train-ratio", "0.8"])

        self.assertEqual(code, EXIT_INVALID_USAGE)
        self.assertIn("must sum to 1.0", stderr.getvalue())
        self.boundary.assert_not_called()

    def test_an_invalid_dataset_is_reported_as_a_failure(self) -> None:
        self.load_training_input.side_effect = DatasetValidationError("result column is missing")

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = main(ARGUMENTS)

        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("result column is missing", stderr.getvalue())

    def test_an_unresolved_dataset_version_is_reported_as_a_failure(self) -> None:
        self.fetch_dataset.side_effect = ValueError("Could not find dataset version 9.9.9")

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = main(ARGUMENTS)

        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("9.9.9", stderr.getvalue())

    def test_an_input_that_cannot_be_split_is_reported_as_a_failure(self) -> None:
        self.train_classifier.side_effect = PreprocessingError("label 'fail' holds 2 rows")

        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = main(ARGUMENTS)

        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("label 'fail' holds 2 rows", stderr.getvalue())

    def test_an_interrupted_run_is_not_reported_as_a_failure(self) -> None:
        self.fetch_dataset.side_effect = KeyboardInterrupt

        with contextlib.redirect_stderr(io.StringIO()):
            code = main(ARGUMENTS)

        self.assertEqual(code, EXIT_INTERRUPTED)

    def test_a_malformed_invocation_is_rejected_by_the_parser(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main([])

        self.assertEqual(raised.exception.code, EXIT_INVALID_USAGE)
        self.boundary.assert_not_called()


class PackageManagerInvocationTest(TrainingRunTestCase):
    """`corepack pnpm ml:train -- --dataset-version 1.0.0` reaches the parser intact."""

    def test_a_forwarded_separator_still_starts_the_run(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["--", *ARGUMENTS])

        self.assertEqual(code, EXIT_SUCCESS)
        self.boundary.assert_called_once()

    def test_the_forwarded_separator_is_not_recorded_on_the_task(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            main(["--", *ARGUMENTS])

        self.assertEqual(self.boundary.call_args.kwargs["command_line"], tuple(ARGUMENTS))


class ExecutionPlanArgumentTest(unittest.TestCase):
    def test_a_run_without_a_queue_stays_in_this_process(self) -> None:
        command = parse_arguments(ARGUMENTS)

        self.assertTrue(command.plan.runs_locally)

    def test_the_queue_alone_names_the_one_the_agent_subscribes_to(self) -> None:
        command = parse_arguments([*ARGUMENTS, "--queue"])

        self.assertEqual(command.plan.queue, DEFAULT_TRAINING_QUEUE)

    def test_another_queue_can_be_named(self) -> None:
        command = parse_arguments([*ARGUMENTS, "--queue", "gpu-training"])

        self.assertEqual(command.plan.queue, "gpu-training")

    def test_a_blank_queue_name_is_rejected_before_a_task_is_created(self) -> None:
        with self.assertRaises(ConfigurationError) as raised:
            parse_arguments([*ARGUMENTS, "--queue", "  "])

        self.assertIn("queue", str(raised.exception))

    def test_the_queue_is_part_of_the_recorded_invocation(self) -> None:
        argv = [*ARGUMENTS, "--queue", "gpu-training"]

        command = parse_arguments(argv)

        self.assertEqual(command.command_line, tuple(argv))


class EnqueueTrainingTest(TrainingRunTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.command = parse_arguments([*ARGUMENTS, "--queue", "gpu-training"])

    def test_nothing_is_trained_by_the_process_that_queues_the_run(self) -> None:
        enqueue_training(self.command)

        self.boundary.assert_not_called()
        self.train_classifier.assert_not_called()

    def test_the_task_carries_the_contract_and_the_queue_it_was_meant_for(self) -> None:
        enqueue_training(self.command)

        arguments = self.start_training_task.call_args
        self.assertEqual(arguments.args[0], self.command.config)
        self.assertEqual(arguments.kwargs["command_line"], self.command.command_line)
        self.assertEqual(arguments.kwargs["plan"], ExecutionPlan(queue="gpu-training"))

    def test_the_task_is_handed_to_the_queue_that_was_named(self) -> None:
        enqueue_training(self.command)

        self.started_task.hand_over.assert_called_once_with("gpu-training")

    def test_the_queued_task_is_reported_so_it_can_be_followed(self) -> None:
        queued = enqueue_training(self.command)

        self.assertEqual(queued, QueuedTraining(task_id="queued-task-id", queue="gpu-training"))

    def test_a_task_that_cannot_be_queued_is_left_behind_as_failed(self) -> None:
        failure = RuntimeError("the queue does not exist")
        self.started_task.hand_over.side_effect = failure

        with self.assertRaises(RuntimeError):
            enqueue_training(self.command)

        self.started_task.fail.assert_called_once_with(failure)

    def test_a_run_without_a_queue_is_carried_out_here(self) -> None:
        outcome = carry_out(parse_arguments(ARGUMENTS))

        self.assertNotIsInstance(outcome, QueuedTraining)
        self.boundary.assert_called_once()

    def test_a_run_with_a_queue_is_handed_over_instead(self) -> None:
        outcome = carry_out(self.command)

        self.assertIsInstance(outcome, QueuedTraining)
        self.boundary.assert_not_called()

    def test_the_queued_task_is_named_in_the_output(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = main([*ARGUMENTS, "--queue", "gpu-training"])

        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("queued-task-id", stdout.getvalue())
        self.assertIn("gpu-training", stdout.getvalue())


class AgentBootstrapTest(TrainingRunTestCase):
    """An Agent re-runs the entry point without the arguments the run was asked for."""

    def setUp(self) -> None:
        super().setUp()
        self.running_under_agent.return_value = True

    def test_the_invocation_is_read_back_from_the_task(self) -> None:
        self.queued_command_line.return_value = ("--dataset-version", "2.0.0")

        command = build_command([])

        self.queued_command_line.assert_called_once_with()
        self.assertEqual(command.config.dataset.dataset_version, "2.0.0")

    def test_a_queued_run_is_not_queued_a_second_time(self) -> None:
        self.queued_command_line.return_value = (*ARGUMENTS, "--queue", "gpu-training")

        command = build_command([])

        self.assertTrue(command.plan.runs_locally)

    def test_how_the_run_was_asked_for_is_still_the_recorded_invocation(self) -> None:
        queued = (*ARGUMENTS, "--queue", "gpu-training")
        self.queued_command_line.return_value = queued

        command = build_command([])

        self.assertEqual(command.command_line, queued)

    def test_the_agent_trains_instead_of_queueing(self) -> None:
        self.queued_command_line.return_value = (*ARGUMENTS, "--queue", "gpu-training")

        with contextlib.redirect_stdout(io.StringIO()):
            code = main([])

        self.assertEqual(code, EXIT_SUCCESS)
        self.boundary.assert_called_once()
        self.start_training_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()

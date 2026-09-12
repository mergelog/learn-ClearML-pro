"""Command line contract of the data quality checks.

Three questions can be asked, and they are deliberately separate.

``profile`` measures a Dataset version and prints what is in it. It judges
nothing. It is what somebody runs when they want to know what they have.

``check`` judges a Dataset version against the expectations and answers with an
exit code. It is what runs before training, and what a pipeline step calls.

``drift`` compares two Dataset versions and says what moved between them. It
answers "is the new data still the same kind of data", which no single version
can answer on its own.

Each command works on registered ClearML Dataset versions, because that is
what training uses. Reading a local file instead is possible with ``--csv``,
which is how a Dataset is judged before it is registered at all.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ml.semiconductor_quality.clearml_tracking import connected_settings, fetch_dataset
from ml.semiconductor_quality.config import (
    DEFAULT_DATASET_CSV_PATH,
    DEFAULT_DATASET_NAME,
    DEFAULT_DATASET_PROJECT,
    DatasetConfig,
)
from ml.semiconductor_quality.dataset import resolve_csv_path

from .checks import check as apply_checks
from .contract import load_contract
from .domain import DataQualityError, DatasetProfile
from .drift import DriftThresholds, compare
from .profile import profile_csv


EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_INVALID_USAGE = 2

ARGUMENT_SEPARATOR = "--"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure a registered Dataset version, judge it against the data "
            "quality contract, or compare two versions."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    profile = commands.add_parser("profile", help="Measure one Dataset version.")
    _add_dataset_arguments(profile)

    checked = commands.add_parser(
        "check",
        help="Judge one Dataset version against the data quality contract.",
    )
    _add_dataset_arguments(checked)

    drifted = commands.add_parser("drift", help="Compare two Dataset versions.")
    _add_dataset_arguments(drifted)
    drifted.add_argument(
        "--against",
        default=None,
        help="The earlier Dataset version to compare against.",
    )
    drifted.add_argument(
        "--against-csv",
        default=None,
        help="The earlier local CSV to compare against, when --csv is used.",
    )
    drifted.add_argument("--numeric-threshold", type=float, default=DriftThresholds().numeric)
    drifted.add_argument(
        "--categorical-threshold",
        type=float,
        default=DriftThresholds().categorical,
    )
    drifted.add_argument("--label-threshold", type=float, default=DriftThresholds().labels)
    return parser


def _add_dataset_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dataset-version",
        help="Version of the registered ClearML Dataset. Never inferred.",
    )
    parser.add_argument("--dataset-project", default=DEFAULT_DATASET_PROJECT)
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    parser.add_argument("--dataset-csv-path", default=DEFAULT_DATASET_CSV_PATH)
    parser.add_argument(
        "--csv",
        default=None,
        help=(
            "Read a local CSV instead of a registered Dataset. Use this to judge "
            "data before it is registered."
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Carry out one data quality command and report its outcome as an exit code."""
    arguments = build_parser().parse_args(
        _forwarded_arguments(sys.argv[1:] if argv is None else argv)
    )

    try:
        return _carry_out(arguments)
    except DataQualityError as error:
        print(error, file=sys.stderr)
        return EXIT_INVALID_USAGE
    # 理由は報告する。握り潰さないための広い捕捉である。
    except Exception as error:
        print(f"The command failed: {error}", file=sys.stderr)
        return EXIT_FAILURE


def _carry_out(arguments: argparse.Namespace) -> int:
    if arguments.command == "profile":
        profile = _profile_of(arguments, arguments.dataset_version)
        print(json.dumps(profile.as_document(), indent=2))
        return EXIT_SUCCESS

    if arguments.command == "check":
        profile = _profile_of(arguments, arguments.dataset_version)
        quality = apply_checks(load_contract(), profile)
        print(quality.describe())
        return EXIT_SUCCESS if quality.passed else EXIT_FAILURE

    reference, reference_name = _reference_profile(arguments)
    current = _profile_of(arguments, arguments.dataset_version)
    drift = compare(
        reference,
        current,
        reference_name=reference_name,
        current_name=arguments.dataset_version or str(arguments.csv),
        thresholds=DriftThresholds(
            numeric=arguments.numeric_threshold,
            categorical=arguments.categorical_threshold,
            labels=arguments.label_threshold,
        ),
    )
    print(drift.describe())
    return EXIT_FAILURE if drift.has_drifted else EXIT_SUCCESS


def _reference_profile(arguments: argparse.Namespace) -> tuple[DatasetProfile, str]:
    """Measure the version being compared against, and name it for the report.

    The two sides are read the same way, so comparing a registered version with
    a local file is refused rather than silently comparing a file with itself.
    """
    if arguments.csv is not None:
        if arguments.against_csv is None:
            raise DataQualityError(
                "--csv compares two local files, so --against-csv is required. "
                "To compare registered versions, drop --csv and use --against"
            )
        return profile_csv(Path(arguments.against_csv)), str(arguments.against_csv)

    if arguments.against_csv is not None:
        raise DataQualityError("--against-csv only makes sense together with --csv")

    if not arguments.against:
        raise DataQualityError("--against is required, so there is something to compare with")

    return _profile_of(arguments, arguments.against), str(arguments.against)


def _profile_of(arguments: argparse.Namespace, version: str | None) -> DatasetProfile:
    """Measure whichever Dataset the invocation named."""
    if arguments.csv is not None:
        return profile_csv(Path(arguments.csv))

    if not version:
        raise DataQualityError("either --dataset-version or --csv is required")

    connected_settings()
    fetched = fetch_dataset(
        DatasetConfig(
            dataset_version=version,
            dataset_project=arguments.dataset_project,
            dataset_name=arguments.dataset_name,
            dataset_csv_path=arguments.dataset_csv_path,
        ).validate()
    )
    return profile_csv(resolve_csv_path(fetched.local_root, arguments.dataset_csv_path))


def _forwarded_arguments(argv: Sequence[str]) -> list[str]:
    """Drop the separator a package manager puts in front of the arguments."""
    arguments = list(argv)
    if arguments and arguments[0] == ARGUMENT_SEPARATOR:
        del arguments[0]
    return arguments


if __name__ == "__main__":
    raise SystemExit(main())

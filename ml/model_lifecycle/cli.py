"""Command line contract of the model lifecycle.

Promotion is a decision, not a computation. The command therefore asks for the
two things a decision has that a computation does not: who is making it and
why. Both are refused when empty, because a stage nobody signed cannot be
reviewed afterwards.

Four things can be asked for.

``status`` shows which model holds each stage. It is what a runbook starts
with, and what a rollback is decided from.

``promote`` moves one model one step. Only declared moves are carried out.

``rollback`` puts the model that production replaced back into production. It
takes the same approval as any other promotion, because reverting is also a
decision.

``show`` prints everything recorded about one model, which is where an audit of
"how did this reach production" begins.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from ml.semiconductor_quality.clearml_tracking import connected_settings

from .domain import (
    METADATA_DATASET_ID,
    METADATA_DATASET_VERSION,
    METADATA_MODEL_VERSION,
    METADATA_TRAIN_TASK_ID,
    LifecycleError,
    ModelStage,
    PromotionRequest,
)
from .registry import ModelRegistry, RegisteredModel, describe_record


EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_INVALID_USAGE = 2

ARGUMENT_SEPARATOR = "--"

# `status` が並べる順。段階の意味の順序であって、列挙の宣言順に依存しない。
REPORTED_STAGES = (
    ModelStage.PRODUCTION,
    ModelStage.STAGING,
    ModelStage.CANDIDATE,
    ModelStage.ARCHIVED,
)

PROMOTABLE_STAGES = (ModelStage.STAGING, ModelStage.PRODUCTION, ModelStage.ARCHIVED)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect and move the registered semiconductor quality models "
            "through candidate, staging and production."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("status", help="Show which model holds each stage.")

    show = commands.add_parser("show", help="Show everything recorded about one model.")
    show.add_argument("--model-id", required=True)

    promote = commands.add_parser("promote", help="Move one model to another stage.")
    promote.add_argument("--model-id", required=True)
    promote.add_argument(
        "--to",
        required=True,
        choices=[stage.value for stage in PROMOTABLE_STAGES],
        dest="target",
    )
    promote.add_argument(
        "--approved-by",
        required=True,
        help="Who is making this decision. Recorded on the model.",
    )
    promote.add_argument(
        "--reason",
        required=True,
        help="Why the model may move. Recorded on the model.",
    )

    rollback = commands.add_parser(
        "rollback",
        help="Put the model that production replaced back into production.",
    )
    rollback.add_argument("--approved-by", required=True)
    rollback.add_argument("--reason", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Carry out one lifecycle command and report its outcome as an exit code."""
    arguments = build_parser().parse_args(
        _forwarded_arguments(sys.argv[1:] if argv is None else argv)
    )

    connected_settings()
    registry = ModelRegistry()

    try:
        print(_carry_out(registry, arguments))
    except LifecycleError as error:
        print(error, file=sys.stderr)
        return EXIT_INVALID_USAGE
    # 理由は報告する。握り潰さないための広い捕捉である。
    except Exception as error:
        print(f"The command failed: {error}", file=sys.stderr)
        return EXIT_FAILURE

    return EXIT_SUCCESS


def _carry_out(registry: ModelRegistry, arguments: argparse.Namespace) -> str:
    if arguments.command == "status":
        return _describe_status(registry)
    if arguments.command == "show":
        return _describe_model(registry.find(arguments.model_id))
    if arguments.command == "promote":
        request = PromotionRequest(
            model_id=arguments.model_id,
            target=ModelStage(arguments.target),
            approved_by=arguments.approved_by,
            reason=arguments.reason,
        )
        return describe_record(registry.promote(request))
    return describe_record(registry.rollback(arguments.approved_by, arguments.reason))


def _describe_status(registry: ModelRegistry) -> str:
    lines: list[str] = []
    for stage in REPORTED_STAGES:
        held = registry.in_stage(stage)
        if not held:
            lines.append(f"{stage}: none")
            continue
        lines.append(f"{stage}:")
        lines.extend(f"  {_summarise(model)}" for model in held)
    return "\n".join(lines)


def _summarise(model: RegisteredModel) -> str:
    identity = model.identity
    return f"{identity.model_version} ({identity.model_id}) from dataset {identity.dataset_version}"


def _describe_model(model: RegisteredModel) -> str:
    identity = model.identity
    lines = [
        f"{identity.name} {identity.model_version}",
        f"  id: {identity.model_id}",
        f"  stage: {identity.stage}",
        f"  dataset: {identity.dataset_version} ({identity.dataset_id})",
        f"  trained by task: {identity.train_task_id}",
        "  recorded:",
    ]
    lines.extend(
        f"    {name}: {value}"
        for name, value in sorted(model.metadata.items())
        if name
        not in (
            METADATA_MODEL_VERSION,
            METADATA_DATASET_ID,
            METADATA_DATASET_VERSION,
            METADATA_TRAIN_TASK_ID,
        )
    )
    return "\n".join(lines)


def _forwarded_arguments(argv: Sequence[str]) -> list[str]:
    """Drop the separator a package manager puts in front of the arguments."""
    arguments = list(argv)
    if arguments and arguments[0] == ARGUMENT_SEPARATOR:
        del arguments[0]
    return arguments


if __name__ == "__main__":
    raise SystemExit(main())

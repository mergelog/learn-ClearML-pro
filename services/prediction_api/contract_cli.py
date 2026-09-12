"""Write down the API this service publishes.

The document is derived from the code, so this command never decides
anything: it only moves what the code already says into the file the review
can read. Run it after deliberately changing what the service accepts or
answers, and the diff becomes part of the change.
"""

from __future__ import annotations

import sys

from .contract import write_snapshot


EXIT_SUCCESS = 0
EXIT_INVALID_USAGE = 2

USAGE = "usage: python -m services.prediction_api.contract_cli"


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    if arguments:
        print(USAGE, file=sys.stderr)
        return EXIT_INVALID_USAGE

    print(f"wrote {write_snapshot()}")
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())

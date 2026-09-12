"""Start the ops exporter."""

from __future__ import annotations

import sys

import uvicorn

from ml.semiconductor_quality.config import ConfigurationError

from .app import create_app
from .config import OpsExporterConfig


EXIT_SUCCESS = 0
EXIT_INVALID_USAGE = 2


def main() -> int:
    """Serve until the process is stopped, or refuse to start."""
    try:
        config = OpsExporterConfig.from_environment().validate()
    except (ConfigurationError, ValueError) as error:
        print(error, file=sys.stderr)
        return EXIT_INVALID_USAGE

    uvicorn.run(
        create_app(config),
        host=config.host,
        port=config.port,
        log_level="info",
        # 推論サービスと同じ理由でuvicornの既定設定を使わない。監視の
        # ログだけが別の形をしていると、同じ道具で読めなくなる。
        log_config=None,
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())

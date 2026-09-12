"""Start the prediction service.

The process is the unit of deployment, so this is deliberately thin: read the
configuration, refuse it if it cannot be used, and hand the application to the
server. Everything that decides what the service does lives in :mod:`app`.

TLS is terminated here when a certificate is configured. Locally there is
none: the service listens on the loopback address, and a certificate whose
private key sits in the same working tree buys nothing. Where the service is
reachable over a network — anything past a developer's machine — the
credentials it accepts travel in the request, so the transport has to be
encrypted, either here or by whatever stands in front of it.
"""

from __future__ import annotations

import sys

import uvicorn

from ml.semiconductor_quality.config import ConfigurationError

from .app import create_app
from .config import ServiceConfig


EXIT_SUCCESS = 0
EXIT_INVALID_USAGE = 2


def main() -> int:
    """Serve until the process is stopped, or refuse to start."""
    try:
        config = ServiceConfig.from_environment().validate()
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return EXIT_INVALID_USAGE

    uvicorn.run(
        create_app(config),
        host=config.host,
        port=config.port,
        # 片方だけ設定されている状態は config が拒否する。ここへ来るのは
        # 「両方ある」か「どちらも無い」のどちらかだけである。
        ssl_certfile=str(config.tls_certificate_file) if config.serves_over_tls else None,
        ssl_keyfile=str(config.tls_private_key_file) if config.serves_over_tls else None,
        log_level="info",
        # uvicornの既定設定はrootのハンドラを張り替えるため、渡さないと
        # 起動後のログだけが平文へ戻る。Noneにして、この1行1JSONへ合流させる。
        log_config=None,
        # 1リクエスト1行はミドルウェアがcorrelation id付きで書いている。
        # アクセスログを併記すると、同じ出来事が2つの形で残る。
        access_log=False,
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())

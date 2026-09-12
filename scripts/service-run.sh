#!/bin/sh
# サービスをホスト上で直接起動するときの前置き。
#
# コンテナで起動する場合は scripts/backend-up.sh が呼び手の資格情報を渡す。
# ホストで起動する場合にだけ手で環境変数を用意する形にすると、同じことをする
# 方法が2つになり、片方だけが直される。前置きをここに1つ置いて、どちらの
# 経路でも資格情報の出所を .generated/security/clients.env に保つ。
#
# ClearMLの接続設定は従来どおり scripts/clearml-run.sh が決める。ここは
# その手前に「誰が呼んでよいか」を足すだけの層である。
#
# 使い方: scripts/service-run.sh .venv/bin/python -m services.prediction_api.main

set -eu

REPOSITORY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLIENTS_FILE="${REPOSITORY_ROOT}/.generated/security/clients.env"

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <command> [arguments...]" >&2
  exit 2
fi

# 既に設定されているものは尊重する。検証環境以降は secret manager から届く。
if [ -z "${PREDICTION_API_CLIENTS:-}" ] || [ -z "${OPS_EXPORTER_CLIENTS:-}" ]; then
  if [ ! -f "${CLIENTS_FILE}" ]; then
    "${REPOSITORY_ROOT}/scripts/security-tokens.sh" >/dev/null
  fi
  # shellcheck source=/dev/null
  . "${CLIENTS_FILE}"
  export PREDICTION_API_CLIENTS
  export OPS_EXPORTER_CLIENTS
fi

exec "${REPOSITORY_ROOT}/scripts/clearml-run.sh" "$@"

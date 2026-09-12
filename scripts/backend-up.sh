#!/bin/sh
# ClearML Server と clearml-agent を起動する。
#
# 直接 `docker compose up` を呼ばずにこの薄い層を挟むのは、起動時にしか
# 決められないものが3つあるため。
#
#   1. Agentへ渡すイメージのdigest。動いているコンテナは自分がどのイメージから
#      起動したかを読めないので、外から名乗らせるしかない。
#   2. Prometheusのscrape対象。Prometheusは設定ファイルの中で環境変数を
#      展開しないため、`.env` のポートをこちらで埋めて書き出す。
#   3. サービスを呼んでよい者。サービスは呼び手が設定されていないと起動しない。
#      ローカルの資格情報は scripts/security-tokens.sh が作り、ここで読み込む。
#
# ローカルビルドのイメージにはregistryのdigestがないため、イメージ設定の
# 内容ハッシュ（docker image inspect の .Id）を来歴として使う。まだイメージが
# 無いときは unknown を渡し、起動そのものは止めない。

set -eu

REPOSITORY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="${REPOSITORY_ROOT}/infra/clearml/compose.yaml"
ENVIRONMENT_FILE="${REPOSITORY_ROOT}/.env"
PROMETHEUS_TEMPLATE="${REPOSITORY_ROOT}/infra/observability/prometheus.yml.template"
PROMETHEUS_CONFIGURATION="${REPOSITORY_ROOT}/.generated/observability/prometheus.yml"
SECURITY_CLIENTS_FILE="${REPOSITORY_ROOT}/.generated/security/clients.env"

# ポートを1つ読む。優先順位はdocker composeと同じく シェル > .env > 既定値。
#
# `.env` を `.` で読み込まないのは、値に空白を含む行（OPS_EXPORTER_PROJECTS）が
# あり、シェルがそれをコマンドとして実行してしまうためである。欲しいのは
# ポートだけなので、数字の代入行だけを取り出す。
port() {
  name="$1"
  fallback="$2"
  value="$(eval "printf '%s' \"\${${name}:-}\"")"
  if [ -z "${value}" ] && [ -f "${ENVIRONMENT_FILE}" ]; then
    value="$(
      sed -n "s/^[[:space:]]*${name}=\([0-9][0-9]*\)[[:space:]]*\$/\1/p" \
        "${ENVIRONMENT_FILE}" | tail -n 1
    )"
  fi
  printf '%s' "${value:-${fallback}}"
}

# Prometheusは設定ファイルの中で環境変数を展開しない。scrape対象のポートを
# 直書きすると、`.env` を変えたときに監視だけが古いポートを見続け、
# 「落ちていないのにダッシュボードが空」という気付きにくい壊れ方をする。
# 出所を `.env` の1か所に保つため、起動のたびに書き出す。
mkdir -p "$(dirname "${PROMETHEUS_CONFIGURATION}")"
sed \
  -e "s/{{PREDICTION_PORT}}/$(port PREDICTION_PORT 8090)/g" \
  -e "s/{{OPS_EXPORTER_PORT}}/$(port OPS_EXPORTER_PORT 8091)/g" \
  -e "s/{{NODE_EXPORTER_PORT}}/$(port NODE_EXPORTER_PORT 9100)/g" \
  -e "s/{{PROMETHEUS_PORT}}/$(port PROMETHEUS_PORT 9090)/g" \
  -e "s/{{ALERTMANAGER_PORT}}/$(port ALERTMANAGER_PORT 9093)/g" \
  "${PROMETHEUS_TEMPLATE}" >"${PROMETHEUS_CONFIGURATION}"

# 呼び手の資格情報。無ければ作る。作ってあるものには触らない。
"${REPOSITORY_ROOT}/scripts/security-tokens.sh" >/dev/null
# shellcheck source=/dev/null
. "${SECURITY_CLIENTS_FILE}"
export PREDICTION_API_CLIENTS
export OPS_EXPORTER_CLIENTS

TRAINING_AGENT_IMAGE="${TRAINING_AGENT_IMAGE:-stackup/semiconductor-agent:0.1.0}"
TRAINING_AGENT_IMAGE_DIGEST="$(
  docker image inspect --format '{{.Id}}' "${TRAINING_AGENT_IMAGE}" 2>/dev/null || echo unknown
)"

PREDICTION_API_IMAGE="${PREDICTION_API_IMAGE:-stackup/semiconductor-prediction-api:0.1.0}"
PREDICTION_API_IMAGE_DIGEST="$(
  docker image inspect --format '{{.Id}}' "${PREDICTION_API_IMAGE}" 2>/dev/null || echo unknown
)"

export TRAINING_AGENT_IMAGE
export TRAINING_AGENT_IMAGE_DIGEST
export PREDICTION_API_IMAGE
export PREDICTION_API_IMAGE_DIGEST

exec docker compose -f "${COMPOSE_FILE}" up -d "$@"

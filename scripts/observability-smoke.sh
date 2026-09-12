#!/bin/sh
# 監視が「見えている」ことを確かめる最小の検査。
#
# 監視の失敗は、監視対象の失敗より気付きにくい。ダッシュボードが空でも
# 「今日は静かだ」に見えるためである。だからここでは、対象が生きていることは
# 確かめず、監視が対象を取れていることだけを確かめる。
#
# 使い方: scripts/observability-smoke.sh

set -eu

REPOSITORY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLIENTS_FILE="${REPOSITORY_ROOT}/.generated/security/clients.env"

PROMETHEUS="${PROMETHEUS_URL:-http://localhost:${PROMETHEUS_PORT:-9090}}"
ALERTMANAGER="${ALERTMANAGER_URL:-http://localhost:${ALERTMANAGER_PORT:-9093}}"
GRAFANA="${GRAFANA_URL:-http://localhost:${GRAFANA_PORT:-3000}}"
EXPORTER="${OPS_EXPORTER_URL:-http://localhost:${OPS_EXPORTER_PORT:-8091}}"

fail() {
  echo "SMOKE FAILED: $1" >&2
  exit 1
}

if [ ! -f "${CLIENTS_FILE}" ]; then
  "${REPOSITORY_ROOT}/scripts/security-tokens.sh" >/dev/null
fi
# shellcheck source=/dev/null
. "${CLIENTS_FILE}"

OPERATOR_HEADER="Authorization: Bearer ${LOCAL_OPERATOR_TOKEN}"

ask() {
  curl --silent --show-error --max-time 10 "$1" || fail "$2"
}

# メトリクスは metrics:read を要求する。運用の役割で読む。
ask_metrics() {
  curl --silent --show-error --max-time 10 --header "${OPERATOR_HEADER}" "$1" || fail "$2"
}

echo "Checking the observability stack"

ask "${EXPORTER}/health" "the ops exporter did not answer" | grep -q '"status":"alive"' \
  || fail "the ops exporter is not alive"
echo "  ops-exporter: alive"

EXPORTED="$(ask_metrics "${EXPORTER}/metrics" "the ops exporter published no metrics")"
echo "${EXPORTED}" | grep -q 'clearml_reachable' \
  || fail "the ops exporter did not report whether ClearML is reachable"
echo "${EXPORTED}" | grep -q 'clearml_reachable 1' \
  || fail "the ops exporter cannot read the ClearML Server"
echo "  ops-exporter: reading ClearML"

# 監視の数字は、このシステムの状態そのものである。名乗らない相手には答えない。
STATUS="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 10 \
  "${EXPORTER}/metrics")" || fail "the ops exporter did not answer an unauthenticated read"
[ "${STATUS}" = "401" ] \
  || fail "the metrics were readable without a credential (${STATUS})"
echo "  ops-exporter: refuses an unauthenticated read"

ask "${PROMETHEUS}/-/healthy" "Prometheus did not answer" >/dev/null
echo "  prometheus: alive"

# 対象を1つでも取れていないなら、そのダッシュボードは嘘をつく。
TARGETS="$(ask "${PROMETHEUS}/api/v1/targets?state=active" "Prometheus did not list its targets")"
for JOB in prediction-api ops-exporter node-exporter prometheus; do
  echo "${TARGETS}" | grep -q "\"job\":\"${JOB}\"" \
    || fail "Prometheus does not know about the ${JOB} target"
done
echo "  prometheus: knows every target"

DOWN="$(echo "${TARGETS}" | tr ',' '\n' | grep -c '"health":"down"' || true)"
[ "${DOWN}" = "0" ] || echo "  prometheus: WARNING ${DOWN} target(s) are down"

RULES="$(ask "${PROMETHEUS}/api/v1/rules" "Prometheus did not list its rules")"
for ALERT in PredictionServiceDown QueueUnattended PredictionDistributionShifted; do
  echo "${RULES}" | grep -q "\"name\":\"${ALERT}\"" \
    || fail "the ${ALERT} rule is not loaded"
done
echo "  prometheus: alert rules loaded"

ask "${ALERTMANAGER}/-/healthy" "Alertmanager did not answer" >/dev/null
echo "  alertmanager: alive"

ask "${GRAFANA}/api/health" "Grafana did not answer" | grep -q '"database"' \
  || fail "Grafana did not report its health"
echo "  grafana: alive"

ask "${GRAFANA}/api/search?query=Semiconductor" "Grafana did not answer a search" \
  | grep -q 'semiconductor-quality' \
  || fail "the dashboard was not provisioned into Grafana"
echo "  grafana: dashboard provisioned"

echo "SMOKE OK"

#!/bin/sh
# 推論サービスが「配備できている」ことを確かめる最小の検査。
#
# 単体テストはモデルを差し替えて動きを確かめる。ここで確かめたいのはその逆で、
# 本物のRegistryから本物のモデルを読み、本物のHTTPで答えが返るかである。
#
# 5つ見る。後ろの2つは「配備できている」の一部である。答えられることと、
# 答えてよい相手にだけ答えることは、どちらも欠けたら配備が壊れている。
#   1. 生きているか            /health
#   2. 提供できるか、何を       /ready
#   3. 実際に答えるか           /predict
#   4. 名乗らない呼び出しを断るか
#   5. 権限の無い呼び出しを断るか
#
# 使い方: scripts/serving-smoke.sh [base url]

set -eu

REPOSITORY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLIENTS_FILE="${REPOSITORY_ROOT}/.generated/security/clients.env"

BASE_URL="${1:-http://localhost:${PREDICTION_PORT:-8090}}"

# ローカルの資格情報。無ければ、認証を外すのではなく作る。
if [ ! -f "${CLIENTS_FILE}" ]; then
  "${REPOSITORY_ROOT}/scripts/security-tokens.sh" >/dev/null
fi
# shellcheck source=/dev/null
. "${CLIENTS_FILE}"

PREDICTOR_HEADER="Authorization: Bearer ${LOCAL_PREDICTOR_TOKEN}"
OPERATOR_HEADER="Authorization: Bearer ${LOCAL_OPERATOR_TOKEN}"

fail() {
  echo "SMOKE FAILED: $1" >&2
  exit 1
}

echo "Checking ${BASE_URL}"

HEALTH="$(curl --silent --show-error --max-time 10 "${BASE_URL}/health")" \
  || fail "/health did not answer"
echo "${HEALTH}" | grep -q '"status":"alive"' \
  || fail "/health did not report the service as alive: ${HEALTH}"
echo "  health: alive"

READY="$(curl --silent --show-error --max-time 30 \
  --header "${PREDICTOR_HEADER}" "${BASE_URL}/ready")" \
  || fail "/ready did not answer"
echo "${READY}" | grep -q '"status":"ready"' \
  || fail "/ready did not report the service as ready: ${READY}"
echo "${READY}" | grep -q '"stage":"production"' \
  || fail "/ready is serving a model that was never promoted: ${READY}"
echo "  ready: $(echo "${READY}" | sed 's/.*"model_version":"\([^"]*\)".*/\1/')"

PREDICTION="$(curl --silent --show-error --max-time 30 \
  --header "${PREDICTOR_HEADER}" \
  --header 'Content-Type: application/json' \
  --data '{"measurements":[{"sample_id":"SMOKE-00001","equipment_id":"EQ-01","process_step":"ETCH","temperature":415.2,"pressure":12.5,"process_time":60.0,"gas_flow":32.5,"sensor_1":0.42,"sensor_2":-0.13,"inspection_value":8.75}]}' \
  "${BASE_URL}/predict")" || fail "/predict did not answer"

echo "${PREDICTION}" | grep -q '"sample_id":"SMOKE-00001"' \
  || fail "/predict did not answer about the product it was asked: ${PREDICTION}"
echo "${PREDICTION}" | grep -qE '"label":"(pass|fail)"' \
  || fail "/predict answered with a label outside the contract: ${PREDICTION}"
echo "${PREDICTION}" | grep -q '"model_version"' \
  || fail "/predict did not name the model that answered: ${PREDICTION}"
echo "  predict: $(echo "${PREDICTION}" | sed 's/.*"label":"\([^"]*\)".*/\1/')"

# 壊れた入力を受け付けてしまわないことも配備の一部である。
STATUS="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 10 \
  --header "${PREDICTOR_HEADER}" \
  --header 'Content-Type: application/json' \
  --data '{"measurements":[{"sample_id":"SMOKE-00002"}]}' \
  "${BASE_URL}/predict")" || fail "/predict did not answer an invalid request"
[ "${STATUS}" = "422" ] \
  || fail "an incomplete request was not refused with 422, but with ${STATUS}"
echo "  invalid request: refused with 422"

# 名乗らない呼び出し。401 は「誰か分からない」であって「してはいけない」ではない。
STATUS="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 10 \
  --header 'Content-Type: application/json' \
  --data '{"measurements":[]}' \
  "${BASE_URL}/predict")" || fail "/predict did not answer an unauthenticated request"
[ "${STATUS}" = "401" ] \
  || fail "an unauthenticated request was not refused with 401, but with ${STATUS}"
echo "  unauthenticated request: refused with 401"

# 名乗れるが、予測は許されていない相手。403 でなければ役割が効いていない。
STATUS="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 10 \
  --header "${OPERATOR_HEADER}" \
  --header 'Content-Type: application/json' \
  --data '{"measurements":[]}' \
  "${BASE_URL}/predict")" || fail "/predict did not answer the operator"
[ "${STATUS}" = "403" ] \
  || fail "a caller without the predict permission was not refused with 403, but ${STATUS}"
echo "  caller without the permission: refused with 403"

echo "SMOKE OK"

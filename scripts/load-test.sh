#!/bin/sh
# 推論サービスへ負荷を掛け、運用が決めた期限の内側で答え続けるかを見る。
#
# k6 は手元へ入れずdockerで走らせる。入れる道具を1つ増やすと、
# 「その機械にだけ入っている検査」が生まれる。イメージなら誰でも同じものを
# 走らせられる。
#
# backendと推論サービスが起動していることが前提なので、`verify` にも CI にも
# 載せていない。載せると、走らせられない場所で失敗する検査になる。
#
# 使い方: scripts/load-test.sh [base url]
#   VUS=10 DURATION=30s BATCH_SIZE=10 scripts/load-test.sh
#
# 期限は `infra/observability/alerts.yml` と同じ値で、試験側は
# `services/perf/prediction_api.js` が持つ。2つがずれていないことは
# `scripts/tests/perf-thresholds.test.mjs`（`pnpm run web:gates:test`）が見る。

set -eu

REPOSITORY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLIENTS_FILE="${REPOSITORY_ROOT}/.generated/security/clients.env"
SCRIPT="services/perf/prediction_api.js"

BASE_URL="${1:-http://localhost:${PREDICTION_PORT:-8090}}"
VUS="${VUS:-10}"
DURATION="${DURATION:-30s}"
BATCH_SIZE="${BATCH_SIZE:-10}"
K6_IMAGE="${K6_IMAGE:-grafana/k6:latest}"

fail() {
  echo "LOAD TEST FAILED: $1" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "docker が要る（k6 はイメージで走らせる）"
docker info >/dev/null 2>&1 || fail "docker daemon へ繋がらない"

# 手元の資格情報。無ければ、認証を外すのではなく作る（serving:smoke と同じ）。
if [ ! -f "${CLIENTS_FILE}" ]; then
  "${REPOSITORY_ROOT}/scripts/security-tokens.sh" >/dev/null
fi
# shellcheck source=/dev/null
. "${CLIENTS_FILE}"

echo "Loading ${BASE_URL} with ${VUS} VUs for ${DURATION} (batch ${BATCH_SIZE})"

# --network host は、コンテナの中の localhost を手元の localhost に合わせる
# ためである。これが無いと、起動しているサービスへ届かないことを
# 「サービスが答えない」と読むことになる。
docker run --rm --interactive --network host \
  --env "BASE_URL=${BASE_URL}" \
  --env "PREDICTOR_TOKEN=${LOCAL_PREDICTOR_TOKEN}" \
  --env "VUS=${VUS}" \
  --env "DURATION=${DURATION}" \
  --env "BATCH_SIZE=${BATCH_SIZE}" \
  "${K6_IMAGE}" run - < "${REPOSITORY_ROOT}/${SCRIPT}" \
  || fail "期限（p95 1秒 / 失敗 5%）を超えたか、応答の形が契約から外れた"

echo "LOAD TEST OK"

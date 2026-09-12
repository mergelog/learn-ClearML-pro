#!/bin/sh
# ローカル環境の資格情報を用意する。
#
# サービスは「呼んでよい者」が設定されていないと起動しない（開いたまま起動する
# より、起動しないほうが安全側であるため）。ローカルでそれを人手で作らせると、
# 全員が同じ値を貼るか、認証を切る改造が入る。どちらも避けたいので、無ければ
# ここで作る。
#
# 作るのは3つ。
#
#   local-predictor  推論を求める側（smokeとcurlが使う）
#   local-operator   運用する側（メトリクスと /ready を読む）
#   prometheus       数字だけを読む。scrape専用の最小権限
#
# 置き場所は .generated/security/（gitignore済み）。トークンの平文はここにしか
# 無く、リポジトリにもイメージにも入らない。staging以降ではこのファイルではなく
# secret manager から fingerprint を渡す。ここが「ローカルだけの近道」である
# ことは docs/security の脅威モデルに書いてある。
#
# 使い方:
#   scripts/security-tokens.sh            無ければ作る。あるものは触らない
#   scripts/security-tokens.sh --rotate   作り直す（古いトークンは無効になる）

set -eu

REPOSITORY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SECURITY_DIRECTORY="${REPOSITORY_ROOT}/.generated/security"
CLIENTS_FILE="${SECURITY_DIRECTORY}/clients.env"
PROMETHEUS_TOKEN_FILE="${SECURITY_DIRECTORY}/prometheus-token"
PYTHON="${REPOSITORY_ROOT}/.venv/bin/python"

ROTATE=0
if [ "${1:-}" = "--rotate" ]; then
  ROTATE=1
fi

if [ -f "${CLIENTS_FILE}" ] && [ "${ROTATE}" -eq 0 ]; then
  echo "Local credentials already exist: ${CLIENTS_FILE}"
  sed -n 's/^\([A-Z_]*\)_CLIENTS=.*/  \1/p' "${CLIENTS_FILE}"
  exit 0
fi

if [ ! -x "${PYTHON}" ]; then
  echo "The virtual environment is missing. Run: pnpm run py:setup" >&2
  exit 1
fi

issue() {
  "${PYTHON}" -m tools.security.cli token --name "$1" --role "$2" --format json
}

extract() {
  # 生成されたJSONから1つの値を取り出す。jqに依存しないため python で読む。
  printf '%s' "$1" | "${PYTHON}" -c "import json,sys;print(json.load(sys.stdin)['$2'])"
}

mkdir -p "${SECURITY_DIRECTORY}"

PREDICTOR="$(issue local-predictor predictor)"
OPERATOR="$(issue local-operator operator)"
SCRAPER="$(issue prometheus scraper)"

PREDICTOR_CLIENT="$(extract "${PREDICTOR}" client)"
OPERATOR_CLIENT="$(extract "${OPERATOR}" client)"
SCRAPER_CLIENT="$(extract "${SCRAPER}" client)"

# 先に権限を絞ってから書く。書いてから chmod すると、その間だけ誰でも読める。
UMASK_BEFORE="$(umask)"
umask 077

cat >"${CLIENTS_FILE}" <<EOF
# 生成物。scripts/security-tokens.sh が作る。手で編集しない。
#
# トークンの平文はこのファイルにしか無い。作り直すには --rotate を付けて実行する。
# 作り直すと、古いトークンを持っている手元のシェルや curl は 401 になる。
PREDICTION_API_CLIENTS='${PREDICTOR_CLIENT};${OPERATOR_CLIENT};${SCRAPER_CLIENT}'
OPS_EXPORTER_CLIENTS='${OPERATOR_CLIENT};${SCRAPER_CLIENT}'
LOCAL_PREDICTOR_TOKEN='$(extract "${PREDICTOR}" token)'
LOCAL_OPERATOR_TOKEN='$(extract "${OPERATOR}" token)'
EOF

umask "${UMASK_BEFORE}"

# Prometheus はコンテナの中から nobody として読む。600 のままだと読めず、
# 対象が down になる。gitignore された生成物の中に置き、権限だけ緩める。
extract "${SCRAPER}" token >"${PROMETHEUS_TOKEN_FILE}"
chmod 644 "${PROMETHEUS_TOKEN_FILE}"

echo "Issued local credentials: ${CLIENTS_FILE}"
echo "  local-predictor (predictor), local-operator (operator), prometheus (scraper)"
echo "The tokens are in that file only. It is gitignored, and nothing copies it."

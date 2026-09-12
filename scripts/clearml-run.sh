#!/bin/sh
# このリポジトリのClearMLコマンドを、常に同じ接続設定で動かす。
#
# 認証情報は ./clearml.conf に置く（AGENTS.local.md）。ところがClearML SDKは
# 環境変数 CLEARML_API_ACCESS_KEY / CLEARML_API_SECRET_KEY を設定ファイルより
# 優先する。別プロジェクト用のキーがシェルへexportされていると、こちらの
# コマンドだけが 401 で落ち、その理由は設定ファイルにもコードにも現れない。
# 環境変数はここで一度だけ剥がし、資格情報の出所を1か所に決める。
#
# 意図して環境変数の資格情報を使う場合（認証を有効にした別サーバへ繋ぐなど）は
# CLEARML_ALLOW_ENV_CREDENTIALS=1 を付ける。剥がすのを既定にしているのは、
# 「明示的に渡した」と「別プロジェクトのものが残っていた」を、実行する側が
# 区別できないためである。
#
# 使い方: scripts/clearml-run.sh .venv/bin/python -m ml.pipeline.cli --dataset-version 1.0.0

set -eu

REPOSITORY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

CLEARML_CONFIG_FILE="${CLEARML_CONFIG_FILE:-${REPOSITORY_ROOT}/clearml.conf}"
export CLEARML_CONFIG_FILE

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <command> [arguments...]" >&2
  exit 2
fi

if [ "${CLEARML_ALLOW_ENV_CREDENTIALS:-0}" = "1" ]; then
  exec "$@"
fi

exec env -u CLEARML_API_ACCESS_KEY -u CLEARML_API_SECRET_KEY "$@"

# syntax=docker/dockerfile:1.7

# 学習をこのリポジトリの外で動かすためのイメージ。
#
# 二つの役割を一つのDockerfileから作る。
#
#   training : 固定版の学習依存とコードを持ち、単体で学習を実行できる
#   agent    : Queueを購読し、Taskごとに学習環境を用意して実行する
#
# agent へ学習依存を入れていないのは意図的である。agent は Task に記録された
# requirements/training.txt から改めて環境を作る。そうすることで「記録した
# 固定版が本当に入る」ところまで実行で確かめられ、記録と実行がずれない。
#
# ベースイメージはタグではなくdigestで固定する。タグは後から差し替わるため、
# 同じタグから同じイメージが得られる保証がない。
ARG PYTHON_IMAGE=python:3.10-slim-bookworm@sha256:68d914ec641a0b69267ce65184d000a2bc3a9ee2590ab702b82250ab2385735a


# --- 共通の土台 ------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS base

# 中間ファイルを残さない。ログを溜め込まない。pipの版数確認で止まらない。
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# 実行時の権限を絞る。uid/gidを固定するのは、読み取り専用で持ち込む
# ワークスペースの所有者と突き合わせられるようにするため。
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app


# --- 学習依存を組み立てる --------------------------------------------------
FROM base AS training-builder

COPY requirements/training.txt /tmp/requirements/training.txt

RUN python -m venv "${VIRTUAL_ENV}" \
    && "${VIRTUAL_ENV}/bin/pip" install --require-virtualenv -r /tmp/requirements/training.txt


# --- 学習イメージ ----------------------------------------------------------
FROM base AS training

# 実行時にビルド情報を名乗れるようにする。動いているコンテナは自分が
# どのイメージから起動したかを知らないため、来歴はここから供給する。
ARG IMAGE_REFERENCE=unknown
ARG IMAGE_DIGEST=unknown
ARG GIT_COMMIT=unknown

ENV SEMICONDUCTOR_TRAINING_IMAGE=${IMAGE_REFERENCE} \
    SEMICONDUCTOR_TRAINING_IMAGE_DIGEST=${IMAGE_DIGEST} \
    SEMICONDUCTOR_GIT_COMMIT=${GIT_COMMIT}

COPY --from=training-builder --chown=root:root ${VIRTUAL_ENV} ${VIRTUAL_ENV}

WORKDIR /opt/app
COPY --chown=root:root requirements/ /opt/app/requirements/
COPY --chown=root:root ml/ /opt/app/ml/

USER app

# 依存が壊れたイメージを起動したまま気付かない状態にしない。
# 学習は常駐しないので、健全性の基準は「学習コードが読み込めること」にする。
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import ml.semiconductor_quality.cli" || exit 1

ENTRYPOINT ["python", "-m", "ml.semiconductor_quality.cli"]


# --- agentの依存を組み立てる -----------------------------------------------
FROM base AS agent-builder

COPY requirements/agent.txt /tmp/requirements/agent.txt

RUN python -m venv "${VIRTUAL_ENV}" \
    && "${VIRTUAL_ENV}/bin/pip" install --require-virtualenv -r /tmp/requirements/agent.txt


# --- agentイメージ ---------------------------------------------------------
FROM base AS agent

ARG IMAGE_REFERENCE=unknown
ARG IMAGE_DIGEST=unknown

ENV SEMICONDUCTOR_TRAINING_IMAGE=${IMAGE_REFERENCE} \
    SEMICONDUCTOR_TRAINING_IMAGE_DIGEST=${IMAGE_DIGEST}

# git: clearml-agent がコードの来歴を読むために使う。
# procps: healthcheck が常駐プロセスの生存を見るために使う。
RUN apt-get update \
    && apt-get install --no-install-recommends --yes git=1:2.39.* procps=2:4.0.* \
    && rm -rf /var/lib/apt/lists/*

COPY --from=agent-builder --chown=root:root ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# agentがTaskごとに作る環境と、pipのキャッシュの置き場所。
# 書き込みが必要なのはここだけなので、他は読み取り専用で運用できる。
ENV HOME=/home/app \
    CLEARML_AGENT_HOME=/home/app/.clearml
RUN mkdir -p "${CLEARML_AGENT_HOME}" && chown -R app:app /home/app

WORKDIR /workspace
USER app

# 常駐プロセスなので、健全性の基準は「daemonが生きていること」。
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD pgrep -f "clearml-agent" > /dev/null || exit 1

ENTRYPOINT ["clearml-agent"]
CMD ["daemon", "--foreground"]

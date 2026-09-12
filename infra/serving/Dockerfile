# syntax=docker/dockerfile:1.7

# 推論サービスのイメージ。
#
# 学習用イメージ（infra/training/Dockerfile）と同じベースをdigestで固定する。
# 学習と推論で土台がずれると、同じjoblibを読み込めない事態が起こりうる。
# 依存も requirements/serving.txt が requirements/training.txt を制約に
# 解決しているため、scikit-learn / numpy / joblib の版数は学習と一致する。
#
# モデルはイメージへ焼かない。起動時にRegistryから production のモデルを
# 取得する。どのモデルを提供するかはRegistryが唯一の答えであり、
# 配備の設定が二つ目の答えになってはいけない。
ARG PYTHON_IMAGE=python:3.10-slim-bookworm@sha256:68d914ec641a0b69267ce65184d000a2bc3a9ee2590ab702b82250ab2385735a


FROM ${PYTHON_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

RUN groupadd --gid 10002 serving \
    && useradd --uid 10002 --gid serving --create-home --shell /usr/sbin/nologin serving


FROM base AS builder

COPY requirements/training.txt /tmp/requirements/training.txt
COPY requirements/serving.txt /tmp/requirements/serving.txt

RUN python -m venv "${VIRTUAL_ENV}" \
    && "${VIRTUAL_ENV}/bin/pip" install --require-virtualenv -r /tmp/requirements/serving.txt


FROM base AS serving

ARG IMAGE_REFERENCE=unknown
ARG IMAGE_DIGEST=unknown
ARG GIT_COMMIT=unknown

ENV SEMICONDUCTOR_SERVING_IMAGE=${IMAGE_REFERENCE} \
    SEMICONDUCTOR_SERVING_IMAGE_DIGEST=${IMAGE_DIGEST} \
    SEMICONDUCTOR_GIT_COMMIT=${GIT_COMMIT} \
    HOME=/home/serving \
    PREDICTION_HOST=0.0.0.0 \
    PREDICTION_PORT=8090 \
    SERVICE_HEALTH_PORT=8090

COPY --from=builder --chown=root:root ${VIRTUAL_ENV} ${VIRTUAL_ENV}

WORKDIR /opt/app
# 推論はドメインの一部を共有する。データ契約とモデルの段階の定義は
# 学習側と同じものを使わなければ、契約の検査そのものが意味を失う。
COPY --chown=root:root ml/ /opt/app/ml/
COPY --chown=root:root services/ /opt/app/services/

# SDKのキャッシュだけ書き込みが要る。それ以外は読み取り専用で運用できる。
ENV CLEARML_CACHE_DIR=/home/serving/.clearml
RUN mkdir -p "${CLEARML_CACHE_DIR}" && chown -R serving:serving /home/serving

USER serving
EXPOSE 8090

# 生きているかどうかは /health で見る。モデルを触らないので、
# モデルの読み込みが遅いだけのプロセスを「死んでいる」と誤判定しない。
#
# 見に行く先はハードコードしない。このイメージは推論サービス（8090）と
# ops-exporter（8091）の両方が使い、どちらもホストのネットワークで動く。
# 番号を固定すると、ops-exporter の健康状態を尋ねたのに推論サービスが
# 答えることになり、自分が死んでいても healthy と名乗る。
# ``${SERVICE_HEALTH_PORT}`` はビルド時ではなく実行時にシェルが展開するので、
# Composeが渡した値がそのまま効く。
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${SERVICE_HEALTH_PORT}/health', timeout=3)" \
    || exit 1

ENTRYPOINT ["python", "-m", "services.prediction_api.main"]

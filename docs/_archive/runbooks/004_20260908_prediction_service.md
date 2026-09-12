# Runbook: 推論サービス

production へ昇格したモデルで、製品の良否を判定するHTTP APIを動かす。

## この構成の考え方

```text
Registry (stage:production)
      │  起動時に1回だけ取得
      v
prediction-api ── GET  /health   生きているか（モデルを見ない）
                ── GET  /ready    提供できるか、どのモデルで
                ── POST /predict  判定する
```

決めていること。

- **提供するモデルはRegistryだけが決める。** 配備の設定にモデルIDは書かない。
  昇格は `ml:model promote`、反映はプロセスの再起動で行う
- **モデルは起動時に1回だけ読み、実行中は差し替えない。** 応答に載る
  `model_version` は、そのプロセスが返した全ての答えについて正しい
- **production 以外は提供しない。** candidate や staging を指定すると起動に失敗する
- **契約に合わないモデルでは起動しない。** 学習した列と提供する列が違う、
  公開していないラベルを返す、といったモデルは起動時に拒否する

## 前提

- ClearML Serverが起動している
- production のモデルが1つある（`corepack pnpm ml:model status`）

## 1. 手元で起動する

```bash
corepack pnpm serving:start
```

既定は `http://0.0.0.0:8090`。ポートは `PREDICTION_PORT` で変えられる。
`../learn-ClearML` と共有する 8008 / 8080 / 8081 は使わない。

OpenAPIは <http://localhost:8090/docs> で読める。

## 2. コンテナで起動する

```bash
corepack pnpm serving:build
corepack pnpm serving:up
corepack pnpm serving:logs
```

`serving:up` は `scripts/backend-up.sh` を通す。起動しているコンテナは
自分がどのイメージから来たか読めないため、digestを外から渡す必要がある。

## 3. 配備できたことを確認する

```bash
corepack pnpm serving:smoke
```

4つを確認する。

| 確認 | 期待 |
| --- | --- |
| `/health` | `"status":"alive"` |
| `/ready` | `"status":"ready"` かつ `"stage":"production"` |
| `/predict` | `pass` か `fail`、`model_version` 付き |
| 不完全な入力 | 422 で拒否される |

単体テストはモデルを差し替えて動きを確かめる。smoke testはその逆で、
本物のRegistryから本物のモデルを読み、本物のHTTPで答えるかを見る。

### 負荷を掛けて確かめる

smoke testは「答えるか」を1回ずつ見る。負荷試験は「**決めた期限の内側で
答え続けるか**」を見る。

```bash
corepack pnpm serving:load                 # 10 VU / 30秒
VUS=30 DURATION=2m corepack pnpm serving:load
```

k6は手元へ入れず、dockerイメージで走らせる（`scripts/load-test.sh`）。
入れる道具を増やすと、その機械にだけ入っている検査ができる。

期限はこの試験のために決めた数字ではなく、運用が鳴らすと決めている値
（`infra/observability/alerts.yml`）と同じである。

| 期限 | 値 | 対応するアラート |
| --- | --- | --- |
| 95パーセンタイルの応答 | 1秒 | `PredictionLatencyHigh` |
| サービス側の失敗 | 5% | `PredictionErrorRateHigh` |
| 応答の形（件数・モデル） | 全件 | － |

2つがずれていないことは `pnpm run web:gates:test` が見ている。片方だけを
変えると、そこで落ちる。

backendと推論サービスの起動が前提なので、`verify` にもCIにも載せていない。

## 4. 使う

```bash
curl -X POST http://localhost:8090/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "measurements": [{
      "sample_id": "SAMPLE-00001",
      "equipment_id": "EQ-01",
      "process_step": "ETCH",
      "temperature": 415.2,
      "pressure": 12.5,
      "process_time": 60.0,
      "gas_flow": 32.5,
      "sensor_1": 0.42,
      "sensor_2": -0.13,
      "inspection_value": 8.75
    }]
  }'
```

応答。

```json
{
  "model": {
    "model_id": "...",
    "model_version": "1.0.0-20260907T193604Z-6a9d9fe3",
    "stage": "production",
    "dataset_id": "...",
    "dataset_version": "1.0.0",
    "train_task_id": "..."
  },
  "predictions": [
    {"sample_id": "SAMPLE-00001", "label": "pass", "confidence": 0.87}
  ]
}
```

`confidence` は、アルゴリズムが確信度を出せる場合だけ入る。
出せないモデルのときは省略する。無い数字を作らない。

1回の呼び出しで受け付けるのは500件までである。それ以上は分けて呼ぶ。

受け付ける値と答えの形は
[services/prediction_api/openapi.json](../../services/prediction_api/openapi.json)
に全部書いてある。起動中のサービスなら `http://localhost:8090/docs` でも読める。
この2つは必ず一致する（`services:test` が突き合わせている）ので、
サービスを起動できない相手にはファイルのほうを渡せばよい。

APIの形を意図して変えたときは、次を走らせて差分をコミットに載せる。
忘れると `pnpm verify:python` が落ちる。

```bash
corepack pnpm serving:openapi:update
```

判断の経緯は
[docs/_archive/adr/006_20260911_published_api_snapshot.md](../adr/006_20260911_published_api_snapshot.md)
にある。

## 5. モデルを入れ替える / 戻す

```bash
# 新しいモデルをproductionへ
corepack pnpm ml:model promote -- --model-id <id> --to production --approved-by "..." --reason "..."

# 推論サービスを作り直して反映
docker compose -f infra/clearml/compose.yaml restart prediction-api
corepack pnpm serving:smoke
```

戻すときも同じである。

```bash
corepack pnpm ml:model rollback -- --approved-by "..." --reason "..."
docker compose -f infra/clearml/compose.yaml restart prediction-api
corepack pnpm serving:smoke
```

`/ready` の `model_version` が変わっていることを必ず確認する。
再起動を忘れると、Registryは新しいモデルを指しているのにサービスは
古いモデルで答え続ける。

## 6. 障害の再現

特定のモデルで再現したいときだけ、モデルを固定して起動できる。

```bash
PREDICTION_MODEL_ID=<model id> corepack pnpm serving:start
```

固定できるのは production のモデルだけである。これは調査のための例外で、
通常の配備では使わない。

## トラブルシュート

| 症状 | 原因と対処 |
| --- | --- |
| 起動時 `no model is marked production` | 昇格していない。`ml:model promote` を先に行う |
| 起動時 `N models are marked production` | Registryの状態が壊れている。`ml:model status` で確認し、片方を archived へ |
| 起動時 `the model was fitted on other columns` | 学習時と提供時のデータ契約がずれている。モデルを作り直す |
| 起動時 `does not hold a fitted pipeline` | モデルの中身が学習パイプラインではない。登録経路を確認する |
| 起動時 `the weights of model ... cannot be read (EOFError: ...)` | 重みのファイルが途中で切れている。転送の失敗か、書き込み中のものを登録した。Pipelineを再実行してモデルを作り直す |
| 起動時 `... cannot be read (KeyError: 0)` | 登録されているファイルがモデルではない。`register-candidate` が上げたファイルを確認する |
| 起動時 `the model registry cannot be read` | ClearML Serverが応答していない。モデル側の問題ではないので、`backend:status` と `backend:logs` を先に見る |
| 起動時 `failed downloading file:///...` | モデルが「作ったマシンの中だけ」に登録されている。Pipelineの `register-candidate` が `output_uri` を設定しているか確認する（現在は登録時に検査して失敗させる） |
| `/predict` が 503 | サービス側の状態の問題であって入力の誤りではない。ログでモデルの状態を確認する |
| `/predict` が 422 | 入力が契約に合っていない。応答の `detail` に不足・範囲外の項目名が入る |
| 応答の `model_version` が古い | 昇格後にプロセスを再起動していない |

# Runbook: 観測性と運用アラート

何かがおかしいときに、どこを見て、何をするか。

## 何を見ているか

```text
[推論]  prediction-api ──/metrics──┐
                                    │
[学習]  ClearML ──ops-exporter──────┼──▶ Prometheus ──▶ Alertmanager
        (Queue/Agent/Task)          │         │
                                    │         └──▶ Grafana
[資源]  ホスト ──node-exporter──────┘
```

学習側はHTTPを話さない。Queueも、Agentも、Taskも、誰かが取りに行かないと
状態が分からない。`ops-exporter` がその役をする。

| URL | 何が見えるか |
| --- | --- |
| <http://localhost:3000> | Grafana。ダッシュボード「Semiconductor quality」 |
| <http://localhost:9090> | Prometheus。生の数値と、鳴っている警報 |
| <http://localhost:9093> | Alertmanager。まとめられた警報 |
| <http://localhost:8090/metrics> | 推論サービスの数値 |
| <http://localhost:8091/metrics> | 学習側の数値 |
| <http://localhost:9100/metrics> | ホストの資源 |

## 起動と確認

```bash
corepack pnpm ops:up      # exporter / Prometheus / Alertmanager / Grafana
corepack pnpm ops:smoke   # 監視が対象を取れているか
```

`ops:smoke` は対象が健康かどうかは見ない。**監視が対象を見えているか**だけを見る。
監視が落ちているとダッシュボードは空になり、それは「今日は静かだ」と
区別が付かないためである。

## 何を測っているか、なぜそれか

| メトリクス | これが無いと見えないこと |
| --- | --- |
| `prediction_requests_total{outcome}` | 失敗率。`unavailable`（5xx）と `invalid`（4xx）を分けている。混ぜると呼び出し側の不具合でこちらが起こされる |
| `prediction_request_seconds_bucket` | 応答の遅さ。平均ではなく分位で見る。平均は遅い一部を隠す |
| `predictions_total{label}` | モデルが全部 `pass` と答え始めても、失敗率は完璧なまま |
| `predicted_failure_share` / `training_failure_share` | 予測のdrift。壊れていないのに世界が変わった状態 |
| `clearml_queue_pending_tasks` / `clearml_queue_workers` | Queueが捌けているか。待ちがあってAgentが0は、放っておくと永久に捌けない |
| `clearml_tasks_failed_recent` | 毎回失敗するPipelineは、Queueを空にしAgentを暇にする。滞留では見えない |
| `clearml_reachable` | 監視が対象を読めているか。0とスクレイプ成功時の0は別物 |
| `node_filesystem_avail_bytes` / `node_memory_MemAvailable_bytes` | ホストの残り。学習も推論も監視も同じホストに載っており、尽きると症状は3か所に出る |

## 警報の設計

段階は **warning** と **critical** の2つだけにしている。増やすと、
どれが人を起こしてよいものか誰も覚えていられなくなる。

すべての規則に `for` を付けている。1回の観測で鳴る規則は、
一過性のゆらぎで鳴り続け、やがて誰も見なくなる。

| 警報 | 段階 | 継続 | 意味 |
| --- | --- | --- | --- |
| `PredictionServiceDown` | critical | 2分 | 推論が応答しない |
| `PredictionServiceHasNoModel` | critical | 2分 | 提供できるモデルが無い |
| `PredictionErrorRateHigh` | critical | 5分 | サービス側の失敗が5%超 |
| `ClearmlUnreachable` | critical | 5分 | 学習側の状態が読めない |
| `QueueUnattended` | critical | 10分 | 待ちがあるのにAgentが0 |
| `PredictionLatencyHigh` | warning | 10分 | p95が1秒超 |
| `PredictionDistributionShifted` | warning | 30分 | 学習時と不良率が20ポイント以上違う |
| `QueueBacklogGrowing` | warning | 30分 | 滞留が続いている |
| `PipelineFailuresRecurring` | warning | 15分 | 直近30分で3件以上失敗 |
| `HostDiskFillingUp` | warning | 15分 | ディスクの空きが10%未満 |
| `HostMemoryExhausted` | warning | 15分 | 空きメモリが10%未満 |

`PredictionServiceDown` が鳴っているときは、応答が遅い・失敗率が高いは
当たり前なので抑止する（Alertmanagerの `inhibit_rules`）。
原因ではなく結果の警報で人を起こさない。

## 症状別の手順

### 推論サービスが応答しない

```bash
docker compose -f infra/clearml/compose.yaml logs --tail 50 prediction-api
```

起動時のログに理由が出る。よくあるのは次の3つで、いずれも起動を止めている。

- `no model is marked production` → 昇格していない。`pnpm ml:model status`
- `N models are marked production` → Registryの状態が壊れている
- `cannot be downloaded from 'file://...'` → 配備できない形で登録されたモデル

直したら再起動して確認する。

```bash
docker compose -f infra/clearml/compose.yaml restart prediction-api
corepack pnpm serving:smoke
```

### ops-exporter が答えない（`ops:smoke` が「did not answer」で落ちる）

```bash
docker compose -f infra/clearml/compose.yaml logs --tail 30 ops-exporter
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8091/health
```

多いのは起動途中である。ClearML Serverがまだ応答しないと `auth.login` を
再試行し続け、その間 8091 では待ち受けない。ClearML Serverが起きるのを待つ。

コンテナの `healthy` 表示だけを見て「動いている」と判断しないこと。
このコンテナは推論サービスと同じイメージを使い、ホストのネットワークを
共有している。ヘルスチェックの宛先は `SERVICE_HEALTH_PORT` で渡しており、
渡し忘れると 8090（推論サービス）を見に行って、自分が答えられなくても
healthy と名乗る。確認は次で行う。

```bash
docker inspect learn01-clearml-ops-exporter-1 \
  --format '{{range .Config.Env}}{{println .}}{{end}}' | grep SERVICE_HEALTH_PORT
```

### 提供できるモデルがない

```bash
corepack pnpm ml:model status
```

production が `none` なら昇格されていない。
[003_20260908_model_promotion.md](003_20260908_model_promotion.md) の手順で昇格する。

### 失敗率が上がった

1. Grafanaの「推論の失敗率」で、`unavailable` か `invalid` かを見る
2. `invalid` なら呼び出し側の入力の問題。こちらは正常に拒否している
3. `unavailable` なら次でログを読む。correlation id で1件を追える

```bash
docker compose -f infra/clearml/compose.yaml logs --tail 200 prediction-api \
  | grep '"level": "error"'
```

ログは1行1JSONで、`correlation_id` / `model_version` / `endpoint` が入っている。
呼び出し側が受け取った `X-Correlation-Id` を聞けば、その1件だけを取り出せる。

### 応答が遅い

まず処理量を見る。増えているなら容量の問題、増えていないならモデルか
サーバ側の問題である。RandomForestは推論が重い（W5の測定で185 µs/行）。
モデルの選び直しは
[docs/_archive/adr/001_20260908_learning_algorithm_choice.md](../adr/001_20260908_learning_algorithm_choice.md)
に測定値がある。

### 予測の分布が変わった

**モデルは壊れていない。** 返している不良率が学習時と離れただけである。

1. Grafanaの「予測の偏り」で、いつから離れたかを見る
2. 新しいDatasetがあるなら、学習時のデータと比べる

```bash
corepack pnpm ml:data drift -- --dataset-version 2.0.0 --against 1.0.0
```

3. 工程が変わったのなら再学習する。変わっていないなら入力の質を疑う

判断したことは記録する。放置したなら、なぜ放置してよいと判断したかを残す。

### ClearML Serverが読めない

```bash
corepack pnpm backend:status
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8008/debug.ping
```

`clearml_reachable` が0でも、対象が落ちているとは限らない。
exporterの認証情報（`clearml.conf`）が読めていない場合もある。

### Queueが捌けない

```bash
curl -s http://localhost:8091/metrics | grep clearml_queue
```

- `workers` が 0 → Agentが停止している。`pnpm agent:up`
- `workers` が 0 ではないが `pending` が減らない → Agentのログを見る

```bash
corepack pnpm agent:logs
```

購読しているQueue名が投入先と違うのが典型的な原因である。

### Taskが繰り返し失敗する

失敗したTaskのCONSOLEを読む。原因の多くは次のどちらかである。

- Datasetが品質条件を満たしていない → `validate` ステップの
  `data_quality` アーティファクトに理由が全部載っている
- Agentの実行環境 → `Environment setup` の途中で落ちていないか

### ホストの資源が足りない

```bash
curl -s http://localhost:9100/metrics | grep -E 'node_filesystem_avail_bytes|node_memory_MemAvailable_bytes'
df -h /
```

ディスクから先に尽きる。Elasticsearchは空きが逼迫すると索引を読み取り専用へ
切り替えるため、症状は「学習が失敗する」「画面に出ない」の形で現れ、
原因がディスクだとは見えない。

減らせるものは順に、古いTaskの成果物、`.generated/` の生成データ、
未使用のDockerイメージである。

```bash
docker image prune              # 停止中のコンテナは消さない
```

`docker volume prune` と `docker system prune --volumes` は使わない。
このホストには別プロジェクトのClearMLボリュームが同居しており、
停止中のものを消してしまう。

保存期間そのものの設計（Dataset・Artifact・ログをいつ捨てるか）は
計画書のP3「コスト・容量・ライフサイクル管理」で扱う。

## SLI / SLO

学習環境なので目標値は控えめに置く。実運用では利用側と合意して決める。

| SLI（何を測るか） | SLO（どこまで許すか） | 破ったときの警報 |
| --- | --- | --- |
| 推論の可用性: `unavailable` でない応答の割合 | 30日で 99% | `PredictionErrorRateHigh` |
| 推論の応答性: p95 応答時間 | 30日の95%の時間で 1秒未満 | `PredictionLatencyHigh` |
| 学習の到達性: Queueに入れたTaskが実行される | 30日で 99% | `QueueUnattended` |
| データの健全性: 学習に使えるDatasetの割合 | 品質条件を満たさないものは0件 | `PipelineFailuresRecurring` |

SLOは「破ってはいけない線」ではなく「破ったら手を止めて直す線」である。
余裕（error budget）を使い切ったら、新機能より先に安定させる。

## 障害の記録（postmortem）

障害が終わったら、次の形で残す。人を責めないために、**何が起きたか**と
**なぜそれが起こりうる状態だったか**だけを書く。

```markdown
# Postmortem: <一行で何が起きたか>

- 日時: <検知> 〜 <復旧>（UTC）
- 影響: <誰が、何を、どれだけできなかったか>
- 検知: <どの警報か。人が気付いたなら「警報では気付けなかった」と書く>

## 時系列
| 時刻 | 出来事 |
| --- | --- |

## 直接の原因
<何が壊れたか>

## そうなりえた理由
<なぜ壊れる状態だったか。1つで止めず、3回くらい掘る>

## 効いた対応 / 効かなかった対応

## 再発を防ぐためにすること
| やること | 誰が | いつまで |
| --- | --- | --- |

## 検知は十分だったか
<警報で気付けたか。気付けなかったなら、どの指標があれば気付けたか>
```

最後の節が一番大事である。同じ障害が二度目も人力で見つかるなら、
監視は何も学んでいない。

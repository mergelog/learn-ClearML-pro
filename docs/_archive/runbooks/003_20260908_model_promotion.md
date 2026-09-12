# Runbook: モデルの評価ゲートと昇格・rollback

学習できたモデルを、そのまま推論環境へ出さないための仕組みと手順。

## 段階と、段階の間で許される移動

```text
                (評価ゲートを通過)
学習 ──────────> candidate ──> staging ──> production
                                  │            │
                                  └──> archived <┘
                                        │
                                        └──> production   （rollback）
```

| 段階 | 意味 |
| --- | --- |
| `candidate` | 合格基準を満たしたが、まだ誰も使っていない |
| `staging` | 人が承認し、試用している |
| `production` | 人が承認し、推論環境が使う。同時に1つだけ |
| `archived` | かつてproductionだった、または見送った |

基準を満たさなかったモデルは **登録されない**。段階を付けて残すより、
Registryに入れないほうが確実だからである。何点だったかは、そのPipeline実行の
`registration_decision` アーティファクトに残る。

`candidate` から `production` へ直接は行けない。`staging` での確認を
飛ばさないためである。

## 合格基準

`config/model_gate.yaml` に書く。編集すれば次のPipeline実行から効く。
コード変更もデプロイも要らない。

```yaml
split: validation
minimums:
  recall: 0.55
  f1: 0.65
```

判定は **validation** で行う。test は選定後の最終確認に一度だけ使うので、
選定には使わない。基準に挙げた指標が実行結果に無い場合は「不合格」とする。
数値が無いことは品質の証拠にならない。

## 1. いまどのモデルがどの段階にいるか

```bash
corepack pnpm ml:model status
```

```text
production:
  1.0.0-20260908T043015Z-9f21ab30 (a1b2...) from dataset 1.0.0
staging: none
candidate:
  1.0.0-20260908T051201Z-5c77de91 (c3d4...) from dataset 1.0.0
archived: none
```

モデル名（version）は `{Dataset Version}-{UTC時刻}-{学習Taskの先頭8桁}` である。
どのデータから、いつ、どの実行で作られたかが名前だけで分かり、
UTCなので別の端末で作ったものとも並べ替えられる。

## 2. 1つのモデルの記録を全部見る

```bash
corepack pnpm ml:model show -- --model-id <model id>
```

`dataset_id` / `train_task_id` / `promoted_by` / `promotion_reason` /
`gate_detail` などが出る。ここから学習Taskへ行けば、`Provenance/git_commit` で
コードまで遡れる。

## 3. staging へ上げる

```bash
corepack pnpm ml:model promote -- \
  --model-id <model id> \
  --to staging \
  --approved-by "山田" \
  --reason "validation recall 0.71。既存productionより不良検出が改善"
```

`--approved-by` と `--reason` は必須である。理由の無い昇格は後から
レビューできないため、空文字は拒否される。

## 4. production へ上げる

```bash
corepack pnpm ml:model promote -- \
  --model-id <model id> \
  --to production \
  --approved-by "山田" \
  --reason "1週間のstaging試用で誤検知の増加なし"
```

このとき、それまでproductionだったモデルは同じ操作の中で `archived` へ移る。
「production が2つある瞬間」は作られない。退いたモデルには
`replaced_by` として後継のIDが記録される。

## 5. rollback する

直前のproductionへ戻す。

```bash
corepack pnpm ml:model rollback -- \
  --approved-by "佐藤" \
  --reason "新モデルが良品を不良と判定する事象が発生"
```

rollbackも承認と理由を要求する。戻すことも決定だからである。
戻せるモデルが無い場合（まだ一度も置き換えていない場合）は拒否される。

## 6. 追跡の鎖

productionのモデルから、次の順で遡れる。

```text
Model
  ├── metadata: dataset_id / dataset_version
  ├── metadata: train_task_id ──> 学習Task
  │                                 └── Provenance/git_commit ──> コード
  ├── metadata: evaluate_task_id ──> 評価Task（SCALARS / evaluation）
  ├── metadata: register_task_id ──> 登録Task（registration_decision）
  └── metadata: promoted_by / promoted_at / promotion_reason / previous_stage
```

## トラブルシュート

| 症状 | 原因と対処 |
| --- | --- |
| `a candidate model cannot become production` | 段階を飛ばしている。先に `--to staging` を実行する |
| `the model is already production` | 同じ段階への移動。`status` で現状を確認する |
| `2 models are marked production` | 手動でタグを編集した結果、状態が2つある。片方を `archived` へ直してから操作する |
| `no archived model is available to roll back to` | まだ一度も置き換えていない。戻す先が無い |
| `the model carries no stage tag` | Registry外で作られたモデル。Pipelineの `register-candidate` 以外で作らない |
| ゲートで止まった | `registration_decision` の `gate` を見る。基準を変えるなら `config/model_gate.yaml` を編集し、理由をコミットに残す |

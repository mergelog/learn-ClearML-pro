# Runbook: ハイパーパラメータ探索と、勝った設定の引き渡し

手で `--n-estimators` を変えて回す代わりに、範囲・目的・予算を先に決めて
探索させる。探索は設定を選ぶだけで、モデルは登録しない。

## 全体の流れ

```text
config/experiment/{base,<環境>}.yaml
  -> ml:experiment（探索Task）
       -> 試行Task × N（学習用Queue、trainのみを交差検証）
       -> 勝った設定 + 確率のしきい値
  -> --handoff で学習Pipelineへ
       -> validation で評価ゲート -> test で最終評価1回 -> candidate 登録
  -> ml:model promote（人の承認）
```

## どの行が誰のものか

探索を入れると「選定に使った行で評価する」事故が起きやすい。
この実装では役目を分けてある。

| 部分 | 使う人 | 回数 |
| --- | --- | --- |
| train | 探索（fold分割して交差検証、しきい値の選定も内側で） | 何度でも |
| validation | 評価ゲート | 候補1件につき1回 |
| test | 最終評価 | 1回だけ |

探索に validation / test を渡すと、`ml/experiment/trials.py` が拒否する。

## 1. 何を探すつもりかを先に読む

ClearMLへ何も作らずに、これから許す範囲と予算を確認する。

```bash
corepack pnpm ml:experiment -- --dataset-version 2.0.0 --dry-run
```

```text
Environment: dev
Algorithm: random-forest
Objective: maximise the f1 of the train split
Judged by: 5 fold cross validation over the train split, with the probability cut chosen on 3 inner folds
Budget: at most 6 trials, 1 at a time, 5.0 minutes per trial and 20.0 minutes in total
Trials run on: semiconductor-training
Varying:
- n_estimators: 100 to 600 in steps of 50
- min_samples_leaf: 1 to 20 in steps of 1
- max_depth: one of (unset), 8, 12, 16, 24
- class_weight: one of none, balanced
```

範囲を変えるのは `config/experiment/base.yaml`、予算とQueueは
`config/experiment/<環境>.yaml`。知らないキーや資格情報らしき値が
書かれていると、読み込みの時点で失敗する。

## 2. 探索する

```bash
# 既定は dev の予算
corepack pnpm ml:experiment -- --dataset-version 2.0.0

# 勝った設定をそのまま学習Pipelineへ渡す
corepack pnpm ml:experiment -- --dataset-version 2.0.0 --handoff

# 別の環境の予算で走らせる（明示が必要）
corepack pnpm ml:experiment -- --dataset-version 2.0.0 --environment staging
```

`--handoff` を付けない限り、探索は何も登録しない。

## 3. どこを見るか

| 見るもの | 場所 |
| --- | --- |
| 探索空間・目的・予算・判定方法 | 探索Taskの Parameters（`Objective` / `Budget` / `Trial` / `Search Space`）と `search_plan` |
| 勝った試行と成績 | 探索Taskの `best_trial` |
| 試行1件の中身 | 試行Taskの `objective` グラフ（横軸はfold数）と `trial_result` |
| 選ばれたしきい値 | 試行Taskの `decision threshold` グラフと `trial_result.decision_threshold` |
| 引き渡し先 | Pipeline Taskの Parameters `Handoff/search_task_id` / `Handoff/trial_task_id` |

プロジェクトは `Semiconductor Quality Prediction/Optimization`、
試行は その下の `Trials`。

## 4. 早期停止と予算

| 設定 | 効き方 |
| --- | --- |
| `max_trials` | 試す候補の総数 |
| `parallel_trials` | 同時に走る試行の数。Agentの台数を超えても意味はない |
| `trial_minutes` | 1試行の上限。超えたらその試行を打ち切る |
| `total_minutes` | 探索全体の上限。超えたら走っている試行ごと打ち切る |
| `minimum_folds` | これだけfoldを見るまでは、成績が悪くても打ち切らない |
| `keep_top` | 上位いくつの試行Taskを残すか。残り物のTaskで画面を埋めない |

試行はfoldごとに途中経過を報告し、見込みの無い候補はOptunaが途中で止める。
`stopped` の試行はこれである（失敗ではない）。

## 5. 勝った設定は、ふつうの学習として扱う

引き渡しは「モデル」ではなく「設定」である。Pipelineが改めて train で
学習し、validation でゲートにかけ、test で1回だけ評価し、
通ったものだけを candidate にする。

しきい値は学習済みpipelineの中に入る（`FixedThresholdClassifier`）ので、
推論サービス側の変更は要らない。保存されたファイルが、そのまま
「その位置で切るモデル」である。

引き渡し後の昇格手順は `docs/_archive/runbooks/003_20260908_model_promotion.md`。

## 6. うまくいかないとき

| 症状 | 見るところ |
| --- | --- |
| `the rarest label holds N rows ... cannot fill` | trainの不良件数に対して `folds` × `threshold_folds` が多すぎる。foldを減らすか、Datasetを増やす |
| 試行が `created` のまま動かない | 学習用Agentが起きているか（`corepack pnpm agent:logs`）。Queue名は `config/experiment/<環境>.yaml` の `trial_queue` |
| すべての試行が `failed` | 試行Task 1件のログを読む。Dataset Version・データ品質・依存の導入で落ちていることが多い |
| `Search ... finished without a trial that reported a score` | 上と同じ。1件も成績を報告できていない |
| 勝った設定でゲートに落ちる | 探索は train しか見ていない。validation で落ちたのなら過学習を疑う。`config/model_gate.yaml` の基準と `registration_decision` を読む |
| 同じ設定なのに成績が違う | 森の並列度は再現性のため1に固定してある（ADR 004）。`n_jobs` を戻すと再現しなくなる |

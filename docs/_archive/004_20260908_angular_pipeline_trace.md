# Angularから学習Pipelineまでのデータの流れ

「画面のボタンを押してからモデルが登録されるまで」に何が起きているかを、
コードの位置と対応させて追えるようにした資料。

対象は `src/app/features/quality-pipeline/`（新規に追加した画面）と、
それが呼ぶClearML APIから先である。

## 1. 全体のシーケンス

```text
[ブラウザ]                    [ClearML Server]        [clearml-agent]
QualityPipelineComponent
  │ 「Start」を押す
  ▼
qualityPipelineActions.startRun
  │
  ▼
QualityPipelineEffects.startRun
  │
  ▼
QualityPipelineApiService.startRun
  │ ① tasks.clone ──────────────▶ Pipeline Taskを複製
  │    （Dataset/dataset_version を上書き）
  │ ② tasks.enqueue ────────────▶ semiconductor-pipeline へ投入
  │                                        │
  │                                        ▼
  │                              pipeline-agent が取得
  │                                        │
  │                                        ▼
  │                              PipelineController が
  │                              ステップTaskを複製・投入
  │                                        │
  │                                        ▼
  │                              semiconductor-training へ
  │                                        │
  │                                        ▼
  │                              training-agent が
  │                              validate ▸ preprocess ▸ train
  │                              ▸ evaluate ▸ register-candidate
  │                                        │
  │ ③ tasks.get_all_ex（親=実行Task）◀─────┘ 状態とステップ
  │ ④ events.get_task_latest_scalar_values   評価指標
  │ ⑤ models.get_all_ex（tag=stage:production）提供中のモデル
  ▼
qualityPipelineActions.runRefreshed / scoresLoaded
  │
  ▼
reducer が state を更新 ─▶ signal ─▶ テンプレートが再描画
```

## 2. 層と責務

| 層 | ファイル | 持つもの | 持たないもの |
| --- | --- | --- | --- |
| Component | `quality-pipeline.component.ts` / `.html` | 利用者の操作、stateの表示 | 取得、判断、ClearMLの語彙 |
| Actions | `quality-pipeline.actions.ts` | 「何が起きたか」 | 「次に何をするか」 |
| Reducer | `quality-pipeline.reducer.ts` | state遷移、selector | 非同期処理 |
| Effects | `quality-pipeline.effects.ts` | 外部への問い合わせ、失敗のaction化 | state遷移の判断 |
| API境界 | `quality-pipeline-api.service.ts` | 操作単位のAPI呼び出し | 画面の都合 |
| Adapter | `quality-pipeline.adapter.ts` | APIの形 -> 画面の形の変換 | 通信 |
| View model | `quality-pipeline.model.ts` | 画面が扱う形 | APIの形 |

### なぜEffectsをfeature配下に置くか

更新する state と同じディレクトリにあると、「この state はどこから書き換わるか」を
ディレクトリを見るだけで追える。共通のEffectsディレクトリへ集めると、
feature が増えるほど「自分の state を誰が触るか」が分からなくなる。

`quality-pipeline.routes.ts` で `provideState` と `provideEffects` を
route の providers に置いているため、この画面へ入ったときだけ state と Effects が
生まれ、離れれば消える。

### なぜadapterを分けるか

ClearML APIの応答は「Taskという汎用の入れ物」で、`hyperparams.Dataset.dataset_version.value`
のように深く、欠けていることもある。これをコンポーネントが直接読むと、
同じ欠損に対して画面ごとに違う振る舞いをするようになる。

adapterの決めごとは3つ。

- 知らない状態は捨てず `unknown` として残す
- 無い値は既定値で埋めず `null` のままにする（「測っていない」と「0だった」を混ぜない）
- 変換は一方向にしか行わない

## 3. 状態遷移

```text
                 openPage
初期 ──────────────────────▶ loading=true
                                │
      overviewLoaded ───────────┼───────────▶ 表示（error=null）
      overviewFailed ───────────┘            loading=false, error=理由
                                             （直前の表示は消さない）

      startRun ─────────────▶ starting=true
        runStarted ─────────▶ run=新しい実行、steps=[]、scores=[]
        startFailed ────────▶ starting=false, error=理由

      （実行中は5秒ごとに）
        runRefreshed ───────▶ run/steps を置き換え、error=null
        refreshFailed ──────▶ error=理由（直前の run/steps は残す）

      scoresLoaded ─────────▶ scores を置き換え

      cancelRun ────────────▶ tasks.stop → runCancelled → 読み直し
        cancelFailed ───────▶ error=理由

      leavePage ────────────▶ 初期状態へ戻す（再取得も止める）
```

決めごと。

- **loading と starting を分ける。** 再読込中でも起動は押せてよいが、
  起動中の二度押しは防ぐ必要がある。1つのフラグでは必ずどちらかが不自然になる
- **成功したら error を消す。** 前の失敗が残ると、成功しているのに赤い文字が出続ける
- **失敗しても直前の結果は消さない。** 取得に失敗しただけで、見えていた実行結果まで
  消える必要はない。消すのは離脱したときだけ
- **走っている間だけ再取得する。** 終わった実行を叩き続けても状態は変わらない
- **離脱したら `takeUntil` で止める。** 付けないと別の画面へ移った後も問い合わせが続く

## 4. 既存画面（Task一覧・詳細）との対応

新しい画面を読む前に、既存のClearML Web側がどう作られているかを対応付けておく。

| 役割 | 既存（experiments） | 新規（quality-pipeline） |
| --- | --- | --- |
| 一覧のComponent | `webapp-common/experiments/experiments.component.ts` | `quality-pipeline.component.ts` |
| 一覧のstate | `reducers/experiments-view.reducer.ts` | `quality-pipeline.reducer.ts` |
| 一覧のEffects | `effects/common-experiments-view.effects.ts` | `quality-pipeline.effects.ts` |
| 詳細のstate | `reducers/common-experiment-info.reducer.ts` | 同じstateの `run` / `steps` |
| API Client | `business-logic/api-services/tasks.service.ts`（生成物） | 同じものを `quality-pipeline-api.service.ts` が包む |
| ClearML API | `tasks.get_all_ex` / `tasks.get_by_id_ex` | 同じ |

違いは2つある。

既存はEffectsを `webapp-common/experiments/effects/` にまとめている。新規は
更新する state と同じ feature 配下へ置いた（`AGENTS.local.md` の指摘に合わせた）。

既存は生成されたAPIモデルをほぼそのまま state に入れている。新規は adapter を挟み、
state には画面用の形しか入れない。

## 5. 動かして確かめる

```bash
# 1. サーバとAgentを起動する
corepack pnpm backend:up

# 2. 複製元になるPipeline Taskを1つ作る（初回のみ）
corepack pnpm ml:pipeline -- --dataset-version 1.0.0 --submit

# 3. Angularを起動して /quality-pipeline を開く
corepack pnpm web:start
```

画面で「Start」を押すと、ClearML Web の PIPELINES 画面にも同じ実行が現れる。
両方を並べて見ると、画面の state と ClearML 側の Task が1対1で対応していることが
確認できる。

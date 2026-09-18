# 実験名の変更と一覧反映 シーケンス図集

詳細パネルのヘッダーで実験名を変更し、左側の実験一覧（カード表示）に新しい名前が出るまでを、観点別に図にした。

元資料: [ngbi-03 実験管理画面で実験名を変更して一覧に新しい名前を反映する](../../ngbi-03-実験管理画面で実験名を変更して一覧に新しい名前を反映する.260918.md)

## 前提

- 対象は詳細パネル表示中（URL が `projects/:projectId/tasks/:experimentId/...`）。
  このとき `minimizedView()` が true になり、一覧はカード表示になる。
- 最大化表示（`:experimentId/output`）でも同じ Action が流れる。
  ただしこのルートでは `ExperimentsComponent` が描画されていないため、一覧の描画は起きない。

## 目次

| No | 資料 | 何を追うか |
| --- | --- | --- |
| 01 | [コンポーネント経路](./01_コンポーネント経路.md) | 入力欄と一覧カードまで、どのコンポーネントを経由するか |
| 02 | [状態経路](./02_状態経路.md) | 名前が Store のどこに置かれ、どの Action で書き換わるか（要点のみ） |
| 03-01 | [編集モードに入る](./03-01_編集モードに入る.md) | クリックから入力可能になるまで |
| 03-02 | [確定して一覧へ反映する](./03-02_確定して一覧へ反映する.md) | Enter / Tab / ✓ からカードの再描画まで（本線） |
| 03-03 | [編集を取り消す](./03-03_編集を取り消す.md) | Esc / × / 外側クリック / 変更なしの確定 |
| 03-04 | [保存されない分岐](./03-04_保存されない分岐.md) | 入力欄の検証・短い名前・フォーム不正・API 失敗 |

## 登場人物の略称

| 略称 | 実体 | ファイル |
| --- | --- | --- |
| User | 操作者 | - |
| EC | ExperimentsComponent | [experiments.component.ts](../../src/app/webapp-common/experiments/experiments.component.ts#L162) |
| ExpTable | sm-experiments-table | [experiments-table.component.ts](../../src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L127) |
| SmTable | sm-table（PrimeNG `p-table` のラッパ） | [table.component.ts](../../src/app/webapp-common/shared/ui-components/data/table/table.component.ts#L118) |
| Card | sm-table-card | [table-card.component.html](../../src/app/webapp-common/shared/ui-components/data/table-card/table-card.component.html#L20) |
| Output | sm-experiment-output（ExperimentOutputComponent / 基底 BaseExperimentOutputComponent） | [base-experiment-output.component.ts](../../src/app/webapp-common/experiments/containers/experiment-ouptut/base-experiment-output.component.ts#L55) |
| InfoHeader | sm-experiment-info-header | [experiment-info-header.component.ts](../../src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.ts#L75) |
| Inline | sm-inline-edit | [inline-edit.component.ts](../../src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.ts#L38) |
| Store | NgRx Store（`experiments` feature の `info` / `view`） | [features/experiments/reducers/index.ts](../../src/app/features/experiments/reducers/index.ts#L30) |
| InfoEff | CommonExperimentsInfoEffects | [common-experiments-info.effects.ts](../../src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L450) |
| TasksApi | ApiTasksService | [tasks.service.ts](../../src/app/business-logic/api-services/tasks.service.ts#L2159) |
| Server | ClearML apiserver | - |

## 最初に押さえる要点

- 入力欄から Store までは **output の連鎖**、Store から一覧カードまでは **Selector と input の連鎖**。二つの線は Store で切れている。
- 一覧は API から再取得しない。`tasks.update` 成功後の `updateExperiment` で該当行だけ差し替える。
- 名前は Store の3か所に置かれ、書き換わるタイミングがそれぞれ違う（[02](./02_状態経路.md)）。

# ExperimentsComponent と ExperimentOutputComponent の違い

## 結論

- **ExperimentsComponent**: Experiment**一覧**画面のコンテナ。
  - `src/app/webapp-common/experiments/experiments.component.ts`
  - テンプレートは `sm-experiment-header` を中心に、テーブルのカラム選択・フィルタ・比較モード（scalars/plots）・自動更新などを扱う。
  - NgRxのselectorを多数importしており（`selectExperimentsList`, `selectTableFilters`, `selectSelectedExperiments` 等）、テーブル状態管理が中心。

- **ExperimentOutputComponent**: 選択した**単一Experimentの詳細出力**画面のコンテナ。
  - `src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.ts`
  - `BaseExperimentOutputComponent`（`src/app/webapp-common/experiments/containers/experiment-ouptut/base-experiment-output.component.ts`、セレクタ `sm-base-experiment-output`）を継承した薄いラッパー。
  - `ExperimentInfoHeaderComponent`（ヘッダー情報）、`GraphSettingsBarComponent`（グラフ設定バー）、`ExperimentInfoNavbarComponent`（ナビバー）、`RouterOutlet`（Console/Scalars/Plots等のサブタブ切替）を組み合わせて1件のExperimentの詳細を表示する。

## 一言でいうと

- ExperimentsComponent = 一覧（テーブル）
- ExperimentOutputComponent = 個別詳細（ヘッダー＋グラフ＋サブタブのRouterOutlet）

## 関連資料

- [03_ExperimentsとExperimentOutputの接続経路.md](./03_ExperimentsとExperimentOutputの接続経路.md) — 両者がどう繋がっているか（ルーティング経路）の資料

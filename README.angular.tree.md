# Angular のフォルダ構成

この文書は、現在の `src/app` を読むための案内図です。ツリーは **2026-09-23 時点の実際の配置**に基づきます。深い階層では代表的なフォルダ・ファイルを示し、省略した場所には `…` を付けています。`containers` や `dumb` はこのコードベースの既存の名前です。

## まず全体

```text
src/
├── main.ts                  # 設定取得後に Angular アプリを起動
├── index.html               # HTML の入口
├── environments/            # 実行環境の設定
├── assets/                  # アプリ側の画像など
└── app/
    ├── app.ts               # 起動時のルートコンポーネント
    ├── app.component.*       # ログイン後のアプリ画面枠
    ├── app.config.ts         # 全体の provider / Router / HTTP など
    ├── app.routes.ts         # 画面 URL の入口
    ├── build-specifics/      # ビルドごとの差し替え
    ├── business-logic/       # ClearML API サービスとデータモデル
    ├── core/                 # アプリ全体の state・Effects・初期化
    ├── features/             # 画面単位の実装・拡張
    ├── layout/               # アプリ側のヘッダー・サイドナビなど
    ├── shared/               # app 側で共有するコード
    └── webapp-common/        # 取り込んだ ClearML Web の共通実装
```

大きな境界は `features/`、`shared/`、`webapp-common/` です。`features/` は画面ごとの入口と実装、`webapp-common/` は多数の既存画面と共通 UI、`app/shared/` はそれらとは別のアプリ側共有コードです。**`app/shared/` と `webapp-common/shared/` は別フォルダ**です。

## `features/`：画面単位

```text
src/app/features/
├── dashboard/               # ダッシュボードの画面入口
├── dashboard-search/        # 全体検索の拡張と provider
├── data-catalog/            # このリポジトリで追加したデータカタログ
├── datasets/                # データセットの route
├── delete-entity/           # 削除操作の Effect
├── experiments/             # 実験画面の拡張・state・provider
├── experiments-compare/     # 実験比較の拡張
├── login/                   # ログイン画面・state
├── models/                  # モデル画面の拡張
├── not-found/               # 404 画面
├── projects/                # プロジェクトの route・拡張・state
├── quality-pipeline/        # このリポジトリで追加した品質パイプライン
├── serving/                 # Serving の拡張
├── settings/                # 設定画面の拡張・state
└── workers-and-queues/     # Worker / Queue の画面・route
```

ここはすべて同じ形ではありません。取り込み由来の画面・拡張と、自作の `quality-pipeline/`・`data-catalog/` が混在します。例えば `projects/projects.routes.ts` は `webapp-common/projects/` のページを読み込み、`experiments/` は `webapp-common/experiments/` の画面や Effect と組み合わせて動きます。したがって、画面の実体が `features/` の中だけで完結するとは限りません。

自作した二つの feature は、ほぼ次の形です。

```text
src/app/features/
├── quality-pipeline/
│   ├── quality-pipeline.routes.ts     # URL と経路内 provider
│   ├── quality-pipeline.model.ts      # 画面で使う型
│   ├── quality-pipeline.consts.ts     # 定数
│   ├── containers/
│   │   └── quality-pipeline-page/     # store と子部品をつなぐ画面
│   ├── components/                    # 表・フォーム・カードなど
│   ├── data-access/
│   │   ├── quality-pipeline-api.service.ts  # API 呼び出し
│   │   └── quality-pipeline.adapter.ts      # API 応答の変換
│   ├── state/                         # actions / reducer / effects / selectors
│   └── styles/
└── data-catalog/
    ├── data-catalog.routes.ts
    ├── data-catalog.model.ts
    ├── data-catalog.consts.ts
    ├── data-catalog.query.ts          # カタログ固有の検索条件
    ├── data-catalog.export.ts         # 書き出し用の整形
    ├── data-catalog.download.ts       # ブラウザへのダウンロード
    ├── data-catalog.surface.ts        # 外向きの画面契約
    ├── containers/                    # 一覧・詳細ページ
    ├── components/                    # 表・フィルタ・詳細部品など
    ├── data-access/                   # API 呼び出しと変換
    ├── state/                         # actions / reducer / effects / selectors
    └── styles/
```

`routes.ts` は画面に入る経路を定義します。この二つの自作 feature では、経路側で NgRx state・Effects・API service を登録します。`state/` は画面の状態、`data-access/` は ClearML API との境界です。`containers/` は状態を読み操作を渡すページ、`components/` は表示や入力を担当する子部品です。

## `webapp-common/`：既存 ClearML Web の共通実装

直下のディレクトリをすべて示します。ここには「共通部品」だけでなく、実験・モデルなどの**画面そのもの**もあります。

```text
src/app/webapp-common/
├── angular-notifier/       # 通知表示
├── assets/                 # フォント・アイコンなど
├── clearml-applications/   # ClearML アプリケーション関連
├── common-search/          # 検索 UI
├── core/                   # 共通の state・Effects・サービス
├── dashboard/              # ダッシュボードの画面部品
├── dashboard-search/       # 全体検索の画面部品
├── dataset-version/        # データセットの版の詳細
├── datasets/               # データセット画面
├── debug-images/           # デバッグ画像
├── enterprise-visibility/  # Enterprise 機能の表示
├── experiments/            # 実験一覧・詳細・出力
├── experiments-compare/    # 実験・モデルの比較
├── layout/                 # 共通のヘッダー・ナビ・パンくず
├── login/                  # ログイン画面部品
├── models/                 # モデル画面
├── nested-project-view/    # 入れ子のプロジェクト表示
├── pipelines/              # Pipeline 一覧
├── pipelines-controller/   # Pipeline 実行詳細
├── project-info/           # プロジェクト概要
├── project-workloads/      # プロジェクトの Workloads
├── projects/               # プロジェクト一覧
├── reports/                # レポート
├── select-model/           # モデル選択
├── serving/                # Serving / Endpoint 画面
├── settings/               # 設定画面部品
├── shared/                 # 複数画面で使う UI・処理
├── styles/                 # 共通テーマ・SCSS
├── tasks/                  # Task の型・定数・関数
├── workers-and-queues/     # Worker / Queue 画面
├── constants.ts
└── user-preferences.ts     # ユーザー設定
```

代表例の `experiments/` は次のように分かれています。

```text
src/app/webapp-common/experiments/
├── experiment-routes.ts      # 一覧・詳細・出力タブの経路
├── experiments.component.*   # 実験一覧の中心コンポーネント
├── actions/                 # 実験操作の NgRx action
├── reducers/                # 一覧・詳細・出力の state
├── effects/                 # 取得・保存などの副作用
├── containers/              # 詳細タブなどの画面側コンポーネント
├── dumb/                    # 表・ヘッダーなどの表示部品
└── shared/                  # 実験機能内で共有する型・部品・サービス
```

ここでの `experiments/shared/` は**実験機能内の共有**です。次の `webapp-common/shared/` は**複数の機能をまたぐ共有**です。

## 二つの `shared/`

```text
src/app/
├── shared/                            # app 側の共有コード
│   ├── clearml/                       # ClearML API の失敗を画面用に整える処理
│   ├── constants/
│   ├── directives/
│   ├── guards/
│   ├── resolvers/
│   ├── services/
│   ├── utils/
│   └── custom-styles.scss
└── webapp-common/
    └── shared/                      # 既存 ClearML Web の共有コード
        ├── components/              # 複合的な共通コンポーネント
        ├── debug-sample/            # 画像・サンプル表示
        ├── directive/
        ├── entity-page/             # 一覧画面の共通土台・削除・フッター
        ├── experiment-graphs/       # 実験グラフ
        ├── experiment-info-header-status-icon-label/
        ├── experiment-info-header-status-progress-bar/
        ├── experiment-status-icon-label/
        ├── experiment-type-icon-label/
        ├── guards/
        ├── pipes/
        ├── portal/
        ├── project-dialog/          # プロジェクト操作ダイアログ
        ├── queue-create-dialog/     # Queue 作成ダイアログ
        ├── services/
        ├── single-graph/
        ├── single-value-summary-table/
        ├── ui-components/           # より小さな共通 UI
        ├── utils/
        └── validators/
```

`webapp-common/shared/` のうち、画面を読むとよく辿る場所は以下です。

```text
src/app/webapp-common/shared/
├── entity-page/
│   ├── base-entity-page.ts           # 一覧ページの共通基底
│   ├── base-entity-header/           # 一覧のヘッダー
│   ├── entity-delete/                # 共通の削除処理とダイアログ
│   ├── entity-footer/                # 選択行に対するフッター
│   └── footer-items/                # フッターの各操作
├── components/
│   ├── charts/                      # チャート
│   ├── custom-columns-list/        # カスタム列
│   ├── markdown-editor/            # Markdown 編集
│   ├── refresh-button/             # 更新ボタン
│   └── …
└── ui-components/
    ├── buttons/
    ├── data/
    │   ├── table/                   # 表本体・列フィルタ・並べ替え
    │   ├── table-card/
    │   └── …
    ├── directives/
    ├── indicators/
    ├── inputs/
    │   ├── inline-edit/            # インライン編集
    │   └── …
    ├── overlay/                     # ダイアログ・通知・オーバーレイ
    ├── panel/                       # カード・メニュー・ドロワー
    ├── tags/                        # タグ表示・操作
    └── template-forms-ui/
```

## その他の app 直下

```text
src/app/
├── business-logic/
│   ├── api-services/        # tasks.service.ts などの ClearML API サービス
│   ├── model/               # API のデータ型を対象別に配置
│   └── services/            # Task・Model 関連のサービス
├── core/
│   ├── actions/
│   ├── reducers/
│   ├── effects/
│   ├── interceptors/
│   ├── services/
│   ├── core.providers.ts    # アプリ全体の store と Effects
│   └── app-init.ts          # 起動時の初期化
├── layout/                  # app 側の画面枠
│   ├── breadcrumbs/
│   ├── header/
│   └── side-nav/
└── build-specifics/         # 環境別の差し替え
```

`webapp-common/core/` にも `actions/`・`reducers/`・`effects/` があります。`app/core/` の設定がそれらを取り込むため、全体 state を追うときは両方を見ます。同様に `layout/` も app 側と `webapp-common/` 側の両方にあります。

## 画面からコードを辿る例

```text
src/main.ts
  → src/app/app.config.ts
  → src/app/app.routes.ts
      ├── /quality-pipeline → features/quality-pipeline/quality-pipeline.routes.ts
      │                       → containers/ → components/・state/・data-access/
      ├── /data-catalog     → features/data-catalog/data-catalog.routes.ts
      │                       → containers/ → components/・state/・data-access/
      └── /projects/:projectId/tasks
                            → webapp-common/experiments/experiment-routes.ts
                            → experiments.component.ts
                            → dumb/・containers/・effects/・reducers/
                            → webapp-common/shared/ui-components/
```

ファイルを探すときの import 別名は `tsconfig.json` にあります。`@features/*` は `src/app/features/*`、`@common/*` は `src/app/webapp-common/*`、`~/*` は `src/app/*` です。例えば `@common/shared/ui-components/data/table` は `webapp-common/shared/` 側を指します。

配置と依存方向の規約は [アーキテクチャ規約](docs/phase7_チーム開発標準/61_アーキテクチャ規約.md) を参照してください。実験画面のコンポーネントの親子関係を追う場合は [ng-■Experiments.md](ng-■Experiments.md) が別途あります。

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

## `business-logic/`：ClearML API とその型

ここは ClearML の API を呼ぶためのコードと、API が受け渡すデータの型を置く場所です。フォルダ名に `business-logic` とありますが、画面固有の業務手順をすべてここに集めているわけではありません。たとえば品質パイプラインの「Task を複製して Queue に入れる」という手順は `features/quality-pipeline/data-access/` にあります。

```text
src/app/business-logic/
├── api-services/
│   ├── tasks.service.ts        # tasks.get_all_ex など、Task API の操作
│   ├── models.service.ts       # Model API の操作
│   ├── projects.service.ts     # Project API の操作
│   ├── …                       # Events・Queues・Workers などの API
│   ├── api-requests.service.ts # 共通の HTTP 呼び出しと応答の取り出し
│   └── api.ts                  # Task API の再エクスポートと ApiOptions
├── model/
│   ├── tasks/                 # Task と Task API の Request・Response
│   ├── models/                # Model と Model API の Request・Response
│   ├── projects/              # Project API の型
│   ├── …                      # API の対象別の型
│   └── api-request.ts         # HTTP 応答の data・meta など
├── services/
│   ├── tasks.service.ts        # Task・Queue の状態やタグに関する判断
│   └── models.service.ts       # Model のタグに関する判断
├── configuration.ts           # API の接続設定とヘッダーの選択
├── variables.ts               # BASE_PATH などの値
├── constants.ts               # 対象エンティティの定数
└── encoder.ts                 # URL 内の + をエンコードする処理
```

### `api-services/`：API 操作と HTTP

`tasks.service.ts` の `ApiTasksService` は、`tasksGetAllEx()`・`tasksClone()` のように ClearML API の操作ごとにメソッドを持ちます。ほかの対象も `models.service.ts` の `ApiModelsService`、`projects.service.ts` の `ApiProjectsService` という対応です。API ごとのファイルは `auth`・`events`・`login`・`models`・`organization`・`pipelines`・`projects`・`queues`・`reports`・`server`・`serving`・`storage`・`tasks`・`users`・`workers` の 15 個です。

各 API サービスはエンドポイントとリクエスト型を選び、`SmApiRequestsService` に HTTP 呼び出しを渡します。たとえば `tasksGetAllEx(request)` は `TasksGetAllExRequest` を受け、`/tasks.get_all_ex` に POST します。共通の `api-requests.service.ts` は `HttpClient` を使い、通常の `post<T>()` では ClearML の応答 `{ data, meta }` から `data` を取り出します。そのため呼び出し元が受け取るのは、通常は外側の `{ data, meta }` ではなく `TasksGetAllExResponse` に相当する中身です。また、`post<T>()` は `withCredentials` を有効にします。HTTP リクエストは [app.config.ts](src/app/app.config.ts) で登録した interceptor も通り、そこではクライアントを示すヘッダーの追加と 401 エラーの処理を行います。

### `model/`：API の入出力型

`model/` は API 対象ごとに分かれます。直下の対象別フォルダは `auth`・`debug`・`events`・`login`・`models`・`organization`・`pipelines`・`projects`・`queues`・`reports`・`server`・`serving`・`storage`・`tasks`・`users`・`workers` です。`api-request.ts` のように `model/` 直下にある共通の型もあります。

`model/tasks/` を例にすると、次の 3 種類を区別すると読みやすくなります。

| 例 | 役割 |
| --- | --- |
| `task.ts`・`taskStatusEnum.ts` | Task 自体の項目と状態の値 |
| `tasksGetAllExRequest.ts` | 一覧取得に渡す検索条件。`project`・`status`・`page_size` など |
| `tasksGetAllExResponse.ts` | 一覧取得で返る `tasks`・`scroll_id` など |

API サービスと多くのモデルは OpenAPI のコード生成に由来します。ただし、このリポジトリには追加・調整されたコードや手書きの共通処理も混在します。生成由来の `ApiTasksService.tasksGetAllEx()` は、内部で `TasksGetAllExResponse` を使っていても、公開シグネチャが `Observable<any>` です。呼び出し側では生成モデルの応答型を明示し、画面が使う項目を adapter で整えます。型注釈だけでは実行時の応答内容を保証できないため、欠損値の扱いも adapter で決めます。

以下は `model/` の **16 分野すべて**の案内です。同じ分野の `XxxRequest.ts` は API に渡す値、`XxxResponse.ts` は返る値、短い名前のファイルはその中で使うエンティティや入れ子の型を表します。各分野の `models.ts` は型の再エクスポート用ですが、`debug/models.ts` は空です。型名が同じでも、`tasks/task.ts` と `reports/task.ts` のように置き場所が違えば別の型なので、import 元を確認します。

#### `auth/`：認証情報と権限

`credentials.ts` はアクセスキー・シークレットキーなどの認証情報、`role.ts` はユーザー権限の値を表します。`authLoginRequest.ts`／`authLoginResponse.ts` は認証トークン取得の入出力、`authValidateTokenResponse.ts` はトークンの有効性と対応するユーザー・会社 ID です。資格情報の作成・編集・失効や、ユーザー作成に使う Request／Response もここにあります。後述の `login/` はログイン画面が利用できる方式の問い合わせが中心です。

#### `debug/`：現在は型定義なし

現状は空の `models.ts` だけです。デバッグ画像やログの型を探す場合は `events/` を、Report の取得結果に含まれるデバッグ画像の型を探す場合は `reports/` を見ます。

#### `events/`：Task が記録したログ・指標・画像

`metricsScalarEvent.ts`・`metricsVectorEvent.ts`・`metricsPlotEvent.ts`・`metricsImageEvent.ts` は数値や可視化データのイベント、`taskLogEvent.ts` はログ 1 件の形です。`eventsGetTaskLatestScalarValuesRequest.ts` は Task ID を渡し、Response は `metrics[] → variants[] → last_value` という入れ子で最新値を返します。系列の履歴、複数 Task の比較、デバッグ画像、プロット、Task ログの取得にもそれぞれ Request／Response があります。`tasks/` が Task 本体なら、こちらは Task に蓄積された観測データです。

#### `login/`：利用できるログイン方式

`loginSupportedModesResponse.ts` は Basic 認証、ゲスト、SSO、認証済みかどうか、サーバー側の問題などを表します。`loginSupportedModesResponseBasic.ts` などはその入れ子の型で、`loginLogoutResponse.ts` はログアウトの応答です。`auth/` のトークン・資格情報と分けて読むと、ログイン画面が何を表示できるかを追いやすくなります。

#### `models/`：Model の登録情報

`model.ts` は ID・名前・所属 Project・作成元 Task・framework・保存先 URI・公開準備の状態・metadata などを持ちます。`modelsGetAllExRequest.ts` は名前・タグ・Project・ページなどでの検索条件、Response の `models[]` は Model の一覧です。作成・更新・移動・アーカイブ・公開などの操作型もあります。`metadataItem.ts` は Model のメタデータ 1 項目で、`tasks/taskModels.ts` は Task 側が参照する Model 情報なので役割が異なります。

#### `organization/`：組織全体の集計と共通情報

`organizationGetEntitiesCountResponse.ts` は Project・Task・Model・Dataset・Report などの件数です。`organizationGetTagsResponse.ts` は組織で使われるタグ、`organizationGetUserCompaniesResponse.ts` は所属会社の情報を返します。`organizationGetProjectWorkloadsRequest.ts` は期間・Project ID・集計軸を指定し、Response の `projects`・`users`・`queues` に `workloads.ts` の合計値と時系列を収めます。個別 Project の詳細型とは分けて読みます。

#### `pipelines/`：Pipeline 実行の API

`pipelinesCheckNewRunRequest.ts` は既存の controller Task と実行先 Project 名を渡し、新しい実行を始められるか確認します。`pipelinesStartPipelineRequest.ts` は元 Task・Queue・引数など、Response は Pipeline ID・投入結果・新規 Project 情報などです。`pipelinesDeleteRunsResponse.ts` は削除成功分と失敗分を別の配列で返します。ここには Pipeline API の入出力型があり、個々の実行を表す Task 自体の型は `tasks/` にあります。

#### `projects/`：Project とその配下の集計

`project.ts` は Project の ID・名前・説明・タグ・既定の成果物出力先・集計値などを表します。一覧 API の `projectsGetAllExResponse.ts` は `projects[]` とスクロール ID を持ち、配列の要素には `projectsGetAllResponseSingle.ts` が使われます。この要素には子 Project や集計値も含まれるため、`project.ts` と同一視しません。作成・更新・削除・移動・統合に加え、タグ・指標・ハイパーパラメータの候補を取得する型もここにあります。

#### `queues/`：実行待ち Queue と投入された Task

`queue.ts` は Queue の ID・名前・タグ・待機中の `Entry[]`・Worker 情報など、`entry.ts` は投入された Task ID と投入時刻を表します。`queuesGetAllExResponse.ts` は Queue 一覧、`queueMetrics.ts` は時刻ごとの Queue 長と平均待ち時間です。Task の追加・除去・別 Queue への移動・順番変更・次の Task の取得などの Request／Response があり、`tasks/` の実行状態とは別に「どの Queue で待つか」を扱います。

#### `reports/`：Report と Report 用の取得データ

`report.ts` は Report の ID・名前・状態・所属 Project・本文・添付資産などを表します。`reportsGetAllExResponse.ts` の一覧プロパティ名は `reports` ではなく `tasks` で、要素型は `Report` です。`reportsGetTaskDataResponse.ts` は関連 Task・プロット・デバッグ画像・指標をまとめて返します。`view.ts`・`filtering.ts` など表示・絞り込み用の型や、Report の作成・公開・共有・移動の操作型もあります。ここにある `task.ts` は Report 用データに含まれる Task の型です。

#### `server/`：ClearML サーバーの情報と設定

`serverInfoResponse.ts` はバージョン・ビルド・API バージョンなど、`serverConfigRequest.ts` は設定の取得対象パスです。`serverReportStatsOptionRequest.ts`／Response は統計送信オプションの設定と有効状態を表します。Task や Project の業務データではなく、接続先サーバーそのものに関する型です。

#### `serving/`：Model の配信 Endpoint

`servingGetEndpointsResponse.ts` は Endpoint 一覧、`endpointStats.ts` は各 Endpoint の Model・URL・インスタンス数・要求数・遅延などです。`servingGetEndpointDetailsResponse.ts` は入力形式や稼働中のインスタンスまで含む詳細、`servingGetEndpointMetricsHistoryResponse.ts` は全体とインスタンス別の履歴です。Container の登録・解除・状態報告に使う Request もあり、`models/` が Model の保存情報なら、こちらは配信中の状態を扱います。

#### `storage/`：成果物の保存先と接続設定

`storage.ts` は保存先の ID・名前・URI・資格情報を表し、`storageGetAllResponse.ts` の `results[]` に並びます。`storageGetSettingsResponse.ts` は AWS・Google・Azure の設定を `aws.ts`・`google.ts`・`azure.ts` で分けて持ち、Bucket／Container の型もあります。保存先の作成・削除・設定変更に使う Request／Response を探す場所で、`assets/` のようなフロントエンドの静的ファイル置き場ではありません。

#### `tasks/`：実験・実行を表す中心的な型

`task.ts` は ID・名前・種類・状態・所属 Project・親 Task・実行設定・出力・タグなどを持ちます。`taskStatusEnum.ts` は `created`・`queued`・`in_progress`・`completed` などの状態です。`execution.ts` は実行設定、`artifact.ts` はその中の成果物、`output.ts` は実行結果の参照先を表します。`tasksGetAllExRequest.ts` は検索条件・ページ・取得項目（`only_fields`）、Response は `tasks[]` と `scroll_id` を持ちます。複製、Queue 投入、停止、公開、設定やハイパーパラメータの編集など多数の操作型もここです。`only_fields` を指定した応答では、`Task` のすべての項目が返るとは限りません。

#### `users/`：ユーザー情報と個人設定

`user.ts` はユーザー ID・名前・メールアドレス・役割など、`usersGetAllExResponse.ts` はユーザー一覧です。`usersGetCurrentUserResponse.ts` は現在のユーザーに加えて設定や開始時の情報を含み、`usersGetPreferencesResponse.ts` は個人設定を返します。ユーザー作成・更新・削除、招待情報の取得に関わる型もあります。認証トークンや資格情報の形式は `auth/` を見ます。

#### `workers/`：Task を実行する Worker の稼働状況

`worker.ts` は Worker ID・所属・接続先 Queue・現在の Task・最終報告時刻などを表します。`workersGetStatsResponse.ts` と `machineStats.ts` は CPU・GPU・メモリなどの利用状況、`workersGetActivityReportResponse.ts` は稼働の時系列です。Worker の登録・解除・状態報告、取得する指標キーの指定に使う Request／Response もあります。`queues/` の待機列と合わせると、投入された Task をどの Worker が処理するかを追えます。

`model/` 直下には分野別フォルダ以外に 4 ファイルあります。`api-request.ts` は共通 HTTP 応答の `data`・`meta` と汎用リクエスト、`al-task.ts` は `Task` の一部を画面で使う形に差し替えた `ITask` です。`LoginModeResponse.ts` と `FixedUserModeExResponse.ts` は認証方式やゲスト・サーバーエラー情報を補う型です。

### `services/`：API サービスと名前が似ている別の処理

`api-services/tasks.service.ts` の **`ApiTasksService` は通信**を担当します。一方、`services/tasks.service.ts` の **`BlTasksService` は判断**を担当します。後者には、既定の Queue を探す、Task を Queue に投入・解除できるか判定する、`archived` などのタグを操作する、といったメソッドがあります。`services/models.service.ts` の `BlModelsService` は Model の `archived` タグを操作します。ファイル名が同じ `tasks.service.ts` でも、import 元とクラス名で見分けます。

### 画面から API まで辿る例

品質パイプライン画面で実行中のステップを読む場合は、次の経路です。

```text
features/quality-pipeline/state/quality-pipeline.effects.ts
  → features/quality-pipeline/data-access/quality-pipeline-api.service.ts の getSteps()
  → business-logic/api-services/tasks.service.ts の tasksGetAllEx()
  → business-logic/api-services/api-requests.service.ts の post<T>()
  → HttpClient → ClearML API の /tasks.get_all_ex
  → model/tasks/tasksGetAllExResponse.ts の型で応答を読む
  → features/quality-pipeline/data-access/quality-pipeline.adapter.ts の toStep()
  → 画面用の PipelineStep
```

`getSteps()` は「親 Task の ID」「取得する項目」「並び順」などを API の検索条件に変え、返った `Task` を画面用の `PipelineStep` に変換します。このような画面固有の組み立ては `features/*/data-access/` が担当します。[アーキテクチャ規約](docs/phase7_チーム開発標準/61_アーキテクチャ規約.md) では `business-logic/` を取り込み済みの凍結領域とし、新しい feature が生成 API に触れる場所を境界ファイルに限定しています。

## その他の app 直下

```text
src/app/
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

# 実験管理画面（ExperimentsComponent）シーケンス図集

ClearML Web UI の「Tasks 一覧画面」を構成する `ExperimentsComponent` について、
関心事ごとにシーケンス図を分けて収録した資料。

対象コンポーネント: [experiments.component.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/experiments/experiments.component.ts:142)

## 資料の分け方

一枚の図にすべての登場人物を載せると読めなくなるため、次の5系統に分けた。
同じ操作でも系統によって注目する線が違うので、同じ操作が複数の図に登場する。

| 系統 | ディレクトリ | 何を追うか |
| --- | --- | --- |
| コンポーネントの繋がり | [01_コンポーネント連携/](./01_コンポーネント連携/) | 親子コンポーネント間の input / output と、DOM イベントがどこまで登るか |
| 状態保持の繋がり | [02_状態保持/](./02_状態保持/) | 値の原本がどこにあるか（URL / Store / サーバ保存の設定 / localStorage / コンポーネント内） |
| ng-content・ng-template の繋がり | [03_テンプレート投影/](./03_テンプレート投影/) | テンプレートが誰から誰へ渡り、どこで実体化するか |
| バックエンドデータとの経路 | [04_バックエンド経路/](./04_バックエンド経路/) | Action から HTTP リクエストまでと、応答が画面に戻るまで |
| 部品ごとの到達経路 | [05_部品別経路/](./05_部品別経路/) | ある部品まで辿り着くコンポーネント経路と、テーブルの操作別の流れ |

## 目次

### 01 コンポーネントの繋がり

- [01-01 画面初期化とビュー構築](./01_コンポーネント連携/01-01_画面初期化とビュー構築.md)
- [01-02 行クリックから Info パネル表示まで](./01_コンポーネント連携/01-02_行クリックからInfoパネル表示.md)
- [01-03 ヘッダー操作の伝播](./01_コンポーネント連携/01-03_ヘッダー操作の伝播.md)
- [01-04 コンテキストメニューの起動](./01_コンポーネント連携/01-04_コンテキストメニューの起動.md)
- [01-05 フッターからの一括操作](./01_コンポーネント連携/01-05_フッターからの一括操作.md)
- [01-06 比較モードへの切替](./01_コンポーネント連携/01-06_比較モードへの切替.md)

### 02 状態保持の繋がり

- [02-01 状態の五つの置き場所](./02_状態保持/02-01_状態の五つの置き場所.md)
- [02-02 URL から Store への初期化](./02_状態保持/02-02_URLからStoreへの初期化.md)
- [02-03 操作から URL への書き戻し](./02_状態保持/02-03_操作からURLへの書き戻し.md)
- [02-04 ユーザープリファレンスの永続化](./02_状態保持/02-04_ユーザープリファレンスの永続化.md)
- [02-05 選択状態の四系統](./02_状態保持/02-05_選択状態の四系統.md)
- [02-06 スクロールIDとページング](./02_状態保持/02-06_スクロールIDとページング.md)

### 03 ng-content・ng-template の繋がり

- [03-01 テンプレート受け渡しの全体像](./03_テンプレート投影/03-01_テンプレート受け渡しの全体像.md)
- [03-02 pTemplate と contentChildren](./03_テンプレート投影/03-02_pTemplateとcontentChildren.md)
- [03-03 contextMenuTemplate の逆流](./03_テンプレート投影/03-03_contextMenuTemplateの逆流.md)
- [03-04 ng-content によるカード組み立て](./03_テンプレート投影/03-04_ng-contentによるカード組み立て.md)
- [03-05 ヘッダーへのテンプレート注入](./03_テンプレート投影/03-05_ヘッダーへのテンプレート注入.md)

### 04 バックエンドデータとの経路

- [04-01 一覧取得の全経路](./04_バックエンド経路/04-01_一覧取得の全経路.md)
- [04-02 自動更新と追い読み](./04_バックエンド経路/04-02_自動更新と追い読み.md)
- [04-03 フィルタ選択肢の取得](./04_バックエンド経路/04-03_フィルタ選択肢の取得.md)
- [04-04 詳細パネルの二段取得](./04_バックエンド経路/04-04_詳細パネルの二段取得.md)
- [04-05 一括操作とCSV出力](./04_バックエンド経路/04-05_一括操作とCSV出力.md)

### 05 部品ごとの到達経路

部品の住所を追う系統。テーブルは操作単位で分けてある（索引は 05-10）。

- [05-00 部品マップと読み方](./05_部品別経路/05-00_部品マップと読み方.md)
- [05-01 ヘッダーまでの経路](./05_部品別経路/05-01_ヘッダーまでの経路.md)
- [05-02 テーブル本体までの経路](./05_部品別経路/05-02_テーブル本体までの経路.md)
- [05-03 セルまでの経路](./05_部品別経路/05-03_セルまでの経路.md)
- [05-04 列ヘッダーまでの経路](./05_部品別経路/05-04_列ヘッダーまでの経路.md)
- [05-05 カードビューまでの経路](./05_部品別経路/05-05_カードビューまでの経路.md)
- [05-06 情報パネルまでの経路](./05_部品別経路/05-06_情報パネルまでの経路.md)
- [05-07 フッターまでの経路](./05_部品別経路/05-07_フッターまでの経路.md)
- [05-08 コンテキストメニューまでの経路](./05_部品別経路/05-08_コンテキストメニューまでの経路.md)
- [05-10 テーブル操作の一覧](./05_部品別経路/05-10_テーブル操作の一覧.md)
- [05-11 行クリックとダブルクリック](./05_部品別経路/05-11_行クリックとダブルクリック.md)
- [05-12 チェックボックス選択と全選択](./05_部品別経路/05-12_チェックボックス選択と全選択.md)
- [05-13 列ソート](./05_部品別経路/05-13_列ソート.md)
- [05-14 列フィルタ](./05_部品別経路/05-14_列フィルタ.md)
- [05-15 列の並べ替えと幅変更](./05_部品別経路/05-15_列の並べ替えと幅変更.md)
- [05-16 追い読み](./05_部品別経路/05-16_追い読み.md)
- [05-17 右クリックメニュー](./05_部品別経路/05-17_右クリックメニュー.md)
- [05-18 キーボード操作とフォーカス](./05_部品別経路/05-18_キーボード操作とフォーカス.md)
- [05-19 カードビューの操作](./05_部品別経路/05-19_カードビューの操作.md)
- [05-20 CSVダウンロード](./05_部品別経路/05-20_CSVダウンロード.md)

## 登場人物の略称

図の `participant` は全資料で次の略称に統一している。

| 略称 | 実体 | ファイル |
| --- | --- | --- |
| User | 操作者 | - |
| Router | Angular Router | - |
| EC | ExperimentsComponent | [experiments.component.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/experiments/experiments.component.ts:142) |
| Base | BaseEntityPageComponent（ECの基底） | [base-entity-page.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/shared/entity-page/base-entity-page.ts:57) |
| Header | sm-experiment-header | [experiment-header.component.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/experiments/dumb/experiment-header/experiment-header.component.ts) |
| ExpTable | sm-experiments-table | [experiments-table.component.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts:115) |
| SmTable | sm-table（PrimeNG p-table のラッパ） | [table.component.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/shared/ui-components/data/table/table.component.ts) |
| Footer | sm-entity-footer | [entity-footer.component.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/shared/entity-page/entity-footer/entity-footer.component.ts) |
| Menu | sm-experiment-menu-extended | [experiment-menu-extended.component.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/features/experiments/containers/experiment-menu-extended/experiment-menu-extended.component.ts:27) |
| Store | NgRx Store（`experiments` feature） | [reducers/index.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/experiments/reducers/index.ts) |
| ViewEff | CommonExperimentsViewEffects | [common-experiments-view.effects.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts) |
| InfoEff | CommonExperimentsInfoEffects | [common-experiments-info.effects.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts) |
| MenuEff | CommonExperimentsMenuEffects | [common-experiments-menu.effects.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/experiments/effects/common-experiments-menu.effects.ts) |
| RouterEff | RouterEffects | [router.effects.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/core/effects/router.effects.ts:28) |
| TasksApi | ApiTasksService | [tasks.service.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/business-logic/api-services/tasks.service.ts:126) |
| ProjApi | ApiProjectsService | [projects.service.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/business-logic/api-services/projects.service.ts) |
| Http | SmApiRequestsService → HttpClient | [api-requests.service.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/business-logic/api-services/api-requests.service.ts:11) |
| Server | ClearML apiserver | - |

## 最初に押さえる原則

`ExperimentsComponent` は API を直接呼ばない。操作は必ず `store.dispatch()` で Action になり、
Effects が HTTP を叩き、結果は Reducer 経由で Selector から戻る。
そのため 01 の図（コンポーネント連携）は Store で線が途切れ、04 の図（バックエンド経路）が Store から先を引き継ぐ。

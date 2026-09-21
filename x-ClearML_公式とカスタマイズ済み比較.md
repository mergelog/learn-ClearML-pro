# ClearML Web 公式 vs カスタマイズ版 — `src/app` 差分調査

| 項目 | 内容 |
|---|---|
| カスタマイズ版 | `/Users/yasu/work/mergelog/learn-ClearML-pro` (HEAD `6d5da3b`, version 2.5.0) |
| 公式 | `/Users/yasu/work/mergelog/ClearML-official-20260921` (HEAD `067b4851`, version 2.5.0) |
| fork base | `refs/tags/v2.5` / `48b61702f703`（`upstream.json` の記録どおり） |
| 公式側の上流進捗 | fork base から **1コミットのみ**（`067b4851 update dependencies to fix security advisory`）。`src/app` には触れていない |
| 調査対象 | `src/app` 配下のみ（`x-docs` 等の増設物は対象外） |
| 調査日 | 2026-09-21 |

つまり **`src/app` の差分はすべてカスタマイズ側で入れたもの**であり、上流が進んだことによる差は含まれていない。

---

## 0. 結論（先に要点）

**「そんなに変化ない」という見立ては、状態管理・コンポーネント構造については正しい。** 公式の既存 Store／既存コンポーネントは1つも削られておらず、置き換えられてもいない。差分の実体は次の3つに切り分けられる。

1. **新規 feature 2本の増設**（`features/data-catalog`, `features/quality-pipeline`）… 追加物のほぼ全量。18クラス・NgRx feature 2本・5,393行。既存コードのロジックには割り込んでいない（既存側の変更は、サイドナビ・モデル/データセット画面の導線リンク3箇所と `app.routes.ts` の lazy route 登録だけ）。
2. **パスエイリアスの改名**（`~/features/...` → `@features/...`）… 共通ファイル差分173件のうち **134件はこれ1行だけ**。挙動に影響しない。
3. **Angular 21→22 追随に伴う API 置き換え**… 公式は Angular 21 / NgRx 21 / PrimeNG 21 / TS 5.9、カスタマイズ版は **Angular 22 / NgRx 22 / PrimeNG 22 / TS 6**。`ComponentFactoryResolver` の撤去、PrimeNG の signal 化 API 追随などがここに属する。

**公式にしか無いもの（＝カスタマイズ側で消したもの）は実質 4ファイル・1シンボルだけ**で、うち1つは公式でも誰も使っていない dead code である。

---

## 1. ファイル数サマリ

| 区分 | 件数 | 内訳 |
|---:|---:|---|
| `src/app` 総ファイル数（カスタマイズ版） | 2,512 | — |
| `src/app` 総ファイル数（公式） | 2,439 | — |
| **カスタマイズ版にしか無い** | **77** | 新規 feature 2本 = 64／`.md`（解説・調査メモ）= 7／`.ts` = 6 |
| **公式にしか無い** | **4** | `business-logic.providers.ts` + `.spec.ts` 3本 |
| 両方にある | 2,435 | うち内容一致 2,262 |
| 　└ 内容が違う | 173 | **エイリアス改名のみ = 134** ／ 実質差分 = **39** |
| 実質差分の行数合計 | 368行 | 39ファイル分。1ファイル平均9行 |

新規 feature 2本の規模：

| feature | `.ts` | `.html` | `.scss` | `.json` | 総行数 |
|---|---:|---:|---:|---:|---:|
| `features/data-catalog` | 20 | 7 | 8 | 1 | 3,458 |
| `features/quality-pipeline` | 15 | 6 | 7 | 0 | 1,897 |
| 合計 | 35 | 13 | 15 | 1 | **5,393** |

---

## 2. 片方にしかないコンポーネント

デコレータ付きクラスの総数は **カスタマイズ版 569 / 公式 551**。差の18クラスはすべてカスタマイズ版側の追加で、**公式にしか無いコンポーネント／ディレクティブ／サービス／パイプは0件**。既存クラスの selector 変更・ファイル移動も（後述の `AppComponent` 1件を除き）0件。

### 2.1 カスタマイズ版にしか無いクラス（18件）

| # | クラス | 種別 | selector | feature |
|---:|---|---|---|---|
| 1 | `DataCatalogPageComponent` | Component | `sm-data-catalog-page` | data-catalog（container） |
| 2 | `CatalogAssetDetailPageComponent` | Component | `sm-catalog-asset-detail-page` | data-catalog（container） |
| 3 | `CatalogAssetsTableComponent` | Component | `sm-catalog-assets-table` | data-catalog |
| 4 | `CatalogFiltersComponent` | Component | `sm-catalog-filters` | data-catalog |
| 5 | `CatalogAssetFactsComponent` | Component | `sm-catalog-asset-facts` | data-catalog |
| 6 | `CatalogLineageComponent` | Component | `sm-catalog-lineage` | data-catalog |
| 7 | `CatalogMetadataFormComponent` | Component | `sm-catalog-metadata-form` | data-catalog |
| 8 | `QualityPipelinePageComponent` | Component | `sm-quality-pipeline-page` | quality-pipeline（container） |
| 9 | `PipelineStepsTableComponent` | Component | `sm-pipeline-steps-table` | quality-pipeline |
| 10 | `EvaluationScoresTableComponent` | Component | `sm-evaluation-scores-table` | quality-pipeline |
| 11 | `ProductionModelCardComponent` | Component | `sm-production-model-card` | quality-pipeline |
| 12 | `RunSummaryComponent` | Component | `sm-run-summary` | quality-pipeline |
| 13 | `StartRunFormComponent` | Component | `sm-start-run-form` | quality-pipeline |
| 14 | `DataCatalogApiService` | Injectable | — | data-catalog（data-access） |
| 15 | `CatalogDownloadService` | Injectable | — | data-catalog |
| 16 | `QualityPipelineApiService` | Injectable | — | quality-pipeline（data-access） |
| 17 | `DataCatalogEffects` | Injectable | — | data-catalog（state） |
| 18 | `QualityPipelineEffects` | Injectable | — | quality-pipeline（state） |

内訳：Component 13／API・補助サービス 3／NgRx Effects 2。

### 2.2 公式にしか無いファイル（4件）

| ファイル | 種別 | 消した影響 |
|---|---|---|
| `business-logic/business-logic.providers.ts` | providers 配列 | **なし**。公式側でも定義のみで参照0件（dead code）。§7.1 参照 |
| `features/dashboard/dashboard.component.spec.ts` | spec | 公式の唯一の jasmine 依存 spec。vitest 移行に伴い削除 |
| `features/experiments/shared/services/clone-naming.service.spec.ts` | spec | 同上 |
| `features/settings/containers/admin/usage-stats/usage-stats.component.spec.ts` | spec | 同上 |

### 2.3 既存コンポーネントへの割り込み（導線リンクのみ）

新 feature は既存画面を書き換えずに増設されているが、到達経路として3箇所だけ既存テンプレートに追記がある。

| ファイル | 追記内容 |
|---|---|
| `layout/side-nav/side-nav.component.html` | `/quality-pipeline`・`/data-catalog` へのサイドナビ `<a>` 2本（+14行） |
| `webapp-common/models/dumbs/model-info-header/model-info-header.component.html` | `['/data-catalog','model',modelId]` への導線。併せて `@if (model()?.id; as modelId)` へ変更、`RouterLink` を `imports` に追加 |
| `webapp-common/dataset-version/open-dataset-version-details/open-dataset-version-details.component.html` | `['/data-catalog','dataset',entity().id]` への導線。`RouterLink` を `imports` に追加 |
| `app.routes.ts` | `quality-pipeline` / `data-catalog` の lazy route 2本（`data: {search: false}`） |

---

## 3. 片方にしかない NgRx Store

### 3.1 feature state の登録状況

`provideState` の呼び出しは **公式 25箇所／カスタマイズ版 27箇所**（`provideEffects` は 24/26）。差は追加された2本のみで、**既存の feature key・登録場所・reducer は25箇所すべて一致**（`StoreModule.forFeature` / `EffectsModule.forFeature` は両者0件、すべて standalone providers 方式）。

| feature key | 登録場所 | 公式 | カスタマイズ版 |
|---|---|:-:|:-:|
| `app` / `auth` / `singleGraph` / `colorsPreference` | `app.config.ts` | ○ | ○ |
| `search`（dashboard-search） | `features/dashboard-search/dashboard-search.providers.ts` | ○ | ○ |
| `dashboard` | `features/dashboard/dashboard.routes.ts` | ○ | ○ |
| `EXPERIMENTS_STORE_KEY` | `features/experiments/shared/experiments.providers.ts` 他3箇所 | ○ | ○ |
| `settingsFeatureKey` | `features/settings/settings.providers.ts` | ○ | ○ |
| `debugImages` / `debugSample` | `webapp-common/debug-images`, `.../shared/debug-sample` | ○ | ○ |
| `COMPARE_STORE_KEY` | `webapp-common/experiments-compare/experiments-compare.providers.ts` | ○ | ○ |
| `selectQueue` | `webapp-common/experiments/shared/components/select-queue` | ○ | ○ |
| `MODELS_STORE_KEY` | `webapp-common/models/models.providers.ts` | ○ | ○ |
| `projects` | `webapp-common/projects`, `webapp-common/pipelines` | ○ | ○ |
| `REPORTS_KEY` | `webapp-common/reports/reports.providers.ts` | ○ | ○ |
| `selectModel` | `webapp-common/select-model/select-model.providers.ts` | ○ | ○ |
| `servingFeatureKey` | `webapp-common/serving/serving.providers.ts` | ○ | ○ |
| `deleteEntityDialog` / `projectCreateDialog` / `queueCreateDialog` | `webapp-common/shared/...` | ○ | ○ |
| `workersAndQueues` | `webapp-common/workers-and-queues/workers-and-queues.providers.ts` | ○ | ○ |
| **`dataCatalog`** | **`features/data-catalog/data-catalog.routes.ts`** | **×** | **○** |
| **`qualityPipeline`** | **`features/quality-pipeline/quality-pipeline.routes.ts`** | **×** | **○** |

`createFeatureSelector` に渡している feature key 文字列の集合も完全一致（`commonSearch` / `dashboard` / `debugImages` / `debugSample` / `deleteEntityDialog` / `projectCreateDialog` / `queueCreateDialog` / `search` / `selectModel` / `singleGraph`）。

### 3.2 NgRx API 使用量の差

| API | カスタマイズ版 | 公式 | 差 | 差の出どころ |
|---|---:|---:|---:|---|
| `createFeature` | 5 | 3 | +2 | `dataCatalogFeature`, `qualityPipelineFeature` |
| `createReducer` | 82 | 78 | +4 | 新 feature 2本＋その spec |
| `createActionGroup` | 14 | 10 | +4 | 同上 |
| `createAction` | 666 | 662 | +4 | 同上 |
| `createSelector` | 517 | 505 | +12 | 新 feature の派生セレクタ |
| `createEffect` | 331 | 315 | +16 | 新 feature の Effects（7 + 7 ＋ spec） |
| `provideState`（import 文含む出現数） | 51 | 47 | +4 | 呼び出し箇所ベースでは 27 / 25（+2） |
| `provideEffects`（同） | 52 | 48 | +4 | 呼び出し箇所ベースでは 26 / 24（+2） |
| `Store<...>`（型引数付き） | 3 | 5 | **-2** | 削除した `dashboard.component.spec.ts` 内の `SpyObj<Store<any>>` 2行のみ。プロダクトコードは同一 |
| `ActionReducerMap` | 8 | 8 | 0 | — |

**既存 Store への action / selector / reducer の追加・削除は0件。** エクスポートシンボル全体（3,324 vs 3,193）を突き合わせても、新 feature 外で増えたのは §5 の4シンボルだけである。

### 3.3 追加された Store 2本の構造

どちらも `createActionGroup` + `createFeature`（`createReducer`）+ 派生セレクタ分離という同一の型で書かれている。

| | `dataCatalog` | `qualityPipeline` |
|---|---|---|
| 定数 | `DATA_CATALOG_FEATURE = 'dataCatalog'` | `QUALITY_PIPELINE_FEATURE = 'qualityPipeline'` |
| actions | `dataCatalogActions`（`createActionGroup`, source `'Data Catalog'`, 15 event） | `qualityPipelineActions`（source `'Quality Pipeline'`, 14 event） |
| reducer | `dataCatalogFeature`（190行） | `qualityPipelineFeature`（136行） |
| feature から取り出すセレクタ | `selectFilter` `selectAssets` `selectHasMore` `selectProjects` `selectAvailableTags` `selectDetail` `selectLineage` `selectLoading` `selectDetailLoading` `selectSaving` `selectError` | `selectTemplate` `selectRun` `selectSteps` `selectStepsTruncated` `selectScores` `selectProductionModel` `selectLoading` `selectStarting` `selectCancelling` `selectError` |
| 派生セレクタ（`createSelector`） | `selectFilterIsEmpty` `selectEmptyReason` `selectDetailAsset` `selectCanSave` `selectLineageNodes` `selectLineageIsPartial`（6本） | `selectCanStart` `selectRunInProgress` `selectCanCancel` `selectRunIsTemplate`（4本） |
| Effects | `loadList` `syncUrl` `loadOptions` `loadDetail` `loadLineage` `saveMetadata` `reloadAfterSave`（7本） | `loadOverview` `startRun` `followRun` `refreshRun` `loadScores` `cancelRun` `refreshAfterCancel`（7本）＋ private `follow()` / `refresh()` |
| 設計上の特徴（コメントより） | 条件変更→URL→再取得の1本経路、失敗を用途別に分けた action、保存は楽観更新しない（ADR 008） | 読み込み中／起動中／停止中を別フラグで保持し二度押しを防ぐ、失敗しても直前結果を消さない |

`selectSignal`（`store.selectSignal`）は公式でも既に99ファイルで使われている既存流儀で、新 feature も28箇所でこれに従っている（**新しい状態管理流儀の持ち込みではない**）。

---

## 4. 片方にしかない Angular の関数・アノテーション

`src/app` 内の全 import 文からシンボルを抽出して集合比較した結果、**差はわずか7シンボル**（共通350シンボル）。npm パッケージ単位では **差0**（新規ライブラリの持ち込みも撤去もない）。

| シンボル | カスタマイズ版 | 公式 | 箇所 | 理由 |
|---|:-:|:-:|---|---|
| `createComponent`（`@angular/core`） | ○ | × | `webapp-common/shared/services/dom-service.service.ts` | Angular 22 対応。`ComponentFactoryResolver` の置き換え |
| `EnvironmentInjector`（`@angular/core`） | ○ | × | 同上 | 同上（`createComponent` の必須引数） |
| `ComponentFactoryResolver`（`@angular/core`） | × | ○ | 同上 | **Angular 22 で撤去された API**。公式は 21 なので残っている |
| `withInterceptorsFromDi`（`@angular/common/http`） | ○ | × | `app.config.ts` | Angular 22 では `HttpClient` が `providedIn:'root'` のため、これを付けないと `HTTP_INTERCEPTORS`（`WebappInterceptor`）が黙って無効化される。コード中の日本語コメントで明記済み |
| `DOCUMENT`（`@angular/common`） | ○ | × | `features/data-catalog/data-catalog.download.ts` | 新 feature のファイル DL 実装 |
| `ParamMap`（`@angular/router`） | ○ | × | `features/data-catalog/containers/catalog-asset-detail-page/...` | 新 feature |
| `fakeAsync` / `tick` / `waitForAsync`（`@angular/core/testing`） | × | ○ | 削除した spec 2本 | vitest 移行で削除。プロダクトコードには無関係 |

### 4.1 デコレータの使用数（`@X(` の実数）

| デコレータ | カスタマイズ版 | 公式 | 差 |
|---|---:|---:|---:|
| `@Component` | 352 | 339 | **+13**（新 feature の13コンポーネント。既存側は増減なし） |
| `@Injectable` | 102 | 97 | **+5**（API サービス2・DL サービス1・Effects 2） |
| `@Directive` | 40 | 40 | 0 |
| `@Pipe` | 81 | 81 | 0 |
| `@NgModule` | 1 | 1 | 0 |
| `@Input` | 153 | 153 | **0** |
| `@Output` | 65 | 65 | **0** |
| `@ViewChild` | 31 | 31 | **0** |
| `@HostListener` | 20 | 20 | **0** |

### 4.2 Signals / 関数 API の使用量

| API | 差 | 補足 |
|---|---|---|
| `input()` | +14 | すべて新 feature 内 |
| `computed()` / `effect()` | +3 / +4 | すべて新 feature 内 |
| `toSignal()` | +7 | すべて新 feature 内 |
| `signal()` `model()` `viewChild()` `viewChildren()` `contentChild()` `linkedSignal()` `resource()` `rxResource()` `untracked()` `afterNextRender()` `forwardRef()` | **±0** | 既存側に変更なし |
| `toObservable()` `takeUntilDestroyed()` `DestroyRef` | ±0 | — |
| `ChangeDetectorRef` | 使用ファイル **+1** | `experiment-info-execution.component.ts`（§5）のみ |
| `@ngrx/signals` 系（`signalStore` `signalStoreFeature` `withState` `withMethods` `withComputed` `withReducer` `eventGroup` `injectDispatch` 等） | **±0（使用9ファイルが完全一致）** | 公式が既に signalStore 方式を一部で採用済み。新 feature 2本はそれを使わず従来の `createFeature` 方式で書かれている |

つまり **「片方にしか無い Angular の書き方」は存在しない**。新 feature も既存と同じ standalone + signal inputs + `selectSignal` 流儀で書かれている。

---

## 5. 上記以外の状態管理関数

新 feature 外で追加された state 関連のコードは、**純関数への切り出し2件だけ**（＋新 feature 内の純関数群）。

| 追加物 | ファイル | 内容 |
|---|---|---|
| `createExecutionRequirementsState()` / `interface ExecutionRequirementsState` | `webapp-common/experiments/containers/experiment-info-execution/execution-requirements-state.ts`（新規、spec 付き） | `ExperimentInfoExecutionComponent` の subscribe 内に直書きされていた「requirements の選択肢・選択値・編集可否・リセット tooltip の算出」を純関数へ抽出。`options` / `selected` / `editable` / `resetTooltip` の4値を返す |
| `describeClearmlFailure()` / `UNEXPLAINED_FAILURE` | `shared/clearml/clearml-failure.ts`（新規、spec 付き） | サーバ応答から失敗理由の文字列を導出。新 feature の `*Failed` action の `reason` 生成に使用 |

呼び出し側（`experiment-info-execution.component.ts`、実質差分31行・最大の変更ファイル）では次のようになっている。

| 公式 | カスタマイズ版 |
|---|---|
| `private requirementLabels = {pip:'PIP', …}` をコンポーネントが保持 | ラベル表は純関数側へ移動（コンポーネントから削除） |
| `if (formData) { …算出をインラインで… }` | `const s = createExecutionRequirementsState(formData, this.selectedRequirement)` の4値代入 |
| （なし） | `inject(ChangeDetectorRef)` + `markForCheck()` をコメント付きで追加（タスク切替時にコンポーネントが再利用され再描画されない問題への対処） |

> ⚠ **挙動差が1つある**：公式は `formData` が falsy のとき算出を丸ごとスキップし前回値を保持したが、抽出後は `options: []` / `selected: 'pip'` / `editable: true` / `resetTooltip: ''` を返して**上書きする**。実験を切り替えた瞬間の中間状態で見え方が変わり得る（`markForCheck()` 追加の目的からすると意図的なリセットに見えるが、ここだけは仕様として明示しておくのが安全）。

### 5.1 新 feature 内の状態導出用の純関数（NgRx 外）

新 feature は「Store に入れる形」と「URL・API から state を導く関数」を明確に分離している。これらは公式側に対応物が無い。

| ファイル | 役割 | 主な関数 |
|---|---|---|
| `data-catalog/data-catalog.query.ts` | URL ⇄ filter 変換（条件をURLへ載せる経路の中核） | `fromQueryParams` `toQueryParams` `toReferenceUrl` `isDefaultFilter` `sameFilter` |
| `data-catalog/data-catalog.model.ts` | state の型と初期値 | `DataCatalogState` `initialDataCatalogState` `emptyCatalogFilter` `isEmptyFilter` `CATALOG_ASSET_KINDS` |
| `data-catalog/data-access/data-catalog.adapter.ts` | ClearML API 応答 → ドメイン型 | `toDatasetAsset` `toRunAsset` `toModelAsset` `toDatasetDetail` `toRunDetail` `toModelDetail` `toTaskState` `toModelState` `readDatasetVersion` `readRuntimeVersion` |
| `data-catalog/data-catalog.export.ts` | エクスポート文書の生成 | `catalogExportDocument` `catalogExportText` `catalogExportFilename` |
| `data-catalog/data-catalog.surface.ts` | 公開インターフェースの固定と差分検知 | `catalogSurface` `surfaceDrift`（+ `data-catalog.surface.published.json`） |
| `quality-pipeline/quality-pipeline.model.ts` | state の型・初期値・状態判定 | `QualityPipelineState` `initialQualityPipelineState` `isRunning` `isUnfinished` `RUNNING_STATUSES` `UNFINISHED_STATUSES` |
| `quality-pipeline/data-access/quality-pipeline.adapter.ts` | ClearML API 応答 → ドメイン型 | `toStatus` `toTemplate` `toRun` `toStep` `toProductionModel` `toScores` |

`ComponentStore` と独自 state クラスは両者とも未使用。`@ngrx/signals` の `signalStore` 方式は **公式が既に9ファイルで採用しており、カスタマイズ版もその9ファイルが完全一致**（増減0）。

| `@ngrx/signals` 使用ファイル（両者共通・9件） |
|---|
| `webapp-common/core/state/view.store.ts` / `view.events.ts` |
| `webapp-common/experiments/containers/experiment-output-log/experiment-output-log.store.ts` / `...component.ts` |
| `webapp-common/experiments-compare/containers/select-experiments-for-compare/select-task-store.ts` / `table-store.ts` / `...component.ts` |
| `webapp-common/shared/project-dialog/project-settings/project-settings-dialog.store.ts` |
| `features/dashboard-search/project-settings-dashboard-search-permissions.store.ts` |

新 feature 2本はこの signalStore 方式を採らず、`createActionGroup` + `createFeature` の従来型で書かれている（既存の大多数の feature と同じ流儀）。

---

## 6. 共通173ファイルの差分の実体

| # | 分類 | ファイル数 | 行数 | 内容 |
|---:|---|---:|---:|---|
| 1 | **`~/features` → `@features` の改名のみ** | **134** | 392 | `tsconfig.json` に `@features/*` `@environments/*` を追加したことによる一括置換 |
| 2 | その他の import パス書き換えのみ | 11 | 64 | `'../../../business-logic/...'` → `'~/business-logic/...'`、`'../../webapp-common/...'` → `'@common/...'` 等 |
| 3 | `templateUrl` / `styleUrls` / `@import` / `url()` の相対パス変更 | 7 | 20 | `'../../../../webapp-common/...'` → `'../../../../../../src/app/webapp-common/...'` |
| 4 | spec の初期 state 整備・vitest 化 | 7 | 113 | `open-dataset-versions`(33) `rename-dialog`(17) `storage-credentials`(15) `model-info-scalars`(13) `global-search-dialog`(13) `model-info-plots`(12) `global-search-filter-container`(10) |
| 5 | Angular 22 / PrimeNG 22 追随 | 4 | 42 | `dom-service.service.ts`(24) `table.component.html`(10) `table.component.ts`(6) `app.ts`(2) |
| 6 | 新 feature への導線追加 | 5 | 42 | `side-nav.component.html`(14) `model-info-header.component.html`(13)/`.ts`(4) `open-dataset-version-details.component.html`(7)/`.ts`(4) |
| 7 | `app.routes.ts` | 1 | 30 | 新 feature の lazy route 2本（12行）＋ `./features/` → `@features/`（18行） |
| 8 | 状態算出の純関数化 | 1 | 31 | `experiment-info-execution.component.ts`（§5） |
| 9 | `app.config.ts` | 1 | 18 | interceptor 修正・PrimeNG license 引数（§7.4）＋パス書き換え4行 |
| 10 | その他 | 2 | 8 | `report-widgets/.../environment.ts`(4, §7.3) `app.component.ts`(4 = selector 改名2 + パス2, §7.2) |
| | **実質差分 合計** | **39** | **368** | |

**差分760行のうち、約540行（71%）が import / アセットのパス書き換え**（分類1〜3 ＋ 7・9 のパス分）である。挙動に関わる差は残り約220行、うち113行は spec。

※ 内容一致は2,262ファイル。`webapp-common` の Store・Effects・reducer 本体は **`reducers/index.ts` などがエイリアス改名で触られているだけ**で、ロジック差分は0。

### 6.1 Angular 22 / PrimeNG 22 追随の内容

| ファイル | 公式（Angular 21 / PrimeNG 21） | カスタマイズ版（Angular 22 / PrimeNG 22） |
|---|---|---|
| `dom-service.service.ts` | `componentFactoryResolver.resolveComponentFactory(c).create(injector)` | `createComponent(c, {environmentInjector, elementInjector: injector})` |
| `table.component.ts` | `this.table().first = 0` | `this.table().first.set(0)` |
| 同 | `table()?.wrapperViewChild.nativeElement` | `table()?.wrapperViewChild()?.nativeElement` |
| 同 | `table()?.selection` | `table()?.selection()` |
| `table.component.html` | `<p-contextMenu>` | `<p-context-menu>` |
| 同 | `[style.top.px]="this.scrollable && noDataTop"` | `[style.top.px]="scrollable() ? noDataTop : null"` ※下記 |
| `app.ts` | `<router-outlet></router-outlet>` | `<router-outlet />` |

> ※ `scrollable` は**両者とも `scrollable = input(false)`**（signal input）。公式テンプレートの `this.scrollable && noDataTop` は signal 関数そのものを真偽評価しており**常に truthy**になる潜在バグで、カスタマイズ版は `scrollable() ? … : null` に直している。同種の `&&` 混入の修正が `max-width` にも2箇所ある（`… && col.style?.width` → `… ? col.style?.width : null`）。Angular 22 追随というより、追随の過程で拾ったバグ修正。

参考・依存バージョン差：

| パッケージ | カスタマイズ版 | 公式 |
|---|---|---|
| `@angular/*` | `^22.1.5` | `^21.2.22` |
| `@ngrx/*` | `^22.0.0` | `^21.1.1` |
| `primeng` / `@primeuix/*` | `^22.1.0` / `^3.0.0` | `^21.1.9` / `^2.0.3` |
| `typescript` | `~6.0.0` | `^5.9.3` |
| テストランナー | vitest `^4.1.11`（`src/test-setup.ts`） | karma + jasmine（`karma.conf.js` / `src/test.ts`） |

---

## 7. 見つかった細かい相違（記録用）

### 7.1 公式の dead code を1つ削除
`business-logic/business-logic.providers.ts` の `businessLogicProviders`（18サービスの配列）は、**公式リポジトリ内でも定義箇所以外からの参照が0件**。standalone 化で `providedIn:'root'` に移った際の取り残しと見られる。カスタマイズ版はファイルごと削除している。

### 7.2 root component の selector 重複を解消
公式では `app.ts` の `AppRootComponent` と `app.component.ts` の `AppComponent` が**どちらも `selector: 'sm-root'`** を宣言している（`index.html` が指すのは前者）。カスタマイズ版は `AppComponent` を `sm-app-shell` に改名して衝突を解いた。`index.html` は両者とも `<sm-root>` のままで、ブートストラップ経路は同じ。

### 7.3 リポジトリに入っていた資格情報を空に
`webapp-common/clearml-applications/report-widgets/src/environments/environment.ts` の `userKey` / `userSecret` にハードコードされていた値（公式リポジトリにコミットされている）を、カスタマイズ版では空文字列に置換。

### 7.4 `app.config.ts` の2点変更
- `provideHttpClient(withInterceptorsFromDi())` を追加。Angular 22 では未指定時に `HTTP_INTERCEPTORS`（`WebappInterceptor`）が**エラーも出さずに無効化**されるため。
- `getAppConfig(configData, primeUiLicense?)` の第2引数を追加し、PrimeNG テーマ設定へ `license` として渡すようにした。

### 7.5 `src/app` 直下に置かれた調査用 `.md`（7件）
`webapp-common/experiments/解説.md`、`*.ts.code.md` 5件、`ng-maze-InlineEditComponent-*.md` 1件。ビルド対象外だがファイル数差に含まれるため記載（対象外指定の `x-docs` とは別に `src/app` 内へ置かれている点だけ注意）。

### 7.6 spec の増減

| | カスタマイズ版 | 公式 |
|---|---:|---:|
| `src/app` 内 `*.spec.ts` 総数 | 48 | 47 |
| jasmine 依存 spec | 0 | 1 |
| 追加された spec | `clearml-failure.spec.ts` / `execution-requirements-state.spec.ts` / `experiment-info-execution.component.spec.ts` / `report-widgets/src/app/app.reducer.spec.ts` | — |
| 削除された spec | — | `dashboard.component.spec.ts` / `clone-naming.service.spec.ts` / `usage-stats.component.spec.ts` |

---

## 8. まとめ表（観点別）

| 観点 | 公式のみ | カスタマイズ版のみ | 既存の書き換え |
|---|---|---|---|
| **コンポーネント** | 0件 | 13件（新 feature 2本）＋サービス3・Effects 2 | selector 改名1件（`sm-root`→`sm-app-shell`）、導線追加5ファイル、lazy route 2本 |
| **NgRx Store** | 0件 | 2 feature（`dataCatalog` / `qualityPipeline`）。actionGroup 2・reducer 2・selector 33本（自動生成23＋派生10）・Effects 14本 | 0件（既存25箇所の `provideState` 登録・reducer・action・selector は完全一致） |
| **Angular 関数・アノテーション** | `ComponentFactoryResolver`、テスト用3種 | `createComponent` / `EnvironmentInjector` / `withInterceptorsFromDi` / `DOCUMENT` / `ParamMap` | Angular 22・PrimeNG 22 追随4ファイル（うち signal 誤用の潜在バグ修正1件）。デコレータ／Signals API の使い方は同一 |
| **その他の状態管理関数** | 0件（`businessLogicProviders` は dead code） | `createExecutionRequirementsState` / `describeClearmlFailure` ＋ 新 feature の query・adapter・surface 系純関数 | `experiment-info-execution.component.ts` のインライン算出を純関数へ置換（挙動差1点あり／§5） |
| **サービス・DI** | `business-logic.providers.ts` 削除 | API サービス2 / DL サービス1 | `dom-service.service.ts` の生成方式 |
| **新規ライブラリ** | — | **0件**（`src/app` の import パッケージ集合は完全一致） | 依存バージョンは Angular 21→22 / NgRx 21→22 / PrimeNG 21→22 / TS 5.9→6 |

---

## 付録：再現手順

```bash
cd /Users/yasu/work/mergelog
PRO=learn-ClearML-pro/src/app
OFF=ClearML-official-20260921/src/app

# ファイル単位の集合差
diff <(cd $PRO && find . -type f | sort) <(cd $OFF && find . -type f | sort)

# 内容が違う共通ファイル
while read f; do cmp -s "$OFF/$f" "$PRO/$f" || echo "$f"; done < <(comm -12 \
  <(cd $PRO && find . -type f | sort) <(cd $OFF && find . -type f | sort))

# エイリアス改名のみのファイルを除外して実質差分を見る
diff -u <(sed "s|'~/features/|'@features/|g" "$OFF/$f") \
        <(sed "s|'~/features/|'@features/|g" "$PRO/$f")

# NgRx feature の登録状況
grep -rn "provideState(" --include=*.ts $PRO $OFF
grep -rn -A2 "createFeature(" --include=*.ts $PRO $OFF | grep "name:"
```

Angular / NgRx シンボルの集合比較は、各 `.ts` の `import {...} from '@angular/...' | '@ngrx/...'` を抽出して
`(パッケージ, シンボル)` の集合差を取る方法で確認した（共通350シンボル、差7シンボル）。

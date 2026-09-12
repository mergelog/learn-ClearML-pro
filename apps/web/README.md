# ClearML Webapp

---

## 本リポジトリ固有の取り決め

> 以降の英語セクションは ClearML Web 由来の記述であり、NgModule 前提の古い構成を説明している。
> 本プロジェクトの現行ルールはこの節を正とする。

### 設定ファイルの役割

`apps/web` 直下の設定ファイルには、**参照ゼロに見えるが消してはいけないもの**がある。
「どこからも import されていない」を根拠に削除しないこと。

| ファイル | 役割 | 消すとどうなるか |
| --- | --- | --- |
| `tsconfig.json` | 共通ベース。`@common/*` `~/*` の path alias を定義 | ビルド不能 |
| `tsconfig.app.json` | アプリビルド用。`angular.json` の build target が参照 | ビルド不能 |
| `tsconfig.spec.json` | テスト用。`angular.json` の test target が参照 | テスト不能 |
| `tsconfig.strict.json` | **strict 移行済み範囲の宣言**。ファイルからは参照されず、`scripts/web-strict.mjs` が読む | strict ゲートが無効化され、新規コードの型が緩むことに気付けなくなる |
| `eslint-baseline.json` | ベンダーコードに残る ESLint 違反の基準値。`scripts/eslint-baseline.mjs` が読む。**実値はこのファイルの `totals` を見ること**（README に書き写すと必ずずれる） | 違反増加を検知できなくなる |
| `web-boundaries.json` | feature 間・生成 API への依存規則と `knownViolations`。`scripts/web-boundaries.mjs` が読む | レイヤ違反を検知できなくなる |
| `vitest.config.ts` | `angular.json` の `runnerConfig`。`setupFiles` は `src/test-setup.ts` | テスト不能 |
| `vitest.mutation.config.ts` / `stryker.execution.config.json` | ミューテーションテスト用 | `test:mutation:execution` が動かない |

いずれも「**ベンダーコードの既存違反を許容しつつ、新規コードには厳格なルールを課す**」ための
baseline / 宣言ファイルであり、実行時に import されないのは設計上正しい。

### tsconfig の階層

```text
tsconfig.json          共通ベース（strict: false ← ベンダーコードのため）
├── tsconfig.app.json      アプリビルド用
├── tsconfig.spec.json     テスト用（types: vitest/globals, node）
└── tsconfig.strict.json   strict を効かせる範囲の宣言
```

`tsconfig.strict.json` は `include` に書かれた範囲だけを strict 検査する。
`tsc -p tsconfig.strict.json` を直接叩くと**範囲外（ベンダーコード）のエラーも出るが、それは正常**。
判定は範囲内のエラーだけを見る `scripts/web-strict.mjs` が行う。

```bash
pnpm run web:typecheck:strict          # リポジトリルートから
node scripts/web-strict.mjs --all      # 範囲外の残件数も出す
```

**ルール: 新しく feature を追加したら `tsconfig.strict.json` の `include` に必ず足す。**
足した時点でゲートが通らないなら、その feature はまだ strict に耐えていない。

### HttpClient と interceptor の提供（2026-09-10）

**`app.config.ts` の `provideHttpClient(withInterceptorsFromDi())` を消さないこと。**
消しても通信は動き続け、`WebappInterceptor` だけが黙って止まる。

Angular 22 では `HttpClient` / `HttpHandler` / `HttpBackend` が
`@Injectable({providedIn: 'root'})` になっており、既定の backend は `FetchBackend` である
（`node_modules/@angular/common/fesm2022/_module-chunk.mjs`）。
つまり **`provideHttpClient()` を書かなくても `HttpClient` は注入できてしまう**。
実測でも `NullInjectorError` は出ず、アプリは正常に起動していた。

問題はその先にある。実際にリクエストを流す `HttpInterceptorHandler` は、
interceptor chain を **`HTTP_INTERCEPTOR_FNS` からだけ**組み立てる。
`{provide: HTTP_INTERCEPTORS, useClass: ...}` で登録したクラス型 interceptor を
そこへ橋渡しするのは `withInterceptorsFromDi()` だけである。

そのため 2026-09-10 の修正前は、次の状態だった。

| | 修正前 | 修正後 |
| --- | --- | --- |
| `HttpClient` の注入 | できる（root 既定） | できる |
| API リクエスト | 飛ぶ | 飛ぶ |
| `X-Clearml-Client` ヘッダ | **付かない** | 付く（`Webapp-<version>`） |
| 401 での `logout()` | **走らない** | 走る |

Playwright で `login.supported_modes` / `users.get_all` のリクエストヘッダを見て確認した。

```text
修正前: POST .../login.supported_modes :: X-Clearml-Client=(none)
修正後: POST .../login.supported_modes :: X-Clearml-Client=Webapp-2.3.0-000
```

**エラーが出ないので、壊れていることに気付けない**種類の欠落だった。
`provideHttpClient()` を書き足す際に `withInterceptorsFromDi()` を落とすと同じ状態に戻る。

副次的な変更として、`provideHttpClient()` は XSRF interceptor
（cookie `XSRF-TOKEN` → header `X-XSRF-TOKEN`）を chain に加える。
cookie が無ければ何も付かないため、ClearML API への影響は無い。

なお `report-widgets`（`webapp-common/clearml-applications/report-widgets`）は
別アプリで、interceptor を持たないため `provideHttpClient()` だけで足りている。

### ディレクトリ構成

書いてあるのは各層の**出自**である。ファイル数より、そこが誰のものかが判断を決める。

```text
src/app/
├── core/              17 files   app初期化 / interceptor / グローバルstate   ベンダー由来・薄く保つ
├── shared/            12 files   guard / directive / util / service         自作の共有層 ← ここを育てる
│   └── clearml/        2 files   ClearML API の失敗を1行にする              自作（strict / web-unit の対象）
├── layout/             7 files   header / side-nav / breadcrumbs            ベンダー由来
├── features/         188 files   quality-pipeline（39）/ data-catalog（45）が自作、他はベンダー由来
├── business-logic/   607 files   OpenAPI生成のAPIクライアント                生成物・手で編集しない
├── webapp-common/   1687 files   ClearMLベンダー由来の共有層                 凍結領域
└── build-specifics/    3 files   ビルド別provider差し替え
```

**方針: ベンダー由来コードは凍結領域として扱い、自作コードだけを現行推奨に合わせる。**
ベンダーコードまで直すと ClearML 追従時に全面衝突する。
「全体を綺麗にする」ことは最初から目標にしない。

このリポジトリは `eslint-baseline` / `web-boundaries` / `web-strict` という
**「ベンダーの既存違反は許すが、新規コードには厳格」** の仕組みを持っている。
新しいゲートを増やすのではなく、この3つに乗せる。

3つのルール

1. **`webapp-common` に新規の共有コードを足さない。** 自作の共有物は `shared/` へ置く。
   `webapp-common` へ足すと、ClearML 追従時にベンダー差分と混ざって判別不能になる
   （`web-boundaries.json` の `no-cross-feature-import` の description もこれに合わせてある）。
   **`shared/` へ自作コードを足すときは、feature を足すときと同じ受け皿が要る**
   — `tsconfig.strict.json` の `include` と、`test-pyramid.json` の `web-unit`
   `include` / `web-unit-vendor` `exclude` の3か所。足し忘れると、そのコードだけが
   strict 検査を外れ、spec はベンダーの層として数えられる
2. **`business-logic` は生成物。** 名前は「ビジネスロジック層」を想起させるが、
   実体は OpenAPI から生成された API クライアントである。**改名しない。**
   607ファイルと全 feature からの import があり、改名の利得が費用に見合わない
   （**判断の記録**。書いておかないと誰かが改名を始める）
3. **`webapp-common` 内を編集したら理由を記録する。** ベンダー差分はそのまま追従コストになる

**何を `shared/` へ上げるか**は
[docs/_archive/adr/009_20260912_shared_layer_and_deferred_decisions.md](../../docs/_archive/adr/009_20260912_shared_layer_and_deferred_decisions.md)
にある。基準は一言でいえば「同じ**判断**が2つあるなら上げる、同じ**事実**が
2つあるだけなら上げない」で、同じ文書に `libs/` / `@defer` / zoneless を
**いま動かさないと決めた理由と、再開する条件**も書いてある。

### 凍結領域へ入れた例外（2026-09-12 時点）

上の3番目のルールの実体がこの表である。**ここに無い改造は残さない。**
記録の無い例外が増えると、凍結領域という約束そのものが意味を失う。

| ファイル | 入れたもの | なぜ他所に置けないか |
| --- | --- | --- |
| `src/app/app.routes.ts` | `quality-pipeline` / `data-catalog` の lazy route 各1件 | 自作 feature への入口はここにしか登録できない |
| `src/app/layout/side-nav/side-nav.component.html` | 同2つへの導線 各1件 | 導線が無ければ URL を直に打つしか開く手段が無い |
| `src/app/webapp-common/models/dumbs/model-info-header/model-info-header.component.html` / `.ts` | Model からカタログへ戻るリンク1件（`RouterLink` を `imports` へ追加） | 台帳は**横断の入口**であって置き換えではない。既存画面から戻れないと導線が片道になる |
| `src/app/webapp-common/dataset-version/open-dataset-version-details/open-dataset-version-details.component.html` / `.ts` | Dataset 版数からカタログへ戻るリンク1件（同上） | 同上 |

守っている決まり

- **足すだけで、既存の行の意味を変えない。** ClearML を追従するときの衝突は
  「同じ行を両側が変えた」ときにだけ解決が要る。追加だけなら衝突しても機械的に済む
- **判断をベンダー側へ置かない。** 上のリンクはどれも `/data-catalog/<kind>/<id>` を
  組み立てるだけで、条件分岐も store 参照も持たない。持たせると、ベンダーファイルが
  自作 feature の都合を知ることになり、追従のたびに読み直す羽目になる
- **ベンダーファイルでも baseline は増やさない。** 例えば `<mat-icon></mat-icon>` と
  書くと `prefer-self-closing-tags` が1件増えて `web:lint:baseline` が落ちる。
  周りの既存行がそう書いていても、**新しく足す行は現行のルールに従う**
- `web-boundaries.json` の更新は要らなかった。境界の規則は
  「共有層は feature に依存しない」であり、上のリンクは feature を import していない

### feature の標準形

```text
features/<feature-name>/
├── components/         presentational（store を知らない。input() / output() のみ）
│   └── <name>/  .ts + .html + .scss + .spec.ts
├── containers/         smart（store に触れるのはここだけ）
├── data-access/        <feature>-api.service.ts / <feature>.adapter.ts（+ spec）
├── state/              actions / reducer / selectors / effects（+ spec）
├── styles/             _<feature>.mixins.scss
├── <feature>.model.ts          画面が扱う型（ClearMLの語彙を持ち込まない）
├── <feature>.consts.ts
└── <feature>.routes.ts         loadComponent + provideState + provideEffects
```

自作 feature は `features/quality-pipeline` と `features/data-catalog` の2つで、
どちらもこの形に従う。**2つ目が出たことで、この形は「実例」から「規約」になった**
（点検済み。2つ目は ADR 007 の4つの決定すべてに沿っていた）。
**3つ目からは、沿わない書き方をするなら先に ADR 007 を直す。**

`data-catalog` はこの形に2つ足している。どちらも feature 固有の事情である。

| 追加 | 中身 | なぜ feature の中に置くか |
| --- | --- | --- |
| `data-catalog.query.ts`（+ spec） | 絞り込み条件と URL クエリの相互変換 | **URL は外向きの約束**で、container の中に埋めると独立して確かめられない |
| `containers` が2つ | 一覧と詳細 | 同じ state を共有するため、provider は親の route に置く |
| `data-catalog.export.ts`（+ spec） | 外へ渡す JSON の組み立て（封筒 + `CatalogAsset`） | この feature にしか出口が無い |
| `data-catalog.download.ts`（+ spec） | ブラウザへファイルを渡す境界 | ClearML と並ぶ**もう1つの外向きの境界**。差し替えられる形にして container を確かめる |
| `data-catalog.surface.ts` / `.surface.published.json`（+ spec） | 外へ公開している面と、コミットしてある公開中の面 | 出口が feature の中にあるので、面もここで守る |

**`data-catalog.surface.published.json` は「台帳が外へ何を約束しているか」の
回答である。** URL のクエリ鍵・種別と状態の語・書き出しの封筒と列が入っている。
コードが組み立てる面とこのファイルが違えば `web:test` が落ちる。意図した変更なら、
失敗の文言が出した内容へこのファイルを直し、**差分をレビューに載せる**
（守り方は `prediction_api` の `openapi.json` と同じ。ADR 006 / ADR 010）。

決まり

- **`containers` を使う（`pages` ではない）。** container / presentational の語彙を
  採用している以上こちらが一貫する。**混在させないことが重要**で、
  どちらが正しいかはこの際どうでもよい
- **新しい feature を作ったら `tsconfig.strict.json` の `include` に足す。**
  足した時点でゲートが通らないなら、その feature はまだ strict に耐えていない
- **presentational component には spec を書く。** store を持たず `input()` / `output()`
  だけで動く層は最も安くテストできる。しかもこれらは単なる表示ではなく判断を持つ
  （桁を揃える、打ち切りを黙らない、「まだ無い」を空白ではなく文で出す）。
  **そう見えること自体が仕様**で、壊れても型では気付けない
- **`webapp-common` 配下は ClearML の命名が混在しているが、凍結領域なので統一対象外**

**なぜこの形なのか**は
[docs/_archive/adr/007_20260912_angular_feature_composition.md](../../docs/_archive/adr/007_20260912_angular_feature_composition.md)
にある（standalone / Signals と NgRx の責務 / lazy route の provider /
失敗の扱い）。ここは形、ADR は理由で、二重には書かない。

### 変更検知とコンポーネントの命名（決定の記録）

同じ議論を繰り返さないための記録。どちらも**決定済み**で、部分的に変えない。

#### `changeDetection: ChangeDetectionStrategy.OnPush` を明示する

**Angular 22 では OnPush が既定の変更検知戦略である。**

```ts
enum ChangeDetectionStrategy { OnPush = 0, Eager = 1, Default = 1 }
//   OnPush = 0 に「NOTE: OnPush is enabled by default.」と書かれている

// ɵɵdefineComponent
onPush: componentDefinition.changeDetection !== ChangeDetectionStrategy.Eager
//   changeDetection を書かない（undefined）なら onPush: true になる
```

つまり `changeDetection` を省略した component は OnPush であり、離脱するには
`ChangeDetectionStrategy.Default`（= `Eager`）を明示する必要がある。
実測では `@Component` 345個のうち、明示的に離脱しているのは**1個だけ**である。

**それでも自作コードには `OnPush` を明示する。**
このリポジトリでは 235個が明示しており、明示が多数派である。
`webapp-common` を凍結領域として扱う以上、そちらの書き方に揃えるほうが一貫する。
実行時には no-op であり、**意図の表明としてのみ**書いている。

このため `eslint.config.js` では
`prefer-on-push-component-change-detection` に `allowExplicitOnPush: false` を**指定しない**。
指定すると、明示した `OnPush` の側が「冗長」として咎められる。
このルールがいま咎めるのは `Default` への明示的な離脱だけである。

#### `.component` 接尾辞を維持する

Angular v20 以降の命名規約は `.component` を落とす（`foo.ts` / `FooComponent`）が、
**本リポジトリは採用しない。**

理由は数である。`.component.ts` は全体で数百ファイルあり、その大半が
`webapp-common` 配下の凍結領域にある。凍結領域を改名すれば ClearML 追従時に
全面衝突し、自作分だけ改名すれば**命名が2系統に割れる**。
一貫していない命名は、規約が無いことより読み手を迷わせる。

**部分的な改名をしない。** 迷ったらこの節を指す。

### 削除済みの死骸（2026-09-09）

同じ調査を繰り返さないための記録。いずれも参照ゼロ・依存ゼロを確認のうえ削除した。

| ファイル | 理由 |
| --- | --- |
| `karma.conf.js` / `src/test.ts` | Vitest 移行済み。`package.json` に `karma*` / `jasmine*` の依存は無く、`src/test.ts` は `tsconfig.spec.json` の `include` にも入っていなかった |
| `tslint.json` | ESLint へ一本化済み。`tslint` / `codelyzer` の依存も無い |
| `src/tsconfig.json` / `src/tsconfig.app.json` / `src/tsconfig.spec.json` | Angular 6 以前の残骸。ルート側と重複し、IDE が「最も近い tsconfig」を拾って設定が2系統に見える事故のもとだった |
| `src/app/business-logic/business-logic.providers.ts`（2026-09-10） | 18サービスを並べた provider 配列だが import 元がゼロ。並んでいる `Api*Service` は全て `@Injectable({providedIn: 'root'})` を持つため DI には既に載っており、この配列は一度も効いていなかった。**「ここに足せば DI に載る」と誤解した追加を防ぐために消す。** ただし `business-logic/` は API 再生成の対象領域なので、再生成で復活しうる。復活したら同じ理由でまた消す |

---

## Building the UI from source
### Prerequisite
* Node 24 with pnpm@10
* use git to clone the project to your local machine 

### Build
* `cd clearml-web` to the root of the project
* run `pnpm install  --force --frozen-lockfile` to install required node modules
* run `pnpm run build`


### Development
During development, the development server will need to proxy an API server. to achieve that:
* in [proxy.config.mjs](proxy.config.mjs) update the list of targets in line 3 with a working API server URI.
* Angular is already configured to use this proxy configuration
* If more than 1 API server is configured `apiBaseUrl` should be updated with the server enumeration in [environment.ts](src%2Fenvironments%2Fenvironment.ts) 

Start the development server: `npm run start`

#### Business Logic module
Contains ClearML logic. api calls and ClearML objects (e.g tasks, models) and ClearML logic function (e.g isTaskHidden)

#### Core module
Contains only logic. no declarations. no dependency with any other module beside ngrx.
- **services** - utilities classes. file name: `<name>.service.ts`

#### Feature Modules
Application feature modules. each module can contain declarations and providers **specific to the the feature**  
Depend only on shared module for ui components

##### Each feature should contain the following: 
- **module** - the feature module: `<featureName>.module.ts`. 
- **component** - the feature main component js file, should contain the feature's containers components only: `<featureName>.component.ts`. 
- **component** html - the feature component html: `<featureName>.component.html`. 
- **component** style - the feature component style: `<featureName>.component.scss`.
- **utils** - the feature utils, a page with list of pure functions for utils purposes: `<featureName>.utils.ts`.
- **constants** - the feature constants values: `<featureName>.const.ts`. 
- **model** - the feature types, interfaces and objects declarations: `<featureName>.model.ts`.
- **actions** - redux action classes - file name: `<name>.actions.ts`
- **effects** - ngrx effects classes. manage data flow and side effects - file name: `<name>.effect.ts`
- **reducers** - simple functions for state composition. file name: `<name>.reducer.ts`
- **services** - utilities classes with the same responsibility under `services` folder : `<name>.service.ts`.
- **container components** - components that will include dumb components and will pass data from the state to the dumb components and dispatch actions of the dumb components, the container components will be under `containers` folder.
- **dumb components** - stateless view components that will communicate through inputs and outputs, the dumb components will be under `dumb` folder. 

#### Shared Module
Application shared UI components, directives and pipes. **contain only declarations**.
All the components should be **reusable**.


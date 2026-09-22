# ダッシュボードを開いた後に、一覧で「My Work」を選ぶと、URL から絞り込みの条件が消える

| 項目 | 内容 |
|---|---|
| カテゴリー | 状態 |
| 不具合内容 | 同じタブで一度でもダッシュボードを開いた後、プロジェクト・パイプライン・データセット・レポートの一覧で、絞り込みのメニューから「My Work」を選ぶと、URL の `filter` パラメータが丸ごと消える。同じパラメータに入っているタグ・ユーザー・状態の絞り込みも URL から消える。画面の絞り込み（Store）はそのまま残る |
| 期待動作 | ダッシュボードを開いていない場合と同じく、URL に `filter=myWork:true`（タグなどがあれば `filter=myWork:true,tags:…`）が残る |
| 直さないと困ること | URL を共有・ブックマークしても、受け取った側や後で開いたときに絞り込みが再現されない。画面の絞り込みと URL が食い違うため、利用者は URL が今の表示を表していると誤解する |
| 修正規模 | 極小 |

| 項目 | 内容 |
|---|---|
| 画面 | プロジェクト・パイプライン・データセット・レポートの一覧の絞り込みメニュー（`sm-main-pages-header-filter`）。原因はダッシュボードのヘッダーの「My work」（`sm-show-only-user-work`） |
| 観点 | E（購読の破棄）、H（URL と状態の同期） |
| 重大度 | S3 |
| 確度 | 再現済み（モック API） |
| 由来 | 上流 |
| 発生条件 | 同じタブでダッシュボードを1回以上開いた後（再読み込みするまで続く）。「My Work」を選ぶか、「My Work」が有効な状態で絞り込みを変え、URL の `filter` に `myWork:true` が入ったとき |
| 関連 | [20](./20_画面を離れても購読が解除されず画面のコンポーネント一式がメモリに残る.md)（同じ購読の解除漏れによるメモリの保持。同種の箇所をまとめてある） |

## 症状

モック API で、プロジェクトの一覧の絞り込みメニューから「My Work」を選んだ後の URL の検索部分と、`setFilterByUser` の dispatch の回数を記録した。

| 条件 | 選ぶ前の URL | 選んだ後の URL | `setFilterByUser` | 確認 |
|---|---|---|---:|---|
| ダッシュボードを開いていない | `/projects` | `?filter=myWork:true` | 2 | 再現（モック API） |
| ダッシュボードを1回開いた後 | `/projects` | （空） | 2 | 再現（モック API） |
| ダッシュボードを3回開いた後 | `/projects` | （空） | 4 | 再現（モック API） |
| ダッシュボードを1回開いた後、タグで絞り込んだ状態 | `?filter=tags:bug-tag` | （空） | 2 | 再現（モック API）。Store にはタグ `bug-tag` と My Work が残っている |

ダッシュボードを開いた回数だけ、画面を離れた後の「My work」の購読が残る。残った購読は「My Work」を選ぶたびに `filter` を URL から消し、`setFilterByUser` を1回ずつ dispatch する。

## 再現手順

1. プロジェクトの一覧を開く
2. 左のナビゲーションからダッシュボードを開き、プロジェクトの一覧に戻る（再読み込みはしない）
3. 一覧の見出しの絞り込みボタン（漏斗のアイコン）を押し、「My Work」を選ぶ
4. 一覧は自分のものに絞り込まれるが、アドレスバーの URL に `filter` が付かない

手順2を省くと、手順4で URL に `?filter=myWork:true` が付く。

スクリプトは [scripts/p2e-show-only-user-work.spec.ts](./scripts/p2e-show-only-user-work.spec.ts)（`DASHBOARD_VISITS` でダッシュボードを開く回数を変えられる）。

## 期待する動作

一覧の絞り込みを変えたとき、URL の `filter` が画面の絞り込みと同じ内容になる。ダッシュボードを開いたかどうかで結果が変わらない。

## 原因

ダッシュボードのヘッダーに出る「My work」の部品が、画面から消えた後も Store の購読を解除しない。

- ヘッダーは `userFocus` が true のルート（`app.routes.ts` のダッシュボードだけ）でこの部品を出す（[header.component.html:10](../src/app/webapp-common/layout/header/header.component.html#L10)）。ダッシュボードを離れると部品は破棄される
- 部品のコンストラクタは `selectRouterQueryParams` を購読するが、`takeUntilDestroyed()` を付けていない（[show-only-user-work.component.ts:33](../src/app/webapp-common/shared/components/show-only-user-work/show-only-user-work.component.ts#L33)）。そのため破棄された後も購読が残り、以後の画面遷移のたびに動く
- 購読の処理は、URL の `filter` に `myWork` の条件があると、`router.navigate([], {queryParams: {filter: undefined}, queryParamsHandling: 'merge', replaceUrl: true})` で `filter` を URL から消し、`setFilterByUser` を dispatch する（[同 :39-45](../src/app/webapp-common/shared/components/show-only-user-work/show-only-user-work.component.ts#L39-L45)）。`filter` にはタグ・ユーザー・状態の条件も同じパラメータにまとめて入る（[main-pages-header-filter.component.ts:231](../src/app/webapp-common/shared/components/main-pages-header-filter/main-pages-header-filter.component.ts#L231) の `updateUrlFilters()`）ため、それらも一緒に消える

プロジェクトなどの一覧では、`filter` は絞り込みメニュー（`main-pages-header-filter`）が URL と Store のあいだで同期している。「My work」の部品はこれらの一覧には出ない（`projects-header` は `enableTagsFilter` が false のときだけ出すが、どの一覧も true）。本来は一覧の `filter` に関わらない部品の残った購読が、一覧の URL を書き換えている。

## 影響範囲と同種箇所

- 絞り込みメニューを使う一覧：プロジェクト（[projects-header.component.html:11](../src/app/webapp-common/projects/dumb/projects-header/projects-header.component.html#L11)）、パイプライン、データセット、入れ子のプロジェクト表示、レポート（[reports-header.component.html:12](../src/app/webapp-common/reports/reports-filters/reports-header.component.html#L12)）
- 一覧のあいだを移るときに、`filter` に `myWork:true` を含む URL へアプリ内で遷移した場合も、同じく URL から消える（コードから判断。確かめたのは絞り込みメニューの操作）
- 同じ型の購読の解除漏れ（画面を離れても購読が残るもの）は [20](./20_画面を離れても購読が解除されず画面のコンポーネント一式がメモリに残る.md) にまとめた。この部品の購読はメモリの保持に加えて、この資料の症状を起こす

## 対策案

第一案は、[show-only-user-work.component.ts:33](../src/app/webapp-common/shared/components/show-only-user-work/show-only-user-work.component.ts#L33) の `pipe` の先頭に `takeUntilDestroyed()` を足す。コンストラクタの中なので引数は要らない。1行の追加のため「極小」とした。部品がダッシュボードに出ているあいだの挙動（URL の `myWork` を Store の「My work」に移す）は変わらない。

## 検証範囲

- 確認したこと：Playwright（Chromium）とモック API で、ダッシュボードを開く前後の URL の違い、ダッシュボードを開いた回数と `setFilterByUser` の回数、タグの絞り込みも URL から消えて Store には残ること。画面の出入りで購読とインスタンスが残ることは、実バックエンドの全ルート巡回（[scripts/p2e-leak-crawl.spec.ts](./scripts/p2e-leak-crawl.spec.ts)）でも確かめた（20 の検証範囲）
- 確認していないこと：実バックエンドでの操作（「My Work」は利用者設定としてサーバに保存されるため、書き込みを避けてモック API で行った）。パイプライン・データセット・レポートの一覧での操作（同じ部品のため同じになると判断した）。再読み込みした後の絞り込みの状態（タグなどは localStorage からも戻る設定になっている）
- 由来：`show-only-user-work`・`header`（layout）・`main-pages-header-filter` は比較資料で上流と一致する。購読の解除の仕組みは Angular 21 でも同じである

# 旧比較 URL のリダイレクトで ids が失われ、詳細画面が例外になる

| 項目 | 内容 |
|---|---|
| カテゴリー | 状態 |
| 不具合内容 | 旧 URL `compare-experiments;ids=…` を直接開くと、`compare-tasks` へのリダイレクトで matrix parameter の `ids` が消える。比較詳細は `ids` がある前提で `slice()` を呼ぶため TypeError になり、比較対象のない壊れた画面になる |
| 期待動作 | 旧 URL でも比較対象の ids を保って新 URL へ移動し、通常の比較詳細を表示する |
| 直さないと困ること | 過去に共有・保存された比較 URL が使えない。ユーザーは対象のタスク ID を失い、URL を手で作り直さなければ比較を開けない |
| 修正規模 | 小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験管理 > 比較（旧 `compare-experiments` URL） |
| 観点 | H（ルーティングと画面遷移） |
| 重大度 | S3 |
| 確度 | 再現済み |
| 由来 | カスタマイズ |
| 発生条件 | `/projects/:projectId/compare-experiments;ids=:id1,:id2/details` を直接開く、または再読み込みする |
| 関連 | [21](./21_ダッシュボードを開いた後に一覧でMy_Workを選ぶとURLから絞り込みの条件が消える.md)（URL と画面状態の不整合） |

## 症状

実データの比較対象2件を含む旧 URL を開くと、最終 URL とコンソールは次のとおりになる。

| 開いた URL | 最終 URL | 結果 |
|---|---|---|
| `/projects/37d…/compare-experiments;ids=c97…,c186…/details` | `/projects/37d…/compare-tasks/details` | `ids` が消え、`TypeError: Cannot read properties of undefined (reading 'slice')` |

Playwright（Chromium、実バックエンドは読み取りのみ）で [scripts/p2h-legacy-route.spec.ts](./scripts/p2h-legacy-route.spec.ts) を実行し、最終 URL に `;ids=` がないことと例外の両方を確認した。

## 再現手順

1. タスク ID を2件用意する
2. `/projects/{projectId}/compare-experiments;ids={taskId1},{taskId2}/details` をアドレスバーで開く
3. URL が `/compare-tasks/details` に変わり、比較対象がない状態になる
4. コンソールに `Cannot read properties of undefined (reading 'slice')` が出る

## 原因

旧パスは `redirectTo` だけで新パスへ置き換えている。Angular Router の static redirect は matrix parameter を引き継がないため、`ids` が落ちる。

```ts
{path: 'compare-experiments', redirectTo: 'compare-tasks'},
```

([app.routes.ts:98](../src/app/app.routes.ts#L98))

一方、比較画面は router params の `ids` が届く前提で Store を更新する。旧 URL の場合は `taskIds$` が `undefined` を流し、詳細コンポーネントの `experimentIds.slice(...)` で例外になる。

([experiment-compare-details.component.ts:67](../src/app/webapp-common/experiments-compare/containers/experiment-compare-details/experiment-compare-details.component.ts#L67))

## 影響範囲と同種箇所

- プロジェクト配下の実験比較と、`projects/*` 配下の全タスク比較にある旧 `compare-experiments` パス
- `experiments` → `tasks` の旧パスは同じ実行で確認し、query parameter は保持されてタスク一覧を開けた
- データセットの `experiments` → `tasks` も比較対象を持たない一覧パスであり、この `ids` 消失の型には当たらない
- `compare-models` には今回の旧 `compare-experiments` リダイレクトはない

## 対策案

`redirectTo` を使わず、`CanMatch` / `CanActivate` のリダイレクトまたは専用コンポーネントで `route.paramMap.get('ids')` を読み、`compare-tasks;ids=${ids}` を明示して `UrlTree` を返す。`ids` が欠けている URL は比較画面へ入れず、一覧へ戻すか空の比較画面として扱う。

あわせて `ExperimentCompareDetailsComponent` では、入力境界で `experimentIds` が配列かを確認する。旧ブックマーク、手入力、将来の別リダイレクトで params が欠けても、未捕捉例外にはしない。

## 検証範囲

- 確認したこと：Playwright（Chromium、実バックエンド読み取りのみ）で旧 URL のリダイレクト、ids の消失、詳細画面の TypeError を確認。`experiments` → `tasks` とデータセットの旧一覧パスは、最終 URL が tasks 側になり表示できることを確認した
- 確認していないこと：Firefox・Safari、旧 URL の比較サブタブすべて。リダイレクトが共通なため同じ ids 消失になると判断した
- 由来：`compare-experiments` の旧 URL への導線はカスタマイズで追加されている。比較詳細の ids 前提の実装は上流由来

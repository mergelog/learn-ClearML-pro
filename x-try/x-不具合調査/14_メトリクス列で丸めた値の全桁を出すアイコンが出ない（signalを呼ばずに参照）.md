# 一覧のメトリクス列で、丸めて表示した値の全桁を出す展開アイコンとツールチップが出ない

| 項目 | 内容 |
|---|---|
| カテゴリー | 画面UI |
| 不具合内容 | タスク一覧などにメトリクスの列を足すと、値は小数第3位程度に丸めて表示される。丸めた値には、全桁を表示する展開アイコンと、全桁を示すツールチップが付く作りだが、どちらも出ない |
| 期待動作 | 丸めて表示した値のセルに展開アイコンが出て、押すと列の全行が全桁で表示される。ツールチップでも全桁が見える |
| 直さないと困ること | 一覧で値を比べる利用者が、丸めた値でしか比べられない（0.8583 と 0.8577 がどちらも 0.858 に見える） |
| 修正規模 | 極小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験管理 > 一覧（メトリクスの列）、モデル > 一覧（メトリクスの列）、エンドポイント > 一覧（メトリクスの列） |
| 観点 | D（変更検知と描画：signal を呼ばずに参照） |
| 重大度 | S3 |
| 確度 | 再現済み（タスク一覧）。モデル一覧・エンドポイント一覧はコード上確定 |
| 由来 | 上流 |
| 発生条件 | 常に |
| 関連 | なし |

## 症状

タスク一覧に `accuracy / validation` の列を足すと、値は `0.86`・`0.858`・`0.834` などと表示される。このうち4件は全桁の値と丸めた値が違う（`roundedMetricValues()` の計算結果）が、展開アイコン（`al-ico-line-expand`）は1つも表示されない。

## 再現手順

実バックエンドの既存プロジェクトで行う（読み取りだけ）。

1. タスク一覧の列の設定で、メトリクスの列（例：`accuracy` の `validation`）を足す
2. 値が丸めて表示されているセルにマウスを乗せても、展開アイコンもツールチップも出ない

スクリプトは [scripts/p2d-rounded-metric.spec.ts](./scripts/p2d-rounded-metric.spec.ts)。開発モードの `ng.getComponent()` で、一覧のコンポーネントの `roundedMetricValues()` と、セルのコンポーネントの入力 `roundedMetricValue` を読み比べている。

## 期待する動作

丸めた値のセルに展開アイコンとツールチップが出る。

## 原因

[experiments-table.component.html:193](../src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html#L193) は `[roundedMetricValue]="roundedMetricValues[col.id]"` と書いているが、[roundedMetricValues](../src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L185) は `computed()` で作った signal である。signal を呼ばずに添字で読むと関数のプロパティを読むことになり、常に `undefined` になる。

セルのコンポーネント（[hyper-param-metric-column.component.html:5](../src/app/webapp-common/experiments/shared/components/hyper-param-metric-column/hyper-param-metric-column.component.html#L5)）は `@if (roundedMetricValue && roundedMetricValue[experiment.id])` で展開アイコンを出し、ツールチップも `roundedMetricValue?.[experiment.id]` で出し分けるため、入力が `undefined` だと両方とも出ない。

`tsconfig.json` は `strictTemplates: true` でテンプレートを型検査しているが、`strict: false`（`noImplicitAny` が無効）のため、関数を文字列の添字で読む式は暗黙の `any` として通り、ビルドでは検出されない。`web:typecheck:strict` は tsc による `.ts` の検査で、テンプレートは対象外である。

## 影響範囲と同種箇所

テンプレートで signal を呼ばずに、添字・プロパティ参照・論理演算で読んでいる箇所を全テンプレートで機械的に探した（テンプレート変数で同名を上書きしているものは除いた）。

| 箇所 | 読み方 | 症状 | 確度 |
|---|---|---|---|
| [experiments-table.component.html:193](../src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html#L193) | `roundedMetricValues[col.id]` | 本件（タスク一覧） | 再現済み |
| [models-table.component.html:170](../src/app/webapp-common/models/shared/models-table/models-table.component.html#L170) | 同上 | 本件（モデル一覧） | コード上確定 |
| [serving-table.component.html:137](../src/app/webapp-common/serving/serving-table/serving-table.component.html#L137) | 同上 | 本件（エンドポイント一覧） | コード上確定 |
| [welcome-message.component.html:100](../src/app/webapp-common/layout/welcome-message/welcome-message.component.html#L100) | `community() && workspace.name` | `workspace` は `selectSignal`（中身は Angular の `computed()`）で、`workspace.name` は signal の関数自体の名前（`@angular/core` の実装では `const computed = () => …` のため `'computed'`。本番ビルドでは短縮された名前）になり、空でないため常に真。コミュニティ版のサーバでは、資格情報を作る手順の枠に `has-ws` クラスが常に付き、高さが 10px 増える | コード上確定 |

比較資料 §6.1 で、カスタマイズ版が `table.component.html` の `this.scrollable && noDataTop` を直した跡がある。同じ型が上の4箇所に残っている。

## 対策案

4箇所とも signal を呼ぶ形に直す（`roundedMetricValues()[col.id]`、`workspace()?.name`）。テンプレートの1箇所ずつの変更のため「極小」とした。再発を防ぐには `noImplicitAny` を有効にする必要があり、`strict` の段階的な移行（`scripts/web-strict.mjs`）の中で扱うことになる。

## 検証範囲

- 確認したこと：Playwright（Chromium、実バックエンドの既存プロジェクト）で、タスク一覧のメトリクスの列について、`roundedMetricValues()` が丸めの生じる4件を返すこと、セルの入力 `roundedMetricValue` が `undefined` であること、展開アイコンが0件であること
- 確認していないこと：モデル一覧・エンドポイント一覧・ようこそ画面の画面上の症状（テンプレートが同じ書き方のため同じになると判断した）。展開アイコンを押したときの動き（アイコンが出ないため確かめられない）
- 由来：4つのテンプレートとコンポーネントは比較資料で上流と一致する。`computed()` の signal を呼ばずに読む誤りは Angular の版によらない

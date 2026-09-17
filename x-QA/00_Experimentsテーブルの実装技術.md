# Experimentsテーブルの実装技術

## Q. Experiments画面のテーブルは、単純に`<table>`タグを自作しているのか

いいえ。テーブルの基盤には **PrimeNGの`p-table`** を使用しています。

ただし、PrimeNGをそのままExperiments画面から呼び出しているわけではありません。ClearML独自の共通テーブルコンポーネントで包み、その上からExperiments固有の表示内容を差し込んでいます。

```text
ExperimentsTableComponent
  └─ <sm-table>                    ClearML独自の共通ラッパー
       └─ <p-table>               PrimeNGのテーブル
            └─ <tr>/<th>/<td>     最終的に描画されるHTML要素
```

## 各層の役割

### `ExperimentsTableComponent`

Experiments画面固有の次の内容を担当します。

- 表示する列
- 各セルの表示内容
- 実験ステータス、タグ、ユーザーなどのフィルター
- 実験の選択処理
- ソートや追加読み込みを上位コンポーネントへ通知する処理

`experiments-table.component.html`では、共通コンポーネントの`<sm-table>`を使用しています。

- [experiments-table.component.html](../src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html)
- [experiments-table.component.ts](../src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts)

### ClearML独自の`TableComponent`

`<sm-table>`として利用される、アプリ全体の共通テーブルです。内部でPrimeNGの`TableModule`と`Table`を読み込んでいます。

主に次の共通機能をまとめています。

- 行選択
- 列幅の変更
- 列の並べ替え
- ソート
- 仮想スクロール
- 右クリックメニュー
- 行展開
- 追加読み込み
- キーボード操作
- CSV出力

- [table.component.ts](../src/app/webapp-common/shared/ui-components/data/table/table.component.ts)

### PrimeNGの`p-table`

実際のテーブル機能を提供するUIライブラリです。共通テーブルのテンプレートでは`<p-table>`を使用し、その中に`<tr>`、`<th>`、`<td>`のテンプレートを定義しています。

- [table.component.html](../src/app/webapp-common/shared/ui-components/data/table/table.component.html)

したがって、最終的なDOMは通常のHTMLテーブル要素になりますが、列操作や選択、仮想スクロールなどの振る舞いはPrimeNGが基盤になっています。

## セル内容の差し込み

Experiments固有のセル内容は、PrimeNGの`pTemplate="body"`などを利用して`<sm-table>`へ渡しています。

たとえば、同じ共通テーブルを使いながら、列IDに応じて次のような専用コンポーネントを表示します。

- 実験タイプ: `ExperimentTypeIconLabelComponent`
- タグ: `TagListComponent`
- ステータス: `StatusIconLabelComponent`
- ハイパーパラメーター・メトリクス: `HyperParamMetricColumnComponent`

また、チェックボックスや一部のメニューにはAngular Materialも併用しています。

## 結論

Experiments画面のテーブルは、**PrimeNGの`p-table`をClearML独自の`<sm-table>`でラップし、Experiments固有のセルテンプレートを差し込む構成**です。

Ag GridやAngular Material Tableがテーブル本体になっているわけではありません。Angular Materialは、チェックボックスやメニューなどの周辺UIに使用されています。

使用しているPrimeNGのバージョン指定は`package.json`の`^22.1.0`です。

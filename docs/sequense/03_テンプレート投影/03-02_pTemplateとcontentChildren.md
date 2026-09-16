# 03-02 pTemplate と contentChildren

`sm-experiments-table` は `sm-table` の中に 7 種類の `ng-template` を書き込む。
`sm-table` はそれを `contentChildren(PrimeTemplate)` で集め、
`ngAfterContentInit` で種類ごとにフィールドへ振り分けてから `ngTemplateOutlet` で描く。

`pTemplate` は PrimeNG の `PrimeTemplate` ディレクティブで、
`ng-template` に「名前」を付けるためだけに使われている。

## 図1: 収集と振り分け

```mermaid
sequenceDiagram
    autonumber
    participant ExpTable as sm-experiments-table
    participant PT as PrimeTemplate ディレクティブ
    participant SmTable as sm-table

    Note over ExpTable: sm-table の中に<br/>ng-template pTemplate="body" などを 7 つ書く
    ExpTable->>PT: 各 ng-template に PrimeTemplate ディレクティブが付く
    PT->>PT: type = 'body' / 'card' / 'sort-filter' / ...
    Note over SmTable: templates = contentChildren(PrimeTemplate)

    SmTable->>SmTable: ngAfterContentInit()
    loop templates() の各要素
        SmTable->>PT: item.getType()
        alt 'body'
            SmTable->>SmTable: bodyTemplate = item.template
        else 'card'
            SmTable->>SmTable: cardTemplate = item.template
        else 'sort-filter'
            SmTable->>SmTable: sortFilterTemplate = item.template
        else 'checkbox'
            SmTable->>SmTable: checkboxTemplate = item.template
        else 'cardFilter'
            SmTable->>SmTable: cardHeaderTemplate = item.template
        else 'rowexpansion'
            SmTable->>SmTable: rowExpansionTemplate = item.template
        else それ以外
            SmTable->>SmTable: bodyTemplate = item.template（既定）
        end
    end
```

## 図2: 1 セルが描かれるまで

```mermaid
sequenceDiagram
    autonumber
    participant PT as p-table
    participant SmTable as sm-table
    participant Body as bodyTemplate<br/>（ExpTable で宣言）
    participant Cell as sm-hyper-param-metric-column ほか

    PT->>SmTable: 行データ rowData と可視列 visibleColumns を渡す
    loop 可視列ごと
        SmTable->>Body: ngTemplateOutlet で bodyTemplate を描画<br/>context は $implicit=col, rowData, rowIndex, expanded
        Body->>Body: @switch (col.id) で列種別を判定
        alt 既知の列（name / status / tags / user ...）
            Body->>Cell: 専用コンポーネントやパイプで描画
        else それ以外（メトリクス列・ハイパーパラメータ列）
            Body->>Cell: sm-hyper-param-metric-column に col と experiment を渡す
        end
    end
```

`@switch` の `@default` がメトリクス列とハイパーパラメータ列を受け持つ。
これらは実行時に URL から復元されて増える列なので、固定の `@case` を書けない。

## 図3: テーブル表示とカード表示の切り替え

```mermaid
sequenceDiagram
    autonumber
    participant EC as ExperimentsComponent
    participant ExpTable as sm-experiments-table
    participant SmTable as sm-table

    EC->>ExpTable: [minimizedView]=minimizedView()
    ExpTable->>SmTable: [minimizedView]
    alt minimizedView が false（一覧全画面）
        SmTable->>SmTable: header + bodyTemplate で表として描画
        SmTable->>SmTable: sortFilterTemplate を各列ヘッダに描画
    else true（Info パネルが開いていて幅が狭い）
        SmTable->>SmTable: cardHeaderTemplate（cardFilter）をヘッダに描画
        SmTable->>SmTable: cardTemplate を 1 行 1 枚で描画
    end
```

同じ `sm-table` に対して、表用のテンプレートとカード用のテンプレートを
両方渡しておき、描画時にどちらを使うかだけ切り替えている。
`sm-experiments-table` 側は両方を常に宣言している。

## 読みどころ

- 収集と振り分け: [table.component.ts:334](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/shared/ui-components/data/table/table.component.ts:334)
- 受け皿のフィールド定義: [table.component.ts:85](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/shared/ui-components/data/table/table.component.ts:85)
- `contentChildren`: [table.component.ts:104](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/shared/ui-components/data/table/table.component.ts:104)
- 描画側の `ngTemplateOutlet`: [table.component.html:154](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/shared/ui-components/data/table/table.component.html:154)
- テンプレート宣言側: [experiments-table.component.html:37](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html:38)

`templates` は `contentChildren`（signal ベースのクエリ）で宣言されているが、
読み出しは `ngAfterContentInit` で 1 回だけ行い、以後はフィールドに保持した
`TemplateRef` を使い続ける。

そのため、`@if` で囲われたテンプレートは初期評価の結果しか反映されない。
実際に `pTemplate="checkbox"` は `@if (enableMultiSelect())` の中にある
（[experiments-table.component.html:56](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html:56)）。
`enableMultiSelect` は `input(true)` の既定値のまま使われるか、呼び出し側で固定値を渡すだけなので、
現状の使い方では問題にならない。

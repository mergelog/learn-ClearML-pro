# 03-04 ng-content によるカード組み立て

`ng-content` を使っているのは `sm-table-card` である。
`sm-experiments-table` が `pTemplate="card"` の中に `<sm-table-card>` を書き、
その子要素をカード側が `select` 属性で slot に振り分ける。

カード表示は Info パネルが開いていて一覧の幅が狭いとき（`minimizedView()` が true）に使われる。

## 図: 投影が起きる順序

```mermaid
sequenceDiagram
    autonumber
    participant SmTable as sm-table
    participant CardTpl as cardTemplate<br/>（ExpTable で宣言）
    participant Card as sm-table-card
    participant Slot as ng-content slots

    SmTable->>CardTpl: ngTemplateOutlet で cardTemplate を描画<br/>context は rowData, rowNumber, selected
    CardTpl->>Card: sm-table-card に cardName, columns, rowData, checked,<br/>tagsTemplate=tagList, compactColDataTemplate=compactCol を渡す
    Note over CardTpl,Card: 開始タグと終了タグの間に書いた要素が投影対象

    CardTpl->>Slot: div[sm-name-icon]（共有アイコン）
    CardTpl->>Slot: div[sm-name-version]（バージョン表示）
    CardTpl->>Slot: sm-experiment-type-icon-label
    CardTpl->>Slot: div[sm-mini-tags]（折りたたみ時のタグ）
    CardTpl->>Slot: sm-status-icon-label
    CardTpl->>Slot: mat-checkbox

    Card->>Slot: ng-content select="mat-checkbox"
    Card->>Slot: ng-content select="sm-experiment-type-icon-label"
    Card->>Slot: ng-content select="[sm-name-icon]"
    Card->>Slot: ng-content select="[sm-name-version]"
    Card->>Slot: ng-content select="[sm-mini-tags]"
    Card->>Slot: ng-content select="sm-status-icon-label"
    Note over Card,Slot: 書いた順ではなく、カード側のレイアウト上の位置に配置される
```

## 投影とテンプレート渡しの併用

同じ `sm-table-card` に対して、2 つの方式が同時に使われている。

| 渡すもの | 方式 | 理由 |
| --- | --- | --- |
| アイコン、ステータス、チェックボックス | `ng-content`（slot 分配） | 常に 1 個ずつ、位置が固定 |
| タグ一覧（`#tagList`） | `input` + `ngTemplateOutlet` | カード側が `@if(tagsTemplate())` で有無を判定して描く |
| 補足列（`#compactCol`） | `input` + `ngTemplateOutlet` | 同上 |

`ng-content` の投影は、渡されたかどうかをカード側で判定しづらい。
`TemplateRef` を `input` で受け取る形なら `@if(tagsTemplate())` で分岐でき、
渡されなかった場合のラッパー要素ごと省略できる
（[table-card.component.html:30](../../../src/app/webapp-common/shared/ui-components/data/table-card/table-card.component.html:30)）。
カードのタグ行・補足行は他の画面では使わないため、この形になっている。

## 評価文脈

`ng-content` で投影した `<mat-checkbox (click)="rowSelectedChanged(...)">` の
`rowSelectedChanged` は `sm-experiments-table` のメソッドである。
投影しても評価文脈は移らない。

## 読みどころ

- 投影元（カードテンプレート）: [experiments-table.component.html:215](../../../src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html:215)
- slot 定義: [table-card.component.html:10](../../../src/app/webapp-common/shared/ui-components/data/table-card/table-card.component.html:10)
- テンプレート渡しの 2 つ: [experiments-table.component.html:269](../../../src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html:269)
- カード描画の呼び出し元: [table.component.html:165](../../../src/app/webapp-common/shared/ui-components/data/table/table.component.html:165)

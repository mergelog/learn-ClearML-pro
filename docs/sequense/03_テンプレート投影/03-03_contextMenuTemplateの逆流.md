# 03-03 contextMenuTemplate の逆流

`sm-experiment-menu-extended` は `ExperimentsComponent` のテンプレート末尾で宣言されているのに、
DOM 上は `sm-experiments-table` の中に現れる。
そして `ExperimentsComponent` の `viewChild.required` はそれを取得できる。

DOM の位置（挿入ビュー）と、クエリやバインディングの基準（宣言ビュー）が食い違う例である。

## 図1: 渡されて実体化するまで

```mermaid
sequenceDiagram
    autonumber
    participant EC as ExperimentsComponent
    participant ExpTable as sm-experiments-table
    participant View as 埋め込みビュー
    participant Menu as sm-experiment-menu-extended

    Note over EC: ng-template contextMenuExtendedTemplate の中に<br/>sm-experiment-menu-extended を書く
    EC->>EC: この時点では TemplateRef があるだけで<br/>Menu のインスタンスは存在しない

    EC->>ExpTable: contextMenuTemplate に contextMenuExtendedTemplate を渡す
    ExpTable->>View: ngTemplateOutlet で contextMenuTemplate() を描画<br/>context の $implicit は contextExperiment()（テンプレート 1 行目）
    View->>Menu: インスタンス生成
    Note right of Menu: DOM 位置 = ExpTable のホスト要素の直下

    EC->>EC: contextMenuExtended = viewChild.required(ExperimentMenuExtendedComponent)
    EC-->>Menu: 解決される
    Note over EC,Menu: 埋め込みビューは EC のテンプレートから生成されたため、<br/>EC のビュークエリの探索範囲に入る
```

## 図2: バインディングの評価者

```mermaid
sequenceDiagram
    autonumber
    participant ExpTable as sm-experiments-table
    participant View as 埋め込みビュー
    participant EC as ExperimentsComponent
    participant Menu as sm-experiment-menu-extended

    ExpTable->>View: context.$implicit = contextExperiment()
    Note right of View: let-contextExperiment で受ける<br/>＝ ExpTable の状態はここだけ流れ込む

    View->>EC: selectedExperiments の式を評価
    Note right of EC: singleRowContext / checkedExperiments は EC のフィールド
    View->>EC: projectTags の式 tags$ | ngrxPush を評価
    Note right of EC: tags$ も EC の Observable
    EC-->>Menu: 評価結果が input に入る

    Menu->>EC: (menuOpened) → setContextMenuStatus(true)
    Note right of EC: output も EC のメソッドに繋がる
```

テンプレート内の式はすべて `ExperimentsComponent` のインスタンスを `this` として評価される。
`sm-experiments-table` から届くのは `let-contextExperiment` で受け取った 1 個の値だけである。

## なぜこの形になっているか

コンテキストメニューの実体を `sm-experiments-table` の中に入れておくと、
右クリックした行の近くにメニューを重ねられる。
一方でメニューが必要とする値（チェック済み一覧、タグ一覧、活性判定）は
`ExperimentsComponent` 側にある。

テンプレートだけを渡す形にすると、
`sm-experiments-table` に「メニューの入力を中継するための `input`」を足さずに済む。
`sm-experiments-table` が知っているのは `contextMenuTemplate` という `TemplateRef` 1 つだけで、
中身が何であるかを知らない。

## 読みどころ

- テンプレート宣言: [experiments.component.html:140](../../../src/app/webapp-common/experiments/experiments.component.html:140)
- 受け渡し: [experiments.component.html:94](../../../src/app/webapp-common/experiments/experiments.component.html:94)
- 描画位置: [experiments-table.component.html:1](../../../src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html:1)
- `input` 定義: [experiments-table.component.ts:119](../../../src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts:119)
- `viewChild.required`: [experiments.component.ts:240](../../../src/app/webapp-common/experiments/experiments.component.ts:240)
- メニューを開く側: [experiments.component.ts:735](../../../src/app/webapp-common/experiments/experiments.component.ts:735)

`viewChild.required` は解決できないと実行時に例外を投げる。
ここで `required` を使えているのは、`contextMenuTemplate` が
`sm-experiments-table` のテンプレート 1 行目で `@if` なしに常に描画されるためである。

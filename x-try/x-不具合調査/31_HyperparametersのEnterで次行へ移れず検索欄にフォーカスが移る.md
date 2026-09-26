# Hyperparameters の Enter で次行へ移れず、ページ上部の検索欄にフォーカスが移る

| 項目 | 内容 |
|---|---|
| カテゴリー | 操作 |
| 不具合内容 | Hyperparameters の編集時にパラメータ名または値で Enter を押すと、次行の入力欄へ移動するはずが、ページ上部の検索欄にフォーカスが移る |
| 期待動作 | 次行がある場合はその行の入力欄へ、最終行では追加した行の入力欄へフォーカスを移す |
| 直さないと困ること | 多数のパラメータをキーボードで編集する利用者が、毎回入力位置を探してクリックし直す必要がある |
| 修正規模 | 小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験管理 > 詳細 > Hyperparameters |
| 観点 | J（操作性とアクセシビリティ） |
| 重大度 | S3 |
| 確度 | 再現済み |
| 由来 | 上流 |
| 発生条件 | 編集モードで、仮想スクロール領域にあるパラメータの入力欄で通常の Enter を押す |
| 関連 | [02](./02_名前変更ダイアログ・タグ追加・実行パラメータで変換確定のEnterにより確定処理が走る.md)（IME の Enter）、[08](./08_編集セクションでEscを押すと確認なしに編集全体が取り消される.md)（同じ編集セクション） |

## 症状

調査用タスク（General に3件の Hyperparameters）を編集し、先頭行の値で通常の Enter を押すと、次の行の値欄ではなく、タスク一覧上部の `Type to search` 検索欄がフォーカスされた。Enter は `preventDefault()` されるため、値の保存やフォーム送信は起きない。

## 再現手順

1. 3件以上の Hyperparameters を持つ下書きタスクを開く
2. Hyperparameters の EDIT を押す
3. 表示中のパラメータ名または値の入力欄で、IME 変換中ではない通常の Enter を押す
4. 次の行ではなくページ上部の検索欄にフォーカスが移る

Playwright の再現は [scripts/p3-experiments-navigation.spec.ts](./scripts/p3-experiments-navigation.spec.ts) にある。実データへの保存要求は送らず、最後に CANCEL を押す。

## 原因

[experiment-execution-parameters.component.html:14](../src/app/webapp-common/experiments/dumb/experiment-execution-parameters/experiment-execution-parameters.component.html#L14)・[同:43](../src/app/webapp-common/experiments/dumb/experiment-execution-parameters/experiment-execution-parameters.component.html#L43) は Enter ごとに `nextRow()` を呼ぶ。

[experiment-execution-parameters.component.ts:234](../src/app/webapp-common/experiments/dumb/experiment-execution-parameters/experiment-execution-parameters.component.ts#L234) は `viewChildren<MatInput>('row')` の `index + 1` を50ms後に focus する。しかし編集フォームは [HTML:3](../src/app/webapp-common/experiments/dumb/experiment-execution-parameters/experiment-execution-parameters.component.html#L3) の `cdk-virtual-scroll-viewport` 内にあり、画面外の次行は `rows()` に生成されていない。`scrollToIndex()` で次行を描画してから focus する処理もないため、focus 対象が `undefined` となる。

## 影響範囲と同種箇所

- Hyperparameters の Parameter / Value の両方で発生する
- `nextRow()` は最終行では `addRow()` も呼ぶため、追加直後の行が描画される前に同じ問題を起こし得る
- 実行パラメータの入力はこのコンポーネントだけで扱うため、ほかの詳細タブには波及しない

## 対策案

`nextRow()` で次の index を決めたら、`CdkVirtualScrollViewport.scrollToIndex(nextIndex)` を実行する。レンダリング完了を待って `rows()` から対象を取得して focus する。最終行の追加後も同じ経路を使う。失敗時に現在のフォーカスをページ外の検索欄へ渡さないことを回帰テストで確認する。

## 検証範囲

- 確認したこと：Playwright（Chromium）と実バックエンドの調査用タスクで、Enter 後の `document.activeElement` が `data-id="searchInputField"` になることを確認した。3件の General パラメータを持つことは ClearML API で読み取り確認した
- 確認していないこと：タッチ端末、スクロール済みの位置、ブラウザ・支援技術ごとのフォーカス移動
- 由来：対象の TypeScript・HTML は比較資料で実質差分に含まれない

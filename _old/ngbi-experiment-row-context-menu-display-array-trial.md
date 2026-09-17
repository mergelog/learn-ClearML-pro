# Bulletin Trial: 実験一覧の右クリックメニューをオブジェクト配列で追う

この資料は、説明を先に読むのではなく、`flow[0]` から順番にリンク先の実装を開きながら処理を追うための試作版。

JSONコードブロック内ではMarkdownリンクをクリックできないため、**構造はJSON風、記法はMarkdown**としている。

```text
flow[0] → flow[1] → flow[2] → flow[3] → flow[4] → flow[5]
```

---

<a id="flow0"></a>

## `flow[0]` — 行の右クリックを検出

- `"トリガー（呼び出し元。通常は上のオブジェクト）"`:
  - `"呼び出し元"`: ユーザー操作
  - `"発生イベント"`: 実験一覧の行を右クリック
  - `"接続根拠"`: 行に `[pContextMenuRow]="rowData"` が設定されている

- `"クラス名:行番号"`:
  - `TableComponent template:124`
  - `TableComponent template:36`

- `"リンク"`:
  - [右クリック対象となる行 `pContextMenuRow`](./src/app/webapp-common/shared/ui-components/data/table/table.component.html#L124)
  - [PrimeNGイベントの受け口 `onContextMenuSelect`](./src/app/webapp-common/shared/ui-components/data/table/table.component.html#L36)

- `"概要"`:
  - `"これは何を表示するComponentか"`: 列定義と行データを受け取り、アプリ内の各一覧画面で再利用される共通テーブル
  - `"誰からデータをもらうか"`: この画面では `ExperimentsTableComponent` から実験一覧を受け取る
  - `"誰にイベントを返すか"`: 右クリック情報を `rowRightClick` で `ExperimentsTableComponent` へ返す

- `"処理概要"`:
  - `"技術"`: PrimeNG `p-table` / `pContextMenuRow` / `onContextMenuSelect`
  - `"処理"`: PrimeNGが右クリックされた行の `rowData` と元のマウスイベントを組み立て、`openContext($event)` を呼ぶ
  - `"注意"`: [`p-context-menu #cm`](./src/app/webapp-common/shared/ui-components/data/table/table.component.html#L214) は `d-none`。ここでは表示せず、イベント検出だけに使う

- `"影響範囲"`:
  - `"影響名"`: 共通テーブルの `openContext()` が実行される
  - `"画面表示"`: この時点ではアプリ独自のメニューはまだ表示されない

- `"次の遷移"`: [`flow[1] — 右クリック情報を実験テーブルへ返す`](#flow1)

---

<a id="flow1"></a>

## `flow[1]` — 右クリック情報を実験テーブルへ返す

- `"トリガー（呼び出し元。通常は上のオブジェクト）"`:
  - `"呼び出し元"`: [`flow[0]`](#flow0) の `onContextMenuSelect`
  - `"呼び出しコード"`: `(onContextMenuSelect)="openContext($event)"`
  - `"接続根拠"`: テンプレートのイベントバインディングが `TableComponent.openContext()` を直接呼ぶ

- `"クラス名:行番号"`:
  - `TableComponent.openContext():421`

- `"リンク"`:
  - [`TableComponent.openContext()`](./src/app/webapp-common/shared/ui-components/data/table/table.component.ts#L421)
  - [`rowRightClick` outputの定義](./src/app/webapp-common/shared/ui-components/data/table/table.component.ts#L174)
  - [`ExperimentsTableComponent` 側の受信](./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html#L31)

- `"概要"`:
  - `"これは何を表示するComponentか"`: `flow[0]` と同じ共通テーブル。ここでは表示よりもイベント中継を担当する
  - `"誰からデータをもらうか"`: PrimeNGから `originalEvent` と右クリックされた `data` を受け取る
  - `"誰にイベントを返すか"`: `rowRightClick` を購読する `ExperimentsTableComponent`

- `"処理概要"`:
  - `"技術"`: Angular `EventEmitter` / `@Output()`
  - `"中心コード"`: `rowRightClick.emit({e: originalEvent, rowData: data, single})`
  - `"処理"`: PrimeNG固有のイベントを、アプリ側が扱う `{e, rowData, single}` へ変換して上位Componentへ渡す
  - `"後処理"`: PrimeNGの選択状態を解除し、非表示の `p-context-menu` を閉じる

- `"影響範囲"`:
  - `"影響名"`: 右クリック処理が共通テーブルから実験固有テーブルへ移る
  - `"状態変更"`: PrimeNGの `contextMenuSelection` は `null` に戻る

- `"次の遷移"`: [`flow[2] — 対象実験と座標を確定する`](#flow2)

---

<a id="flow2"></a>

## `flow[2]` — 対象実験と座標を確定する

- `"トリガー（呼び出し元。通常は上のオブジェクト）"`:
  - `"呼び出し元"`: [`flow[1]`](#flow1) の `rowRightClick.emit(...)`
  - `"受信コード"`: `(rowRightClick)="openContextMenu($event)"`
  - `"接続根拠"`: `ExperimentsTableComponent` のテンプレートが `rowRightClick` を購読している

- `"クラス名:行番号"`:
  - `ExperimentsTableComponent.openContextMenu():349`

- `"リンク"`:
  - [`ExperimentsTableComponent.openContextMenu()`](./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L349)
  - [`contextExperiment` Signal](./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L197)
  - [`contextMenu` output](./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L165)

- `"概要"`:
  - `"これは何を表示するComponentか"`: 実験一覧の列、セル、選択状態、カード表示など、実験固有のテーブルUI
  - `"誰からデータをもらうか"`: `ExperimentsComponent` から実験一覧、チェック済み実験、列定義などをinputで受け取る
  - `"誰にイベントを返すか"`: メニュー表示要求を `contextMenu` outputで `ExperimentsComponent` へ返す

- `"処理概要"`:
  - `"技術"`: Angular `signal()` / `output()`、DOM `MouseEvent`
  - `"対象確定"`: 右クリックされた実験を `contextExperiment` へ保存する
  - `"選択分岐"`: 未チェック行なら選択対象をその1件へ変更し、チェック済み行なら現在の複数選択を維持する
  - `"標準動作の抑止"`: `event.preventDefault()` でブラウザ標準メニューを止める
  - `"表示要求"`: `contextMenu.emit({x: event.clientX, y: event.clientY, ...})` で座標を親へ渡す

- `"影響範囲"`:
  - `"影響名"`: メニュー操作の対象実験が決まる
  - `"状態変更"`: 未チェック行の場合のみ、実験のチェック状態も変わる
  - `"出力"`: 親Componentへ右クリック位置が通知される

- `"次の遷移"`: [`flow[3] — 表示対象のメニューComponentを呼ぶ`](#flow3)

---

<a id="flow3"></a>

## `flow[3]` — 表示対象のメニューComponentを呼ぶ

- `"トリガー（呼び出し元。通常は上のオブジェクト）"`:
  - `"呼び出し元"`: [`flow[2]`](#flow2) の `contextMenu.emit(...)`
  - `"受信コード"`: `(contextMenu)="onContextMenuOpen($event)"`
  - `"接続根拠"`: 親テンプレートが `ExperimentsTableComponent` のoutputを購読している

- `"クラス名:行番号"`:
  - `ExperimentsComponent.onContextMenuOpen():735`

- `"リンク"`:
  - [`contextMenu` の受信](./src/app/webapp-common/experiments/experiments.component.html#L111)
  - [`ExperimentsComponent.onContextMenuOpen()`](./src/app/webapp-common/experiments/experiments.component.ts#L735)
  - [`contextMenuExtended` と `contextMenu` computed](./src/app/webapp-common/experiments/experiments.component.ts#L240)

- `"概要"`:
  - `"これは何を表示するComponentか"`: 実験管理画面全体。検索、一覧、詳細パネル、フッター、コンテキストメニューを束ねるContainer Component
  - `"誰からデータをもらうか"`: NgRx Storeの実験状態と、子Componentが出力するユーザー操作
  - `"誰にイベントを返すか"`: この地点ではoutputせず、子のメニューComponentを直接操作する

- `"処理概要"`:
  - `"技術"`: Angular `viewChild.required()` / `computed()` / Component継承
  - `"状態保存"`: `singleRowContext` と `menuBackdrop` を更新する
  - `"参照解決"`: `contextMenu()` が `ExperimentMenuExtendedComponent` から共通の `ExperimentMenuComponent` 参照を返す
  - `"表示依頼"`: `this.contextMenu().openMenu({x, y})` を直接呼ぶ

- `"事前条件"`:
  - `"テンプレート定義"`: [`contextMenuExtendedTemplate`](./src/app/webapp-common/experiments/experiments.component.html#L140)
  - `"子への受け渡し"`: [`[contextMenuTemplate]="contextMenuExtendedTemplate"`](./src/app/webapp-common/experiments/experiments.component.html#L94)
  - `"描画"`: [`ngTemplateOutlet`](./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html#L1)
  - `"意味"`: 右クリック前からメニューComponentがビュー内に存在するため、`viewChild.required()` で取得できる

- `"影響範囲"`:
  - `"影響名"`: 座標データがイベント通知からメニューComponentへのメソッド呼び出しに変わる
  - `"状態変更"`: 単一行向けメニューか、backdropを持つメニューかが確定する

- `"次の遷移"`: [`flow[4] — 非表示トリガーを右クリック位置へ移動する`](#flow4)

---

<a id="flow4"></a>

## `flow[4]` — 非表示トリガーを右クリック位置へ移動する

- `"トリガー（呼び出し元。通常は上のオブジェクト）"`:
  - `"呼び出し元"`: [`flow[3]`](#flow3) の `this.contextMenu().openMenu({x, y})`
  - `"呼び出し先"`: `ExperimentMenuComponent` が継承する `BaseContextMenuComponent.openMenu()`
  - `"接続根拠"`: 派生Componentに同名メソッドはなく、基底クラスの実装へ到達する

- `"クラス名:行番号"`:
  - `BaseContextMenuComponent.openMenu():48`

- `"リンク"`:
  - [`BaseContextMenuComponent.openMenu()`](./src/app/webapp-common/shared/components/base-context-menu/base-context-menu.component.ts#L48)
  - [`position` Signal](./src/app/webapp-common/shared/components/base-context-menu/base-context-menu.component.ts#L36)
  - [座標を使用する非表示トリガー](./src/app/webapp-common/experiments/shared/components/experiment-menu/experiment-menu.component.html#L11)

- `"概要"`:
  - `"これは何を表示するComponentか"`: 自身は表示を持たず、実験・モデルなどのコンテキストメニューに共通する開閉処理を提供する基底Component
  - `"誰からデータをもらうか"`: 呼び出し元から `{x, y}` をメソッド引数で受け取る
  - `"誰にイベントを返すか"`: 開閉時に `menuOpened` / `menuClosed` を利用側へ返す

- `"処理概要"`:
  - `"技術"`: Angular `signal()` / `viewChild(MatMenuTrigger)`、CSS `position: fixed`
  - `"既存メニュー"`: 開いていれば一度閉じる
  - `"座標反映"`: `position.set({x, y})` により、非表示トリガーの `left` / `top` が右クリック位置へ変わる
  - `"待機理由"`: `setTimeout(..., 100)` でテンプレートへの座標反映後に次の表示処理を行う

- `"影響範囲"`:
  - `"影響名"`: Angular Materialがメニュー位置を計算するときの基準点が変わる
  - `"画面表示"`: トリガーは `visibility: hidden` のため見えない

- `"次の遷移"`: [`flow[5] — Angular Materialのメニューを表示する`](#flow5)

---

<a id="flow5"></a>

## `flow[5]` — Angular Materialのメニューを表示する

- `"トリガー（呼び出し元。通常は上のオブジェクト）"`:
  - `"呼び出し元"`: [`flow[4]`](#flow4) の100ms後に実行されるコールバック
  - `"呼び出しコード"`: `this.trigger().updatePosition(); this.trigger().openMenu()`
  - `"接続根拠"`: 非表示トリガーの `[matMenuTriggerFor]` が `experimentMenu` を参照している

- `"クラス名:行番号"`:
  - `BaseContextMenuComponent.openMenu():54`
  - `ExperimentMenuComponent template:18`

- `"リンク"`:
  - [`MatMenuTrigger` の位置更新と表示](./src/app/webapp-common/shared/components/base-context-menu/base-context-menu.component.ts#L54)
  - [`[matMenuTriggerFor]="experimentMenu"`](./src/app/webapp-common/experiments/shared/components/experiment-menu/experiment-menu.component.html#L11)
  - [`mat-menu #experimentMenu`](./src/app/webapp-common/experiments/shared/components/experiment-menu/experiment-menu.component.html#L18)

- `"概要"`:
  - `"これは何を表示するComponentか"`: 実験に対する詳細表示、キュー操作、共有、削除、アーカイブなどの操作メニュー
  - `"誰からデータをもらうか"`: `ExperimentsComponent` から対象実験、選択実験、各操作の可否をinputで受け取る
  - `"誰にイベントを返すか"`: 開閉状態やタグ操作などを `ExperimentsComponent` へ返す

- `"処理概要"`:
  - `"技術"`: Angular Material `MatMenuTrigger` / `mat-menu`、Angular CDK Overlay
  - `"位置更新"`: `updatePosition()` が移動後のトリガーを基準にオーバーレイ位置を再計算する
  - `"表示"`: `openMenu()` が `#experimentMenu` をオーバーレイへ表示する
  - `"表示通知"`: `menuOpened.emit()` により、親の `contextMenuActive` が `true` になる

- `"影響範囲"`:
  - `"影響名"`: 実験のコンテキストメニューが右クリック位置へ表示される
  - `"行表示"`: `contextMenuActive` により、対象行のハイライトがメニュー表示中も維持される

- `"次の遷移"`: `Bulletin到達点。メニュー項目クリック後は今回の対象外`

---

## Bulletin到達点

`flow[0]` の行右クリックから `flow[5]` の `experimentMenu` 表示まで、振る舞いの遷移順に実装を追跡した。

# 編集セクションで、変換取消の Esc や一覧を閉じる Esc を押すと、確認なしにセクション全体の編集が取り消される

| 項目 | 内容 |
|---|---|
| カテゴリー | 操作 |
| 不具合内容 | 詳細画面の編集セクション（Hyperparameters、Execution の SOURCE CODE など）の編集中に、日本語の変換を取り消す Esc や、ドロップダウン（`mat-select`）の一覧を閉じる Esc を押すと、セクションの編集全体が取り消され、ほかの欄に入力済みの変更も失われる |
| 期待動作 | 変換中の Esc は変換だけを、一覧を開いているときの Esc は一覧だけを閉じ、編集は続く |
| 直さないと困ること | 複数の欄を書き換えている途中の利用者が、確認なしに入力をすべて失う。Hyperparameters のように行の多いセクションでは、やり直しの手間が大きい |
| 修正規模 | 小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験管理 > 詳細（CONFIGURATION の Hyperparameters、EXECUTION の各セクション、INFO の説明など）、モデル > 詳細（METADATA、LABELS） |
| 観点 | A（IME）、J（操作性） |
| 重大度 | S2 |
| 確度 | 再現済み（変換取消の Esc は模擬 IME での再現。実機の IME が変換中の Esc を `key: 'Escape'` の keydown として届けるかは要実機確認） |
| 由来 | 上流 |
| 発生条件 | 変換取消の Esc：変換中の Esc で `key: 'Escape'` の keydown が届くブラウザ・IME。一覧を閉じる Esc：ブラウザを問わない |
| 関連 | [03](./03_インライン編集で変換取消のEscにより編集全体が取り消される.md)（インライン編集の同じ型。取り消される範囲は1つの欄） |

## 症状

| 操作 | 起きること | 確認 |
|---|---|---|
| Hyperparameters の編集中に、1行目の値を書き換え、2行目の値で「がくしゅう」を変換中に Esc | 編集モードが閉じ、1行目の変更も失われる。保存の API は呼ばれない | 再現（模擬 IME） |
| Execution の SOURCE CODE の編集中に、Script path を書き換え、Type の一覧を開いて Esc で閉じる | 一覧が閉じると同時に編集モードも閉じ、Script path の変更も失われる | 再現 |

どちらも確認のダイアログは出ない。Esc で編集を取り消す動き自体は設計どおりで（変換中でも一覧を開いてもいない通常の Esc）、問題は、別の目的の Esc まで同じ取り消しとして扱われることである。

## 再現手順

実バックエンドの調査用タスク A（draft）で行う。どちらの手順も保存せず、書き込みの API が呼ばれないことを確かめている。

変換取消の Esc：

1. タスクの CONFIGURATION > Hyperparameters > General で EDIT を押す
2. 1行目の値の末尾に `-edited` と入力する
3. 2行目の値の末尾で日本語入力に切り替え、「がくしゅう」と打って、変換中に Esc を押す
4. 編集モードが閉じ、1行目の値も元に戻っている

一覧を閉じる Esc：

1. タスクの EXECUTION で、SOURCE CODE の EDIT を押す
2. Script path を `train_edited.py` に書き換える
3. Type のドロップダウンを開き、Esc で閉じる
4. 編集モードが閉じ、Script path も元に戻っている

スクリプトは [scripts/p2a-editable-section-esc.spec.ts](./scripts/p2a-editable-section-esc.spec.ts)。変換中の状態と keydown の模擬は [01](./01_インライン編集で変換確定のEnterにより編集が終了する.md) と同じ方法である。

## 期待する動作

- 変換中の Esc では、変換だけが取り消され、編集は続く
- 一覧を開いているときの Esc では、一覧だけが閉じ、編集は続く
- 一覧も変換も無い状態の Esc では、これまでどおり編集を取り消す

## 原因

[editable-section.component.ts:51](../src/app/webapp-common/shared/ui-components/panel/editable-section/editable-section.component.ts#L51) の `@HostListener('document:keydown')` が、編集中にダイアログが開いていなければ、`e.key == 'Escape'` だけを見て `cancelClickedEvent()` を呼ぶ。キーがどこで押されたか、変換中か、ほかの部品がすでに処理したかを見ていない。

- 変換取消の Esc：`isComposing` と `keyCode === 229` を見ていないため、変換中の Esc も取り消しとして扱う
- 一覧を閉じる Esc：`mat-select` は一覧（オーバーレイ）の keydown で Esc を受けると、`preventDefault()` して一覧を閉じるが、`stopPropagation()` はしない（`@angular/material` の `select.mjs` の `_handleOverlayKeydown`）。keydown はそのまま document まで届き、このハンドラが編集を取り消す。`defaultPrevented` を見ていないため、処理済みの Esc と区別できない

`mat-autocomplete` は一覧を閉じる Esc で `stopPropagation()` するため、この症状は出ない。ダイアログは `matDialog.openDialogs.length === 0` で除外されている。

## 影響範囲と同種箇所

`sm-editable-section` を使う9つのテンプレートすべてが対象になる。

| テンプレート | 入力欄・一覧 |
|---|---|
| [experiment-info-hyper-parameters-form-container](../src/app/webapp-common/experiments/containers/experiment-info-hyper-parameters-form-container/experiment-info-hyper-parameters-form-container.component.html) | パラメータ名・値・説明の入力欄（`experiment-execution-parameters`） |
| [experiment-info-execution](../src/app/webapp-common/experiments/containers/experiment-info-execution/experiment-info-execution.component.html) | SOURCE CODE（リポジトリ・コミット・スクリプトのパスなどの入力欄と Type の `mat-select`）、requirements の種類の `mat-select`、コンテナ、出力先など |
| [experiment-details](../src/app/webapp-common/experiments/dumb/experiment-details/experiment-details.component.html) | 説明 |
| [model-info-metadata](../src/app/webapp-common/models/containers/model-info-metadata/model-info-metadata.component.html) | メタデータのキー・値・型 |
| [model-info-labels-view](../src/app/webapp-common/models/dumbs/model-info-labels-view/model-info-labels-view.component.html) | ラベル名・値 |
| experiment-info-task-model、experiment-info-model、experiment-artifact-item-view、model-view-network | 入力欄は少ないが、同じハンドラを持つ |

キーボードの Esc 以外に、`Ctrl+Enter` の保存も同じハンドラにある（[editable-section.component.ts:57](../src/app/webapp-common/shared/ui-components/panel/editable-section/editable-section.component.ts#L57)）。変換中に `Ctrl+Enter` を押す操作は通常ないため、対象から外した。

## 対策案

ハンドラの先頭で、次のどれかに当たる Esc を無視する。

- `e.isComposing || e.keyCode === 229`（[01](./01_インライン編集で変換確定のEnterにより編集が終了する.md) の第一案で作る共通の判定を使う）
- `e.defaultPrevented`（`mat-select` など、ほかの部品が処理済みの Esc）

第二案として、`document:keydown` をやめてセクションの要素の keydown で受ける案もあるが、編集中にフォーカスがセクションの外（背景の要素など）にあるときに Esc が効かなくなるため、第一案を勧める。変更は `editable-section` の1コンポーネントで完結するため「小」とした。

## 検証範囲

- 確認したこと：Playwright（Chromium、実バックエンドの調査用タスク A）で、Hyperparameters の変換中の Esc（模擬）と、SOURCE CODE の Type の一覧を閉じる Esc（実際のキー入力）で、編集モードが閉じ、ほかの欄の変更が失われること。どちらも書き込みの API が呼ばれないこと。変換中でない通常の Esc で編集が取り消されること（設計どおり）
- 確認していないこと：実機の IME で、変換中の Esc が `key: 'Escape'` の keydown として document まで届くか。モデルのメタデータ・ラベル、Execution のほかのセクションでの画面上の症状（ハンドラが同じため同じ症状になると判断した）
- 由来：`editable-section.component.*` は比較資料で上流と一致する。`mat-select` の Esc の扱いは Material 21 でも同じであり、上流でも同じ症状になる

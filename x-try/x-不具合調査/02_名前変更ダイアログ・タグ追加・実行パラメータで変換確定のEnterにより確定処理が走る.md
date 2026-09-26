# 名前変更ダイアログ・タグ追加・Hyperparameters の編集・資格情報ラベルで、日本語変換を確定する Enter により確定処理が走る

| 項目 | 内容 |
|---|---|
| カテゴリー | 操作 |
| 不具合内容 | 入力欄で日本語を変換中に Enter を押すと、変換の確定と同時に、ダイアログの確定・タグの追加・次の行への移動が走る。名前変更とタグ追加では、変換中の文字を含まない値が保存される |
| 期待動作 | 変換確定の Enter は変換を確定するだけで、ダイアログの確定などは変換後の Enter で行う |
| 直さないと困ること | 日本語で名前・タグを付ける利用者が、意図と違う名前・タグを保存する |
| 修正規模 | 中 |

| 項目 | 内容 |
|---|---|
| 画面 | 比較画面 > 凡例のメニュー > Rename、実験管理 > 詳細ヘッダー > タグ追加、実験管理 > CONFIGURATION > Hyperparameters の編集、設定 > 資格情報のラベル編集 |
| 観点 | A（IME） |
| 重大度 | S1（名前変更・タグ追加）。Hyperparameters と資格情報ラベルは S3 |
| 確度 | 名前変更・タグ追加・Hyperparameters はコード上確定（模擬 IME でアプリ上の再現済み）。資格情報ラベルは要実機確認 |
| 由来 | 上流 |
| 発生条件 | keydown が compositionend より前に `key: 'Enter'` で届くブラウザ（Chromium 系で報告が多い）。資格情報ラベルは keyup の届き方による |
| 関連 | [01](./01_インライン編集で変換確定のEnterにより編集が終了する.md)（インライン編集の同じ原因） |

## 症状

| 箇所 | 変換確定の Enter で起きること | 確認 |
|---|---|---|
| 名前変更ダイアログ | ダイアログが閉じ、変換前の値で名前が保存される | 再現（`調査タスクA-v2` のまま保存され、「テスト」が欠けた） |
| タグ追加メニュー | 変換前に確定していた文字列がタグとして追加される。確定済みの文字列が無ければ何も起きない | 再現（「v2」を打ってから「てすと」を変換し Enter → タグ `v2` が追加された） |
| Hyperparameters のパラメータ名 | 次の行へ移る処理が走り、最終行では空の行が1つ追加される | 再現（3行→4行） |
| 資格情報ラベルの編集 | `keyup.enter` のため、変換確定の keyup が届く実装では、確定した瞬間にダイアログが閉じてラベルが保存される | 未再現（要実機確認） |

名前変更とタグ追加は、値が変換前のもので確定するため、利用者の意図と違う値が保存される。Hyperparameters は入力中の値は失われないが、意図しない空の行が増える。追加された行はパラメータ名が空で、入力欄の `required` に掛かる。

## 再現手順

名前変更ダイアログ（実バックエンドの調査用プロジェクト `zz-不具合調査`）：

1. タスク一覧で2つのタスクを選び、比較画面を開く
2. 左上の TASKS ボタンで凡例を開き、タスク名の右のメニューから Rename を選ぶ
3. 名前の末尾に `-v2` と入力し、日本語入力で「てすと」と打って変換を確定する Enter を押す
4. ダイアログが閉じ、`{元の名前}-v2` で保存される

タグ追加（モック API）：

1. 実験の詳細ヘッダーで ADD TAG を押し、`v2` と入力する
2. 日本語入力で「てすと」と打って変換を確定する Enter を押す
3. `tasks.update_tags` が `add_tags: ['v2']` で送られる

Hyperparameters（実バックエンドの調査用タスク。CANCEL で破棄し、保存しない）：

1. 下書きのタスクの CONFIGURATION > Hyperparameters > General で EDIT を押す
2. 最終行のパラメータ名の末尾で「がくしゅう」と打ち、変換を確定する Enter を押す
3. 空の行が1つ追加される

スクリプトは [scripts/02-ime-enter-other.spec.ts](./scripts/02-ime-enter-other.spec.ts)（タグ）、[scripts/02b-compare-rename.spec.ts](./scripts/02b-compare-rename.spec.ts)（名前変更）、[scripts/02c-execution-parameters.spec.ts](./scripts/02c-execution-parameters.spec.ts)（Hyperparameters）。変換中の状態と keydown の模擬は 01 と同じ方法である。

## 期待する動作

変換確定の Enter ではどの確定処理も走らず、変換後の通常の Enter で走る。

## 原因

4箇所とも、Enter のハンドラが IME の変換中かどうかを見ていない。値は `DefaultValueAccessor` が compositionend で初めて反映するため、keydown の時点ではフォームの値が変換前のままである（[01](./01_インライン編集で変換確定のEnterにより編集が終了する.md) と同じ仕組み）。

| 箇所 | バインド | ハンドラの処理 |
|---|---|---|
| [rename-dialog.component.html:12](../src/app/webapp-common/shared/ui-components/overlay/rename-dialog/rename-dialog.component.html#L12) | `keydown.enter` | `!nameControl.invalid && closeDialog(true)`。`nameControl` の値（変換前）でダイアログを閉じる |
| [tags-menu.component.html:19](../src/app/webapp-common/shared/ui-components/tags/tags-menu/tags-menu.component.html#L19) | `keydown.enter` | [submit()](../src/app/webapp-common/shared/ui-components/tags/tags-menu/tags-menu.component.ts#L144) が `filterText()`（`valueChanges` を signal にしたもの。変換前）をタグとして追加する |
| [experiment-execution-parameters.component.html:14](../src/app/webapp-common/experiments/dumb/experiment-execution-parameters/experiment-execution-parameters.component.html#L14) | `keydown.enter` | [nextRow()](../src/app/webapp-common/experiments/dumb/experiment-execution-parameters/experiment-execution-parameters.component.ts#L230) が最終行なら行を追加し、次の行へフォーカスを移す |
| [edit-credential-label-dialog.component.html:5](../src/app/webapp-common/shared/ui-components/overlay/edit-credential-label-dialog/edit-credential-label-dialog.component.html#L5) | `keyup.enter` | `closeDialog(true)` でラベルを保存して閉じる |

資格情報ラベルの `keyup.enter` は、変換確定後の keyup が compositionend の後に `isComposing: false` で届く実装では変換確定と区別できない（x-QA/02「採らない方がよい案」）。keyup の届き方はブラウザと IME で違うため、要実機確認とした。

## 影響範囲と同種箇所

名前変更ダイアログは比較画面（タスク・モデル）の凡例から開く。実験のメニューにある `renamePopup()`（[experiment-menu.component.ts:322](../src/app/webapp-common/experiments/shared/components/experiment-menu/experiment-menu.component.ts#L322)）とデータセット版の Rename は、テンプレートから呼ばれていない（後者はコメントアウト）。タグ追加メニュー（`sm-tags-menu`）は11のテンプレートで使われる。実験・モデルの詳細ヘッダー、実験・モデル・パイプライン・レポート・データセット版のメニュー、一覧のフッター、全体検索の絞り込み、レポート画面である。

x-QA/02 の調査では、`$event.preventDefault()` や `control.markAsTouched()` だけを行う箇所と、数値入力（`duration-input` など）の `keyup.enter` を、IME による実害が出にくいとして対象から外している。横断観点 A（フェーズ2）で残りの `keydown`・`keyup` を洗い直す。

## 対策案

[01](./01_インライン編集で変換確定のEnterにより編集が終了する.md) の第一案で作る判定（`event.isComposing || event.keyCode === 229`）と Enter 用ディレクティブを、4箇所でも使う。資格情報ラベルは `keyup.enter` をやめ、ディレクティブの keydown で受ける。修正規模は、01 の共通部品ができていれば各箇所はテンプレートの置き換えで済むため、4箇所と確認を合わせて「中」とした。

## 検証範囲

- 確認したこと：名前変更ダイアログ（実バックエンド）、タグ追加（モック）、Hyperparameters（実バックエンド、保存せず破棄）で、変換中の keydown を合成したときの症状。比較画面の名前変更は、比較画面を URL で直接開いた場合もタスク一覧から遷移した場合も `tasks.update` まで届くこと（名前は試験後に元へ戻した）
- 確認していないこと：実機の IME での keydown・keyup の届き方。資格情報ラベルの症状（画面で操作していない）。Hyperparameters で、変換確定の後にフォーカスがどこへ移るか（模擬では次の行ではなくページの検索欄に移ったが、通常の Enter でも最終行以外では同じく検索欄に移ったため、IME とは別の挙動として横断観点 J・画面別の確認で扱う）
- 由来：4箇所のテンプレートとコンポーネントは比較資料で上流と一致する（`rename-dialog` は spec だけが違う）

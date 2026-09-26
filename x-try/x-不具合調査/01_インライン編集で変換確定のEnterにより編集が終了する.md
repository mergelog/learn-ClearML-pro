# インライン編集で、日本語変換を確定する Enter を押すと編集が終了し、変換中の文字を含まない値で保存・取消される

| 項目 | 内容 |
|---|---|
| カテゴリー | 操作 |
| 不具合内容 | 名前のインライン編集で日本語を変換中に Enter（または Tab）を押すと、変換の確定と同時に編集が終わる。変換前に確定していた変更があれば、変換中の文字を含まない名前で保存される |
| 期待動作 | 変換確定の Enter は変換を確定するだけで、編集は続く |
| 直さないと困ること | 日本語で名前を付ける利用者が、意図と違う名前を保存する。英字のあとに日本語を続ける名前（「baseline 実験」など）で起きやすい |
| 修正規模 | 中 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験管理 > 詳細ヘッダー > 名前のインライン編集（`sm-inline-edit` を使う全画面） |
| 観点 | A（IME） |
| 重大度 | S1 |
| 確度 | コード上確定（模擬 IME でアプリ上の再現済み。ブラウザごとの症状は要実機確認） |
| 由来 | 上流 |
| 発生条件 | keydown が compositionend より前に `key: 'Enter'` で届くブラウザ（Chromium 系で報告が多い）。Safari 型の届き方でも症状は出る（下記） |
| 関連 | [02](./02_名前変更ダイアログ・タグ追加・実行パラメータで変換確定のEnterにより確定処理が走る.md)（同じ原因の別箇所）、[03](./03_インライン編集で変換取消のEscにより編集全体が取り消される.md)（Esc）、[04](./04_インライン編集の通常のEnterで保存処理が2回走る.md)（同じテンプレートの Enter） |

## 症状

変換を始める前の ngModel の値によって、症状が3通りに分かれる。

| 変換を始める前の状態 | 変換確定の Enter で起きること |
|---|---|
| 元の名前のまま（全選択して上書き変換した場合など） | 編集が取り消され、入力欄が元の名前に戻る |
| 空、または2文字以下 | 「Name must be more than three letters long」が出て編集が終わる（[06](./06_実験名の長さの下限が入力欄と保存処理で食い違う.md)） |
| 変換前に確定済みの変更がある | 変換中の文字を含まない名前で保存され、編集が終わる |

未確定のまま Tab を押した場合も、同じ判定で保存・取消が走る。

Safari のように keydown が compositionend の後に `isComposing: false` で届く実装では、ngModel は確定後の値になっているため、変換中の文字は欠けない。その代わり、変換を確定した瞬間に保存されて編集が終わる（x-QA/02 の表）。

## 再現手順

1. 実験管理画面で実験を選び、詳細ヘッダーの名前をクリックして編集モードにする
2. 末尾に ` v2 ` と半角で入力する
3. 日本語入力に切り替えて「じっけん」と打ち、変換を確定するために Enter を押す
4. 編集が終わり、`Task A v2 ` で保存される（「実験」が含まれない）

Playwright（モック API、Chromium）では [scripts/01-inline-edit-name.spec.ts](./scripts/01-inline-edit-name.spec.ts) の「01 変換確定の Enter」で再現した。変換中の状態を CDP の `Input.imeSetComposition` で作り、変換中の印を持つ keydown を合成して送っている。

```ts
await edit.input.press('End');
await page.keyboard.type(' v2 ');
await setComposition(session, 'じっけん');              // compositionstart / update
await dispatchComposingKey(edit.input, {key: 'Enter'});  // keydown: key 'Enter', isComposing true, keyCode 229
await commitComposition(session, '実験');                // compositionend
// → tasks.update が name: 'Task A v2 ' で送られ、編集モードが閉じる
```

同じスクリプトで、keydown を送らずに変換だけ確定した場合は編集が続き、入力欄が「実験」になることも確かめている。症状の原因が keydown の扱いにあることの対照である。

実機での届き方は、編集モードで DevTools のコンソールに次を貼り、変換確定の Enter を押すと確認できる。

```js
const el = document.querySelector('.inline-edit-input');
['compositionstart', 'keydown', 'input', 'compositionend', 'keyup'].forEach(type =>
  el.addEventListener(type, e => console.log(type, e.key, e.keyCode, e.isComposing, el.value), true));
```

## 期待する動作

変換確定・変換取消・候補選択のキー操作では編集モードの処理を行わず、変換後の通常の Enter で保存する。

## 原因

入力欄の Enter と Tab は、IME の変換中かどうかを見ずに保存処理を呼んでいる。

- [inline-edit.component.html:34](../src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L34)（`keydown.tab`）
- [inline-edit.component.html:36](../src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L36)（`keydown.enter`）

```html
(keydown.tab)="form.checkValidity() && inlineSaved()"
(keydown.enter)="form.checkValidity() && inlineSaved()"
```

Angular の `keydown.enter` は `event.key` が `'Enter'` かどうかだけで判定し、`isComposing` と `keyCode` は見ない。一方、`[(ngModel)]` の `DefaultValueAccessor` は変換中の `input` イベントを無視し、compositionend で初めて値を反映する。変換確定の keydown が compositionend より前に届くと、`form.checkValidity()` は DOM の値（未確定文字を含む）で検証に通り、[inlineSaved()](../src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.ts#L91) は変換前の ngModel の値で保存・取消を判定する。仕組みの詳細は [x-QA/02](../x-QA/02_インライン編集でIME確定のEnterにより編集が終了する原因と対策.md) にある。

## 影響範囲と同種箇所

`sm-inline-edit` を使うテンプレートは実験の詳細ヘッダーのほかに7つある。1行モードで名前を編集する6つ（プロフィール名、モデルの詳細ヘッダー、データセット・ネストしたプロジェクト・レポート・パイプラインの各カード）は、同じ入力欄を使うため同じ症状が出る。モデルの概要のコメント（`[multiline]="true"`）は `textarea` で、Enter は改行として働くが、`keydown.tab` は同じく変換中かどうかを見ずに保存する（[inline-edit.component.html:47](../src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L47)）。参照元の全体は [madge-rdeps-InlineEditComponent.md](../madge-rdeps-InlineEditComponent.md) にある。

インライン編集以外の Enter は [02](./02_名前変更ダイアログ・タグ追加・実行パラメータで変換確定のEnterにより確定処理が走る.md) にまとめた。

## 対策案

第一案は x-QA/02 の推奨案である。変換中の keydown を除外する判定 `event.isComposing || event.keyCode === 229` を共有ユーティリティにし、Enter はその判定を組み込んだディレクティブ（`smImeSafeEnter` など）で受ける。Tab と Esc はコンポーネントのメソッドで同じ判定を使う。`keyCode` の判定は、Safari が compositionend の後に `isComposing: false` の keydown を送るため必要である。

第二案は、Enter を `<form (ngSubmit)>` の暗黙送信で受ける案である。変換確定の Enter では暗黙送信が起きないというブラウザの挙動に頼るため、実機での確認が要る。[04](./04_インライン編集の通常のEnterで保存処理が2回走る.md) の修正（ボタンの `type`）と同時に行う必要がある。

修正規模は、ユーティリティとディレクティブの追加、インライン編集の変更、単体テストの追加で「中」とした。

## 検証範囲

- 確認したこと：Playwright（Chromium、モック API）で、変換中の keydown（`key: 'Enter'`・`'Tab'`、`isComposing: true`、`keyCode: 229`）を合成したときに、上の表の1行目と3行目の症状が出ること。keydown を送らない変換確定では編集が続くこと。Angular 22.1.5 の `KeyEventsPlugin` と `DefaultValueAccessor` のソース（x-QA/02）
- 確認していないこと：実機の IME で keydown がどう届くか（ブラウザ・OS・IME の組み合わせごと）。Safari 型の届き方での症状は x-QA/02 の整理に基づく推論であり、模擬していない（Playwright は Chromium のみ）
- 由来：`inline-edit.component.*` は比較資料で上流と一致するファイルであり、`keydown.enter` の判定は Angular 21 でも同じ

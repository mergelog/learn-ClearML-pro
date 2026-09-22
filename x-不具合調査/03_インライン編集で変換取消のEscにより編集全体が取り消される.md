# インライン編集で、日本語変換を取り消す Esc を押すと、編集全体が取り消されて確定済みの入力も失われる

| 項目 | 内容 |
|---|---|
| カテゴリー | 操作 |
| 不具合内容 | 名前のインライン編集で日本語を変換中に Esc を押すと、変換だけでなく編集モード全体が取り消され、それまでに確定していた入力も元の名前に戻る |
| 期待動作 | 変換中の Esc は変換だけを取り消し、編集は続く |
| 直さないと困ること | 変換候補を取り消したいだけの利用者が、入力をやり直すことになる |
| 修正規模 | 小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験管理 > 詳細ヘッダー > 名前のインライン編集（`sm-inline-edit` を使う全画面） |
| 観点 | A（IME） |
| 重大度 | S3 |
| 確度 | コード上確定（模擬 IME でアプリ上の再現済み）。実機の IME が変換中の Esc を keydown として届けるかは要実機確認 |
| 由来 | 上流 |
| 発生条件 | 変換中の Esc で、`key: 'Escape'` の keydown が入力欄に届くブラウザ・IME |
| 関連 | [01](./01_インライン編集で変換確定のEnterにより編集が終了する.md)（Enter・Tab の同じ原因） |

## 症状

名前の末尾に ` renamed` と入力してから日本語の変換を始め、Esc を押すと、編集モードが閉じる。もう一度編集を開くと、入力欄は元の名前に戻っており、` renamed` も失われている。保存の API は呼ばれない。

## 再現手順

1. 実験管理画面で実験を選び、詳細ヘッダーの名前をクリックして編集モードにする
2. 末尾に ` renamed` と入力する
3. 日本語入力で「じっけん」と打ち、変換を取り消すために Esc を押す
4. 編集モードが閉じる。再度開くと元の名前に戻っている

Playwright（モック API、Chromium）では [scripts/01-inline-edit-name.spec.ts](./scripts/01-inline-edit-name.spec.ts) の「03 変換取消の Esc」で再現した。

```ts
await edit.input.press('End');
await page.keyboard.type(' renamed');
await setComposition(session, 'じっけん');
await dispatchComposingKey(edit.input, {key: 'Escape'}); // isComposing: true, keyCode: 229
// → 編集モードが閉じ、再度開くと 'Task A' に戻っている
```

## 期待する動作

変換中の Esc は IME に任せ、編集モードの取消は変換していないときの Esc だけで行う。

## 原因

入力欄の Esc は、IME の変換中かどうかを見ずに [inlineCanceled()](../src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.ts#L84) を呼ぶ（[inline-edit.component.html:35](../src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L35)）。`inlineCanceled()` は入力値を元の名前に戻し、編集モードを閉じる。複数行モードの `textarea` も同じである（[inline-edit.component.html:48](../src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L48)）。

```html
(keydown.escape)="inlineCanceled()"
```

## 影響範囲と同種箇所

`sm-inline-edit` を使う8つのテンプレートすべて（[01](./01_インライン編集で変換確定のEnterにより編集が終了する.md) の「影響範囲」）。インライン編集以外の Esc は横断観点 A（フェーズ2）で洗い直し、編集セクション（[08](./08_編集セクションでEscを押すと確認なしに編集全体が取り消される.md)）と検索欄（[09](./09_検索欄で変換中の文字列で検索が走り確定後の検索語と食い違う.md)）に同じ型があった。

## 対策案

01 の第一案で作る判定（`event.isComposing || event.keyCode === 229`）を使い、Esc のハンドラで変換中なら何もしないようにする（x-QA/02 の `onEscape()`）。01 の判定ができていれば、変更は `inline-edit` の1コンポーネントで完結するため「小」とした。

## 検証範囲

- 確認したこと：Playwright（Chromium、モック API）で、変換中の印を持つ Esc の keydown を合成したときに編集全体が取り消されること
- 確認していないこと：実機の IME で、変換中の Esc が `key: 'Escape'` の keydown として入力欄に届くか（`key: 'Process'` で届く、または届かない実装では症状は出ない）
- 由来：`inline-edit.component.*` は比較資料で上流と一致する

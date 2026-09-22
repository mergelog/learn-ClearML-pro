# インライン編集で、✓ボタンが有効なときに Enter で確定すると、保存処理が2回走る

| 項目 | 内容 |
|---|---|
| カテゴリー | 状態 |
| 不具合内容 | 名前を変えて Enter で確定すると、`inlineSaved()` が2回呼ばれ、同じ名前で `tasks.update` が2回送られる。名前が短すぎる場合は、エラー通知が2つ出る |
| 期待動作 | Enter 1回につき保存処理は1回 |
| 直さないと困ること | 同じ更新がサーバへ二重に送られる。エラー通知が重複して表示される |
| 修正規模 | 極小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験管理 > 詳細ヘッダー > 名前のインライン編集（`sm-inline-edit` の1行モードを使う全画面） |
| 観点 | G（フォームと検証） |
| 重大度 | S4 |
| 確度 | 再現済み |
| 由来 | 上流 |
| 発生条件 | ✓ボタンが有効（入力欄の検証に通り、前後の空白を除いた長さが下限以上）な状態で Enter を押す |
| 関連 | [01](./01_インライン編集で変換確定のEnterにより編集が終了する.md)（同じ Enter のバインド）、[06](./06_実験名の長さの下限が入力欄と保存処理で食い違う.md)（エラー通知の重複が見える場面） |

## 症状

| 入力 | Enter の結果 |
|---|---|
| `Renamed task` | `tasks.update` が `name: 'Renamed task'` で2回送られる |
| `abc`（3文字） | `tasks.update` が `name: 'abc'` で2回送られる |
| `実験`（2文字） | 「Name must be more than three letters long」の通知が2つ出る |

✓ボタンをクリックして確定した場合は、`tasks.update` は1回である。

## 再現手順

1. 実験管理画面で実験を選び、詳細ヘッダーの名前をクリックして編集モードにする
2. 名前を `Renamed task` に書き換え、Enter を押す
3. DevTools の Network で `tasks.update` が2回送られている

Playwright（モック API、Chromium、IME の模擬なし）では [scripts/01-inline-edit-name.spec.ts](./scripts/01-inline-edit-name.spec.ts) の「04 通常の Enter」で再現した。✓ボタンに click のリスナを足して数えると、Enter 1回で click が1回発生している。

```ts
await page.keyboard.type('Renamed task');
await edit.input.press('Enter');
// tasks.update の name: ['Renamed task', 'Renamed task']
// ✓ボタンの click: 1回（暗黙送信によるもの）
```

## 期待する動作

Enter で確定したときも、✓ボタンで確定したときも、`inlineSaved()` は1回だけ呼ばれる。

## 原因

入力欄の `keydown.enter` と、フォームの暗黙送信による✓ボタンの click の両方が `inlineSaved()` を呼んでいる。

1. 入力欄の `(keydown.enter)` が `inlineSaved()` を呼ぶ（[inline-edit.component.html:36](../src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L36)）
2. ✓ボタンと×ボタンは `type` 属性を持たない（[inline-edit.component.html:54](../src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L54)、[57](../src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L57)）。Angular Material の `mat-icon-button` も `type` を付けないため、どちらも `type="submit"` として働く
3. keydown の既定動作としてフォームの暗黙送信が起き、先頭の送信ボタンである✓ボタンに click が発生する。✓ボタンの `(click)` も `form.checkValidity() && inlineSaved()` を呼ぶ

2回目の `inlineSaved()` も、1回目と同じく「元の名前と違う」と判定する。比較に使う `originalText` は親から渡される入力で、変更検知で初めて更新される。keydown のハンドラと暗黙送信の click は同じタスクの中で続けて実行されるため、そのあいだに変更検知は走らず、`originalText` は元の名前のままである。

## 影響範囲と同種箇所

`sm-inline-edit` の1行モードを使う7つのテンプレート（[01](./01_インライン編集で変換確定のEnterにより編集が終了する.md) の「影響範囲」）。保存先はそれぞれ違い、名前の更新 API が2回呼ばれる。フォーム内の `type` の無いボタンは、横断観点 G（フェーズ2）で全体を洗い直す。

## 対策案

✓ボタンと×ボタンに `type="button"` を付ける。フォームに送信ボタンが無くなるため、Enter で暗黙送信が起きても✓ボタンの click は発生しない（送信イベントは `NgForm` が受けて既定動作を止める）。変更はテンプレートの属性2つで「極小」とした。

[01](./01_インライン編集で変換確定のEnterにより編集が終了する.md) の第二案（Enter を `ngSubmit` に一本化する）を採る場合は、逆に✓ボタンを `type="submit"` と明示し、click での `inlineSaved()` の呼び出しをやめる。

## 検証範囲

- 確認したこと：Playwright（Chromium、モック API）の通常のキー入力で、Enter 1回につき `tasks.update` が2回送られること、✓ボタンの click が1回発生すること、短すぎる名前ではエラー通知が2つ出ること。✓ボタンのクリックでは1回であること
- 確認していないこと：Firefox・Safari での暗黙送信の順序（HTML の仕様上は同じく既定のボタンに click が発生する）。実験名以外のインライン編集での API 呼び出し回数
- 由来：`inline-edit.component.*` は比較資料で上流と一致する。変更検知が keydown と click のあいだで走らない点は、zoneless の Angular 21 でも同じである

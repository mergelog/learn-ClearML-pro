# タグ追加メニューの入力欄で↓を押しても、タグの一覧へ移れず TypeError が出る

| 項目 | 内容 |
|---|---|
| カテゴリー | 操作 |
| 不具合内容 | タグ追加メニューの入力欄で↓キーを押すと、「Create New」ボタンまたは既存タグの一覧へフォーカスが移るはずだが、移らない。押すたびにコンソールに `TypeError` が出る |
| 期待動作 | ↓で「Create New」ボタン（無ければ最初のタグ）へフォーカスが移り、キーボードだけでタグを選べる |
| 直さないと困ること | キーボードで操作する利用者が、↓でタグを選べない。Tab で届くが、途中のアイコンのボタンを順に経由する |
| 修正規模 | 極小 |

| 項目 | 内容 |
|---|---|
| 画面 | タグ追加メニュー（`sm-tags-menu`）を使う全画面。実験・モデルの詳細ヘッダー、実験・モデル・パイプライン・レポート・データセット版のメニュー、一覧のフッターなど |
| 観点 | J（操作性）。A（IME）の確認の途中で見つけた |
| 重大度 | S3 |
| 確度 | 再現済み |
| 由来 | 上流 |
| 発生条件 | 常に（タグの有無、入力の有無によらない） |
| 関連 | [02](./02_名前変更ダイアログ・タグ追加・実行パラメータで変換確定のEnterにより確定処理が走る.md)（同じメニューの変換確定の Enter） |

## 症状

入力欄の状態ごとに↓を押した結果は次のとおりである。どの場合もフォーカスは入力欄に残る。

| 入力欄 | 表示されているボタン | コンソールのエラー |
|---|---|---|
| 空 | 既存タグ（alpha、beta） | `Cannot read properties of undefined (reading 'nativeElement')` |
| `v2-`（新しいタグ名） | Create New だけ | `Cannot read properties of undefined (reading 'nativeElement')` |
| `al`（既存タグに一致） | Create New と alpha | `Cannot read properties of undefined (reading 'focus')` |

Tab を押すと、入力欄の右のアイコンのボタンを経由して、Create New と既存タグへ順にフォーカスが移る。

## 再現手順

モック API（既存タグ `alpha`・`beta`）で行う。

1. 実験の詳細ヘッダーで ADD TAG を押す
2. 入力欄にフォーカスがある状態で↓を押す
3. フォーカスが移らず、コンソールに `TypeError` が出る

スクリプトは [scripts/p2a-tags-menu-arrow.spec.ts](./scripts/p2a-tags-menu-arrow.spec.ts)。

## 期待する動作

↓で「Create New」ボタンへ、それが無ければ最初のタグへフォーカスが移る。

## 原因

[tags-menu.component.html:6](../src/app/webapp-common/shared/ui-components/tags/tags-menu/tags-menu.component.html#L6) の `(keyup.arrowDown)` は `createButton().nativeElement ? createButton().nativeElement.focus() : tagButton().nativeElement.focus()` を実行する。

[tags-menu.component.ts:92](../src/app/webapp-common/shared/ui-components/tags/tags-menu/tags-menu.component.ts#L92) の `createButton` と `tagButton` は `viewChild<ElementRef<HTMLButtonElement>>('tagCreateButton')` のように宣言されているが、テンプレート参照 `#tagCreateButton`・`#tagButton` は `mat-menu-item` 部品の付いた `<button>` にある。部品の付いた要素のテンプレート参照を `read` の指定なしに問い合わせると、`ElementRef` ではなく部品のインスタンス（`MatMenuItem`）が返る。`MatMenuItem` には `nativeElement` が無いため、`createButton().nativeElement` は常に undefined になり、`tagButton().nativeElement.focus()` へ進んで例外になる。ボタンが無いときは `createButton()` 自体が undefined で、最初の参照で例外になる。

Material の `mat-menu` は自前の keydown で矢印キーの移動を扱うが、入力欄を囲む `<form>` が `(keydown)="$event.stopPropagation()"`（[同:5](../src/app/webapp-common/shared/ui-components/tags/tags-menu/tags-menu.component.html#L5)）で止めているため、メニューの移動も働かない。

同じ参照は、Create New ボタンと最初のタグの `(keyup.arrowUp)`（[同:53](../src/app/webapp-common/shared/ui-components/tags/tags-menu/tags-menu.component.html#L53)・[同:62](../src/app/webapp-common/shared/ui-components/tags/tags-menu/tags-menu.component.html#L62)）でも使われている。最初のタグの↑の条件 `!createButton().nativeElement` は、Create New ボタンがあっても常に true になり、ボタンが無いときは `createButton()` が undefined で例外になる。メニュー項目の上では `mat-menu` 自身の矢印キーの移動も働くため、画面上でどう見えるかは確かめていない。

## 影響範囲と同種箇所

`sm-tags-menu` を使う11のテンプレートすべて（[02](./02_名前変更ダイアログ・タグ追加・実行パラメータで変換確定のEnterにより確定処理が走る.md) の「影響範囲」）。

`viewChild` の型を `ElementRef` とし、部品の付いた要素を `read` なしで問い合わせている箇所がほかにもあるかは、横断観点 D（型検査を通るが値が違う参照）で洗い直す。

## 対策案

`viewChild('tagCreateButton', {read: ElementRef})` のように `read: ElementRef` を指定し、テンプレートでは `createButton()?.nativeElement` のように undefined を許す。

直すと↓でフォーカスが移るようになるため、IME の変換候補を↓で選ぶ操作と衝突する。実際の IME では変換中の keydown は `keyCode: 229` で届くが、keyup は元のキー（`ArrowDown`）で届く実装があり、keyup で受けたままだと候補の選択中にフォーカスがボタンへ移って変換が確定してしまう。そのため `(keyup.arrowDown)` を keydown で受けるように替え、[01](./01_インライン編集で変換確定のEnterにより編集が終了する.md) の第一案の共通の判定（`isComposing || keyCode === 229`）で変換中を除く。テンプレートと宣言の数行の変更のため「極小」とした。

## 検証範囲

- 確認したこと：Playwright（Chromium、モック API）で、入力欄の3つの状態で↓を押してもフォーカスが移らず、`TypeError` が3件出ること。Tab では Create New と既存タグへ移れること。変換中を模した keyup（`ArrowDown`、`isComposing: true`）でも、現状はフォーカスが移らないこと
- 確認していないこと：実機の IME で、変換中の↓の keyup がどう届くか（対策案の注意点にだけ関わる）。↑（Create New ボタンと最初のタグ）での症状は、コードを読んだだけで画面では確かめていない
- 由来：`tags-menu.component.*` は比較資料で上流と一致する。テンプレート参照を部品のインスタンスとして返す挙動は Angular 21 でも同じ

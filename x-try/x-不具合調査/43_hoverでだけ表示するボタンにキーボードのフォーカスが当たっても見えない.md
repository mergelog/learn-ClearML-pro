# hover でだけ表示するボタンに、キーボードのフォーカスが当たっても見えない

| 項目 | 内容 |
|---|---|
| カテゴリー | 操作 |
| 不具合内容 | 編集セクションの EDIT、インライン編集の鉛筆、表の行メニュー（︙）などは、マウスが乗ったときだけ `opacity: 1` になり、ふだんは `opacity: 0` で透明になっている。Tab でこれらにフォーカスが移っても透明のままで、どこにフォーカスがあるか見えない。見えないまま Enter で操作できる |
| 期待動作 | キーボードでフォーカスしたときも、hover と同じくボタンを表示する（WCAG 2.4.7 フォーカスの可視化） |
| 直さないと困ること | キーボードで操作する利用者は、フォーカスの位置を見失い、見えないボタンを押してしまう。どのボタンで何が起きるかを見て判断できない |
| 修正規模 | 小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験・モデルの詳細（EDIT、鉛筆）、タスク・キューの一覧（行メニュー）、比較画面（ドロワーの展開） |
| 観点 | J（hover でしか出ないボタン、キーボードだけでの操作） |
| 重大度 | S3 |
| 確度 | 再現済み（実バックエンド、読み取りだけ） |
| 由来 | 上流 |
| 発生条件 | マウスを乗せずに、Tab キーで対象のボタンへフォーカスを移す |
| 関連 | [29](./29_実験詳細のアイコンボタンに操作名がなく支援技術で判別できない.md)・[32](./32_実験一覧の表で操作名と選択欄のラベルが不足している.md)・[35](./35_共通のアイコン操作に操作名がない.md)（同じボタンの操作名の不足）、[30](./30_インライン編集で外側をクリックすると未保存の変更が確認なしに失われる.md)（同じインライン編集） |

## 症状

実バックエンドの主要な9画面で Tab を順に押し、フォーカスが当たった要素のうち、祖先を含めた `opacity` の積が0のものを集めた（Material のチェックボックスの本来の入力欄は、見た目の箱と別に置く正常な作りのため除いた）。

| ボタン | 画面 | 部品 |
|---|---|---|
| EDIT（`editSectionButton`） | 実験詳細の EXECUTION・Hyperparameters・INFO | `sm-editable-section` |
| Reset Python Packages | 実験詳細の EXECUTION | `sm-editable-section` の中の追加ボタン |
| 検索ボタン | 実験詳細の Hyperparameters | `sm-editable-section` の中の `sm-search` |
| 鉛筆（名前・説明の編集） | 実験・モデルの詳細ヘッダー、モデルの GENERAL | `sm-inline-edit` |
| 行メニュー（`3DotMenuButton`） | タスクの一覧、キューの一覧 | `sm-table` |
| ドロワーの展開（`drawerExpandButton`） | 比較画面の DETAILS | `al-drawer` |

EXECUTION の SOURCE CODE で EDIT にフォーカスした状態を撮影すると、セクションの右上には何も表示されない。そのまま Enter を押すと編集モードに入る（CANCEL で抜け、書き込みは0件）。

## 再現手順

1. 下書きのタスクの詳細（EXECUTION）を開き、マウスを詳細の外に置く
2. Tab を押していき、SOURCE CODE の EDIT にフォーカスを移す（DevTools で `document.activeElement` を見ると `data-id="editSectionButton"` になる）
3. 画面上に EDIT ボタンもフォーカスの枠も表示されない
4. Enter を押すと編集モードに入る

Playwright の再現は [scripts/p4-invisible-focus.spec.ts](./scripts/p4-invisible-focus.spec.ts)。1件目は9画面の巡回（結果は `test-results/bug-investigation/invisible-focus.json`）、2件目は EDIT の撮影と Enter の確認で、どちらも実バックエンドを読み取るだけ。

## 原因

どの部品も、ボタンを `opacity: 0` にし、親の `:hover` でだけ `opacity: 1` に戻す。`:focus-within` や `:focus-visible` の指定は無い。

- 編集セクション：`.edit-wrapper` が `opacity: 0`、`.editable-container:hover` で1（[editable-section.component.scss:27](../src/app/webapp-common/shared/ui-components/panel/editable-section/editable-section.component.scss#L27)、[同:54](../src/app/webapp-common/shared/ui-components/panel/editable-section/editable-section.component.scss#L54)）
- インライン編集：`.editable-pen` が `opacity: 0`、`:hover` で1（[inline-edit.component.scss:96](../src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.scss#L96)、[同:102](../src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.scss#L102)）
- 表の行メニュー：`.context-button` が `opacity: 0`、行の `:hover` かメニューを開いている間だけ1（[table.component.scss:288](../src/app/webapp-common/shared/ui-components/data/table/table.component.scss#L288)、[同:273](../src/app/webapp-common/shared/ui-components/data/table/table.component.scss#L273)）
- ドロワー：展開ボタンが `opacity: 0`、`:hover` で1（[drawer.component.scss:86](../src/app/webapp-common/shared/ui-components/panel/drawer/drawer.component.scss#L86)）

`opacity: 0` の要素は `display: none` や `visibility: hidden` と違い、フォーカスを受け取れる。そのため Tab で届くが、見えない。

## 影響範囲と同種箇所

- 上の4部品は共通部品で、使っている全画面に及ぶ（編集セクションとインライン編集は実験・モデル・データセット・パイプラインの詳細、表は一覧の全画面）
- hover で表示を切り替える SCSS は46ファイルあり、この調査で Tab の巡回をしたのは9画面である。`visibility: hidden` で隠すもの（デバッグ画像のエラー表示の下部のボタンなど）は、そもそもフォーカスを受け取れず、キーボードでは届かない。これらは網羅していない

## 対策案

各部品の SCSS で、`:hover` と同じ指定を `:focus-within` にも付ける（例：`&:hover, &:focus-within { .edit-wrapper { opacity: 1; } }`）。ボタンにフォーカスがある間は表示され、マウスの操作には影響しない。

`visibility: hidden` で隠しているものは、`:focus-within` で `visibility: visible` にしても、隠れている間はフォーカスを受け取れないため届かない。`opacity` で隠す作りに揃えるか、常に表示する。

## 検証範囲

- 確認したこと：実バックエンドの9画面で Tab を最大160回押し、フォーカスした要素の見え方を記録した。EDIT はフォーカスしても `opacity` が0で撮影でも見えず、Enter で編集モードに入ることを確認した
- 確認していないこと：9画面以外。スクリーンリーダーでの読み上げ（操作名の不足は 29・32・35）。Safari・Firefox
- 由来：対象の4部品は比較資料で実質差分に含まれない（`table.component` の差分は PrimeNG 22 追随の書き換えで、行メニューの表示とは関係しない）

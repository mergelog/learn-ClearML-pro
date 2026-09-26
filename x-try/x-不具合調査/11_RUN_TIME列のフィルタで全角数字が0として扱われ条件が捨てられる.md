# RUN TIME 列のフィルタに全角数字を入力すると0として扱われ、条件が黙って捨てられる

| 項目 | 内容 |
|---|---|
| カテゴリー | 処理値 |
| 不具合内容 | タスク一覧の RUN TIME 列のフィルタ（日・時・分・秒の入力欄）に、日本語入力をオンにしたまま数字を打つと全角数字（「１」）が入る。Enter や別の場所へのフォーカス移動で確定すると、全角数字は0として扱われ、入力欄は「00」に戻り、フィルタの条件は送られない。エラーの表示も無い |
| 期待動作 | 全角数字を半角数字と同じ値として受け付ける。受け付けない場合は、入力できないか、受け付けなかったことが分かる |
| 直さないと困ること | 日本語入力をオンにしたまま操作する利用者が、条件を入れたのに絞り込まれない理由が分からない |
| 修正規模 | 小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験管理 > 一覧 > RUN TIME 列のフィルタ（既定では非表示の列）、パイプラインの実行一覧の RUN TIME 列 |
| 観点 | A（IME）、B（文字列の値の扱い） |
| 重大度 | S3 |
| 確度 | 再現済み（全角数字の入力は模擬 IME） |
| 由来 | 上流 |
| 発生条件 | 日本語入力がオンで、数字が全角で入力される設定（Microsoft IME・macOS の日本語入力とも、ひらがなモードでは既定で全角） |
| 関連 | なし |

## 症状

RUN TIME 列のフィルタの「Equals or greater than」の時間の欄に数字の1を入れて Enter を押したときの結果は次のとおりである。

| 入力 | 確定後の入力欄 | 送られた条件（`tasks.get_all_ex` の `active_duration`） |
|---|---|---|
| 半角の `1` | `01` | `["3600", null]`（1時間以上） |
| 全角の `１` | `00` | 送られない（条件なし） |

## 再現手順

実バックエンドの既存プロジェクトのタスク一覧で行う（読み取りだけ）。

1. タスク一覧の列の設定で RUN TIME 列を表示する（URL に `columns=active_duration` を足してもよい）
2. RUN TIME 列の見出しのフィルタを開き、「Equals or greater than」の時間の欄を選ぶ
3. 日本語入力をオンにしたまま `1` を打ち、Enter で確定してからもう一度 Enter を押す
4. 入力欄が「00」に戻り、一覧は絞り込まれない

スクリプトは [scripts/p2a-duration-fullwidth.spec.ts](./scripts/p2a-duration-fullwidth.spec.ts)。全角の入力は CDP の `Input.imeSetComposition` と `Input.insertText` で行った。

## 期待する動作

全角数字の「１」を半角の「1」と同じく1時間として扱い、条件を送る。

## 原因

入力欄の値は [duration-input-list.component.html:12](../src/app/webapp-common/shared/ui-components/inputs/duraion-input-list/duration-input-list.component.html#L12) の `(input)` でそのまま保持される。数字以外を弾く `checkChars()` は `(keypress)` で呼ばれるが（[同:14](../src/app/webapp-common/shared/ui-components/inputs/duraion-input-list/duration-input-list.component.html#L14)）、変換中の入力では keypress が発生しないため、全角数字は弾かれずに入る。

確定時の [currentTimeInMs()](../src/app/webapp-common/shared/ui-components/inputs/duration-input/duration-input.base.ts#L84) は `+this.hours * TIME_IN_MILLI.ONE_HOUR || 0` で数値に変える。JavaScript の数値変換は全角数字を受け付けず `+'１'` は `NaN` になり、`|| 0` で0に置き換わる。フィルタ側は [table-filter-duration.component.html:18](../src/app/webapp-common/shared/ui-components/data/table/table-duration-sort-template/table-filter-duration/table-filter-duration.component.html#L18) で `$event > 0 ? $event : null` とするため、0は「条件なし」になる。`NaN` を0として黙って扱うため、利用者には何も伝わらない。

## 影響範囲と同種箇所

`sm-duration-input-list` は RUN TIME 列のフィルタ（`table-filter-duration`）の2つの入力（以上・以下）でだけ使われる。RUN TIME 列はタスク一覧（[experiment.consts.ts:136](../src/app/webapp-common/experiments/experiment.consts.ts#L136)）とパイプラインの実行一覧（[controllers.consts.ts:99](../src/app/webapp-common/pipelines-controller/controllers.consts.ts#L99)）にある。

同じ部品の系統の `sm-duration-input`（`duration-input.component`）は、どのテンプレートからも使われていない。

## 対策案

`setValue()` で値を保持するときに、全角数字を半角に変換する（`value.replace(/[０-９]/g, c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0))`）。あわせて、`currentTimeInMs()` で `NaN` を0に置き換えるのをやめ、数値にならない値は確定しないようにする案もあるが、既存の挙動（空欄を0として扱う）を変えるため、第一案は変換だけとする。1ファイルの変更のため「小」とした。

## 検証範囲

- 確認したこと：Playwright（Chromium、実バックエンドの既存プロジェクト）で、半角の `1` では `active_duration: ["3600", null]` が送られ、全角の `１` では条件が送られず入力欄が `00` に戻ること。Node.js で `+'１２'` が `NaN` になること
- 確認していないこと：実機の IME で数字を打ったときの入力（全角になるか、確定の Enter の keyup で `keyup.enter` が走るか）。パイプラインの実行一覧での画面上の症状
- 由来：`duration-input-list`・`duration-input.base`・`table-filter-duration` は比較資料で上流と一致する

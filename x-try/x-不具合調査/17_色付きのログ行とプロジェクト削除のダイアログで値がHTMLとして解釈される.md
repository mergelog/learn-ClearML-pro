# 色付きのログ行とプロジェクト削除のダイアログで、利用者の値の `<` が HTML として解釈され、文字が消える

| 項目 | 内容 |
|---|---|
| カテゴリー | セキュリティ |
| 不具合内容 | CONSOLE（ログ）のうち ANSI の色コードを含む行と、「Unable to Delete Project」ダイアログのプロジェクト名は、値を HTML として描画する。`<` から `>` までが HTML のタグとして解釈されて表示から消え、`<img>` などのタグは要素として作られる。スクリプトは DOMPurify が除くため実行されない |
| 期待動作 | ログの本文やプロジェクト名は文字列として表示され、`<module>` や `a<b` もそのまま見える |
| 直さないと困ること | 色付きで出力されたトレースバックの `in <module>` や、`loss<best_loss` のような比較が消え、利用者がログを読み違える。値に `<img src="外部の URL">` を含めると、閲覧した人のブラウザが外部へ要求を送る |
| 修正規模 | 小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験管理 > 詳細 > CONSOLE ほかログの表示（[10](./10_ログのフィルタがキー操作を伴わない入力では反映されない.md) と同じ画面）、プロジェクト > プロジェクトのメニュー > Delete（未アーカイブのタスクがあるとき） |
| 観点 | C（HTML として描画される値） |
| 重大度 | S3 |
| 確度 | 再現済み（どちらもモック API。プロジェクト削除のダイアログは、ダイアログを開くメソッドを開発モードの ng API から直接呼んで確認） |
| 由来 | 上流 |
| 発生条件 | ログ：色コード（`ESC[31m` など）を含む行に `<` と英字で始まる語がある（Python のトレースバック、`rich`・`colorama`・`logging` の色付き出力など）。プロジェクト削除：プロジェクト名に `<` と英字で始まる語がある |
| 関連 | なし |

## 症状

ログ（モック API で4行を返した）：

| ログの本文 | 表示 |
|---|---|
| `ESC[31m  File "train.py", line 3, in <module>ESC[0m`（色付き） | `  File "train.py", line 3, in `（`<module>` が消える） |
| `  File "train.py", line 3, in <module>`（色なし） | `  File "train.py", line 3, in <module>`（正しい） |
| `ESC[33mloss<best_loss: 0.12 (improved)ESC[0m`（色付き） | `loss`（`<best_loss: 0.12 (improved)` が1つのタグとして消える） |
| `ESC[36mpreview: <img src="x" onerror="…"> doneESC[0m`（色付き） | `preview:  done`。`img` 要素が作られる。`onerror` は除かれ、実行されない |

プロジェクト削除のダイアログ（プロジェクト名 `score<best の比較 <i>斜体 <img src="x" onerror="…"> & 記号`）：本文の名前は `score斜体 [画像] & 記号` と表示される。`<best の比較 <i>` までが1つのタグとして消え、`img` 要素が作られる。`onerror` は除かれる。

## 再現手順

ログ（モック API）：

1. `events.get_task_log` が上の表の4行を返すようにして、タスクの CONSOLE を開く
2. 色付きの行だけ、`<` 以降の文字が消えている

プロジェクト削除のダイアログ：

1. 名前に `<` と英字で始まる語を含むプロジェクト（例：`score<best の比較`）に、アーカイブしていないタスクを置く
2. プロジェクトのカードのメニューから Delete を選ぶ
3. 「Unable to Delete Project」ダイアログの本文で、プロジェクト名の `<best の比較` が消えている

スクリプトは [scripts/p2c-log-ansi-html.spec.ts](./scripts/p2c-log-ansi-html.spec.ts) と [scripts/p2c-html-in-dialog.spec.ts](./scripts/p2c-html-in-dialog.spec.ts)。後者は削除の検証 API の応答を模擬する代わりに、`ng.getComponent()` で取った画面のコンポーネントの `showConfirmDialog()` を呼んでいる。

## 期待する動作

ログの本文とプロジェクト名は、HTML の特殊文字をエスケープしてから埋め込み、文字どおりに表示される。

## 原因

ログは [experiment-log-info.component.ts:51](../src/app/webapp-common/experiments/dumb/experiment-log-info/experiment-log-info.component.ts#L51) の `new Convert()`（`ansi-to-html`）で色コードを HTML に変換し、[experiment-log-info.component.html:6](../src/app/webapp-common/experiments/dumb/experiment-log-info/experiment-log-info.component.html#L6) の `[innerHTML]="line.entry | purify"` で描画する。`ansi-to-html` の既定は `escapeXML: false` で、本文の `<`・`&` をエスケープしない。色コードを含まない行は `{{line.entry}}` で描画するため、同じ本文でも色の有無で表示が変わる。

プロジェクト削除は [projects-page.component.ts:256](../src/app/webapp-common/projects/containers/projects-page/projects-page.component.ts#L256) が本文の文字列に `readyForDeletion.project.name.split('/').pop()` をそのまま埋め込み、[confirm-dialog.component.html:10](../src/app/webapp-common/shared/ui-components/overlay/confirm-dialog/confirm-dialog.component.html#L10) が `[innerHTML]="body | purify"` で描画する。ほかの確認ダイアログは名前を [htmlTextShort()](../src/app/webapp-common/shared/utils/shared-utils.ts#L176)（lodash の `escape`）に通しているが、ここだけ通していない。

`purify` パイプは DOMPurify で `<script>` やイベント属性を除いてから `bypassSecurityTrustHtml` するため、スクリプトは実行されない。一方、DOMPurify の既定の設定は `img`・`a` などのタグと `style` 属性を残す。

## 影響範囲と同種箇所

`[innerHTML]` の14箇所と、HTML の文字列を組み立てる箇所を全体で調べた。

| 箇所 | 値 | 結果 |
|---|---|---|
| ログの色付きの行 | タスクの出力 | 本件 |
| プロジェクト削除のダイアログ | プロジェクト名 | 本件 |
| [htmlTextShort()](../src/app/webapp-common/shared/utils/shared-utils.ts#L178) の80文字（引数で200文字）を超えた名前 | キュー名・モデル名・資格情報のラベルなど | 本文はエスケープするが、`<span title="${name}">` の属性値に名前をそのまま入れる。名前に `"` を含むと属性が途中で閉じ、残りが別の属性として解釈される（DOMPurify は `style` 属性を残す）。コード上確定で、画面では確かめていない |
| モデルの公開失敗の通知（[models-menu.effects.ts:104](../src/app/webapp-common/models/effects/models-menu.effects.ts#L104)） | タスク名 | エスケープせずにリンクへ埋め込むが、呼び出し元が配列を渡しているためこの分岐に到達しない（観点 I で扱う） |
| プロジェクトのカード（`breadcrumbsEllipsis`） | プロジェクト名 | lodash の `escape` を通しており問題ない |
| Tip of the day・更新情報・共有ダイアログ・入力欄の説明・S3 の資格情報の見出し・ヘッダーのバッジ | 固定の文言、または URL のバケット名 | 利用者の自由な値が入らない |

`safe` パイプ（`bypassSecurityTrust*` の5箇所）は、HTML のデバッグサンプルを表示する iframe の `src`（[debug-image-snippet.component.html:78](../src/app/webapp-common/shared/debug-sample/debug-image-snippet/debug-image-snippet.component.html#L78) の `safe: 'url'`）でだけ使われる。タスクが出した URL を信頼済みにするが、iframe は `sandbox`（`allow-same-origin` なし）で開くため、読み込んだ内容はアプリのオリジンでは実行されない。markdown のチートシートの `bypassSecurityTrustHtml` は、アプリに同梱した固定のファイルだけを扱う。

## 対策案

- ログ：`new Convert({escapeXML: true})` にする。`ansi-to-html` が本文をエスケープしてから色の `<span>` を足すようになる
- プロジェクト削除：名前を `htmlTextShort()` か lodash の `escape` に通す
- `htmlTextShort()`：`title` 属性の値も `escape` する

3ファイルの1行ずつの変更で「小」とした。

## 検証範囲

- 確認したこと：Playwright（Chromium、モック API）で、ログの色付きの行と色なしの行の表示の違い、`img` 要素が作られ `onerror` が除かれること。プロジェクト削除のダイアログの本文（メソッドを直接呼んで開いた）
- 確認していないこと：削除の検証 API を通した実際の操作でのダイアログ（開き方が違うだけで、本文を組み立てるメソッドは同じ）。`htmlTextShort()` の `title` 属性の画面上の症状。実バックエンドのログ（色付きで `<` を含むログを出すタスクが無い）
- 由来：`experiment-log-info`・`projects-page`・`confirm-dialog`・`shared-utils` は比較資料で上流と一致する

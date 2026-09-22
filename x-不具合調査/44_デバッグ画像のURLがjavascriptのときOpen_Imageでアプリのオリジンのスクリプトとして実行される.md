# デバッグ画像の URL が `javascript:` のとき、Open Image でアプリのオリジンのスクリプトとして実行される

| 項目 | 内容 |
|---|---|
| カテゴリー | セキュリティ |
| 不具合内容 | デバッグ画像の URL（SDK からイベントとして登録する値）が `http` で始まらないと、画像の欄はエラー表示になり、その「Open Image」は URL をそのまま `window.open(url, '_blank')` に渡す。URL が `javascript:…` のとき、開いたウィンドウでスクリプトが実行され、`window.opener` を通じてアプリの画面（同じオリジン）を読み書きできる。設定の「ユーザのスクリプトをブロック」（`blockUserScript`）が有効でも、この経路は止まらない |
| 期待動作 | 利用者が登録した URL は、`http:`・`https:` など許可したスキームのときだけ開く。開くときは opener を渡さない（`noopener`） |
| 直さないと困ること | 同じワークスペースで SDK を使える利用者が、細工した URL のデバッグ画像を登録すると、それを開いた別の利用者の権限で API を呼べる（タスクの削除、資格情報の作成など） |
| 修正規模 | 小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験管理 > DEBUG SAMPLES（全画面表示を含む）、比較画面の DEBUG SAMPLES |
| 観点 | K（利用者の値を URL・遷移先として扱う箇所。フェーズ4で追加）、C（利用者の値が HTML・スクリプトとして解釈される） |
| 重大度 | S1 |
| 確度 | 再現済み（モック API） |
| 由来 | 上流 |
| 発生条件 | デバッグ画像のイベントの `url` が `javascript:` で始まる。閲覧者が画像の欄にマウスを乗せ、エラー表示の「Open Image」を押す |
| 関連 | [17](./17_色付きのログ行とプロジェクト削除のダイアログで値がHTMLとして解釈される.md)（利用者の値が HTML として解釈される別件） |

## 症状

モック API で、デバッグ画像のイベントの `url` を次の値にした。

```text
javascript:window.opener&&(window.opener.__fromDebugSample=window.opener.location.origin+window.opener.location.pathname);'done'
```

画像の欄は「Unable to load image」のエラー表示になり、マウスを乗せると下部に「Copy Image URL」「Open Image」が出る。「Open Image」を押すと次のようになった。

| 項目 | 結果 |
|---|---|
| `window.open` に渡された値 | 上の `javascript:` の URL そのまま |
| 新しいウィンドウ | 開いた（`window.open` の戻り値は Window） |
| アプリの画面の `__fromDebugSample` | `http://127.0.0.1:4200/projects/bug-project/tasks/task-a/output/debugImages` |
| `blockUserScript` の設定 | `false`（既定）。この経路は設定を見ない |

新しいウィンドウのスクリプトが、アプリの画面の `location` を読み、変数を書き込めた。オリジンが異なれば `window.opener.location.origin` の読み取りは SecurityError になるため、スクリプトはアプリと同じオリジンで動いている。

対照として、`target="_blank"` の `a` 要素に同じ URL を入れてクリックした場合は、アプリのオリジンでは実行されなかった（Chromium は `target="_blank"` の a 要素に既定で `noopener` を付ける）。

## 再現手順

実データへの登録は行っていない。再現はモック API で行う。

1. デバッグ画像のイベントの `url` を `javascript:` で始まる値にする（SDK では `Logger.report_image(…, url=…)` の `url` に当たる）
2. 閲覧者がタスクの DEBUG SAMPLES を開く
3. 画像の欄が「Unable to load image」になる。マウスを乗せ、下部の「Open Image」を押す
4. 新しいウィンドウで URL のスクリプトが実行され、`window.opener` を通じてアプリの画面を操作できる

Playwright の再現は [scripts/p4-debug-sample-javascript-url.spec.ts](./scripts/p4-debug-sample-javascript-url.spec.ts)（2件目は a 要素の対照）。

## 原因

デバッグ画像の部品は、URL を署名付き URL に置き換えるか、署名が不要ならそのまま使う（[debug-image-snippet.component.ts:63](../src/app/webapp-common/shared/debug-sample/debug-image-snippet/debug-image-snippet.component.ts#L63)、[common-auth-reducer.ts:80](../src/app/webapp-common/core/reducers/common-auth-reducer.ts#L80)）。結果が `http` で始まらなければ読み込みの失敗とみなし（[debug-image-snippet.component.ts:93](../src/app/webapp-common/shared/debug-sample/debug-image-snippet/debug-image-snippet.component.ts#L93)）、エラー表示の部品を出す（[debug-image-snippet.component.html:119](../src/app/webapp-common/shared/debug-sample/debug-image-snippet/debug-image-snippet.component.html#L119)）。

エラー表示の「Open Image」は `openImageClicked` を emit し（[snippet-error.component.html:31](../src/app/webapp-common/shared/ui-components/indicators/snippet-error/snippet-error.component.html#L31)）、`openInNewTab(source)` が `window.open(source, '_blank')` を呼ぶ（[debug-image-snippet.component.html:123](../src/app/webapp-common/shared/debug-sample/debug-image-snippet/debug-image-snippet.component.html#L123)、[debug-image-snippet.component.ts:96](../src/app/webapp-common/shared/debug-sample/debug-image-snippet/debug-image-snippet.component.ts#L96)）。

- URL のスキームを確かめない。テンプレートの `[src]`・`[href]` は Angular が `javascript:` を無害化するが、`window.open` は通らない
- `window.open` に `noopener` を渡さないため、新しいウィンドウは `window.opener` を持つ。`javascript:` の URL は、開いた側と同じオリジンの空のページで実行される
- 画像が正常なときの「Open URL in a new Tab」は `blockUserScripts()` が偽のときだけ出す（[debug-image-snippet.component.html:98](../src/app/webapp-common/shared/debug-sample/debug-image-snippet/debug-image-snippet.component.html#L98)）が、エラー表示の「Open Image」には同じ条件が無い

サーバ（apiserver 2.4.0 の `event_bll`）は、イベントの `url` のスキームを検証しない。

## 影響範囲と同種箇所

| 箇所 | 値の出所 | 確度 |
|---|---|---|
| デバッグ画像のエラー表示の「Open Image」 | デバッグ画像のイベントの `url` | 再現済み（モック API） |
| デバッグ画像の「Open URL in a new Tab」 | 同上。`http` で始まる URL のときだけ出るため、`javascript:` は届かない | 該当しない |
| 比較画面の DETAILS の成果物の「file path」、モデル比較の「model url」のリンク（[experiment-compare-base.ts:576](../src/app/webapp-common/experiments-compare/containers/experiment-compare-base.ts#L576)、[同:578](../src/app/webapp-common/experiments-compare/containers/experiment-compare-base.ts#L578)） | 成果物（audit_log）の `uri`、モデルの `uri`（SDK で登録する値）。署名が不要ならそのまま `window.open` に渡す | コード上確定（モック API で比較画面を描画できず、画面では確かめていない） |
| モデル・成果物のダウンロード（`a.target = '_blank'; a.href = …; a.click()`） | モデル・成果物の `uri` | 該当しない（a 要素は既定で `noopener` になり、対照の試験でアプリのオリジンでは実行されなかった） |

## 対策案

第一案：`window.open` を呼ぶ前に URL を `new URL()` で解釈し、`http:`・`https:`（と、使っているなら `s3:` などを署名した後の `https:`）以外は開かない。共通の関数にして、デバッグ画像と比較画面の両方から使う。

あわせて、`window.open(url, '_blank', 'noopener,noreferrer')` とし、開いたウィンドウに opener を渡さない。スキームの検査が漏れた場合の被害を、同じオリジンの読み書きから切り離せる。

エラー表示の「Open Image」にも、正常時と同じく `blockUserScripts()` の条件を付けるかは、設定の意図（利用者のスクリプトをブラウザで動かさない）に合わせて決める。

## 検証範囲

- 確認したこと：モック API で、`javascript:` の URL のデバッグ画像がエラー表示になり、「Open Image」で `window.open` に渡され、開いたウィンドウのスクリプトがアプリの画面の `location` を読み、変数を書き込めることを確認した。`target="_blank"` の a 要素ではアプリのオリジンで実行されないことを対照として確認した。サーバがイベントの `url` を検証しないことは、起動中の apiserver のコードで確かめた（読み取りだけ）
- 確認していないこと：実バックエンドにイベントを登録しての再現（細工した値を実データに残さないため）。比較画面のリンクの画面上の再現。Chromium 以外のブラウザ（Safari・Firefox の `window.open` と `javascript:` の扱い）
- 由来：`debug-image-snippet`・`snippet-error`・`experiment-compare-base.ts` は比較資料で実質差分に含まれない

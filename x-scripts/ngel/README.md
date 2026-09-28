
レンダリング済みの DOM を、Angular のコンポーネント境界が読める HTML に整形する。`div` を畳み、`style` の中身を落とし、先頭に階層サマリを HTML コメントで付ける。

## Chrome から自動で取得する

Chrome が `--remote-debugging-port=9222` で動いていれば、Playwright で接続して画面を進めてから取得できる。

```
node ngel-capture.mjs --label '実験詳細のヘッダー' [--goto <パス>] [--click <セレクタ>] [--wait <ms|セレクタ>]
```

- 接続先は `--cdp` → `$NGEL_CDP_URL` → `http://127.0.0.1:9222` → WSL のデフォルトゲートウェイ の順に探す
- 既存タブと同じオリジンに新規タブを開いて操作するので、Cookie と localStorage を共有でき再ログインは要らない。ユーザが見ているタブは動かない（`--reuse` を付けたときだけ既存タブを直接操作する）
- `--goto` `--click` `--hover` `--fill` `--press` `--wait` は指定した順に実行される
- 終了コード: 0 成功 / 1 操作失敗 / 2 CDP に到達できない / 3 オプションの誤り / 4 対象タブなし
- オプション一覧は `node ngel-capture.mjs` （引数なし）で出る

## 手動で貼り付けて取得する

xxx.html にCDTから取得した要素を貼り付け
以下コマンド実施
```
cd ./x-scripts/ngel
node ng-el.mjs xxx.html '実験詳細のヘッダー'
```

第2引数はファイル名に入るラベル。省略すると `unlabeled` になる。

## 出力

x-scripts/ngel/x-ngel
に解析結果が出力される。ファイル名は `ngel-{連番}-{ラベル}-{YYYYMMDD-HHMMSS}.html`（時刻は Asia/Tokyo）。ラベルはファイル名に使えない文字と空白が `-` になり、40 文字で切られる。

生成HTMLの先頭には、対象要素の階層をHTMLコメントで記載する。`mat-*` を除くハイフン付きタグと `data-id` 付きタグを表示し、`sm-*` の selector が `src/` のコンポーネントに見つからない場合は `[ns]` を付ける。ハイフン付きタグ以降に `mat-*` タグまたは属性がある標準タグの `data-id` には `in mat` を付ける。

入力の相対パスと出力先は、コマンドを実行した場所ではなく `ng-el.mjs` / `ngel-capture.mjs` のあるディレクトリが基準。
スクリプト内の `PROJECT_ROOT` は、そのディレクトリから `../..` を辿って解決する。

## テスト

```
node --test ng-el.test.mjs
```

---
name: ngel
description: x-scripts/ngel のスクリプトで、画面のレンダリング済みDOMから Angular コンポーネント構成が読める整形HTML ngel-*.html を x-scripts/ngel/x-ngel/ に出力する。Chrome に接続できる環境なら Playwright で目的の画面まで進めて自動取得し、接続できない場合は DevTools からの手動貼り付けを促してから実行する。「/ngel 実験詳細のヘッダー」「/ngel 実験作成モーダルを開いた状態」のように、処理内容やUIの位置を渡して使う。
argument-hint: "[処理内容やUIの位置] [ngel-capture.mjs のオプション]"
allowed-tools: Bash(node x-scripts/ngel/ngel-capture.mjs:*), Bash(node x-scripts/ngel/ng-el.mjs:*), Bash(node --test x-scripts/ngel/:*), Bash(curl:*), Bash(ls:*), Bash(stat:*), Bash(sed:*), Read, Grep, Glob, AskUserQuestion
---

# ngel

レンダリング済みの DOM を `x-scripts/ngel/` のスクリプトで整形し、`x-scripts/ngel/x-ngel/ngel-*.html` に保存する。`div` を畳んでコンポーネント境界だけを残し、先頭に階層サマリ（ハイフン付きタグと `data-id`、未発見の `sm-*` には `[ns]`）を付けた HTML が出る。**どの画面のどの状態を取るか**を決めるのがこのスキルの仕事。

引数: `$ARGUMENTS`

## 引数の分解

1. **処理内容やUIの位置**（必須）: 自然文。到達手順の決定と、出力ファイル名のラベルに使う
2. **`ngel-capture.mjs` のオプション**: `--` で始まるもの。ユーザが明示したものは必ずそのまま渡し、指定の無いオプションは勝手に足さない

指示文が無いときは実行せず「使い方」を案内して終わる。

## 手順

### 1. Chrome への接続可否を判定する

```bash
curl -s -m 3 http://127.0.0.1:9222/json/version | head -c 200; echo; echo "exit=$?"
```

- 応答があれば **接続あり**（→ 2 へ）。`ngel-capture.mjs` は `$NGEL_CDP_URL` → `127.0.0.1:9222` → WSL のデフォルトゲートウェイ の順に自動で探すので、`127.0.0.1` が空振りでもゲートウェイ側が生きていることがある。判定に迷ったら `ngel-capture.mjs` を実行して終了コード 2 かどうかで見る
- 応答が無ければ **接続なし**（→ 4 へ）

### 2. 目的の画面までの到達手順を決める

開いているタブと URL を見る。ユーザが既に目的の画面を開いていることが多い。

```bash
curl -s -m 3 http://127.0.0.1:9222/json/list | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{for(const t of JSON.parse(s))if(t.type==='page')console.log(t.url)})"
```

- アプリのタブ（`:4200` などの http URL）を基準オリジンにする。http のページが複数あるときは `--page <host:port>` で指定する
- **既に目的の画面なら `--goto` は不要**。`ngel-capture.mjs` は基準タブの URL をそのまま新規タブで開く
- 別の画面が必要なら、ルート定義（`src/app/**/*routes.ts`、`app.routes.ts`）を Grep して `--goto` のパスを決める。プロジェクト ID / タスク ID は開いているタブの URL から流用する
- モーダル・ドロワー・メニューを開いた状態が必要なら、`data-id` をテンプレートから Grep して `--click '[data-id="..."]'` を組む。DOM に載るまで時間が要る要素は `--wait '<セレクタ>'` を挟む
- **指示文だけでは画面が特定できない**ときは推測せず、AskUserQuestion でどの画面・どの状態かを聞く。選択肢は URL と画面名で、ユーザが判別できる言葉にする

### 3. 取得する

ラベル（`--label`）は指示文から作る短い識別子。日本語のままでよい。ファイル名に使えない文字と空白は `-` に落ち、40 文字で切られる。

```bash
node x-scripts/ngel/ngel-capture.mjs --label '<ラベル>' [--page <host:port>] [--goto <パス>] [--click <セレクタ>]... [--wait <ms|セレクタ>]...
```

既存タブと同じオリジンに**新規タブ**を開いて操作するので、Cookie と localStorage を共有でき再ログインは要らず、ユーザが見ているタブも動かない。取得後そのタブは閉じる。

終了コードで分岐する。

| 終了コード | 意味 | 対応 |
| --- | --- | --- |
| 0 | 成功。stdout に保存パス、stderr に接続先・実行したステップ・取得時の URL | 5 へ |
| 2 | CDP エンドポイントに到達できない | 4 へ（手動貼り付けに切り替える） |
| 3 | オプションの誤り | エラーをそのまま伝え「使い方」を案内する |
| 4 | 操作対象のタブが見つからない | 開いているページ一覧がエラーに出る。アプリのタブを開いてもらうか `--page` を見直す |
| 1 | 操作の失敗（セレクタのタイムアウト、遷移失敗など） | どのステップで落ちたかは stderr の `step:` がどこまで出たかで分かる。セレクタを Grep で見直し、必要なら `--wait` を挟んで再実行する。`--keep` を付けるとタブが残るので状態を確認できる |

### 4. Chrome に接続できない場合

`x-scripts/ngel/xxx.html` への手動貼り付けに切り替える。

1. ユーザに依頼する: 「Chrome DevTools の Elements で対象の要素（画面全体なら `<html>`）を右クリック → Copy → Copy outerHTML して、`x-scripts/ngel/xxx.html` に貼り付けて保存してください」
2. AskUserQuestion で準備完了を確認する。ここで終わらせず、完了と答えたら必ず実行まで到達させる
3. 貼り付けが新しいか `stat -c '%y %s' x-scripts/ngel/xxx.html` で確かめる。依頼より古い、またはサイズが変わっていないなら、貼り付けが保存されていない可能性を伝えてから進める
4. 取得する

   ```bash
   node x-scripts/ngel/ng-el.mjs xxx.html '<ラベル>'
   ```

   入力の相対パスと出力先は、実行した場所ではなく `ng-el.mjs` のあるディレクトリが基準。

### 5. 報告する

- 保存パスを伝える
- 先頭の階層サマリ（`<!--` から `-->` まで）だけを読んで提示する。**HTML 本体は読まない**

  ```bash
  sed -n '1,/^-->$/p' <保存パス>
  ```
- 自動取得なら、どの URL のどの状態を取ったか（stderr の `url:` と実行したステップ）を 1 行添える

## 使い方（案内用）

```text
/ngel 処理内容やUIの位置 [オプション]
```

| オプション | 意味 |
| --- | --- |
| `--page <部分文字列>` | 基準にする既存タブを URL の部分一致で選ぶ |
| `--reuse` | 新規タブを開かず、その既存タブを直接操作する（ユーザの表示中画面が動く） |
| `--keep` | 開いたタブを閉じずに残す |
| `--goto <URL\|パス>` | 遷移する。パスは基準タブの URL を基準に解決される |
| `--click <セレクタ>` | 最初の一致をクリックする |
| `--hover <セレクタ>` | 最初の一致をホバーする |
| `--fill <セレクタ> <値>` | 入力する |
| `--press <キー>` | キー入力（`Escape` など） |
| `--wait <ms\|セレクタ>` | 待つ。数値ならミリ秒、それ以外はその要素が可視になるまで |
| `--select <セレクタ>` | ドキュメント全体ではなくその要素だけを取得する |
| `--settle <ms>` | 取得前の待ち時間（既定 500） |
| `--timeout <ms>` | ステップごとのタイムアウト（既定 15000） |
| `--out-dir <パス>` | 出力先（既定 `x-ngel`、`ngel-capture.mjs` のある場所が基準） |
| `--raw <パス>` | 整形前の HTML も保存する |
| `--cdp <URL>` | DevTools エンドポイントを明示する |

- `--goto` `--click` `--hover` `--fill` `--press` `--wait` は**指定した順にそのまま実行される**。順序が操作順になる
- 保存先は `x-scripts/ngel/x-ngel/`。ファイル名は `ngel-{連番}-{ラベル}-{YYYYMMDD-HHMMSS}.html`（時刻は Asia/Tokyo）。連番は出力先にある `ngel-数字-` の最大値の次

```text
/ngel 実験詳細のヘッダー
/ngel 実験一覧で New Experiment モーダルを開いた状態
/ngel 実験詳細のハイパーパラメータタブ --goto /projects/189fffaf1f514928a021021f7de81717/tasks/dbb24a5a586241b287f9bde261f53f68/hyper-params
/ngel サイドナビだけ --select sm-side-nav
```

## スクリプトを直したとき

`x-scripts/ngel/` の整形ロジックにはテストがある。変更したら通す。

```bash
node --test x-scripts/ngel/ng-el.test.mjs
```

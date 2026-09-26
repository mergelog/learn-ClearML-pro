---
name: ngwi
description: ng-wiring（npx mergelog/ng-wiring）を実行し、画面要素を起点にしたイベント・状態変更・HTTP通信のつながりを追跡した資料 ngwi-*.md を x-ngwi/ に保存する。「/ngwi data-id=exportTaskButton 実験詳細のヘッダーにある Export ボタン」のように、対象の属性指定と UI 操作の説明を渡して使う。候補が複数出たときは説明文から候補を選び、説明文が無いときはユーザに質問して資料の保存まで到達する。
argument-hint: "[属性=値 | --source パス:行] [ng-wiring のオプション] [UI操作の説明]"
allowed-tools: Bash(npx mergelog/ng-wiring:*), Bash(ls:*), Read, Grep, Glob, AskUserQuestion
---

# ngwi

`npx mergelog/ng-wiring` を実行し、レポートを `x-ngwi/` に保存する。

引数: `$ARGUMENTS`

## 引数の分解

`$ARGUMENTS` には次の 3 種類が混ざっている。CLI に渡すのは 1 と 2 だけで、3 は候補選択の判断材料に使う。

1. **対象指定**（必須・ちょうど 1 つ）: `属性名=値` の位置引数、または `--source パス:行`
2. **ng-wiring のオプション**: `--selector` `--project` `--tsconfig` `--through` `--route` `--event` `--candidate` `--detail` `--belowData` `--json` `--out-dir`
3. **UI 操作などの説明文**: 上記以外の自然文。CLI には渡さない

- 対象指定は常にシングルクォートで囲む（`'data-id=exportTaskButton'`）。値に空白・`"`・記号が含まれてもそのまま渡す。外側の引用符は ng-wiring 側で外れる。
- ユーザが `--selector`（Chrome DevTools の Copy selector）を指定していたら、必ずそのまま渡す。値もシングルクォートで囲む。
- ユーザが指定していないオプションは足さない（`--project` も勝手に付けない）。例外は `--out-dir` だけ。

## 手順

1. 対象指定が見つからないときは、実行せずに「使い方」を案内して終わる。
2. プロジェクトルート（作業ディレクトリ）で実行する。`--out-dir x-ngwi` は常に付ける（ユーザが `--out-dir` を明示したときだけそれに従う）。初回はパッケージのダウンロードがあり解析にも時間がかかるので、タイムアウトは 10 分（`600000`）にする。
   ```bash
   npx mergelog/ng-wiring '<対象指定>' <ユーザ指定のオプション> --out-dir x-ngwi; echo "ngwi exit=$?"
   ```
   - 非 TTY なので候補の対話プロンプトは出ない。候補の選択は `--candidate` で行う。
   - 保存パスは stdout、候補一覧とエラーは stderr に出る。
   - `npm warn Unknown project config ...` はプロジェクトの `.npmrc` に対する npm の警告なので伝えない。
3. 終了コードで分岐する。

   | 終了コード | 意味 | 対応 |
   | --- | --- | --- |
   | 0 | 成功。stdout に保存パス | 保存パスと、複数候補から選んだ場合はどの候補を選んだかを伝えて終わる。資料の中身は読まず、要約もしない |
   | 2 | 対象の候補が複数（stderr に候補一覧） | 「候補の選び方」へ |
   | 1 | 対象が見つからない（`No matching target`） | 属性名・値の綴りを確認するよう伝える。`class` は属性全体の完全一致であること、他プロジェクト側の要素なら `--project` が要ることも添え、テンプレートの属性で特定できない場合の `--source パス:行` も案内する |
   | 5 | stdout に保存パスがあれば、未解決点を含む資料を保存済み。無ければ `Target detection incomplete` | 前者は保存パスと未解決である旨を伝える。後者は対象の特定に失敗したことを伝え、`--selector` や `--source` での指定を提案する |
   | 3 | 引数・オプションの誤り | エラーをそのまま伝え、「使い方」を案内する |
   | 4 | ng-wiring の内部エラー | エラーをそのまま伝える。`.ng-wiring-output.lock` を別実行が掴んでいるメッセージなら、その実行の終了を待って再実行する |

## 候補の選び方（終了コード 2）

候補一覧は 1 件 4 行で stderr に出る。

```text
4. [bootstrap] route: /projects/:projectId/tasks/:experimentId
   path: AppRootComponent -> AppComponent -> ExperimentsComponent -> ExperimentOutputComponent -> ExperimentInfoHeaderComponent
   use: src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.html:6
   target: src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.html (offset 2336)
```

- `[...]` は経路の種別。`bootstrap` は起動からその要素まで辿り切れた経路、`declaration` は使用箇所まで辿れていない宣言だけの経路、`uninstantiated-fragment` は実体化されないテンプレート断片、`unresolved-dynamic` は動的生成で経路が切れたもの。
- `route` = その要素が表示されるルート、`path` = 起動側から属性を持つコンポーネント（末尾）までの経路、`use` = 経路上の使用箇所（複数並ぶことがある）、`target` = 属性が書かれているファイル。

説明文（引数の 3）と突き合わせて 1 件に絞る。

1. `bootstrap` の候補を優先する。`declaration` / `uninstantiated-fragment` / `unresolved-dynamic` は画面までの経路が完結していないので、説明文に合う `bootstrap` があればそちらを選ぶ。
2. 説明文にある画面名・URL・一覧/詳細/モーダル/サイドバーなどの語を `route` と `path` に対応させる。同じ要素でも `route` が違えば別候補になる（例: `.../:experimentId` と `.../:experimentId/output`、一覧に重ねて出る最小化ビューとフル画面）ので、説明文がどの URL の画面を指しているかを見る。
3. まだ複数残るなら、`target` のファイルと `use` の行を読み、説明文が指す操作対象（ボタンのラベル、入力欄の役割、周辺の要素）と一致するものを選ぶ。同名の属性が別コンポーネントにもある場合（例: ヘッダー直下のボタンとメニュー内の同じボタン）は `path` の末尾と `target` で見分ける。
4. 選べたら、**同じコマンドに `--candidate <番号>` を足して再実行する**。番号は直前の実行が出した一覧の番号を使う（絞り込みオプションを変えると番号も変わる）。
5. `Candidate enumeration was truncated.` が出ている場合は一覧が打ち切られている。`--through <クラス名>`、`--route <パス>`、`--project <名前>` で絞ってから選ぶ。

**説明文が無い、または説明文だけでは決め手が無いときは、推測で選ばない。** AskUserQuestion でどの経路を求めているか質問する。

- 選択肢のラベルは `path` 末尾のコンポーネント名など短い識別にし、説明には `route` と経路の要点を、ユーザが画面として判別できる言葉で書く（どの URL のどの部分か、`bootstrap` 以外なら経路が未完である旨）。
- 候補が 4 件を超えるときは `route` と `target` でまとめ、代表的なものを選択肢にして、説明に該当件数を書く。
- 回答を得たら `--candidate` を付けて再実行し、資料の保存まで到達させる。質問して終わりにしない。

## 使い方（案内用）

```text
/ngwi 属性名=値 [オプション] [UI操作の説明]
/ngwi --source パス:行 [オプション] [UI操作の説明]
```

| オプション | 意味 |
| --- | --- |
| `--selector <DevTools パス>` | DevTools の Copy selector で候補を絞る（`>` 区切り、2 要素以上） |
| `--through <クラス名\|パス#クラス名>` | 経路が通るコンポーネントで候補を絞る |
| `--route <パス>` | ルートパターンで候補を絞る |
| `--candidate <番号\|cand:SHA256>` | 候補一覧から対象を選ぶ |
| `--event <名前>` | イベント名で絞る（`click` など） |
| `--project <名前>` | 解析する Angular プロジェクトを指定する（`--tsconfig` と併用不可） |
| `--tsconfig <パス>` | 使用する tsconfig を指定する |
| `--detail` | 詳細な資料を出力する（`--json` と併用不可） |
| `--belowData` | 選択したイベント以降を短い資料に出力する（`--detail` `--json` と併用不可） |
| `--json` | 中間データを JSON で出力する |

- 保存先は `x-ngwi/`。ファイル名は `ngwi-{連番}-{コンポーネント}.{属性}={値}-{YYMMDD.HHMMSS}.md`。連番はワークスペース直下と `x-ngwi/` にある `ngwi-数字-` の最大値の次になる。
- 資料内のコードリンクは保存先からの相対パスになる。

```text
/ngwi data-id=exportTaskButton 実験詳細画面のヘッダーにある Export ボタンを押したとき
/ngwi 'class=cdk-virtual-scroll-content-wrapper' 実験一覧テーブルの仮想スクロール
/ngwi formcontrolname=name --selector 'sm-create-new-queue-form > form > mat-form-field > div.mat-mdc-form-field-infix' キュー作成モーダルの Name 入力
/ngwi data-id=nameField --detail 実験詳細のタイトルのインライン編集
/ngwi --source src/app/webapp-common/experiments/experiments.component.html:52 一覧の分割ペイン
```

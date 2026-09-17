---
name: ngmaze
description: ngmaze（npx mergelog/ng-maze）を --mdh 付きで実行し、Angular コンポーネントの関係ツリーを ng-maze-*.md としてプロジェクト直下に保存する。「/ngmaze ExperimentsComponent」「/ngmaze MenuItemComponent --parents」のように、コンポーネント名と ngmaze のオプションを渡して使う。
argument-hint: "[component] [ngmaze options]"
allowed-tools: Bash(npx mergelog/ng-maze:*)
---

# ngmaze

`npx mergelog/ng-maze` を `--mdh` 付きで実行する。

引数: `$ARGUMENTS`

## 手順

1. 引数に `--why` が含まれていたら、実行せずに「`--why` は `--mdh` の出力に反映されない」と伝え、「使い方」を案内して終わる。
2. プロジェクトルート（作業ディレクトリ）で次を実行する。
   ```bash
   npx mergelog/ng-maze $ARGUMENTS --mdh
   ```
   - 引数に `--mdh` が既にあれば、二重に付けない。
   - 引数が空でも、そのまま `npx mergelog/ng-maze --mdh` を実行する（プロジェクト全体の概要を出力する）。
   - ユーザが指定していないオプション（`--with-routes`、`-p` など）は付けない。
   - シェルの特殊文字を含む引数は、その引数だけをクォートする。
3. 終了コードに応じて結果を伝える。`npm warn Unknown project config ...` の行は、プロジェクトの `.npmrc` に対する npm の警告なので伝えない。

   | 終了コード | 意味 | 対応 |
   | --- | --- | --- |
   | 0 | 成功（警告ありを含む） | 出力（`Saved: ...` の行と `warning:` の行）をそのまま伝えて終わる。生成された md は読まず、要約もしない |
   | 3 | CLI 入力・オプションの組み合わせ・tsconfig・出力先の誤り | エラーをそのまま伝え、「使い方」を案内する |
   | 1 / 2 / 4 | コンポーネントが見つからない / 名前に該当するコンポーネントが複数ある / ngmaze の内部エラー | エラー（2 の場合は候補一覧を含む）をそのまま伝える |

## 使い方（案内用）

```text
/ngmaze [component] [options]
```

`component` には、クラス名・セレクター・`path#ClassName` のいずれかを指定する。省略すると、プロジェクト全体の概要を出力する。`--mdh` は常に付く。

| オプション | 意味 |
| --- | --- |
| `--parents` | 使用箇所を親方向へたどる（component が必要） |
| `--depth <n>` | ツリーの深さを 1〜1000 で制限する |
| `--with-routes` | route 定義に基づく router-outlet の辺を追加する |
| `--ignore-ambiguous` | 解決できない動的コンポーネントのプレースホルダーを隠す |
| `--all` | すべてのルートツリーと到達不能なコンポーネントを出力する（component と併用不可） |
| `--angular-project <name>` | angular.json の指定プロジェクトだけを解析する（`--tsconfig` と併用不可） |
| `--tsconfig <path>` | compilerOptions の取得元にする tsconfig |
| `-p, --project <path>` | 解析ルート。md の保存先もここになる |
| `--verbose` | 解決処理と所要時間の詳細を stderr に出力する |

- `--mdh` と併用できない: `--md` `--mdc` `--json` `-o, --output`
- `--mdh` の出力に反映されない: `--why`

```text
/ngmaze ExperimentsComponent
/ngmaze ExperimentsComponent --with-routes
/ngmaze MenuItemComponent --parents --depth 3
/ngmaze --all
```

---
name: madge-to
description: madge の依存グラフから、指定した .ts ファイルを import している側（親方向）を app.config まで辿り、プロジェクト直下に madge-rdeps-{クラス名}.md（Mermaid 図 + 宣言行へのリンク一覧）を出力する。「/madge-to src/app/.../inline-edit.component.ts」「この部品がどこから使われているか図にして」「参照元を madge で図にして」といった依頼で使う。
argument-hint: "<src/app 配下の .ts パス> [--depth <n>]"
allowed-tools: Bash(node .claude/skills/madge-to/scripts/madge-to.mjs:*)
---

# madge-to

`scripts/madge-to.mjs` を実行する。madge の実行・逆方向の探索・md の出力はすべてスクリプトが行う。

引数: `$ARGUMENTS`

## 手順

1. 引数が空なら、実行せずに「使い方」を案内して終わる。
2. 引数がパスではなくクラス名（例: `InlineEditComponent`）なら、`src/app` 配下で `export class {クラス名}` を検索してファイルを特定する。複数ヒットしたら候補を示してユーザに選んでもらう。
3. プロジェクトルート（作業ディレクトリ）で次を実行する。
   ```bash
   node .claude/skills/madge-to/scripts/madge-to.mjs <パス> [--depth <n>]
   ```
4. 終了コードに応じて結果を伝える。

   | 終了コード | 意味 | 対応 |
   | --- | --- | --- |
   | 0 | 成功（warning ありを含む） | 出力（`Saved:` / `warning:` / 件数の行）をそのまま伝えて終わる。生成された md は読まず、要約もしない |
   | 1 | ファイルが無い / madge の依存グラフに含まれない | エラーをそのまま伝える |
   | 3 | 引数の誤り | エラーをそのまま伝え、「使い方」を案内する |
   | 4 | madge 未インストール | エラーをそのまま伝える |

## 出力

| ファイル | 内容 |
| --- | --- |
| `madge-rdeps-{クラス名}.md` | Mermaid 図（`flowchart LR`、起点はオレンジ太枠）と、各ファイルの宣言行へのリンク一覧。図のノードには `vscode://` のクリックリンクが付くが、効くのはブラウザ表示時（md-to-html）のみ。ノードのツールチップ（ファイルパス）の文字色を固定する `<style>` を冒頭に入れる |

- 既存の同名ファイルは上書きする。
- `*.spec.ts` は除外する。tsconfig は `tsconfig.app.json`、解析対象は `src/app`。
- クラスが無いファイル（`*.routes.ts` など）は、`export const` / `export function` の行にリンクする。

## 使い方（案内用）

```text
/madge-to <src/app 配下の .ts パス | クラス名> [--depth <n>]
```

```text
/madge-to src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.ts
/madge-to InlineEditComponent --depth 2
```

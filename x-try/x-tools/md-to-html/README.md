# md-to-html

Markdown-it ベースの Markdown → HTML 変換CLI。
指定フォルダ配下の `*.md` を再帰的にHTML化する。単一の `.md` ファイル指定にも対応する。

## セットアップ

```bash
cd x-tools/md-to-html
pnpm install --ignore-workspace
```

リポジトリルートに `pnpm-workspace.yaml` があるため、`--ignore-workspace` を付けてこのフォルダ単体でインストールする（ルートのworkspaceには含めない、独立したツール）。

## 使い方

```bash
# フォルダ配下の.mdを再帰的に全てHTML化（各.mdと同じ場所に同名.htmlを出力）
node bin/md-to-html.mjs ./docs

# 出力先フォルダを分ける（元のディレクトリ構造をミラーする）
node bin/md-to-html.mjs ./docs -o ./docs-html

# 単一ファイルのみ変換
node bin/md-to-html.mjs ./x-Docs/01_foo.md

# "_old" ディレクトリも変換対象に含める（既定では除外）
node bin/md-to-html.mjs ./docs --include-old
```

`pnpm exec md-to-html ...` または `package.json` の `bin` 経由でも実行できる。

## 機能

- `_old` ディレクトリ、`node_modules`、`.git`、隠しディレクトリは既定で変換対象から除外する
- 本文中の見出し（`# タイトル`）をHTMLの `<title>` に使う。無ければファイル名を使う
- \`\`\`mermaid コードブロックはブラウザ上で図として描画する（`mermaid.js` をCDNから読み込むため要インターネット接続）

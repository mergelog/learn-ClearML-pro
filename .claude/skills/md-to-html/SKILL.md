---
name: md-to-html
description: 指定したMarkdownファイル、またはフォルダ配下のMarkdownを一括でHTML化する。x-tools/md-to-html のCLIツールを使う。「mdをhtmlにして」「Markdownをhtml化」「md-to-html」「資料をhtmlで見たい」といった依頼で使用する。
---

# md-to-html

`x-tools/md-to-html` にある自作CLIツール（markdown-it製）で、Markdownを単体HTMLファイルに変換する。

## 初回のみ: 依存パッケージの確認

```bash
cd x-tools/md-to-html
[ -d node_modules ] || pnpm install --ignore-workspace
```

リポジトリルートの `pnpm-workspace.yaml` に巻き込まれないよう、必ず `--ignore-workspace` を付ける（このツールはルートworkspaceのメンバーではない独立パッケージ）。

## 使い方

```bash
cd x-tools/md-to-html

# フォルダ配下の.mdを再帰的に全てHTML化（各.mdと同じ場所に同名.htmlを出力）
node bin/md-to-html.mjs <対象フォルダ>

# 出力先フォルダを分けたい場合（元のディレクトリ構造をミラーする）
node bin/md-to-html.mjs <対象フォルダ> -o <出力フォルダ>

# 単一ファイルのみ変換したい場合
node bin/md-to-html.mjs <対象.mdファイル>

# "_old" ディレクトリも変換対象に含めたい場合（既定では除外）
node bin/md-to-html.mjs <対象フォルダ> --include-old
```

パスは相対でも絶対でもよい。プロジェクトルートから実行する場合はフルパスを渡すとよい。

## 仕様メモ

- 既定で `node_modules` / `.git` / 隠しディレクトリ / `_old` ディレクトリは変換対象から除外する（このプロジェクトの `_old` は明示指示がない限り閲覧不要という規約に合わせている）。
- 出力HTMLのタイトルは本文先頭の `# 見出し` から取る。無ければファイル名を使う。
- \`\`\`mermaid コードブロックはブラウザ側で図として描画する。`mermaid.js` をCDN（jsdelivr）から読み込むため、生成したHTMLを開くには要インターネット接続。
- 詳細・実装は `x-tools/md-to-html/README.md` と `x-tools/md-to-html/src/` を参照。

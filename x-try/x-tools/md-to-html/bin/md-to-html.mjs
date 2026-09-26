#!/usr/bin/env node
import { existsSync, statSync } from "node:fs";
import path from "node:path";
import { parseArgs } from "node:util";
import { findMarkdownFiles } from "../src/find-markdown-files.mjs";
import { convertFile } from "../src/convert.mjs";

const USAGE = `使い方:
  md-to-html <フォルダ or .mdファイル> [オプション]

指定したフォルダ配下の Markdown (*.md) をすべて再帰的に HTML化する。
.md ファイルを直接指定した場合はそのファイル単体だけを変換する。

オプション:
  -o, --out <dir>   出力先フォルダ（省略時は各.mdと同じ場所に同名.htmlを出力）
      --include-old  "_old" という名前のディレクトリも変換対象に含める（既定では除外）
  -h, --help         このヘルプを表示

例:
  md-to-html ./docs
  md-to-html ./docs -o ./docs-html
  md-to-html ./x-Docs/01_foo.md
`;

function main() {
  const { values, positionals } = parseArgs({
    args: process.argv.slice(2),
    options: {
      out: { type: "string", short: "o" },
      "include-old": { type: "boolean", default: false },
      help: { type: "boolean", short: "h", default: false },
    },
    allowPositionals: true,
  });

  if (values.help || positionals.length === 0) {
    process.stdout.write(USAGE);
    process.exit(values.help ? 0 : 1);
  }

  const target = path.resolve(process.cwd(), positionals[0]);
  if (!existsSync(target)) {
    console.error(`エラー: パスが見つかりません: ${target}`);
    process.exit(1);
  }

  const outDir = values.out ? path.resolve(process.cwd(), values.out) : undefined;
  const stat = statSync(target);

  /** @type {string[]} */
  let files;
  /** @type {string | undefined} */
  let baseDir;

  if (stat.isDirectory()) {
    baseDir = target;
    files = findMarkdownFiles(target, { includeOld: values["include-old"] });
    if (files.length === 0) {
      console.log(`対象のMarkdownファイルが見つかりませんでした: ${target}`);
      return;
    }
  } else {
    if (!target.toLowerCase().endsWith(".md")) {
      console.error(`エラー: .mdファイルを指定してください: ${target}`);
      process.exit(1);
    }
    files = [target];
  }

  for (const file of files) {
    const outputPath = convertFile(file, { outDir, baseDir });
    console.log(`${path.relative(process.cwd(), file)} -> ${path.relative(process.cwd(), outputPath)}`);
  }

  console.log(`\n${files.length}件のMarkdownをHTMLに変換しました。`);
}

main();

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { renderMarkdown } from "./markdown-renderer.mjs";
import { wrapHtmlDocument } from "./template.mjs";

/**
 * Markdown本文から見出し(# ...)をタイトルとして取り出す。無ければファイル名を使う。
 */
function extractTitle(markdownSource, fallback) {
  const match = markdownSource.match(/^#\s+(.+?)\s*$/m);
  return match ? match[1] : fallback;
}

/**
 * 入力.mdファイルの出力先.htmlパスを決定する。
 * - outDir未指定: 入力と同じディレクトリに同名.htmlを置く
 * - outDir指定 かつ baseDir指定（フォルダ変換時）: baseDirからの相対構造をoutDir配下にミラーする
 * - outDir指定 かつ baseDir未指定（単一ファイル変換時）: outDir直下に同名.htmlを置く
 */
export function resolveOutputPath(inputFile, { outDir, baseDir } = {}) {
  const htmlName = path.basename(inputFile).replace(/\.md$/i, ".html");

  if (!outDir) {
    return path.join(path.dirname(inputFile), htmlName);
  }

  if (baseDir) {
    const relativeDir = path.relative(baseDir, path.dirname(inputFile));
    return path.join(outDir, relativeDir, htmlName);
  }

  return path.join(outDir, htmlName);
}

/**
 * 1件の.mdファイルを.htmlに変換して書き出す。
 * @param {string} inputFile 入力.mdファイルの絶対パス
 * @param {{ outDir?: string, baseDir?: string }} [options]
 * @returns {string} 書き出したHTMLファイルの絶対パス
 */
export function convertFile(inputFile, options = {}) {
  const markdownSource = readFileSync(inputFile, "utf8");
  const { html, hasMermaid } = renderMarkdown(markdownSource);
  const title = extractTitle(markdownSource, path.basename(inputFile, ".md"));
  const document = wrapHtmlDocument({ title, bodyHtml: html, hasMermaid });

  const outputPath = resolveOutputPath(inputFile, options);
  mkdirSync(path.dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, document, "utf8");

  return outputPath;
}

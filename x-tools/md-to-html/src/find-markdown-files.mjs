import { readdirSync } from "node:fs";
import path from "node:path";

// このプロジェクトの規約上、変換対象から常に除外するディレクトリ名
// （node_modules・.git 等の一般的な除外に加え、_old は明示指示がない限り閲覧対象外という規約に合わせる）
const DEFAULT_EXCLUDED_DIRS = new Set(["node_modules", ".git", "_old"]);

/**
 * 指定ディレクトリ配下の *.md ファイルを再帰的に列挙する。
 * @param {string} dir 走査対象のディレクトリ
 * @param {{ includeOld?: boolean }} [options]
 * @returns {string[]} 見つかった .md ファイルの絶対パス一覧（ソート済み）
 */
export function findMarkdownFiles(dir, options = {}) {
  const excludedDirs = new Set(DEFAULT_EXCLUDED_DIRS);
  if (options.includeOld) {
    excludedDirs.delete("_old");
  }

  /** @type {string[]} */
  const results = [];

  const walk = (currentDir) => {
    const entries = readdirSync(currentDir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory()) {
        if (entry.name.startsWith(".") || excludedDirs.has(entry.name)) {
          continue;
        }
        walk(path.join(currentDir, entry.name));
        continue;
      }
      if (entry.isFile() && entry.name.toLowerCase().endsWith(".md")) {
        results.push(path.join(currentDir, entry.name));
      }
    }
  };

  walk(dir);
  return results.sort();
}

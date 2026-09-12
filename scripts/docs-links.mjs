#!/usr/bin/env node
/**
 * `docs/**` の Markdown が張った相対リンクの先が実在するかを確かめるゲート。
 *
 * `docs/` はどの検査の対象でもない。実装を動かしてファイルを移しても、
 * 文書がそれを指したままでも、`verify` は最後まで緑になる。移設のたびに
 * 人が全文を読み直す前提は、89本の時点で既に成り立っていない。
 *
 * 確かめるのは「リンクの先にファイルが在るか」だけである。書いてある説明が
 * 正しいかは読まなければ分からない。一方、指す先が消えたことは機械で分かる。
 * 分かる方だけを機械に渡し、R-19（文書と実装の食い違い）の残りは人が読む。
 *
 * 対象と対象外:
 *
 *   - 対象  `docs/**\/*.md` の相対リンク。`_archive/` を含む（64 §4.11）
 *   - 対象外 `http:` `https:` `mailto:` などの外部参照。実在の確認に通信が要る
 *   - 対象外 `#見出し` だけのリンク。同じ文書の中を指すもので、
 *            見出しの照合はリンクの実在確認とは別の検査になる
 *
 * リンクの先が `docs/` の外にあってもよい。`../../scripts/ci-parity.mjs` の
 * ような参照も実在を確かめる。文書がコードを指す箇所こそ、実装を動かした
 * ときに置き去りにされる。
 *
 * 使い方:
 *   node scripts/docs-links.mjs check
 */

import {readdir, readFile, stat} from 'node:fs/promises';
import {dirname, join, relative, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const DOCUMENT_ROOT = 'docs';

const EXIT_SUCCESS = 0;
const EXIT_FAILURE = 1;
const EXIT_INVALID_USAGE = 2;

/** 実在を確かめずに通す参照の前置き。 */
const EXTERNAL_SCHEMES = ['http:', 'https:', 'mailto:', 'tel:', 'ftp:', 'data:'];

/** `docs/` 配下の Markdown を集める。 */
export async function collectDocuments(root) {
  const files = [];

  const walk = async (directory) => {
    for (const entry of await readdir(directory, {withFileTypes: true})) {
      const path = join(directory, entry.name);

      if (entry.isDirectory()) {
        await walk(path);
        continue;
      }

      if (entry.name.endsWith('.md')) {
        files.push(relative(root, path));
      }
    }
  };

  await walk(resolve(root, DOCUMENT_ROOT));

  return files.sort();
}

/**
 * コード部分を空白へ置き換える。
 *
 * 削除ではなく置き換えなのは、行番号と桁を保つためである。報告に行番号を
 * 出す以上、読み飛ばした分だけ位置がずれると、指された行に何も無いという
 * 報告になる。
 *
 * 対象は ``` と ~~~ で囲んだ塊と、行の中の `...` である。手順書はコマンドを
 * 塊で載せており、その中の `[0-9](...)` のような字面をリンクとして数えると、
 * 直しようのない失敗を報告し続けることになる。
 */
export function withoutCode(source) {
  const lines = source.split('\n');
  let fence = null;

  const stripped = lines.map((line) => {
    const opening = /^\s*(`{3,}|~{3,})/.exec(line);

    if (fence) {
      const closing = opening && opening[1].startsWith(fence[0]) && opening[1].length >= fence.length;
      if (closing) {
        fence = null;
      }
      return '';
    }

    if (opening) {
      fence = opening[1];
      return '';
    }

    return line.replace(/(`+)(?:[^`]|(?!\1)`)*\1/g, (span) => ' '.repeat(span.length));
  });

  return stripped.join('\n');
}

/** `[文言](先)` と `![文言](先)`、および `[ラベル]: 先` の参照定義。 */
const INLINE_LINK = /!?\[[^\]\n]*\]\(\s*<?([^)<>\s]*)>?(?:\s+"[^"]*"|\s+'[^']*')?\s*\)/g;
const REFERENCE_DEFINITION = /^\s{0,3}\[[^\]\n]+\]:\s*<?([^\s<>]+)>?/;

/**
 * 1本の Markdown から、実在を確かめるべき参照を取り出す。
 *
 * 返すのは `{target, line}` の配列で、`target` は `#` と `?` を落とし、
 * パーセント符号化を戻した相対パスである。外部参照と同一文書内の見出しは
 * ここで落とす。
 */
export function referencesIn(source) {
  const references = [];

  withoutCode(source)
    .split('\n')
    .forEach((line, index) => {
      const targets = [...line.matchAll(INLINE_LINK)].map((match) => match[1]);

      const definition = REFERENCE_DEFINITION.exec(line);
      if (definition) {
        targets.push(definition[1]);
      }

      for (const target of targets) {
        const path = relativePathOf(target);
        if (path !== null) {
          references.push({target, path, line: index + 1});
        }
      }
    });

  return references;
}

/**
 * リンクの先から、実在を確かめる相対パスを取り出す。確かめない参照は `null`。
 */
export function relativePathOf(target) {
  const trimmed = target.trim();

  if (trimmed === '' || trimmed.startsWith('#')) {
    return null;
  }

  if (EXTERNAL_SCHEMES.some((scheme) => trimmed.toLowerCase().startsWith(scheme))) {
    return null;
  }

  // `//example.com/x` は scheme を省いた外部参照であって、相対パスではない。
  if (trimmed.startsWith('//')) {
    return null;
  }

  const path = trimmed.split('#')[0].split('?')[0];

  if (path === '') {
    return null;
  }

  try {
    return decodeURIComponent(path);
  } catch {
    // 符号化として壊れているものは、そのままの字面で確かめる。
    return path;
  }
}

/** 実在しない先を指している参照を、説明として返す。 */
export async function brokenLinks(root, files, read = readFile) {
  const found = [];

  for (const file of files) {
    const source = await read(resolve(root, file), 'utf8');

    for (const reference of referencesIn(source)) {
      const path = reference.path.startsWith('/')
        ? resolve(root, `.${reference.path}`)
        : resolve(root, dirname(file), reference.path);

      if (!(await exists(path))) {
        found.push({
          file,
          line: reference.line,
          target: reference.target,
          resolved: relative(root, path),
        });
      }
    }
  }

  return found;
}

const exists = async (path) => {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
};

const check = async () => {
  const files = await collectDocuments(REPOSITORY_ROOT);
  const found = await brokenLinks(REPOSITORY_ROOT, files);

  if (found.length > 0) {
    console.error(`\n実在しない先を指すリンクが ${found.length} 件ある:\n`);
    for (const link of found) {
      console.error(`  ${link.file}:${link.line}  ${link.target}  →  ${link.resolved}`);
    }
    console.error(
      '\nリンクを直すか、指す先を戻すこと。文書だけを直して実装を放置すると、' +
        '次に読む人は実装が消えたことに気付かない。\n',
    );
    return EXIT_FAILURE;
  }

  console.log(`docs のリンク: ${files.length} 本の Markdown、すべての相対リンクの先が実在`);
  return EXIT_SUCCESS;
};

const main = async () => {
  const command = process.argv[2];

  if (command !== 'check') {
    console.error('使い方: node scripts/docs-links.mjs check');
    return EXIT_INVALID_USAGE;
  }

  return check();
};

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main()
    .then((code) => process.exit(code))
    .catch((error) => {
      console.error(error);
      process.exit(EXIT_FAILURE);
    });
}

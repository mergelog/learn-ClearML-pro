#!/usr/bin/env node
/**
 * TypeScript の `strict` を feature 単位で進めるためのゲート。
 *
 * Angular Webは取り込んだClearML Webを土台にしており、リポジトリ全体で
 * `strict` を有効にすると500件以上の型エラーが出る。全件解消を待つと
 * 新しく書くコードにも `strict` が効かないままになるため、
 * 「移行済みの範囲」を `tsconfig.strict.json` の `include` で宣言し、
 * その範囲のエラーだけを失敗として扱う。
 *
 * tsc は `include` の外にあるファイルでも、import されていれば型を検査して
 * 報告する。移行済みの範囲の型付けは「依存先が未移行である」ことに影響を
 * 受けない（依存先の型が緩いだけで、こちら側の型は厳しく検査される）ので、
 * 報告を範囲で絞る形にしてある。範囲を広げるのは `include` へ足すだけで、
 * 足した時点で通らなければ、その feature はまだ移行できていない。
 *
 * 使い方:
 *   node scripts/web-strict.mjs            移行済みの範囲を検査する
 *   node scripts/web-strict.mjs --all      範囲外の残件も件数だけ出す
 */

import {spawn} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

import {globToRegExp} from './lib/glob.mjs';
import {parseJsonc} from './lib/jsonc.mjs';

const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const WEB_DIRECTORY = REPOSITORY_ROOT;
const STRICT_TSCONFIG = 'tsconfig.strict.json';

const EXIT_SUCCESS = 0;
const EXIT_FAILURE = 1;

const TYPESCRIPT_CLI = resolve(
  dirname(createRequire(import.meta.url).resolve('typescript/package.json')),
  'bin/tsc',
);

// `path/to/file.ts(12,3): error TS2322: ...` の先頭のパスだけを取る。
const DIAGNOSTIC_FILE = /^(\S+?)\(\d+,\d+\):\s/;

async function migratedScope() {
  const {include} = parseJsonc(await readFile(resolve(WEB_DIRECTORY, STRICT_TSCONFIG), 'utf8'));

  return include.map(globToRegExp);
}


async function runTypeScript() {
  return new Promise((resolvePromise, rejectPromise) => {
    // PATH に依存しないよう、いま動いている Node をそのまま使う。
    const tsc = spawn(
      process.execPath,
      [TYPESCRIPT_CLI, '-p', STRICT_TSCONFIG, '--pretty', 'false'],
      {cwd: WEB_DIRECTORY, stdio: ['ignore', 'pipe', 'inherit']},
    );

    const chunks = [];
    tsc.stdout.on('data', (chunk) => chunks.push(chunk));
    tsc.on('error', rejectPromise);
    tsc.on('close', () => resolvePromise(Buffer.concat(chunks).toString('utf8')));
  });
}

const main = async () => {
  const scope = await migratedScope();
  const output = await runTypeScript();

  const diagnostics = output.split('\n').filter((line) => DIAGNOSTIC_FILE.test(line));
  const inScope = diagnostics.filter((line) =>
    scope.some((pattern) => pattern.test(line.match(DIAGNOSTIC_FILE)[1])),
  );

  if (process.argv.includes('--all')) {
    console.log(`strict の残件（移行前の範囲を含む）: ${diagnostics.length} 件`);
  }

  if (inScope.length > 0) {
    console.error(`\n移行済みの範囲に strict のエラーが ${inScope.length} 件ある:\n`);
    inScope.forEach((line) => console.error(`  ${line}`));
    console.error(
      `\n直すか、まだ移行できないなら ${STRICT_TSCONFIG} の include から外すこと。`,
    );
    return EXIT_FAILURE;
  }

  console.log(
    `strict の検査: 移行済みの範囲にエラーなし（範囲外の残件 ${diagnostics.length} 件）`,
  );
  return EXIT_SUCCESS;
};

main()
  .then((code) => process.exit(code))
  .catch((error) => {
    console.error(error);
    process.exit(EXIT_FAILURE);
  });

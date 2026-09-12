#!/usr/bin/env node
/**
 * Angular の import 依存を静的に検査するゲート。
 *
 * ESLint の `no-restricted-imports` でも近いことはできるが、
 * 「feature A は feature B を import してはならない」のように
 * *呼び出し元によって禁止先が変わる* 規則は書けない。ここではその形を含む
 * 3種類の規則を、`apps/web/web-boundaries.json` の宣言から検査する。
 *
 * 使い方:
 *   node scripts/web-boundaries.mjs check     既知の違反と比較する（CIとローカル共通）
 *   node scripts/web-boundaries.mjs update    現在の違反を既知として書き直す
 *   node scripts/web-boundaries.mjs report    違反を一覧で出す（判定はしない）
 *
 * `update` は違反を減らしたときに実行する。増やしたときに実行してはならない。
 * 取り込んだClearML Webの既存違反は `knownViolations` に置き、新しい違反だけを
 * 失敗させる。`eslint-baseline.mjs` と同じ考え方だが、件数ではなく
 * 「どの import が許されているか」を残すため、別の違反への入れ替わりも検出する。
 */

import {readdir, readFile, writeFile} from 'node:fs/promises';
import {dirname, join, relative, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

import {globToRegExp, matchesAny} from './lib/glob.mjs';
import {parseJsonc} from './lib/jsonc.mjs';

const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const WEB_DIRECTORY = resolve(REPOSITORY_ROOT, 'apps/web');
const RULES_FILE = resolve(WEB_DIRECTORY, 'web-boundaries.json');
const TSCONFIG_FILE = resolve(WEB_DIRECTORY, 'tsconfig.json');

const EXIT_SUCCESS = 0;
const EXIT_FAILURE = 1;
const EXIT_INVALID_USAGE = 2;

const SOURCE_ROOT = 'src';
const SOURCE_SUFFIXES = ['.ts'];
const SKIPPED_DIRECTORIES = new Set(['node_modules', '.angular', '.stryker-tmp', 'assets']);

/**
 * `from '...'`、`export ... from '...'`、`import('...')` の3形を拾う。
 *
 * TypeScriptのパーサを使えば正確だが、この検査のために `apps/web` の外へ
 * 依存を増やしたくない。行コメント・ブロックコメントを落としてから当てる。
 */
const STATIC_IMPORT = /(?:^|[\s;}])(?:import|export)\s[^;]*?from\s*['"]([^'"]+)['"]/gs;
const DYNAMIC_IMPORT = /\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/g;
const BLOCK_COMMENT = /\/\*[\s\S]*?\*\//g;
const LINE_COMMENT = /(^|[^:])\/\/.*$/gm;

async function readJson(path) {
  // tsconfig はコメントと末尾コンマを許す。文字列の中を巻き込まずに落とす。
  return parseJsonc(await readFile(path, 'utf8'));
}

/**
 * tsconfig の `paths` を、この検査で使う「別名 -> ソース相対パス」へ写す。
 *
 * 別名の定義をここへ書き写すと、tsconfig 側の変更に追従できない。
 */
async function readPathAliases() {
  const tsconfig = await readJson(TSCONFIG_FILE);
  const paths = tsconfig.compilerOptions?.paths ?? {};

  return Object.entries(paths).map(([alias, targets]) => ({
    prefix: alias.replace(/\*$/, ''),
    target: targets[0].replace(/\*$/, ''),
  }));
}

async function collectSourceFiles(directory) {
  const entries = await readdir(directory, {withFileTypes: true});
  const files = [];

  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (SKIPPED_DIRECTORIES.has(entry.name)) {
        continue;
      }
      files.push(...(await collectSourceFiles(join(directory, entry.name))));
      continue;
    }
    if (SOURCE_SUFFIXES.some((suffix) => entry.name.endsWith(suffix))) {
      files.push(join(directory, entry.name));
    }
  }

  return files;
}

function importSpecifiers(contents) {
  const code = contents.replace(BLOCK_COMMENT, '').replace(LINE_COMMENT, '$1');
  const specifiers = [];

  for (const pattern of [STATIC_IMPORT, DYNAMIC_IMPORT]) {
    pattern.lastIndex = 0;
    let match;
    while ((match = pattern.exec(code)) !== null) {
      specifiers.push(match[1]);
    }
  }

  return specifiers;
}

/**
 * import 先を `src/...` 形式のリポジトリ内パスへ解決する。
 *
 * 解決できない（npm パッケージ）ものは null を返す。拡張子は補わない。
 * この検査が見るのはディレクトリの境界であって、ファイルの実在ではない。
 */
function resolveSpecifier(specifier, sourcePath, aliases) {
  if (specifier.startsWith('.')) {
    return toPosix(relative(WEB_DIRECTORY, resolve(dirname(sourcePath), specifier)));
  }

  const alias = aliases.find(({prefix}) => specifier.startsWith(prefix));
  if (!alias) {
    return null;
  }

  return toPosix(join(alias.target, specifier.slice(alias.prefix.length)));
}

const toPosix = (path) => path.split('\\').join('/');


/**
 * `src/app/features/<name>/...` の `<name>` を返す。feature の外なら null。
 */
function featureOf(path, featureRoot) {
  const prefix = `${featureRoot}/`;
  if (!path.startsWith(prefix)) {
    return null;
  }
  return path.slice(prefix.length).split('/')[0] || null;
}

function violationsOf(rule, file, target, featureRoot) {
  if (rule.kind === 'cross-feature') {
    const from = featureOf(file, featureRoot);
    const to = featureOf(target, featureRoot);
    return from !== null && to !== null && from !== to;
  }

  if (rule.kind === 'restricted-import') {
    if (!matchesAny(file, rule.from) || !matchesAny(target, rule.deny)) {
      return false;
    }
    return !(rule.allow ?? []).some((glob) => globToRegExp(glob).test(file));
  }

  throw new Error(`unknown rule kind: ${rule.kind}`);
}

async function findViolations(rules) {
  const aliases = await readPathAliases();
  const files = await collectSourceFiles(resolve(WEB_DIRECTORY, SOURCE_ROOT));
  const found = new Map(rules.rules.map((rule) => [rule.id, new Set()]));

  for (const absolutePath of files) {
    const file = toPosix(relative(WEB_DIRECTORY, absolutePath));
    const contents = await readFile(absolutePath, 'utf8');

    for (const specifier of importSpecifiers(contents)) {
      const target = resolveSpecifier(specifier, absolutePath, aliases);
      if (target === null) {
        continue;
      }

      for (const rule of rules.rules) {
        if (violationsOf(rule, file, target, rules.featureRoot)) {
          found.get(rule.id).add(`${file} -> ${specifier}`);
        }
      }
    }
  }

  return new Map([...found].map(([id, entries]) => [id, [...entries].sort()]));
}

function describe(rules, id) {
  return rules.rules.find((rule) => rule.id === id)?.description ?? id;
}

async function check(rules) {
  const found = await findViolations(rules);
  let failed = false;

  for (const [id, entries] of found) {
    const known = new Set(rules.knownViolations[id] ?? []);
    const added = entries.filter((entry) => !known.has(entry));
    const removed = [...known].filter((entry) => !entries.includes(entry));

    if (added.length > 0) {
      failed = true;
      console.error(`\n[${id}] ${describe(rules, id)}`);
      console.error(`  新しい違反 ${added.length} 件:`);
      added.forEach((entry) => console.error(`    ${entry}`));
    }

    if (removed.length > 0) {
      console.log(
        `[${id}] 既知の違反が ${removed.length} 件なくなった。` +
          '`node scripts/web-boundaries.mjs update` で基準を縮小できる。',
      );
    }
  }

  if (failed) {
    console.error(
      '\n境界の違反が増えた。import を直すか、意図した変更なら ' +
        'web-boundaries.json の規則そのものを見直すこと。',
    );
    return EXIT_FAILURE;
  }

  const total = [...found.values()].reduce((sum, entries) => sum + entries.length, 0);
  console.log(`境界の検査: 新しい違反なし（既知 ${total} 件）`);
  return EXIT_SUCCESS;
}

async function update(rules) {
  const found = await findViolations(rules);
  const knownViolations = Object.fromEntries([...found].map(([id, entries]) => [id, entries]));

  await writeFile(RULES_FILE, `${JSON.stringify({...rules, knownViolations}, null, 2)}\n`, 'utf8');

  for (const [id, entries] of found) {
    console.log(`[${id}] ${entries.length} 件を既知として記録した`);
  }

  return EXIT_SUCCESS;
}

async function report(rules) {
  const found = await findViolations(rules);

  for (const [id, entries] of found) {
    console.log(`\n[${id}] ${describe(rules, id)}: ${entries.length} 件`);
    entries.forEach((entry) => console.log(`  ${entry}`));
  }

  return EXIT_SUCCESS;
}

const COMMANDS = {check, update, report};

const main = async () => {
  const command = COMMANDS[process.argv[2] ?? 'check'];
  if (!command) {
    console.error('使い方: node scripts/web-boundaries.mjs [check|update|report]');
    return EXIT_INVALID_USAGE;
  }

  return command(await readJson(RULES_FILE));
};

main()
  .then((code) => process.exit(code))
  .catch((error) => {
    console.error(error);
    process.exit(EXIT_FAILURE);
  });

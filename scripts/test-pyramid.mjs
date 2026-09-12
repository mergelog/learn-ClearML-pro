#!/usr/bin/env node
/**
 * テストの層の定義（`test-pyramid.json`）と、実際の置き場所を突き合わせるゲート。
 *
 * 「どの層で何を確かめるか」は文章で書ける。しかし文章は、テストが増えても
 * 減っても何も言わない。CI の一致（`ci-parity.mjs`）で分かったのと同じことが
 * ここでも起きる。**宣言と実態のずれは、ずれたという理由では表に出てこない。**
 *
 * そこで、定義のうち機械で確かめられる3つを検査する。
 *
 *   1. すべてのテストが、いずれか1つの層に属していること
 *      未分類は「決めていない場所にテストが置かれた」ことであり、
 *      二重所属は「層の境界が重なっている」ことである
 *   2. 層が宣言している実行コマンドが `package.json` に在ること
 *      層を書いただけで誰も走らせていない、という状態を作らない
 *   3. 上限を宣言した層が、その件数を超えていないこと
 *      いま上限があるのは E2E だけである。ピラミッドの形が崩れるのは
 *      「下で確かめられることを上で確かめ始めた」ときで、それは件数に出る
 *
 * 件数は静的に数える（Python は `def test_`、TypeScript / mjs は `it(` `test(`）。
 * 実行して数えるほうが正確だが、そのためには全層を走らせる必要があり、
 * このゲートが `verify` の先頭で軽く回れなくなる。数え方が実測と合っている
 * ことは着手時に確かめた（813 / 133 / 69 / 273 / 18 / 32 がいずれも一致）。
 *
 * 使い方:
 *   node scripts/test-pyramid.mjs check     宣言と実態を突き合わせる
 *   node scripts/test-pyramid.mjs report    層ごとの内訳を出す（判定はしない）
 */

import {readdir, readFile} from 'node:fs/promises';
import {dirname, join, relative, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

import {globToRegExp, matchesAny} from './lib/glob.mjs';

const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const DEFINITION_FILE = 'test-pyramid.json';
const PACKAGE_JSON = 'package.json';

const EXIT_SUCCESS = 0;
const EXIT_FAILURE = 1;
const EXIT_INVALID_USAGE = 2;

/**
 * 層ごとのテストケースの数え方。
 *
 * Python は `def test_` で始まる行、TypeScript / mjs は `it(` `test(` で
 * 始まる行を1件と数える。`test.describe(` や `test.beforeEach(` は数えない。
 * 修飾子（`.only` `.skip` など）が付いたものは1件として数える。数を減らす
 * 方向の見落としを作らないためで、`.skip` が残っていることは別のゲート
 * （Playwright の `forbidOnly`）が見る。
 */
const COUNTERS = {
  python: /^[ \t]*(?:async\s+)?def\s+test_\w*\s*\(/gm,
  javascript: /^[ \t]*(?:it|test)(?:\.(?:only|skip|fixme|failing|todo|concurrent|sequential|each))*\s*\(/gm,
};

/** リポジトリ全体から、テストとして書かれたファイルを集める。 */
export async function collectTestFiles(root, {patterns, skip}) {
  const skipped = new Set(skip);
  const matchers = patterns.map(globToRegExp);
  const found = [];

  const walk = async (directory) => {
    for (const entry of await readdir(directory, {withFileTypes: true})) {
      if (entry.isDirectory()) {
        if (skipped.has(entry.name)) {
          continue;
        }
        await walk(join(directory, entry.name));
        continue;
      }
      if (matchers.some((matcher) => matcher.test(entry.name))) {
        found.push(toPosix(relative(root, join(directory, entry.name))));
      }
    }
  };

  await walk(root);
  return found.sort();
}

const toPosix = (path) => path.split('\\').join('/');

/** ファイルが属する層を返す。`exclude` に当たるものはその層から外れる。 */
export function layersOf(file, layers) {
  return layers.filter(
    (layer) =>
      matchesAny(file, layer.include) && !matchesAny(file, layer.exclude ?? []),
  );
}

/** 宣言と、集めたファイルの食い違いを説明として返す。 */
export function differences(files, layers, scripts) {
  const found = [];
  const assigned = new Map(layers.map((layer) => [layer.id, []]));

  for (const file of files) {
    const owners = layersOf(file, layers);

    if (owners.length === 0) {
      found.push(
        `${file} がどの層にも属していない` +
          `（${DEFINITION_FILE} の layers へ置き場所を決めてから足すこと）`,
      );
      continue;
    }
    if (owners.length > 1) {
      found.push(
        `${file} が ${owners.map((layer) => layer.id).join(' と ')} の両方に属している` +
          '（層の境界が重なっている。exclude で分けること）',
      );
      continue;
    }

    assigned.get(owners[0].id).push(file);
  }

  for (const layer of layers) {
    if (!(layer.command in scripts)) {
      found.push(
        `${layer.id}: 走らせる script "${layer.command}" が ${PACKAGE_JSON} に無い`,
      );
    }
    if (assigned.get(layer.id).length === 0) {
      found.push(`${layer.id}: 宣言されているのにテストが1件も無い`);
    }
  }

  return {found, assigned};
}

/** 層ごとにテストケースを数える。 */
export async function count(root, layer, files) {
  const pattern = COUNTERS[layer.counter];

  if (pattern === undefined) {
    throw new Error(`${layer.id}: 数え方 "${layer.counter}" を知らない`);
  }

  let total = 0;
  for (const file of files) {
    const contents = await readFile(resolve(root, file), 'utf8');
    pattern.lastIndex = 0;
    total += contents.match(pattern)?.length ?? 0;
  }

  return total;
}

/** 上限を宣言した層が、それを超えていないかを見る。 */
export function overLimit(layer, cases) {
  if (layer.max === undefined || cases <= layer.max) {
    return null;
  }

  return (
    `${layer.id}: ${cases} 件は上限 ${layer.max} 件を超えている\n` +
    `    ${layer.maxReason}`
  );
}

async function load() {
  const definition = JSON.parse(
    await readFile(resolve(REPOSITORY_ROOT, DEFINITION_FILE), 'utf8'),
  );
  const {scripts} = JSON.parse(
    await readFile(resolve(REPOSITORY_ROOT, PACKAGE_JSON), 'utf8'),
  );
  const files = await collectTestFiles(REPOSITORY_ROOT, definition.discovery);

  return {definition, scripts, files};
}

async function check() {
  const {definition, scripts, files} = await load();
  const {found, assigned} = differences(files, definition.layers, scripts);

  for (const layer of definition.layers) {
    const over = overLimit(layer, await count(REPOSITORY_ROOT, layer, assigned.get(layer.id)));
    if (over) {
      found.push(over);
    }
  }

  if (found.length > 0) {
    console.error(`\nテストの層の宣言と合わないものが ${found.length} 件ある:\n`);
    found.forEach((line) => console.error(`  ${line}`));
    console.error(
      `\n決めた置き場所は ${DEFINITION_FILE} に、決めた理由は` +
        '\ndocs/_archive/adr/005_20260911_test_pyramid.md にある。' +
        'テストを足す前に、どの層で\n確かめるべきかを先に決めること。',
    );
    return EXIT_FAILURE;
  }

  console.log(`テストの層: ${files.length} ファイルすべてが宣言どおりの層にある`);
  return EXIT_SUCCESS;
}

async function report() {
  const {definition, scripts, files} = await load();
  const {assigned} = differences(files, definition.layers, scripts);

  console.log('層\tファイル\tケース\t上限\t走らせ方');
  for (const layer of definition.layers) {
    const owned = assigned.get(layer.id);
    const cases = await count(REPOSITORY_ROOT, layer, owned);
    console.log(
      [
        layer.id,
        owned.length,
        cases,
        layer.max ?? '-',
        `pnpm run ${layer.command}`,
      ].join('\t'),
    );
  }

  return EXIT_SUCCESS;
}

const COMMANDS = {check, report};

const main = async () => {
  const command = COMMANDS[process.argv[2]];

  if (command === undefined) {
    console.error('使い方: node scripts/test-pyramid.mjs <check|report>');
    return EXIT_INVALID_USAGE;
  }

  return command();
};

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main()
    .then((code) => process.exit(code))
    .catch((error) => {
      console.error(error.message ?? error);
      process.exit(EXIT_FAILURE);
    });
}

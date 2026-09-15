/**
 * `scripts/test-pyramid.mjs` の検査。
 *
 * このゲートが守っているのは「決めた置き場所と、実際の置き場所が合っている
 * こと」である。守れているかどうかは**落とすべきものを落とすか**でしか
 * 分からないので、通ることより落ちることを確かめる。
 *
 * 実行: node --test scripts/tests/
 */

import assert from 'node:assert/strict';
import {mkdtemp, mkdir, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {dirname, join} from 'node:path';
import {test} from 'node:test';

import {collectTestFiles, count, differences, layersOf, overLimit} from '../test-pyramid.mjs';

const layers = [
  {
    id: 'web-unit',
    command: 'web:test',
    counter: 'javascript',
    include: ['src/tests/features/quality-pipeline/**/*.spec.ts'],
  },
  {
    id: 'web-unit-vendor',
    command: 'web:test',
    counter: 'javascript',
    include: ['src/**/*.spec.ts'],
    exclude: ['src/tests/features/quality-pipeline/**/*.spec.ts'],
  },
  {
    id: 'e2e',
    command: 'web:e2e',
    counter: 'javascript',
    include: ['e2e/**/*.spec.ts'],
    max: 20,
    maxReason: '縦の疎通だけを置く',
  },
];

const scripts = {'web:test': 'pnpm test', 'web:e2e': 'pnpm e2e'};

const ours = 'src/tests/features/quality-pipeline/x.spec.ts';
const vendor = 'src/app/webapp-common/y.spec.ts';
const e2e = 'e2e/z.spec.ts';

test('exclude を書いた層は、より狭い層に譲る', () => {
  assert.deepEqual(layersOf(ours, layers).map((layer) => layer.id), ['web-unit']);
  assert.deepEqual(layersOf(vendor, layers).map((layer) => layer.id), ['web-unit-vendor']);
});

test('どの層にも属さないテストを報告する', () => {
  // 決めていない場所へ置かれたテストは、どの層の約束も守っていない。
  const {found} = differences([ours, vendor, e2e, 'ml/tests/test_new.py'], layers, scripts);

  assert.equal(found.length, 1);
  assert.match(found[0], /ml\/tests\/test_new\.py がどの層にも属していない/);
});

test('2つの層に属するテストを報告する', () => {
  // exclude を書き忘れると、同じテストを2つの層が自分のものだと思う。
  const overlapping = layers.map((layer) =>
    layer.id === 'web-unit-vendor' ? {...layer, exclude: []} : layer,
  );
  const {found} = differences([ours, vendor, e2e], overlapping, scripts);

  // 二重所属のファイルはどの層のものにもならないので、web-unit が空になる
  // という別の指摘も同時に出る。ここで見たいのは前者だけである。
  const overlaps = found.filter((line) => line.includes('両方に属している'));

  assert.equal(overlaps.length, 1);
  assert.match(overlaps[0], /web-unit と web-unit-vendor の両方に属している/);
});

test('層が宣言している script が無ければ報告する', () => {
  // 層を書いただけで誰も走らせていない、という状態を作らない。
  const {found} = differences([ours, vendor, e2e], layers, {'web:test': 'x'});

  assert.equal(found.length, 1);
  assert.match(found[0], /e2e: 走らせる script "web:e2e" が package\.json に無い/);
});

test('宣言されているのに1件も無い層を報告する', () => {
  // 層ごと消えたことに気付かずに定義だけが残る、が一番起きやすい。
  const {found} = differences([ours, vendor], layers, scripts);

  assert.equal(found.length, 1);
  assert.match(found[0], /e2e: 宣言されているのにテストが1件も無い/);
});

test('食い違いが無ければ、層ごとの内訳を返す', () => {
  const {found, assigned} = differences([ours, vendor, e2e], layers, scripts);

  assert.deepEqual(found, []);
  assert.deepEqual(assigned.get('web-unit'), [ours]);
  assert.deepEqual(assigned.get('e2e'), [e2e]);
});

test('上限を超えた層だけを、理由を添えて報告する', () => {
  assert.equal(overLimit(layers[2], 20), null);
  assert.match(overLimit(layers[2], 21), /e2e: 21 件は上限 20 件を超えている/);
  assert.match(overLimit(layers[2], 21), /縦の疎通だけを置く/);
});

test('上限を宣言していない層には、何も言わない', () => {
  assert.equal(overLimit(layers[0], 10_000), null);
});

test('知らない数え方を渡されたら、黙って0件にしない', async () => {
  await assert.rejects(
    () => count(process.cwd(), {id: 'x', counter: 'ruby'}, []),
    /数え方 "ruby" を知らない/,
  );
});

const withTemporaryTree = async (files, run) => {
  const root = await mkdtemp(join(tmpdir(), 'test-pyramid-'));

  try {
    for (const [path, contents] of Object.entries(files)) {
      await mkdir(dirname(join(root, path)), {recursive: true});
      await writeFile(join(root, path), contents);
    }
    await run(root);
  } finally {
    await rm(root, {recursive: true, force: true});
  }
};

test('取り込んだ依存の中にあるテストを、自分たちのものと数えない', async () => {
  await withTemporaryTree(
    {
      'ml/tests/test_a.py': 'def test_one():\n    pass\n',
      'node_modules/pkg/tests/test_b.py': 'def test_two():\n    pass\n',
      '.venv/lib/test_c.py': 'def test_three():\n    pass\n',
      'README.md': 'テストではない',
    },
    async (root) => {
      const found = await collectTestFiles(root, {
        patterns: ['test_*.py', '*.spec.ts'],
        skip: ['node_modules', '.venv'],
      });

      assert.deepEqual(found, ['ml/tests/test_a.py']);
    },
  );
});

test('Python は def test_ の行を、TypeScript は it / test の行を1件と数える', async () => {
  await withTemporaryTree(
    {
      'ml/tests/test_a.py': [
        'class Example(TestCase):',
        '    def test_one(self):',
        '        pass',
        '',
        '    async def test_two(self):',
        '        pass',
        '',
        '    def helper(self):',
        '        pass',
        '',
        '    # def test_commented_out(self):',
        '',
      ].join('\n'),
      'e2e/a.spec.ts': [
        "test.describe('group', () => {",
        '  test.beforeEach(async () => {});',
        "  test('one', async () => {});",
        "  test.skip('two', async () => {});",
        "  it('three', () => {});",
        '});',
      ].join('\n'),
    },
    async (root) => {
      const python = {id: 'p', counter: 'python'};
      const javascript = {id: 'j', counter: 'javascript'};

      // 註釈の中の定義は数えない。修飾子の付いたものは数える。
      assert.equal(await count(root, python, ['ml/tests/test_a.py']), 2);
      // describe と beforeEach は、確かめていることが1件増えたわけではない。
      assert.equal(await count(root, javascript, ['e2e/a.spec.ts']), 3);
    },
  );
});

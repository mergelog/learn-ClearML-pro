/**
 * `scripts/lib/glob.mjs` の検査。
 *
 * 3つのゲート（依存境界・strict の範囲・テストの層）が、同じ宣言の書き方を
 * 共有している。ここの意味が1つずれると、3つとも**黙って対象を取りこぼす**。
 * 取りこぼしは緑として出るので、検査するのは主に「どこまで当たるか」である。
 *
 * 実行: node --test scripts/tests/
 */

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {globToRegExp, matchesAny} from '../lib/glob.mjs';

test('`*` は1階層の中だけに当たる', () => {
  assert.equal(globToRegExp('a/*/b').test('a/x/b'), true);
  assert.equal(globToRegExp('a/*/b').test('a/x/y/b'), false);
});

test('`**` は0階層でもよい', () => {
  // ここを「1階層以上」にすると、feature 直下に置いたファイルが
  // `src/app/features/**/*.ts` の検査から外れる。
  assert.equal(globToRegExp('a/**/*.ts').test('a/x.ts'), true);
  assert.equal(globToRegExp('a/**/*.ts').test('a/b/c/x.ts'), true);
});

test('末尾の `/**` は「配下すべて」であって「配下に何かがあること」ではない', () => {
  assert.equal(globToRegExp('a/**').test('a'), true);
  assert.equal(globToRegExp('a/**').test('a/b/c'), true);
  assert.equal(globToRegExp('a/**').test('ab'), false);
});

test('glob ではない記号を、正規表現として解釈しない', () => {
  // `.` を任意の1文字のまま扱うと、`x.spec.ts` の検査が `xAspecBts` にも当たる。
  assert.equal(globToRegExp('a/x.spec.ts').test('a/xAspecBts'), false);
  assert.equal(globToRegExp('a/x.spec.ts').test('a/x.spec.ts'), true);
});

test('前方一致や部分一致ではなく、全体に当たったものだけを拾う', () => {
  assert.equal(globToRegExp('a/b').test('a/b/c'), false);
  assert.equal(globToRegExp('a/b').test('z/a/b'), false);
});

test('matchesAny は、どれか1つに当たれば真になる', () => {
  assert.equal(matchesAny('a/x.ts', ['b/**', 'a/*.ts']), true);
  assert.equal(matchesAny('a/x.ts', ['b/**', 'c/*.ts']), false);
  assert.equal(matchesAny('a/x.ts', []), false);
});

/**
 * `scripts/lib/jsonc.mjs` の検査。
 *
 * このモジュールを別に切り出したのは、正規表現でコメントを落とす実装が
 * 実際に事故を起こしたためである。`"src/app/features/x/**\/*.ts"` の
 * `/**\/` が空のブロックコメントとして食われ、glob が `features*.ts` に化けて、
 * 品質ゲートが「何も検査せずに成功する」状態になっていた。
 *
 * 実行: node --test scripts/tests/
 */

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {parseJsonc} from '../lib/jsonc.mjs';

test('glob の中の /**/ をコメントとして食わない', () => {
  const text = '{"include": ["src/app/features/x/**/*.ts", "e2e/**/*.ts"]}';

  assert.deepEqual(parseJsonc(text).include, ['src/app/features/x/**/*.ts', 'e2e/**/*.ts']);
});

test('行コメントを落とす', () => {
  const text = '{\n  // どこを見るか\n  "a": 1\n}';

  assert.deepEqual(parseJsonc(text), {a: 1});
});

test('ブロックコメントを落とす', () => {
  const text = '{/* なぜこの値か */ "a": 1}';

  assert.deepEqual(parseJsonc(text), {a: 1});
});

test('文字列の中のコメントらしきものは残す', () => {
  const text = '{"a": "http://example.com // not a comment", "b": "/* neither */"}';

  assert.deepEqual(parseJsonc(text), {a: 'http://example.com // not a comment', b: '/* neither */'});
});

test('末尾コンマを許す', () => {
  const text = '{"lib": ["ES2024", "dom",], "strict": true,}';

  assert.deepEqual(parseJsonc(text), {lib: ['ES2024', 'dom'], strict: true});
});

test('文字列の中のコンマと閉じ括弧を末尾コンマと読み違えない', () => {
  const text = '{"a": "x, }", "b": "y, ]"}';

  assert.deepEqual(parseJsonc(text), {a: 'x, }', b: 'y, ]'});
});

test('引用符を含む文字列を途中で切らない', () => {
  const text = String.raw`{"a": "say \"hi\" // here"}`;

  assert.deepEqual(parseJsonc(text), {a: 'say "hi" // here'});
});

test('コメントを落としても行番号が変わらない', () => {
  const text = '{\n  /* 2行に\n     またがる */\n  "a": 1\n}';

  assert.deepEqual(parseJsonc(text), {a: 1});
  assert.equal(text.split('\n').length, 5);
});

test('このリポジトリの tsconfig を読める', async () => {
  const {readFile} = await import('node:fs/promises');
  const contents = await readFile(new URL('../../apps/web/tsconfig.json', import.meta.url), 'utf8');

  assert.equal(parseJsonc(contents).compilerOptions.paths['@common/*'][0], 'src/app/webapp-common/*');
});

test('移行済みの範囲の宣言をそのまま読める', async () => {
  const {readFile} = await import('node:fs/promises');
  const url = new URL('../../apps/web/tsconfig.strict.json', import.meta.url);

  assert.ok(parseJsonc(await readFile(url, 'utf8')).include.every((glob) => glob.endsWith('*.ts')));
});

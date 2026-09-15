/**
 * `scripts/ci-parity.mjs` の検査。
 *
 * このゲートは「CI が赤くならない種類の欠落」を捕まえるために作った。
 * ゲート自身が同じ性質の欠落を持っていたら意味が無いので、
 * 通ることより**落とすべきものを本当に落とすか**を確かめる。
 *
 * 実行: node --test scripts/tests/
 */

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {ciJobs, differences, expand, missing} from '../ci-parity.mjs';

const workflow = [
  'name: CI',
  '',
  'jobs:',
  '  python:',
  '    steps:',
  '      - name: Lint',
  '        run: pnpm run py:lint',
  '      - name: Tests',
  '        run: pnpm run py:coverage',
  '  web:',
  '    steps:',
  '      - run: |',
  '          pnpm install --frozen-lockfile',
  '          # pnpm run web:e2e はここでは走らせない',
  '      - run: pnpm run web:test',
  '',
  'permissions:',
  '  contents: read',
].join('\n');

test('ジョブごとに、呼ばれている script を出現順で拾う', () => {
  const jobs = ciJobs(workflow);

  assert.deepEqual(jobs.get('python'), ['py:lint', 'py:coverage']);
  assert.deepEqual(jobs.get('web'), ['web:test']);
});

test('`jobs:` の外にある行は拾わない', () => {
  // `permissions:` 以降まで読み続けると、ジョブでない塊をジョブと読み違える。
  assert.equal(ciJobs(workflow).has('permissions'), false);
  assert.equal(ciJobs(workflow).has('contents'), false);
});

test('註釈に書いてある例を、走っているコマンドと読み違えない', () => {
  // ここを素通りさせると、註釈を書いただけでゲートが黙る。
  assert.equal(ciJobs(workflow).get('web').includes('web:e2e'), false);
});

test('`pnpm run` の連結だけの script は、末端まで展開する', () => {
  const scripts = {
    verify: 'pnpm run verify:python && pnpm run verify:web',
    'verify:python': 'pnpm run py:lint && pnpm run py:coverage',
    'verify:web': 'pnpm run web:test',
    'py:lint': '.venv/bin/python -m ruff check .',
    'py:coverage': '.venv/bin/python -m coverage run -m unittest discover -s ml/tests',
    'web:test': 'pnpm test',
  };

  assert.deepEqual(expand('verify', scripts), ['py:lint', 'py:coverage', 'web:test']);
});

test('実コマンドを含む script は、そこで展開を止める', () => {
  // `pnpm test` は `pnpm run <name>` の形ではない。中を覗きに行かない。
  const scripts = {'web:test': 'pnpm test'};

  assert.deepEqual(expand('web:test', scripts), ['web:test']);
});

test('存在しない script を指していたら、黙らずに落ちる', () => {
  assert.throws(
    () => expand('verify:web', {'verify:web': 'pnpm run web:renamed'}),
    /web:renamed/,
  );
});

test('script が自分自身を呼んでいたら、無限に展開せず落ちる', () => {
  assert.throws(() => expand('a', {a: 'pnpm run b', b: 'pnpm run a'}), /自分自身/);
});

test('CI 固有の手順が混ざっていても、何も言わない', () => {
  // lock 検証や Trivy 走査は手元の verify に無い。これを咎めると CI が縛られる。
  assert.deepEqual(missing(['py:lint'], ['py:lock', 'py:lint', 'sec:sbom']), []);
});

test('verify にあって CI に無い script を報告する', () => {
  const found = missing(['py:lint', 'py:coverage'], ['py:lint']);

  assert.equal(found.length, 1);
  assert.match(found[0], /py:coverage が走っていない/);
});

test('順序が入れ替わっていたら、走っていないのとは別の言い方で報告する', () => {
  const found = missing(['py:lint', 'py:coverage'], ['py:coverage', 'py:lint']);

  assert.equal(found.length, 1);
  assert.match(found[0], /py:coverage.*順序/);
});

test('担当ジョブが消えていたら報告する', () => {
  const found = differences(
    [{chain: 'verify:python', job: 'python'}],
    {'verify:python': 'pnpm run py:lint', 'py:lint': 'ruff check .'},
    new Map(),
  );

  assert.equal(found.length, 1);
  assert.match(found[0], /job "python" が無い/);
});

test('単体で書いた項目は、出所を二度言わずに報告する', () => {
  // `web:e2e` は `verify` の連鎖ではなく単体で COVERAGE に書いてある。
  // 「web:e2e が走っていない（web:e2e に入っている）」は読み手に何も足さない。
  const found = differences(
    [{chain: 'web:e2e', job: 'e2e'}],
    {'web:e2e': 'pnpm e2e'},
    new Map([['e2e', []]]),
  );

  assert.equal(found.length, 1);
  assert.equal(found[0], 'e2e job: web:e2e が走っていない');
});

test('どのジョブの何が落ちているかまで含めて報告する', () => {
  const found = differences(
    [{chain: 'verify:web', job: 'web'}],
    {'verify:web': 'pnpm run web:contract && pnpm run web:test', 'web:contract': 'node x.mjs', 'web:test': 'vitest'},
    new Map([['web', ['web:test']]]),
  );

  assert.equal(found.length, 1);
  assert.match(found[0], /web job/);
  assert.match(found[0], /web:contract/);
  assert.match(found[0], /verify:web/);
});

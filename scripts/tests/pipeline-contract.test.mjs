/**
 * `scripts/pipeline-contract.mjs` の検査。
 *
 * このゲートは「見つけられなければ何もしない」種類のものなので、
 * 一致しているときに通ることより、食い違いを本当に見つけられることの方が
 * 重要である。名前だけ変わってPython側の値が読めなくなった場合に黙って
 * 通ってしまうと、ゲートがあるのに何も守っていない状態になる。
 *
 * 実行: node --test scripts/tests/
 */

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {
  fill,
  mismatches,
  pythonConstants,
  typeScriptConstants,
} from '../pipeline-contract.mjs';

const contract = [{typescript: 'MODEL_NAME', source: 'domain.py', python: '{MODEL_NAME}'}];

test('TypeScript の文字列定数だけを読む', () => {
  const source = [
    "export const PIPELINE_NAME = 'semiconductor-quality-training';",
    'export const REFRESH_INTERVAL_MS = 5_000;',
    'export const DATASET_VERSION_PATTERN = /^\\d+$/;',
  ].join('\n');

  const constants = typeScriptConstants(source);

  assert.equal(constants.get('PIPELINE_NAME'), 'semiconductor-quality-training');
  assert.equal(constants.has('REFRESH_INTERVAL_MS'), false);
  assert.equal(constants.has('DATASET_VERSION_PATTERN'), false);
});

test('Python の module 直下の定数を読む', () => {
  const constants = pythonConstants('MODEL_NAME = "semiconductor-quality-classifier"\n');

  assert.equal(constants.get('MODEL_NAME'), 'semiconductor-quality-classifier');
});

test('Enum の要素は クラス名.要素名 で引ける', () => {
  const source = ['class StepName(str, Enum):', '    EVALUATE = "evaluate"', ''].join('\n');

  const constants = pythonConstants(source);

  assert.equal(constants.get('StepName.EVALUATE'), 'evaluate');
  // 同名のmodule定数と取り違えないよう、裸の名前では引けない。
  assert.equal(constants.has('EVALUATE'), false);
});

test('class を抜けたあとの定数を、その class の要素と読み違えない', () => {
  const source = [
    'class StepName(str, Enum):',
    '    EVALUATE = "evaluate"',
    '',
    'MODEL_NAME = "classifier"',
    '',
  ].join('\n');

  const constants = pythonConstants(source);

  assert.equal(constants.get('MODEL_NAME'), 'classifier');
  assert.equal(constants.has('StepName.MODEL_NAME'), false);
});

test('組み立てた文字列を、Python側の値で埋める', () => {
  const constants = new Map([
    ['STAGE_TAG_PREFIX', 'stage'],
    ['ModelStage.PRODUCTION', 'production'],
  ]);

  assert.deepEqual(fill('{STAGE_TAG_PREFIX}:{ModelStage.PRODUCTION}', constants), {
    value: 'stage:production',
    missing: [],
  });
});

test('一致していれば何も報告しない', () => {
  const found = mismatches(contract, new Map([['MODEL_NAME', 'classifier']]), {
    'domain.py': 'MODEL_NAME = "classifier"\n',
  });

  assert.deepEqual(found, []);
});

test('値が食い違っていれば、両方の値を挙げて報告する', () => {
  const found = mismatches(contract, new Map([['MODEL_NAME', 'old-classifier']]), {
    'domain.py': 'MODEL_NAME = "classifier"\n',
  });

  assert.equal(found.length, 1);
  assert.match(found[0], /old-classifier/);
  assert.match(found[0], /classifier/);
});

test('Python側で名前が消えたら、通さずに報告する', () => {
  // ここを素通りさせると、対応表が古いだけのゲートが「合格」を出し続ける。
  const found = mismatches(contract, new Map([['MODEL_NAME', 'classifier']]), {
    'domain.py': 'RENAMED_MODEL_NAME = "classifier"\n',
  });

  assert.equal(found.length, 1);
  assert.match(found[0], /MODEL_NAME が無い/);
});

test('画面側に定数が無ければ報告する', () => {
  const found = mismatches(contract, new Map(), {'domain.py': 'MODEL_NAME = "classifier"\n'});

  assert.equal(found.length, 1);
  assert.match(found[0], /MODEL_NAME/);
});

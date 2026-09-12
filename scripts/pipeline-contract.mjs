#!/usr/bin/env node
/**
 * 画面とPython側が同じ文字列を指していることを確かめるゲート。
 *
 * `apps/web` の Quality pipeline 画面は、ClearML上のプロジェクト名・Pipeline名・
 * Queue名・モデル名・タグ・ステップ名で対象を特定している。同じ文字列は
 * `ml/` 側にもあり、そちらが実際にTaskやモデルを作っている側である。
 *
 * 片方だけ変えても、どちらのテストも通る。画面は例外も出さずに
 * 「実行がありません」と表示し、原因は運用中にしか分からない。
 * 二重管理そのものは残るが、ズレたまま気付かない状態は残さない。
 *
 * Python を起動せず、両方のソースを読んで突き合わせる。検査したいのは
 * 「ソースに書いてある文字列が一致しているか」であって、実行時に何が
 * 組み立てられるかではない。Node だけで動くので、仮想環境の有無に
 * 関係なく走る。
 *
 * 使い方:
 *   node scripts/pipeline-contract.mjs check
 */

import {readFile} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const TYPESCRIPT_SOURCE =
  'apps/web/src/app/features/quality-pipeline/quality-pipeline.consts.ts';

const EXIT_SUCCESS = 0;
const EXIT_FAILURE = 1;

/**
 * 一致していなければならない文字列。
 *
 * `python` は式ではなく、Python側の定数名を `{}` で埋め込んだ書式である。
 * `ModelStage.PRODUCTION` のような Enum の要素は `クラス名.要素名` で書く。
 * ここに書かれた名前がPython側に無ければ、それ自体を失敗として報告する。
 */
export const CONTRACT = [
  {
    typescript: 'PIPELINE_PROJECT',
    source: 'ml/pipeline/domain.py',
    python: '{PIPELINE_PROJECT}',
  },
  {
    typescript: 'PIPELINE_NAME',
    source: 'ml/pipeline/domain.py',
    python: '{PIPELINE_NAME}',
  },
  {
    typescript: 'PIPELINE_QUEUE',
    source: 'ml/semiconductor_quality/config.py',
    python: '{DEFAULT_PIPELINE_QUEUE}',
  },
  {
    typescript: 'MODEL_NAME',
    source: 'ml/semiconductor_quality/domain.py',
    python: '{MODEL_NAME}',
  },
  {
    typescript: 'EVALUATE_STEP_NAME',
    source: 'ml/pipeline/domain.py',
    python: '{StepName.EVALUATE}',
  },
  {
    // タグは前置詞と段階名の組み立て結果なので、組み立て方まで含めて書く。
    typescript: 'PRODUCTION_STAGE_TAG',
    source: 'ml/model_lifecycle/domain.py',
    python: '{STAGE_TAG_PREFIX}:{ModelStage.PRODUCTION}',
  },
];

/** `export const NAME = 'value';` だけを読む。 */
const TYPESCRIPT_CONSTANT = /^export const ([A-Z][A-Z0-9_]*) = '((?:[^'\\]|\\.)*)';$/;

export function typeScriptConstants(source) {
  const constants = new Map();

  for (const line of source.split('\n')) {
    const match = TYPESCRIPT_CONSTANT.exec(line.trim());
    if (match) {
      constants.set(match[1], match[2]);
    }
  }

  return constants;
}

const PYTHON_CLASS = /^class ([A-Za-z_][A-Za-z0-9_]*)\b/;
const PYTHON_CONSTANT =
  /^([A-Za-z_][A-Za-z0-9_]*)(?::\s*[^=]+)?\s*=\s*(?:"([^"]*)"|'([^']*)')\s*(?:#.*)?$/;

/**
 * Python側の文字列定数を読む。
 *
 * モジュール直下のものは名前そのもので、class の中のものは
 * `クラス名.要素名` で引ける。Enum の要素と同名のモジュール定数が
 * 取り違えられないようにするためである。
 */
export function pythonConstants(source) {
  const constants = new Map();
  let currentClass = null;

  for (const line of source.split('\n')) {
    const indented = /^\s/.test(line);
    const trimmed = line.trim();

    const className = PYTHON_CLASS.exec(trimmed);
    if (!indented && className) {
      currentClass = className[1];
      continue;
    }
    if (!indented && trimmed !== '') {
      currentClass = null;
    }

    const constant = PYTHON_CONSTANT.exec(trimmed);
    if (!constant) {
      continue;
    }

    const [, name, doubleQuoted, singleQuoted] = constant;
    const value = doubleQuoted ?? singleQuoted;

    if (indented) {
      if (currentClass) {
        constants.set(`${currentClass}.${name}`, value);
      }
      continue;
    }

    constants.set(name, value);
  }

  return constants;
}

/** `{NAME}` をPython側の値で埋める。埋められない名前は失敗として返す。 */
export function fill(pattern, constants) {
  const missing = [];

  const value = pattern.replace(/\{([A-Za-z_][A-Za-z0-9_.]*)\}/g, (_, name) => {
    if (!constants.has(name)) {
      missing.push(name);
      return '';
    }
    return constants.get(name);
  });

  return {value, missing};
}

/**
 * 契約1件ずつを突き合わせ、食い違いを説明として返す。
 *
 * `pythonSources` は `{相対パス: ソース}`。読み込みを外に出してあるのは、
 * 突き合わせ自体をファイルシステム無しで確かめられるようにするためである。
 */
export function mismatches(contract, typescript, pythonSources) {
  const found = [];

  for (const entry of contract) {
    const source = pythonSources[entry.source];
    if (source === undefined) {
      found.push(`${entry.source} を読めなかった（${entry.typescript} の相手）`);
      continue;
    }

    const {value: expected, missing} = fill(entry.python, pythonConstants(source));

    if (missing.length > 0) {
      found.push(
        `${entry.typescript}: ${entry.source} に ${missing.join(', ')} が無い。` +
          `Python側で名前が変わったなら、この対応表も直すこと`,
      );
      continue;
    }

    if (!typescript.has(entry.typescript)) {
      found.push(`${entry.typescript} が ${TYPESCRIPT_SOURCE} に無い`);
      continue;
    }

    const actual = typescript.get(entry.typescript);
    if (actual !== expected) {
      found.push(
        `${entry.typescript}: 画面は '${actual}'、` +
          `${entry.source} は '${expected}'`,
      );
    }
  }

  return found;
}

const main = async () => {
  const typescript = typeScriptConstants(
    await readFile(resolve(REPOSITORY_ROOT, TYPESCRIPT_SOURCE), 'utf8'),
  );

  const pythonSources = {};
  for (const path of new Set(CONTRACT.map((entry) => entry.source))) {
    pythonSources[path] = await readFile(resolve(REPOSITORY_ROOT, path), 'utf8');
  }

  const found = mismatches(CONTRACT, typescript, pythonSources);

  if (found.length > 0) {
    console.error(`\n画面とPython側で ${found.length} 件の食い違いがある:\n`);
    found.forEach((line) => console.error(`  ${line}`));
    console.error(
      '\n両方を同じ文字列に直すこと。片方だけ直すと、画面は何も見つけられないまま' +
        '「実行がありません」と表示する。',
    );
    return EXIT_FAILURE;
  }

  console.log(`Pipelineの契約: ${CONTRACT.length} 件すべてPython側と一致`);
  return EXIT_SUCCESS;
};

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main()
    .then((code) => process.exit(code))
    .catch((error) => {
      console.error(error);
      process.exit(EXIT_FAILURE);
    });
}

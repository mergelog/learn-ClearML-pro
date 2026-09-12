#!/usr/bin/env node
/**
 * Angular の ESLint 違反を「増やさない」ためのゲート。
 *
 * `apps/web` は ClearML Web を取り込んだ大量の既存コードを持ち、現時点で
 * 数千件の違反が残っている。全件解消を第一ゴールの前提にすると縦スライスの
 * 着手が止まるため、件数の基準値を記録し、それを超えた変更だけを失敗させる。
 *
 * 使い方:
 *   node scripts/eslint-baseline.mjs check    基準値と比較する（CIとローカル共通）
 *   node scripts/eslint-baseline.mjs update   現在の件数を基準値として書き直す
 *
 * `update` は違反を減らしたときに実行する。増やしたときに実行してはならない。
 */

import { spawn } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const WEB_DIRECTORY = resolve(REPOSITORY_ROOT, 'apps/web');
const BASELINE_FILE = resolve(WEB_DIRECTORY, 'eslint-baseline.json');

// pnpm のワークスペースでは eslint がリポジトリ直下へ巻き上げられるため、
// apps/web からの相対パスではなく package の解決結果から辿る。
// eslint は bin を exports で公開していないので、package.json の位置を起点にする。
const ESLINT_CLI = resolve(
  dirname(createRequire(import.meta.url).resolve('eslint/package.json')),
  'bin/eslint.js',
);

const EXIT_SUCCESS = 0;
const EXIT_FAILURE = 1;
const EXIT_INVALID_USAGE = 2;

/**
 * ESLint を JSON で走らせる。
 *
 * 違反があると ESLint は終了コード 1 を返すが、ここでは件数を数えることが
 * 目的なので、標準出力が JSON として読めたかどうかで成否を判断する。
 */
async function runEslint() {
  const output = await new Promise((resolvePromise, rejectPromise) => {
    // PATH に依存しないよう、いま動いている Node をそのまま使う。
    const eslint = spawn(
      process.execPath,
      [ESLINT_CLI, '.', '--format', 'json'],
      { cwd: WEB_DIRECTORY, stdio: ['ignore', 'pipe', 'inherit'] },
    );

    const chunks = [];
    eslint.stdout.on('data', (chunk) => chunks.push(chunk));
    eslint.on('error', rejectPromise);
    eslint.on('close', () => resolvePromise(Buffer.concat(chunks).toString('utf8')));
  });

  try {
    return JSON.parse(output);
  } catch (error) {
    throw new Error(`ESLint did not report JSON: ${error.message}`);
  }
}

function summarise(results) {
  const byRule = {};
  let errors = 0;
  let warnings = 0;

  for (const result of results) {
    for (const message of result.messages) {
      // パースエラーには ruleId がない。規則別の内訳では区別できるようにする。
      const rule = message.ruleId ?? '(parse-error)';
      const severity = message.severity === 2 ? 'errors' : 'warnings';

      byRule[rule] ??= { errors: 0, warnings: 0 };
      byRule[rule][severity] += 1;

      if (severity === 'errors') {
        errors += 1;
      } else {
        warnings += 1;
      }
    }
  }

  return {
    totals: { errors, warnings },
    byRule: Object.fromEntries(Object.entries(byRule).sort(([left], [right]) => left.localeCompare(right))),
  };
}

async function readBaseline() {
  try {
    return JSON.parse(await readFile(BASELINE_FILE, 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT') {
      return null;
    }
    throw error;
  }
}

async function writeBaseline(summary) {
  const baseline = {
    description:
      'apps/web に残る ESLint 違反の基準値。増やす変更は scripts/eslint-baseline.mjs check で失敗する。',
    updatedAt: new Date().toISOString().slice(0, 10),
    ...summary,
  };
  await writeFile(BASELINE_FILE, `${JSON.stringify(baseline, null, 2)}\n`, 'utf8');
  return baseline;
}

function reportNewRules(current, baseline) {
  const regressions = [];

  for (const [rule, counts] of Object.entries(current.byRule)) {
    const before = baseline.byRule?.[rule] ?? { errors: 0, warnings: 0 };
    if (counts.errors > before.errors || counts.warnings > before.warnings) {
      regressions.push(
        `  ${rule}: errors ${before.errors} -> ${counts.errors}, warnings ${before.warnings} -> ${counts.warnings}`,
      );
    }
  }

  return regressions;
}

async function check() {
  const baseline = await readBaseline();
  if (baseline === null) {
    console.error(
      `Baseline is missing. Create it once with:\n  node scripts/eslint-baseline.mjs update`,
    );
    return EXIT_FAILURE;
  }

  const current = summarise(await runEslint());
  const grewErrors = current.totals.errors > baseline.totals.errors;
  const grewWarnings = current.totals.warnings > baseline.totals.warnings;

  console.log(
    `ESLint: errors ${current.totals.errors}/${baseline.totals.errors}, ` +
      `warnings ${current.totals.warnings}/${baseline.totals.warnings}`,
  );

  if (grewErrors || grewWarnings) {
    console.error('\nESLint violations increased beyond the recorded baseline.');
    const regressions = reportNewRules(current, baseline);
    if (regressions.length > 0) {
      console.error('Rules that grew:');
      console.error(regressions.join('\n'));
    }
    console.error('\nFix the new violations. Do not run `update` to hide them.');
    return EXIT_FAILURE;
  }

  if (current.totals.errors < baseline.totals.errors || current.totals.warnings < baseline.totals.warnings) {
    console.log(
      'Violations went down. Record the improvement with:\n  node scripts/eslint-baseline.mjs update',
    );
  }

  return EXIT_SUCCESS;
}

async function update() {
  const written = await writeBaseline(summarise(await runEslint()));
  console.log(
    `Baseline written: errors ${written.totals.errors}, warnings ${written.totals.warnings}`,
  );
  return EXIT_SUCCESS;
}

const COMMANDS = { check, update };

const command = process.argv[2];
if (!Object.hasOwn(COMMANDS, command ?? '')) {
  console.error('Usage: node scripts/eslint-baseline.mjs <check|update>');
  process.exit(EXIT_INVALID_USAGE);
}

process.exit(await COMMANDS[command]());

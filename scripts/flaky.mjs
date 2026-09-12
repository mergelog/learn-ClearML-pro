#!/usr/bin/env node
/**
 * 振れるテスト（flaky）を見つけるための道具。
 *
 * **隔離しない。** skip や quarantine へ移すと赤が消え、赤が消えると直す理由も
 * 消える。retry も入れない。retry を入れた瞬間、振れたテストは緑になり、
 * 検知そのものが無くなる（このリポジトリは retry しない。W12-4）。
 * だから道具の側は「隠す」ではなく「**同じものを繰り返して、振れるかどうかを
 * 数える**」だけをする。
 *
 * 対象は E2E である。下の層は時刻・並行・外部を持たない設計なので、振れるなら
 * それは flaky ではなく設計の綻びであり、隠さずに直す対象になる。E2E だけは
 * 実際のブラウザと時間が入るため、**振れうることを前提に運用する**。
 *
 * 判定の単位はテスト1件である。走行そのものの成否で数えると、1件が振れただけで
 * 全部が振れたことになる。JUnit XML（Playwright が既に書いている）を読む。
 *
 *   ずっと緑            stable
 *   ずっと赤            failing（壊れている。flaky ではない）
 *   緑と赤が混ざる      flaky（これを探している）
 *
 * 走らせ方:
 *   node scripts/flaky.mjs run [--times 5]
 *
 * 見つけたときの手順は docs/_archive/runbooks/009_20260912_flaky_tests.md にある。
 * CI では走らせない（同じ試験を5回走らせる分だけ遅くなる）。疑いが出たときに
 * 手元で回す。
 */

import {spawnSync} from 'node:child_process';
import {readFileSync, rmSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

/** 何を繰り返すか。いまは E2E だけが対象である。 */
const TARGET = {
  script: 'web:e2e',
  report: 'apps/web/reports/e2e/playwright.xml',
};

const DEFAULT_TIMES = 5;

const EXIT_SUCCESS = 0;
const EXIT_FAILURE = 1;
const EXIT_INVALID_USAGE = 2;

/**
 * JUnit XML から、テスト1件ずつの結果を読む。
 *
 * 名前は testsuite（ファイル）と testcase を繋いだものにする。別のファイルに
 * 同じ名前のテストがあったときに、2つを1つとして数えないためである。
 */
export function parseReport(xml) {
  const results = new Map();
  // testsuite の属性と、その中の testcase をまとめて拾う。
  const suites = xml.matchAll(/<testsuite\b([^>]*)>([\s\S]*?)<\/testsuite>/g);

  for (const [, attributes, body] of suites) {
    const suite = attributeOf(attributes, 'name') ?? '';

    for (const [, caseAttributes, caseBody] of body.matchAll(
      // 属性を貪欲に取ると、自己終了タグ（`<testcase ... />`）の `/` まで
      // 属性として飲み込み、次の `</testcase>` までを中身として読んでしまう。
      /<testcase\b([^>]*?)\s*(?:\/>|>([\s\S]*?)<\/testcase>)/g
    )) {
      const name = attributeOf(caseAttributes, 'name') ?? '';
      const contents = caseBody ?? '';
      // skipped は「走っていない」であって「緑」ではない。数に入れない。
      if (/<skipped\b/.test(contents)) {
        continue;
      }
      results.set(`${suite} › ${name}`, !/<(failure|error)\b/.test(contents));
    }
  }

  return results;
}

function attributeOf(attributes, name) {
  const matched = attributes.match(new RegExp(`${name}="([^"]*)"`));
  return matched ? matched[1] : null;
}

/**
 * 走行ごとの結果を、テストごとに畳む。
 *
 * 一度でも欠けたテストは missing として出す。走行ごとに実行された集合が
 * 変わること自体が、振れていることの一種だからである（名前が変わった、
 * 途中で落ちて残りが走らなかった、など）。
 */
export function summarize(runs) {
  const names = new Set(runs.flatMap((run) => [...run.keys()]));
  const flaky = [];
  const failing = [];
  const missing = [];
  let stable = 0;

  for (const name of [...names].sort()) {
    const outcomes = runs.map((run) => run.get(name));
    const seen = outcomes.filter((outcome) => outcome !== undefined);
    const passed = seen.filter(Boolean).length;

    if (seen.length !== runs.length) {
      missing.push({name, ran: seen.length, of: runs.length});
      continue;
    }
    if (passed === seen.length) {
      stable += 1;
    } else if (passed === 0) {
      failing.push({name, passed, of: seen.length});
    } else {
      flaky.push({name, passed, of: seen.length});
    }
  }

  return {flaky, failing, missing, stable};
}

/** 読める報告にする。件数だけでは、何を直せばよいか分からない。 */
export function format(summary, times) {
  const lines = [];

  if (summary.flaky.length > 0) {
    lines.push(`振れたテスト（${times} 回中）:`);
    for (const entry of summary.flaky) {
      lines.push(`  ${entry.passed}/${entry.of} 緑  ${entry.name}`);
    }
    lines.push('');
    lines.push('隔離しない。原因を分類して直し、runbook 009 の台帳へ記録すること。');
  }

  if (summary.failing.length > 0) {
    lines.push(`いつも落ちるテスト（振れてはいない。壊れている）:`);
    for (const entry of summary.failing) {
      lines.push(`  0/${entry.of} 緑  ${entry.name}`);
    }
  }

  if (summary.missing.length > 0) {
    lines.push('走行ごとに実行されたテストが違う:');
    for (const entry of summary.missing) {
      lines.push(`  ${entry.ran}/${entry.of} 回だけ実行  ${entry.name}`);
    }
  }

  if (lines.length === 0) {
    lines.push(`振れたテストは無い（${summary.stable} 件 × ${times} 回すべて緑）`);
  }

  return lines.join('\n');
}

function runOnce() {
  const report = resolve(REPOSITORY_ROOT, TARGET.report);

  // 前の走行の報告が残っていると、走らなかったのに読めてしまう。
  rmSync(report, {force: true});

  spawnSync('pnpm', ['run', TARGET.script], {
    cwd: REPOSITORY_ROOT,
    stdio: 'inherit',
    env: process.env,
  });

  try {
    return parseReport(readFileSync(report, 'utf8'));
  } catch {
    throw new Error(`${TARGET.report} が書かれなかった。走行そのものが立ち上がっていない`);
  }
}

function times(argv) {
  const flag = argv.indexOf('--times');

  if (flag < 0) {
    return DEFAULT_TIMES;
  }

  const value = Number(argv[flag + 1]);

  if (!Number.isInteger(value) || value < 2) {
    // 1回では振れているかどうかは分からない。
    throw new Error('--times には 2 以上の整数を渡す');
  }

  return value;
}

function main(argv) {
  if (argv[0] !== 'run') {
    console.error('使い方: node scripts/flaky.mjs run [--times 5]');
    return EXIT_INVALID_USAGE;
  }

  let count;
  try {
    count = times(argv);
  } catch (error) {
    console.error(error.message);
    return EXIT_INVALID_USAGE;
  }

  const runs = [];
  for (let index = 0; index < count; index += 1) {
    console.log(`\n=== ${index + 1}/${count} 回目 (${TARGET.script})`);
    runs.push(runOnce());
  }

  const summary = summarize(runs);
  console.log(`\n${format(summary, count)}`);

  const settled =
    summary.flaky.length === 0 && summary.failing.length === 0 && summary.missing.length === 0;

  return settled ? EXIT_SUCCESS : EXIT_FAILURE;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  process.exit(main(process.argv.slice(2)));
}

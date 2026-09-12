#!/usr/bin/env node
/**
 * `ci.yml` が手元の `verify` を本当に走らせていることを確かめるゲート。
 *
 * `.github/workflows/ci.yml` の冒頭は「ローカルの `pnpm run verify` と同じ
 * コマンドを、同じ順序で実行する」と宣言している。ところが CI は script を
 * 呼ばず中身を書き写しており、書き写す過程で3か所が落ちていた。
 *
 *   - `py:coverage` のうち `services/tests` の行（認可のテスト13件を含む133件）
 *   - `web:contract`（画面とPython側の定数の突き合わせ）
 *   - `web:e2e`（そもそも `verify:web` にも無い。W12-2 で別ジョブへ）
 *
 * 最後の1つは `verify` の外にあるまま CI へ載せた。速さのために手元の
 * `verify` へは入れないが、そうすると「CI から落ちても誰も気付かない」性質は
 * 残る。だから `COVERAGE` は verify の連鎖だけでなく、`web:e2e` のような
 * 単体の script も対応先のジョブごと書けるようにしてある。
 *
 * どれも**CI が赤くならない種類の欠落**である。走っていないことは、
 * 走っていないという理由では表に出てこない。だから足りない行を足すだけでは
 * 足りず、「次に script が1つ増えたとき、CI へ写し忘れたら失敗する」状態を
 * 作る必要がある。それがこのゲートである。
 *
 * 検査するのは順序を含む包含関係であって、完全一致ではない。
 * `requirements` の lock 検証や Trivy 走査のように**手元の `verify` に無い**
 * CI 固有の手順は、そのまま残せなければならないためである。逆向き、つまり
 * 「`verify` にあるものが CI に無い」だけを失敗にする。
 *
 * 使い方:
 *   node scripts/ci-parity.mjs check
 */

import {readFile} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const PACKAGE_JSON = 'package.json';
const WORKFLOW = '.github/workflows/ci.yml';

const EXIT_SUCCESS = 0;
const EXIT_FAILURE = 1;

/**
 * どの `verify` の連鎖を、どのジョブが引き受けているか。
 *
 * ジョブ分割（python / web / security / supply-chain）は維持する。分割の理由は
 * 「片方の失敗でもう片方の結果が隠れないように」であって、コマンドを再実装する
 * ためではない。ジョブを分けたまま、各ジョブが script を呼べばよい。
 *
 * `supply-chain` がここに無いのは、SBOM・脆弱性照会・イメージ走査が
 * 「今日の世界の状態」を見ており、手元の `verify` に対応物が無いためである。
 *
 * `web:e2e` だけは `verify` の連鎖ではなく単体の script である。ビルドと
 * サーバ起動で数分かかるため `verify:web` へは入れない（入れると「変更ごとに
 * 回す」速さが失われ、回されなくなる）。それでも CI では走らせるので、
 * 対応先のジョブを他と同じ表に書いて固定する。
 *
 * `upstream:status` も同じ扱いである。こちらが `verify` に無いのは速さでは
 * なく、外部へ通信するためで、手元の検証を機内でも回せる状態は崩さない。
 * CI から落ちても誰も気付かない性質は `web:e2e` と同じなので、同じ表で固定する。
 */
export const COVERAGE = [
  {chain: 'verify:docs', job: 'docs'},
  {chain: 'verify:python', job: 'python'},
  {chain: 'verify:web', job: 'web'},
  {chain: 'verify:security', job: 'security'},
  {chain: 'web:e2e', job: 'e2e'},
  {chain: 'upstream:status', job: 'upstream'},
];

/** `pnpm run <name>` だけで構成された script は、連鎖として展開する。 */
const REFERENCE = /^pnpm run ([A-Za-z0-9:._-]+)$/;

/**
 * script 名を、実際に走る末端の script 名の並びへ展開する。
 *
 * 展開するのは「本体が `pnpm run` の連結だけ」の script に限る。
 * `py:coverage` のように実コマンドを含むものは、そこで止めて末端として扱う。
 * どこまで展開するかを別表で持たずに済ませるための規則である。
 */
export function expand(name, scripts, seen = new Set()) {
  const body = scripts[name];

  if (body === undefined) {
    throw new Error(`${PACKAGE_JSON} に script "${name}" が無い`);
  }
  if (seen.has(name)) {
    throw new Error(`script "${name}" が自分自身を呼んでいる`);
  }

  const references = body
    .split('&&')
    .map((part) => REFERENCE.exec(part.trim()));

  if (references.some((reference) => reference === null)) {
    return [name];
  }

  const nested = new Set(seen).add(name);
  return references.flatMap((reference) => expand(reference[1], scripts, nested));
}

const JOB_NAME = /^ {2}([A-Za-z0-9_-]+):\s*$/;
const INVOCATION = /pnpm run ([A-Za-z0-9:._-]+)/g;

/**
 * `ci.yml` から、ジョブごとに呼ばれている script 名を出現順で拾う。
 *
 * YAML として読まずに行で拾っている。見たいのは `run:` に書かれた文字列
 * そのものであって構造ではなく、`run: |` の中身は YAML から見れば
 * ただの1つの文字列だからである。依存を増やさない方を採った。
 */
export function ciJobs(workflow) {
  const jobs = new Map();
  let insideJobs = false;
  let current = null;

  for (const raw of workflow.split('\n')) {
    if (/^jobs:\s*$/.test(raw)) {
      insideJobs = true;
      continue;
    }
    if (!insideJobs) {
      continue;
    }
    // `jobs:` と同じ深さの別のキーが来たら、そこで終わり。
    if (/^\S/.test(raw)) {
      insideJobs = false;
      continue;
    }

    const job = JOB_NAME.exec(raw);
    if (job) {
      current = job[1];
      jobs.set(current, []);
      continue;
    }
    if (current === null) {
      continue;
    }

    const line = raw.trim();
    // 註釈の中の例をコマンドと読み違えない。
    if (line.startsWith('#')) {
      continue;
    }

    for (const invocation of line.matchAll(INVOCATION)) {
      jobs.get(current).push(invocation[1]);
    }
  }

  return jobs;
}

/**
 * 連鎖がジョブの中に、順序を保ったまま現れているかを確かめる。
 *
 * 「現れていない」と「順序が違う」を区別して報告する。前者は写し忘れ、
 * 後者は手元と CI で確かめる順番が違うという別の問題であり、直し方も違う。
 */
export function missing(chain, invocations) {
  const found = [];
  let index = 0;

  for (const script of chain) {
    const at = invocations.indexOf(script, index);

    if (at === -1) {
      found.push(
        invocations.includes(script)
          ? `${script} は走っているが、手元と順序が違う`
          : `${script} が走っていない`,
      );
      continue;
    }

    index = at + 1;
  }

  return found;
}

/** 連鎖とジョブの対応を1件ずつ突き合わせ、食い違いを説明として返す。 */
export function differences(coverage, scripts, jobs) {
  const found = [];

  for (const {chain, job} of coverage) {
    const invocations = jobs.get(job);

    if (invocations === undefined) {
      found.push(`${WORKFLOW} に job "${job}" が無い（${chain} の担当）`);
      continue;
    }

    const expanded = expand(chain, scripts);
    // `web:e2e` のように単体で書いた項目は、出所を添えても同じ名前を
    // 二度言うだけになる。連鎖の一部であるときだけ、どこから来たかを言う。
    const origin =
      expanded.length === 1 && expanded[0] === chain ? '' : `（${chain} に入っている）`;

    for (const line of missing(expanded, invocations)) {
      found.push(`${job} job: ${line}${origin}`);
    }
  }

  return found;
}

const main = async () => {
  const {scripts} = JSON.parse(
    await readFile(resolve(REPOSITORY_ROOT, PACKAGE_JSON), 'utf8'),
  );
  const jobs = ciJobs(await readFile(resolve(REPOSITORY_ROOT, WORKFLOW), 'utf8'));

  const found = differences(COVERAGE, scripts, jobs);

  if (found.length > 0) {
    console.error(`\n手元にあって CI で走っていないものが ${found.length} 件ある:\n`);
    found.forEach((line) => console.error(`  ${line}`));
    console.error(
      `\n${WORKFLOW} の該当ジョブへ \`pnpm run <script>\` のステップを足すこと。` +
        '\nCI 固有の手順を足す分にはこのゲートは何も言わない。' +
        '止めているのは逆向き、\n手元にある検証が CI から落ちることだけである。',
    );
    return EXIT_FAILURE;
  }

  const total = COVERAGE.reduce((sum, {chain}) => sum + expand(chain, scripts).length, 0);
  console.log(`CI の一致: 手元の検証 ${total} 件すべてが ci.yml で走る`);
  return EXIT_SUCCESS;
};

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main()
    .then((code) => process.exit(code))
    .catch((error) => {
      console.error(error.message ?? error);
      process.exit(EXIT_FAILURE);
    });
}

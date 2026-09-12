#!/usr/bin/env node
/**
 * fork 元（ClearML Web）が進んだかどうかを確かめるゲート。
 *
 * `apps/web` は ClearML Web の fork である。fork 元の更新は、こちらが何も
 * しなくても入る。入ったことに気付かなければ、脆弱性の修正も取り込まないまま
 * 進む。71 の R-01・R-02 は、この「見ていない」状態そのものである。
 *
 * 版数の一致では検知できない。実際、着手時点の upstream の `master` は
 * tag `v2.5` より先へ進んでいるが、`package.json` の `version` はどちらも
 * `2.5.0` のままである。そこで見るのは版数ではなく commit にする。
 *
 * このゲートは「最後に見た commit」と「いまの commit」を比べるだけで、
 * 取り込みを促さない。取り込むか見送るかは人が決める（03 §4.15）。
 * 決めたら `upstream.json` の `recorded` を書き換える。書き換えは
 * **見たという記録**であって、取り込んだという記録ではない。
 *
 * 他のゲートと違い、外部の状態を見るので通信が要る。だから `verify` には
 * 入れない。CI では専用のジョブが呼ぶ（供給網の検査と同じ扱いである）。
 *
 * 使い方:
 *   node scripts/upstream-status.mjs check
 */

import {execFile} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {promisify} from 'node:util';

const run = promisify(execFile);

const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const DECLARATION = 'upstream.json';
const WEB_PACKAGE_JSON = 'apps/web/package.json';

const EXIT_SUCCESS = 0;
const EXIT_FAILURE = 1;
const EXIT_INVALID_USAGE = 2;

/** `git ls-remote` の1行目から commit を取り出す。 */
export function commitOf(lsRemoteOutput) {
  const line = lsRemoteOutput.split('\n').find((candidate) => candidate.trim() !== '');

  if (line === undefined) {
    return null;
  }

  const [commit] = line.split('\t');

  return /^[0-9a-f]{40}$/.test(commit) ? commit : null;
}

/** 記録した commit と、いま見えている commit を同じ桁数で比べる。 */
export const sameCommit = (recorded, observed) =>
  observed.startsWith(recorded) || recorded.startsWith(observed);

/**
 * 記録と実際の食い違いを、説明として返す。
 *
 * 通信とファイル読み取りを外に出してあるのは、判定そのものを
 * ネットワーク無しで確かめられるようにするためである。
 */
export function differences(declaration, observed) {
  const found = [];

  if (observed.remoteUrl === null) {
    found.push(
      `remote "${declaration.remote}" が登録されていない。` +
        `\`git remote add ${declaration.remote} ${declaration.repository}\` で登録すること`,
    );
  } else if (normalizeUrl(observed.remoteUrl) !== normalizeUrl(declaration.repository)) {
    found.push(
      `remote "${declaration.remote}" が ${observed.remoteUrl} を指している。` +
        `${DECLARATION} は ${declaration.repository} と書いてある`,
    );
  }

  if (observed.commit === null) {
    found.push(`${declaration.repository} の ${declaration.branch} を読めなかった`);
  } else if (!sameCommit(declaration.recorded.commit, observed.commit)) {
    found.push(
      `upstream の ${declaration.branch} が進んでいる: ` +
        `記録 ${declaration.recorded.commit} → いま ${observed.commit.slice(0, 12)}`,
    );
  }

  if (observed.upstreamVersion !== null && observed.upstreamVersion !== declaration.recorded.version) {
    found.push(
      `upstream の版が変わった: 記録 ${declaration.recorded.version} → ` +
        `いま ${observed.upstreamVersion}`,
    );
  }

  return found;
}

/** 末尾の `.git` と `/` の違いで別物にしない。 */
const normalizeUrl = (url) => url.trim().replace(/\.git$/, '').replace(/\/$/, '');

const remoteUrlOf = async (name) => {
  try {
    const {stdout} = await run('git', ['remote', 'get-url', name], {cwd: REPOSITORY_ROOT});
    return stdout.trim();
  } catch {
    return null;
  }
};

const upstreamCommitOf = async (repository, branch) => {
  try {
    const {stdout} = await run('git', ['ls-remote', repository, `refs/heads/${branch}`], {
      cwd: REPOSITORY_ROOT,
    });
    return commitOf(stdout);
  } catch {
    return null;
  }
};

/**
 * upstream の `package.json` の版を読む。
 *
 * clone せずに1ファイルだけを取りに行く。fork 元の作業ツリーを手元へ
 * 落とすのは、版を1つ読むための代価として大きい。
 */
const upstreamVersionOf = async (repository, commit) => {
  const slug = normalizeUrl(repository).replace('https://github.com/', '');

  try {
    const response = await fetch(`https://raw.githubusercontent.com/${slug}/${commit}/package.json`);
    if (!response.ok) {
      return null;
    }
    return JSON.parse(await response.text()).version ?? null;
  } catch {
    return null;
  }
};

const check = async () => {
  const declaration = JSON.parse(await readFile(resolve(REPOSITORY_ROOT, DECLARATION), 'utf8'));
  const local = JSON.parse(await readFile(resolve(REPOSITORY_ROOT, WEB_PACKAGE_JSON), 'utf8'));

  const remoteUrl = await remoteUrlOf(declaration.remote);
  const commit = await upstreamCommitOf(declaration.repository, declaration.branch);
  const upstreamVersion = commit === null ? null : await upstreamVersionOf(declaration.repository, commit);

  const found = differences(declaration, {remoteUrl, commit, upstreamVersion});

  if (found.length > 0) {
    console.error(`\nfork 元と手元の記録が ${found.length} 件食い違っている:\n`);
    found.forEach((line) => console.error(`  ${line}`));
    console.error(
      `\n差分を見て、取り込むか見送るかを決めること（03 §4.15）。` +
        `\n決めたら ${DECLARATION} の recorded を書き換える。書き換えは見たという記録であり、` +
        `\n取り込んだという記録ではない。見送るなら、見送った理由を note へ書く。\n`,
    );
    return EXIT_FAILURE;
  }

  console.log(
    `fork 元: ${declaration.branch} は記録した ${declaration.recorded.commit} のまま` +
      `（手元 ${local.version} / upstream ${upstreamVersion ?? '版を読めず'}）`,
  );
  return EXIT_SUCCESS;
};

const main = async () => {
  if (process.argv[2] !== 'check') {
    console.error('使い方: node scripts/upstream-status.mjs check');
    return EXIT_INVALID_USAGE;
  }

  return check();
};

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main()
    .then((code) => process.exit(code))
    .catch((error) => {
      console.error(error);
      process.exit(EXIT_FAILURE);
    });
}

/**
 * 負荷試験の期限が、運用のしきい値と同じであることの検査。
 *
 * 負荷試験（`services/perf/prediction_api.js`）は「決めた期限の内側で
 * 答え続けるか」を見る。その期限は試験のために新しく決めた数字ではなく、
 * 運用が鳴らすと決めている値（`infra/observability/alerts.yml`）である。
 *
 * 2つが別々に書かれている以上、片方だけが動く。動いたことは
 * **ずれたという理由では表に出てこない**（W12-1 と同じ形）。試験が緑なのに
 * 本番が鳴る、あるいは本番は静かなのに試験が落ちる、という結果になる。
 * だからずれを検知する側をここへ置く。
 *
 * 負荷試験そのものは走らせない（backendと推論サービスの起動が要る）。
 * ここで見るのは数字の一致だけであり、それは `web:gates:test` の中で
 * 何も立てずに見られる。**検証を増やすために、走らせる場所を増やさない。**
 *
 * 実行: node --test scripts/tests/
 */

import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {test} from 'node:test';

const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');

const ALERTS = 'infra/observability/alerts.yml';
const LOAD_TEST = 'services/perf/prediction_api.js';

/**
 * アラートの式から、しきい値を読む。
 *
 * 式は複数行に折られているので、アラート名から次のアラートまでを1つの塊と
 * して扱い、その中の `> 数値` を拾う。塊で区切らずにファイル全体から拾うと、
 * 別のアラートの数字を読んでも気付けない。
 */
export function readAlertThreshold(text, alertName) {
  const start = text.indexOf(`- alert: ${alertName}`);

  if (start < 0) {
    throw new Error(`${ALERTS} に ${alertName} が無い`);
  }

  const rest = text.slice(start + 1);
  const next = rest.indexOf('- alert: ');
  const block = next < 0 ? rest : rest.slice(0, next);
  const matched = block.match(/>\s*([0-9]+(?:\.[0-9]+)?)\s*$/m);

  if (!matched) {
    throw new Error(`${alertName} の式から比較の数値を読めない`);
  }

  return Number(matched[1]);
}

/** 負荷試験が持っている期限を読む。 */
export function readLoadThreshold(text, name) {
  const matched = text.match(new RegExp(`const ${name} = ([0-9]+(?:\\.[0-9]+)?);`));

  if (!matched) {
    throw new Error(`${LOAD_TEST} に ${name} が無い`);
  }

  return Number(matched[1]);
}

const alerts = readFileSync(resolve(REPOSITORY_ROOT, ALERTS), 'utf8');
const loadTest = readFileSync(resolve(REPOSITORY_ROOT, LOAD_TEST), 'utf8');

test('応答の期限が、鳴らすと決めた値と同じである', () => {
  // アラートは秒で、k6 はミリ秒で書く。単位を揃えずに比べると、
  // 1000倍ずれたまま「一致している」と読むことになる。
  const alerted = readAlertThreshold(alerts, 'PredictionLatencyHigh');
  const measured = readLoadThreshold(loadTest, 'LATENCY_BUDGET_MS');

  assert.equal(measured, alerted * 1000);
});

test('失敗の許容が、鳴らすと決めた値と同じである', () => {
  const alerted = readAlertThreshold(alerts, 'PredictionErrorRateHigh');
  const measured = readLoadThreshold(loadTest, 'ERROR_BUDGET_RATE');

  assert.equal(measured, alerted);
});

test('k6 のしきい値が、読んだ数字をそのまま使っている', () => {
  // 定数だけを合わせても、options に別の数字を直書きできる。
  // 実際に効くのは options のほうである。
  assert.match(loadTest, /p\(95\)<\$\{LATENCY_BUDGET_MS\}/);
  assert.match(loadTest, /rate<\$\{ERROR_BUDGET_RATE\}/);
});

test('アラートごとに区切って読む（隣のアラートの数字を読まない）', () => {
  const text = [
    '      - alert: First',
    '        expr: >-',
    '          something > 7',
    '      - alert: Second',
    '        expr: >-',
    '          other > 9',
  ].join('\n');

  assert.equal(readAlertThreshold(text, 'First'), 7);
  assert.equal(readAlertThreshold(text, 'Second'), 9);
});

test('読めないときは黙って通さない', () => {
  assert.throws(() => readAlertThreshold(alerts, 'NoSuchAlert'), /NoSuchAlert/);
  assert.throws(() => readLoadThreshold(loadTest, 'NO_SUCH_BUDGET'), /NO_SUCH_BUDGET/);
  assert.throws(
    () => readAlertThreshold('      - alert: Empty\n        expr: up\n', 'Empty'),
    /比較の数値/
  );
});

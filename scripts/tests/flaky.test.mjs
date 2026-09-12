/**
 * `scripts/flaky.mjs` の検査。
 *
 * この道具が間違えると、**振れているのに「振れていない」と言う**。それは
 * 隔離よりたちが悪い。隔離は少なくとも印が残るが、誤った緑は何も残さない。
 * だから読み取り（JUnit XML）と畳み方（走行ごとの結果をテスト単位にする）を
 * ここで確かめる。
 *
 * 実行: node --test scripts/tests/
 */

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {format, parseReport, summarize} from '../flaky.mjs';

const REPORT = `<testsuites>
<testsuite name="a.spec.ts" tests="2">
<testcase name="green" classname="a.spec.ts" time="1"></testcase>
<testcase name="red" classname="a.spec.ts" time="1">
<failure message="boom">stack</failure>
</testcase>
</testsuite>
<testsuite name="b.spec.ts" tests="2">
<testcase name="green" classname="b.spec.ts" time="1"/>
<testcase name="skipped" classname="b.spec.ts" time="0"><skipped/></testcase>
</testsuite>
</testsuites>`;

test('テスト1件ずつの結果を読む', () => {
  const results = parseReport(REPORT);

  assert.equal(results.get('a.spec.ts › green'), true);
  assert.equal(results.get('a.spec.ts › red'), false);
});

test('名前はファイルごとに分ける', () => {
  // 2つのファイルに同じ名前のテストがある。1つとして数えると、
  // 片方が振れていても「1回緑・1回赤」に見えてしまう。
  const results = parseReport(REPORT);

  assert.equal(results.has('a.spec.ts › green'), true);
  assert.equal(results.has('b.spec.ts › green'), true);
});

test('走っていないテストを緑として数えない', () => {
  assert.equal(parseReport(REPORT).has('b.spec.ts › skipped'), false);
});

test('error も失敗として読む', () => {
  const xml = `<testsuites><testsuite name="a.spec.ts">
    <testcase name="x"><error message="crashed"/></testcase>
  </testsuite></testsuites>`;

  assert.equal(parseReport(xml).get('a.spec.ts › x'), false);
});

test('緑と赤が混ざったものだけを flaky と呼ぶ', () => {
  const summary = summarize([
    new Map([['t › a', true], ['t › b', true], ['t › c', false]]),
    new Map([['t › a', true], ['t › b', false], ['t › c', false]]),
  ]);

  assert.deepEqual(summary.flaky, [{name: 't › b', passed: 1, of: 2}]);
  // ずっと赤は「壊れている」であって、振れてはいない。
  assert.deepEqual(summary.failing, [{name: 't › c', passed: 0, of: 2}]);
  assert.equal(summary.stable, 1);
});

test('走行ごとに実行されたテストが違うことも見逃さない', () => {
  // 名前が変わった、途中で落ちて残りが走らなかった。どちらも
  // 「安定している」とは言えない状態である。
  const summary = summarize([
    new Map([['t › a', true], ['t › b', true]]),
    new Map([['t › a', true]]),
  ]);

  assert.deepEqual(summary.missing, [{name: 't › b', ran: 1, of: 2}]);
  assert.deepEqual(summary.flaky, []);
});

test('報告は、どのテストが何回緑だったかまで出す', () => {
  const text = format(summarize([
    new Map([['t › a', true]]),
    new Map([['t › a', false]]),
  ]), 2);

  assert.match(text, /1\/2 緑 {2}t › a/);
  assert.match(text, /隔離しない/);
});

test('振れていないときは、そう言う', () => {
  const text = format(summarize([new Map([['t › a', true]]), new Map([['t › a', true]])]), 2);

  assert.match(text, /振れたテストは無い（1 件 × 2 回すべて緑）/);
});

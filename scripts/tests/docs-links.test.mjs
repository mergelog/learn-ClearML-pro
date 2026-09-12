/**
 * `scripts/docs-links.mjs` の検査。
 *
 * このゲートの失敗の仕方は2通りあり、どちらも黙って起きる。リンクを
 * 取りこぼせば、切れたリンクを通してしまう。コード塊の中の字面を
 * リンクとして数えれば、直しようのない失敗を報告し続け、やがて
 * `verify` から外される。取り出しの範囲を、両側から固定する。
 *
 * 実行: node --test 'scripts/tests/**\/*.test.mjs'
 */

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {brokenLinks, referencesIn, relativePathOf, withoutCode} from '../docs-links.mjs';

test('相対リンクを、行番号つきで取り出す', () => {
  const source = ['# 見出し', '', '[要件定義書](phase1_上流設計/01_要件定義書.md) を見る', ''].join('\n');

  assert.deepEqual(referencesIn(source), [
    {
      target: 'phase1_上流設計/01_要件定義書.md',
      path: 'phase1_上流設計/01_要件定義書.md',
      line: 3,
    },
  ]);
});

test('外部参照と同一文書内の見出しは確かめない', () => {
  assert.equal(relativePathOf('https://clear.ml/docs'), null);
  assert.equal(relativePathOf('mailto:someone@example.com'), null);
  assert.equal(relativePathOf('//example.com/x'), null);
  assert.equal(relativePathOf('#401-が返る'), null);
});

test('見出しと問い合わせを落として、パスだけを取り出す', () => {
  assert.equal(relativePathOf('../adr/001_x.md#判断'), '../adr/001_x.md');
  assert.equal(relativePathOf('71_%E3%83%AA%E3%82%B9%E3%82%AF.md'), '71_リスク.md');
});

test('コード塊の中の字面をリンクとして数えない', () => {
  const source = ['```bash', 'sed -n "s/\\[x\\](y.md)//"', '```', '', '[本物](実在.md)'].join('\n');

  const references = referencesIn(source);

  assert.equal(references.length, 1);
  assert.equal(references[0].path, '実在.md');
  // 塊を読み飛ばしても行番号がずれない。
  assert.equal(references[0].line, 5);
});

test('行の中のコードも数えない', () => {
  assert.deepEqual(referencesIn('`[見本](sample.md)` と書いた'), []);
});

test('画像と参照定義も、実在を確かめる対象に含める', () => {
  const source = ['![図](figures/flow.svg)', '', '[台帳]: phase8_プロジェクト管理/71_リスク登録簿.md'].join('\n');

  assert.deepEqual(
    referencesIn(source).map((reference) => reference.path),
    ['figures/flow.svg', 'phase8_プロジェクト管理/71_リスク登録簿.md'],
  );
});

test('コード塊が閉じられていなければ、そこから先を読まない', () => {
  // 閉じ忘れた塊の先を読むと、コマンドの字面を大量に報告し始める。
  assert.deepEqual(referencesIn(['```', '[x](y.md)'].join('\n')), []);
});

test('コード部分を空白へ置き換えても、行数は変わらない', () => {
  const source = ['a', '```', 'b', '```', 'c'].join('\n');

  assert.equal(withoutCode(source).split('\n').length, source.split('\n').length);
});

test('実在しない先だけを、文書名と行番号つきで報告する', async () => {
  const sources = {
    'docs/a.md': '[在る](b.md) と [無い](c.md)',
  };
  const read = async (path) => sources[path.replace(`${process.cwd()}/`, '')];

  const found = await brokenLinks(process.cwd(), ['docs/a.md'], async (path) => {
    const source = await read(path);
    if (source === undefined) {
      throw new Error(`読めない: ${path}`);
    }
    return source;
  });

  // `docs/b.md` も `docs/c.md` も実在しないので、2件とも報告される。
  assert.deepEqual(
    found.map((link) => link.resolved),
    ['docs/b.md', 'docs/c.md'],
  );
  assert.deepEqual(
    found.map((link) => link.line),
    [1, 1],
  );
});

/**
 * `scripts/upstream-status.mjs` の検査。
 *
 * このゲートが黙って通ってしまう形は2つある。upstream が進んでいるのに
 * 同じ commit だと読むことと、remote が別のリポジトリを指しているのに
 * 何も言わないことである。どちらも「追跡している」という外見だけが残る。
 *
 * 実行: node --test 'scripts/tests/**\/*.test.mjs'
 */

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {commitOf, differences, sameCommit} from '../upstream-status.mjs';

const declaration = {
  remote: 'upstream',
  repository: 'https://github.com/clearml/clearml-web.git',
  branch: 'master',
  recorded: {commit: '067b48519563', version: '2.5.0'},
};

const observed = {
  remoteUrl: 'https://github.com/clearml/clearml-web.git',
  commit: '067b48519563a1b2c3d4e5f60718293a4b5c6d7e',
  upstreamVersion: '2.5.0',
};

test('`git ls-remote` の出力から commit を取り出す', () => {
  assert.equal(
    commitOf('067b48519563a1b2c3d4e5f60718293a4b5c6d7e\trefs/heads/master\n'),
    '067b48519563a1b2c3d4e5f60718293a4b5c6d7e',
  );
  assert.equal(commitOf(''), null);
  assert.equal(commitOf('fatal: そんな参照は無い\n'), null);
});

test('記録は短縮形、観測は40桁でも同じ commit と読む', () => {
  assert.equal(sameCommit('067b48519563', '067b48519563a1b2c3d4e5f60718293a4b5c6d7e'), true);
  assert.equal(sameCommit('067b48519563', '48b61702f7033bb699510ecc0314c47fb0b1dc69'), false);
});

test('記録と一致していれば何も報告しない', () => {
  assert.deepEqual(differences(declaration, observed), []);
});

test('upstream が進んでいれば、両方の commit を挙げて報告する', () => {
  const found = differences(declaration, {...observed, commit: '48b61702f7033bb699510ecc0314c47fb0b1dc69'});

  assert.equal(found.length, 1);
  assert.match(found[0], /067b48519563/);
  assert.match(found[0], /48b61702f703/);
});

test('版数が同じでも、commit が進んでいれば報告する', () => {
  // 実際に起きている状態である。upstream の master は tag v2.5 より先にあるが、
  // `version` はどちらも 2.5.0 のままで、版数だけを見ると何も起きていないように見える。
  const found = differences(declaration, {
    ...observed,
    commit: 'ffffffffffffffffffffffffffffffffffffffff',
    upstreamVersion: '2.5.0',
  });

  assert.equal(found.length, 1);
  assert.match(found[0], /進んでいる/);
});

test('remote が登録されていなければ、登録の仕方ごと報告する', () => {
  const found = differences(declaration, {...observed, remoteUrl: null});

  assert.equal(found.length, 1);
  assert.match(found[0], /git remote add upstream/);
});

test('remote が別のリポジトリを指していれば報告する', () => {
  const found = differences(declaration, {
    ...observed,
    remoteUrl: 'https://github.com/someone/another-fork.git',
  });

  assert.equal(found.length, 1);
  assert.match(found[0], /another-fork/);
});

test('末尾の `.git` の有無だけでは食い違いと呼ばない', () => {
  assert.deepEqual(
    differences(declaration, {...observed, remoteUrl: 'https://github.com/clearml/clearml-web'}),
    [],
  );
});

test('upstream を読めなかったときは、通さずに報告する', () => {
  // 通信できないことを「変化なし」と読むと、繋がらない間ずっと緑になる。
  const found = differences(declaration, {...observed, commit: null, upstreamVersion: null});

  assert.equal(found.length, 1);
  assert.match(found[0], /読めなかった/);
});

test('版が上がったことも報告する', () => {
  const found = differences(declaration, {...observed, upstreamVersion: '2.6.0'});

  assert.equal(found.length, 1);
  assert.match(found[0], /2\.6\.0/);
});

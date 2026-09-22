import {expect, Page, test} from '@playwright/test';
import {cdp, commitComposition, dispatchComposingKey, setComposition} from './helpers/ime';
import {INVESTIGATION, loginViaClearmlWeb} from './helpers/real-backend';

/**
 * フェーズ2 観点A：検索欄（sm-search）の IME の扱い。実バックエンドの調査用プロジェクトのタスク一覧で、
 * ページ上部の検索（common-search → sm-search）に日本語を入力する。
 * - 変換中（未確定）の文字列で tasks.get_all_ex が呼ばれるか
 * - 確定後の文字列が最小文字数（3）未満のとき、検索が変換中の文字列のまま残るか
 * - 変換取消の Esc で検索欄が空になるか
 * 読み取りだけで、書き込みは行わない。
 */
const I = INVESTIGATION;

async function closeTipIfShown(page: Page) {
  await page.waitForTimeout(2000);
  const tip = page.locator('mat-dialog-container', {hasText: 'Don\'t show again'});
  if (await tip.count()) {
    await tip.locator('button').first().click();
    await expect(tip).toHaveCount(0);
  }
}

function recordSearches(page: Page): string[] {
  const patterns: string[] = [];
  page.on('request', request => {
    if (request.url().endsWith('/tasks.get_all_ex')) {
      const body = request.postData() ?? '';
      const match = body.match(/"pattern":"((?:[^"\\]|\\.)*)"/);
      patterns.push(match ? JSON.parse(`"${match[1]}"`) : '(no pattern)');
    }
  });
  return patterns;
}

async function openSearch(page: Page) {
  await page.goto(`/projects/${I.project}/tasks`);
  await closeTipIfShown(page);
  await page.locator('sm-common-search button[data-id="searchIcon"]').click();
  const input = page.locator('sm-common-search input[data-id="searchInputField"]');
  await expect(input).toBeFocused();
  // 開くアニメーションの最中（開いて数十ms）に CDP の insertText を送ると、カーソルが先頭に残って文字が逆順に入ることがある（試験側の現象）
  await page.waitForTimeout(500);
  return input;
}

test('変換中の文字列で検索が走り、確定後の2文字では検索が更新されない（確定を Enter 以外で行った場合）', async ({page}) => {
  await loginViaClearmlWeb(page);
  const input = await openSearch(page);
  const searches = recordSearches(page);
  const session = await cdp(page);

  // 「じっけん」まで打って、変換（スペース）の前に 0.8 秒止まる
  for (const text of ['j', 'じ', 'じっ', 'じっk', 'じっけ', 'じっけn', 'じっけん']) {
    await setComposition(session, text);
    await page.waitForTimeout(80);
  }
  await page.waitForTimeout(800);
  const duringComposition = [...searches];
  // 変換して、Enter 以外（候補のクリックなど）で確定する
  await setComposition(session, '実験');
  await page.waitForTimeout(100);
  await commitComposition(session, '実験');
  await page.waitForTimeout(1500);

  const url = page.url();
  console.log(JSON.stringify({duringComposition, all: searches, inputValue: await input.inputValue(), url: decodeURIComponent(url)}));
  expect(duringComposition).toContain('じっけん');
  expect(await input.inputValue()).toBe('実験');
  expect(searches.at(-1)).toBe('じっけん');
});

test('参考：変換確定の Enter（Chromium の順序）で確定した場合', async ({page}) => {
  await loginViaClearmlWeb(page);
  const input = await openSearch(page);
  const searches = recordSearches(page);
  const session = await cdp(page);
  for (const text of ['j', 'じ', 'じっ', 'じっk', 'じっけ', 'じっけn', 'じっけん']) {
    await setComposition(session, text);
    await page.waitForTimeout(80);
  }
  await page.waitForTimeout(800);
  await setComposition(session, '実験');
  await dispatchComposingKey(input, {key: 'Enter'});
  await commitComposition(session, '実験');
  await page.waitForTimeout(1500);
  console.log(JSON.stringify({all: searches, inputValue: await input.inputValue()}));
});

test('参考：Windows の Chrome の届き方（key が Process）で変換確定の Enter を押した場合', async ({page}) => {
  await loginViaClearmlWeb(page);
  const input = await openSearch(page);
  const searches = recordSearches(page);
  const session = await cdp(page);
  for (const text of ['じ', 'じっ', 'じっけ', 'じっけん']) {
    await setComposition(session, text);
    await page.waitForTimeout(80);
  }
  await page.waitForTimeout(800);
  await setComposition(session, '実験');
  await dispatchComposingKey(input, {key: 'Process'});
  await commitComposition(session, '実験');
  await page.waitForTimeout(1500);
  console.log(JSON.stringify({all: searches, inputValue: await input.inputValue()}));
  expect(searches.at(-1)).toBe('じっけん');
});

test('変換取消の Esc で、検索欄の文字列がすべて消え、検索が解除される', async ({page}) => {
  await loginViaClearmlWeb(page);
  const input = await openSearch(page);
  const searches = recordSearches(page);
  await page.keyboard.type('調査タスク');
  await page.waitForTimeout(1500);
  const session = await cdp(page);
  await setComposition(session, 'えー');
  await page.waitForTimeout(100);
  await dispatchComposingKey(input, {key: 'Escape'});
  await page.waitForTimeout(1500);
  console.log(JSON.stringify({all: searches, inputValue: await input.inputValue()}));
  expect(await input.inputValue()).toBe('');
  expect(searches.at(-1)).toBe('(no pattern)');
});

import {expect, Page, test} from '@playwright/test';
import {cdp, setComposition} from './helpers/ime';
import {loginViaClearmlWeb} from './helpers/real-backend';

/** ログが19行ある既存タスク（hyperparameter-optimization） */
const LOG_TASK = {project: '53f9b62a0687460290bac474f2ec8c77', task: '6287d954f8db44d98acd877fad386470'};

/**
 * フェーズ2 観点A：CONSOLE（ログ）の「Filter By Regex」は (keyup) で値を拾う。
 * キーを伴わない入力（右クリックの貼り付け・ドラッグ・変換候補のクリックでの確定）でフィルタが更新されるかを確かめる。
 * Playwright の fill は input イベントだけを発生させ、keyup を発生させないので、貼り付けの代わりに使う。
 * 実バックエンドの既存タスク（読み取りだけ）。
 */
async function openLog(page: Page) {
  await loginViaClearmlWeb(page);
  await page.goto(`/projects/${LOG_TASK.project}/tasks/${LOG_TASK.task}/output/log`);
  await page.waitForTimeout(2500);
  const tip = page.locator('mat-dialog-container', {hasText: 'Don\'t show again'});
  if (await tip.count()) {
    await tip.locator('button').first().click();
  }
  const lines = page.locator('[data-id="logLine"]');
  await expect(lines.first()).toBeVisible();
  return {lines, filter: page.locator('input[data-id="filterByRegexField"]')};
}

test('キーを伴わない入力（貼り付け相当）ではフィルタが更新されず、次のキー操作で初めて反映される', async ({page}) => {
  const {lines, filter} = await openLog(page);
  const before = await lines.count();
  await filter.fill('no-such-log-line-zzz');
  await page.waitForTimeout(800);
  const afterFill = await lines.count();
  await filter.press('End');
  await page.waitForTimeout(800);
  const afterKey = await lines.count();
  console.log(JSON.stringify({before, afterFill, afterKey}));
  expect(afterFill).toBe(before);
  expect(afterKey).toBe(0);
});

test('参考：変換中の文字列でフィルタが掛かる（keyup が届くたびに未確定の文字列で絞り込む）', async ({page}) => {
  const {lines, filter} = await openLog(page);
  const before = await lines.count();
  await filter.click();
  const session = await cdp(page);
  await setComposition(session, 'えぽっk');
  // 実際の IME では変換中の打鍵ごとに keyup（keyCode は元のキー）が届く
  await filter.evaluate(el => el.dispatchEvent(new KeyboardEvent('keyup', {key: 'k', code: 'KeyK', keyCode: 75, bubbles: true})));
  await page.waitForTimeout(800);
  console.log(JSON.stringify({before, duringComposition: await lines.count(), value: await filter.inputValue()}));
});

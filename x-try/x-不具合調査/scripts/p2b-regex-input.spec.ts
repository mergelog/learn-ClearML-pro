import {expect, Page, test} from '@playwright/test';
import {mockClearmlApi} from './helpers/mock-api';
import {loginViaClearmlWeb} from './helpers/real-backend';

/**
 * フェーズ2 観点B：利用者の入力をエスケープせずに new RegExp に渡す箇所。
 * - ログの「Filter By Regex」に正規表現として不正な文字列（`(`）を入れたとき
 * - Enqueue ダイアログのキューの選択欄で、記号を含むキュー名に一致する文字（`(`・`.`）を打ったとき
 */
const LOG_TASK = {project: '53f9b62a0687460290bac474f2ec8c77', task: '6287d954f8db44d98acd877fad386470'};

function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on('console', m => m.type() === 'error' && errors.push(m.text().split('\n')[0].slice(0, 160)));
  page.on('pageerror', e => errors.push(e.message.slice(0, 160)));
  return errors;
}

test('ログのフィルタに `(` を入れると例外が出て、直前の絞り込みのまま残る', async ({page}) => {
  const errors = collectErrors(page);
  await loginViaClearmlWeb(page);
  await page.goto(`/projects/${LOG_TASK.project}/tasks/${LOG_TASK.task}/output/log`);
  await page.waitForTimeout(2500);
  const tip = page.locator('mat-dialog-container', {hasText: 'Don\'t show again'});
  if (await tip.count()) {
    await tip.locator('button').first().click();
  }
  const lines = page.locator('[data-id="logLine"]');
  await expect(lines.first()).toBeVisible();
  const before = await lines.count();
  const filter = page.locator('input[data-id="filterByRegexField"]');
  await filter.click();
  await page.keyboard.type('zzz');
  await page.waitForTimeout(800);
  const afterZzz = await lines.count();
  await page.keyboard.press('Backspace');
  await page.keyboard.press('Backspace');
  await page.keyboard.press('Backspace');
  await page.keyboard.type('(');
  await page.waitForTimeout(800);
  const afterParen = await lines.count();
  console.log(JSON.stringify({before, afterZzz, afterParen, value: await filter.inputValue(), errors}));
  expect(errors.some(e => /Invalid regular expression/.test(e))).toBe(true);
});

test('キューの選択欄で、キュー名に含まれる `(` を打つと例外が出て、候補が表示されない', async ({page}) => {
  const errors = collectErrors(page);
  const queues = [
    {id: 'q-1', name: 'gpu(2)', display_name: '', company: {id: 'test-company'}, entries: []},
    {id: 'q-2', name: 'default', display_name: '', company: {id: 'test-company'}, entries: []},
    {id: 'q-3', name: 'v1.2-queue', display_name: '', company: {id: 'test-company'}, entries: []}
  ];
  await mockClearmlApi(page, {
    overrides: {
      'queues.get_all_ex': () => ({data: {queues}}),
      'queues.get_all': () => ({data: {queues}}),
      'queues.get_default': () => ({data: {id: 'q-2', name: 'default'}})
    }
  });
  await page.goto('/projects/bug-project/tasks/task-a/execution');
  await page.locator('sm-experiment-info-header sm-experiment-menu-extended button').first().click();
  await page.locator('[data-id="Enqueue Option"]').click();
  const input = page.locator('mat-dialog-container input').first();
  await expect(input).toBeVisible();
  const results: Record<string, unknown> = {};
  for (const text of ['gpu', 'gpu(', '.']) {
    await input.fill('');
    await input.click();
    await page.keyboard.type(text);
    await page.waitForTimeout(500);
    results[text] = {
      options: await page.locator('mat-option').allInnerTexts(),
      bold: await page.locator('mat-option b').allInnerTexts()
    };
  }
  console.log(JSON.stringify({results, errors}, null, 1));
  expect(errors.some(e => /Invalid regular expression/.test(e))).toBe(true);
});

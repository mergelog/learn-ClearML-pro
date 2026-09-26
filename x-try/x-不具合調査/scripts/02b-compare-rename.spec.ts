import {expect, Page, test} from '@playwright/test';
import {cdp, commitComposition, dispatchComposingKey, setComposition} from './helpers/ime';
import {INVESTIGATION, loginViaClearmlWeb} from './helpers/real-backend';

/**
 * 比較画面の名前変更（実バックエンド・調査専用プロジェクト）。
 * - 比較画面を URL で直接開いた場合と、タスク一覧から遷移した場合で、保存されるかを比べる（どちらも保存される。不具合ではない）
 * - タスク一覧から遷移した状態で、変換中の Enter でダイアログが閉じるかを見る（02）
 * どのテストも最後にタスク A の名前を戻す。
 */
const I = INVESTIGATION;
const ORIGINAL = '調査タスクA';

function recordUpdates(page: Page): string[] {
  const updates: string[] = [];
  page.on('request', request => {
    if (request.url().endsWith('/tasks.update')) {
      updates.push(request.postData() ?? '');
    }
  });
  return updates;
}

async function closeTipIfShown(page: Page) {
  await page.waitForTimeout(2000);
  const tip = page.locator('mat-dialog-container', {hasText: 'Don\'t show again'});
  if (await tip.count()) {
    await tip.locator('button').first().click();
    await expect(tip).toHaveCount(0);
  }
}

async function openRenameDialog(page: Page) {
  await page.locator('sm-experiment-compare-header button[data-id="entity"]').click();
  const legendA = page.locator('[data-id="experimentLegend"]', {hasText: ORIGINAL});
  await legendA.hover();
  await legendA.locator('button[data-id="closeLegend"]').click({force: true});
  await page.getByRole('menuitem', {name: 'Rename'}).click();
  const input = page.locator('mat-dialog-container input[name="instance-name"]');
  await expect(input).toHaveValue(ORIGINAL);
  await input.focus();
  await input.evaluate((el: HTMLInputElement) => el.setSelectionRange(el.value.length, el.value.length));
  return input;
}

async function restoreName(page: Page) {
  await page.evaluate(async ({id, name}) => {
    await fetch('/service/1/api/tasks.update', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'include',
      body: JSON.stringify({task: id, name})
    });
  }, {id: I.taskA, name: ORIGINAL});
}

async function goCompareFromTasksList(page: Page) {
  await page.goto(`/projects/${I.project}/tasks`);
  await closeTipIfShown(page);
  for (const name of [ORIGINAL, '調査タスクB']) {
    const row = page.locator('sm-experiments-table tr', {hasText: name}).first();
    await row.locator('sm-checkbox-control, .p-checkbox, mat-checkbox, [data-id="selectRow"]').first().click();
  }
  await page.locator('sm-entity-footer button.compare, sm-entity-footer [data-id*="ompare"]').first().click();
  await page.waitForURL(/compare-tasks/);
  await closeTipIfShown(page);
}

test('参考：比較画面を URL で直接開いても、名前変更ダイアログの SAVE で保存される', async ({page}) => {
  await loginViaClearmlWeb(page);
  const updates = recordUpdates(page);
  await page.goto(`/projects/${I.project}/compare-tasks;ids=${I.taskA},${I.taskB}/details`);
  await closeTipIfShown(page);
  await openRenameDialog(page);
  await page.keyboard.type('-direct');
  await page.locator('mat-dialog-container button[data-id="Save"]').click();
  await page.waitForTimeout(2000);
  console.log('[direct] tasks.update bodies:', JSON.stringify(updates));
  console.log('[direct] legend:', JSON.stringify(await page.locator('[data-id="experimentLegend"] .experiment-name').allInnerTexts()));
  await restoreName(page);
  expect(updates.some(body => body.includes('-direct'))).toBe(true);
});

test('タスク一覧から比較画面へ遷移した場合は、SAVE で保存される', async ({page}) => {
  await loginViaClearmlWeb(page);
  const updates = recordUpdates(page);
  await goCompareFromTasksList(page);
  await openRenameDialog(page);
  await page.keyboard.type('-vialist');
  await page.locator('mat-dialog-container button[data-id="Save"]').click();
  await page.waitForTimeout(2000);
  console.log('[via list] tasks.update bodies:', JSON.stringify(updates));
  console.log('[via list] legend:', JSON.stringify(await page.locator('[data-id="experimentLegend"] .experiment-name').allInnerTexts()));
  await restoreName(page);
  expect(updates.some(body => body.includes('-vialist'))).toBe(true);
});

test('02 名前変更ダイアログ：変換中の Enter で、変換前の値のままダイアログが閉じて保存される', async ({page}) => {
  await loginViaClearmlWeb(page);
  const updates = recordUpdates(page);
  await goCompareFromTasksList(page);
  const input = await openRenameDialog(page);
  await page.keyboard.type('-v2');
  const session = await cdp(page);
  await setComposition(session, 'てすと');
  await dispatchComposingKey(input, {key: 'Enter'});
  await commitComposition(session, 'テスト');
  await page.waitForTimeout(2000);
  const dialogOpen = await page.locator('mat-dialog-container').count();
  console.log('[ime] dialog open after composing Enter:', dialogOpen);
  console.log('[ime] tasks.update bodies:', JSON.stringify(updates));
  await restoreName(page);
  expect(dialogOpen).toBe(0);
  expect(updates.some(body => body.includes(`${ORIGINAL}-v2`) && !body.includes('テスト'))).toBe(true);
});

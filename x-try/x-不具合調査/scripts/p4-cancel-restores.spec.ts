import {expect, test} from '@playwright/test';
import {mockClearmlApi} from './helpers/mock-api';

/**
 * フェーズ4（観点の見直し、§3 G の「取消時に元の値へ戻るか」の確認）。
 * EXECUTION の CONTAINER と OUTPUT を書き換えて CANCEL したとき、表示と次の編集の初期値が元の値に戻るか。
 * モック API（CANCEL なので書き込みは出ない）。
 */
test('CONTAINER と OUTPUT：書き換えて CANCEL すると元の値に戻る', async ({page}) => {
  const api = await mockClearmlApi(page);
  await page.goto('/projects/bug-project/tasks/task-a/execution');
  await page.locator('sm-experiment-info-header .experiment-name').waitFor();
  await page.waitForTimeout(1500);
  const results: Record<string, unknown> = {};
  for (const [label, field] of [['CONTAINER', 'imageFieldId'], ['OUTPUT', 'destinationFieldId']] as const) {
    const section = page.locator('sm-editable-section', {has: page.locator(`sm-section-header[label="${label}"]`)});
    await section.scrollIntoViewIfNeeded();
    const before = (await section.innerText()).replace(/\s+/g, ' ');
    await section.hover();
    await section.locator('[data-id="editSectionButton"]').click({force: true});
    const input = section.locator(`[data-id="${field}"]`);
    const original = await input.inputValue();
    await input.fill('取り消す値');
    await section.locator('[data-id="CancelButton"]').click();
    await page.waitForTimeout(500);
    const after = (await section.innerText()).replace(/\s+/g, ' ');
    await section.hover();
    await section.locator('[data-id="editSectionButton"]').click({force: true});
    const reopened = await section.locator(`[data-id="${field}"]`).inputValue();
    await section.locator('[data-id="CancelButton"]').click();
    results[label] = {original, reopened, sameText: before === after, after: after.slice(0, 120)};
    expect(reopened).toBe(original);
    expect(after).toBe(before);
  }
  console.log('取消', JSON.stringify(results), 'writes', api.callsTo('tasks.edit').length);
  expect(api.callsTo('tasks.edit')).toHaveLength(0);
});

import AxeBuilder from '@axe-core/playwright';
import {expect, test} from '@playwright/test';
import {mockClearmlApi} from './helpers/mock-api';

const URL = '/projects/bug-project/tasks/task-a/execution';

test('インライン編集の途中で外側をクリックすると、未保存の値が確認なしに失われる', async ({page}) => {
  const api = await mockClearmlApi(page);
  await page.goto(URL);

  const edit = page.locator('sm-experiment-info-header sm-inline-edit');
  const input = edit.locator('input.inline-edit-input');
  await edit.locator('.value').click();
  await expect(input).toBeFocused();
  await input.fill('Edited but not saved');

  // 編集部品の外側。host の document:click が stopEditing() を呼ぶ。
  // 分割ペインの gutter によるクリック遮断を避け、DOM のイベントとして送る。
  await page.evaluate(() => document.body.dispatchEvent(new MouseEvent('click', {bubbles: true})));
  await expect(edit.locator('.editable-div.edit-mode')).toHaveCount(0);

  await edit.locator('.value').click();
  await expect(input).toHaveValue('Task A');
  expect(api.callsTo('tasks.update')).toEqual([]);
});

test('実験詳細ヘッダーの axe 違反を記録する', async ({page}) => {
  await mockClearmlApi(page);
  await page.goto(URL);
  await page.locator('sm-experiment-info-header').waitFor();

  const results = await new AxeBuilder({page}).include('sm-experiment-info-header').analyze();
  const violations = results.violations.map(violation => ({
    id: violation.id,
    impact: violation.impact,
    targets: violation.nodes.map(node => node.target)
  }));
  console.log(JSON.stringify({violations}));
  expect(violations.map(violation => violation.id).sort()).toEqual([
    'aria-allowed-attr',
    'button-name'
  ]);
});

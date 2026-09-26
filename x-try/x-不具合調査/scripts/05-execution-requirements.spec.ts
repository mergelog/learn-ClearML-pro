import {expect, test} from '@playwright/test';
import {buildTask, mockClearmlApi} from './helpers/mock-api';

/**
 * フェーズ1 05：Execution タブの PYTHON PACKAGES で選んだ requirements（PIP / Original PIP）が、
 * タスクを切り替えたときに保持されるか。
 * カスタマイズ版は formData が falsy のとき選択を 'pip' に戻す。タスク切替時は resetExperimentInfo で
 * formData が一度 null になるため、切替のたびに PIP に戻るはずである。
 */
const requirements = (id: string) => ({pip: `package-${id}==1.0`, orgPip: `original-${id}==0.9`});

test('Original PIP を選んでから別のタスクへ切り替えると、選択が PIP に戻る', async ({page}) => {
  await mockClearmlApi(page, {
    tasks: [
      buildTask('task-a', 'Task A', {script: {repository: 'repo-a', entry_point: 'a.py', working_dir: '.', binary: 'python', branch: 'main', requirements: requirements('a'), diff: ''}}),
      buildTask('task-b', 'Task B', {script: {repository: 'repo-b', entry_point: 'b.py', working_dir: '.', binary: 'python', branch: 'main', requirements: requirements('b'), diff: ''}})
    ]
  });
  await page.goto('/projects/bug-project/tasks/task-a/execution');
  const select = page.locator('mat-select[name="selectedRequirement"]');
  await expect(select).toBeVisible();
  await select.click();
  await page.getByRole('option', {name: 'Original PIP'}).click();
  await expect(select).toContainText('Original PIP');
  await expect(page.getByText('original-a==0.9')).toBeVisible();

  await page.locator('sm-experiments-table').getByText('Task B', {exact: true}).first().click();
  await expect(page).toHaveURL(/\/tasks\/task-b\/execution/);
  await expect(page.getByText(/package-b|original-b/).first()).toBeVisible();
  const selectedAfter = (await select.innerText()).trim();
  const shownPackages = await page.getByText(/package-b==1.0|original-b==0.9/).allInnerTexts();
  console.log(JSON.stringify({selectedAfter, shownPackages}));
  expect(selectedAfter).toBe('PIP');
});

import AxeBuilder from '@axe-core/playwright';
import {expect, test} from '@playwright/test';
import {INVESTIGATION, loginViaClearmlWeb} from './helpers/real-backend';

const I = INVESTIGATION;

async function closeTipIfShown(page) {
  await page.waitForTimeout(1500);
  const tip = page.locator('mat-dialog-container', {hasText: "Don't show again"});
  if (await tip.count()) {
    await tip.locator('button').first().click();
    await expect(tip).toHaveCount(0);
  }
}

test('Hyperparameters：通常の Enter 後も次行の入力欄にフォーカスが移るかを記録する', async ({page}) => {
  await loginViaClearmlWeb(page);
  await page.goto(`/projects/${I.project}/tasks/${I.taskA}/hyper-params/hyper-param/General`);
  await closeTipIfShown(page);

  const section = page.locator('sm-experiment-info-hyper-parameters-form-container sm-editable-section');
  await section.hover();
  await section.locator('[data-id="editSectionButton"]').click({force: true});
  const values = page.locator('sm-experiment-execution-parameters input[data-id="valueField"]');
  await expect(values.first()).toBeVisible();
  await values.first().focus();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(300);

  const active = await page.evaluate(() => {
    const el = document.activeElement as HTMLInputElement | null;
    return {tag: el?.tagName, dataId: el?.getAttribute('data-id'), name: el?.getAttribute('name'), placeholder: el?.getAttribute('placeholder')};
  });
  console.log(JSON.stringify({active}));
  expect(active.dataId).toBe('searchInputField');
  await section.locator('[data-id="CancelButton"]').click();
});

test('実験詳細：タブ遷移後の戻る・進むで URL と表示が一致するかを記録する', async ({page}) => {
  await loginViaClearmlWeb(page);
  const base = `/projects/${I.project}/tasks/${I.taskA}`;
  await page.goto(`${base}/execution`);
  await closeTipIfShown(page);
  await expect(page.locator('sm-experiment-info-execution')).toBeVisible();
  await page.goto(`${base}/hyper-params/hyper-param/General`);
  await expect(page.locator('sm-experiment-info-hyper-parameters-form-container')).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`${I.taskA}/execution(?:\\?|$)`));
  await expect(page.locator('sm-experiment-info-execution')).toBeVisible();
  await page.goForward();
  await expect(page).toHaveURL(new RegExp(`${I.taskA}/hyper-params/hyper-param/General(?:\\?|$)`));
  await expect(page.locator('sm-experiment-info-hyper-parameters-form-container')).toBeVisible();
});

test('存在しないタスク ID：前画面の詳細を残さずエラー画面または空状態になるかを記録する', async ({page}) => {
  await loginViaClearmlWeb(page);
  await page.goto(`/projects/${I.project}/tasks/${I.taskA}/execution`);
  await closeTipIfShown(page);
  await expect(page.locator('sm-experiment-info-execution')).toBeVisible();
  await page.goto(`/projects/${I.project}/tasks/no-such-task-id/execution`);
  await page.waitForTimeout(2000);
  const result = await page.evaluate(() => ({
    title: document.title,
    hasExecution: !!document.querySelector('sm-experiment-info-execution'),
    text: document.body.innerText.slice(0, 1000),
    url: location.href
  }));
  console.log(JSON.stringify(result));
});

test('実験一覧：axe の重大・深刻な違反を記録する', async ({page}) => {
  await loginViaClearmlWeb(page);
  await page.goto(`/projects/${I.project}/tasks`);
  await closeTipIfShown(page);
  const table = page.locator('sm-experiments-table');
  await expect(table).toBeVisible();
  const results = await new AxeBuilder({page}).include('sm-experiments-table').analyze();
  const violations = results.violations
    .filter(violation => violation.impact === 'critical' || violation.impact === 'serious')
    .map(violation => ({
      id: violation.id,
      impact: violation.impact,
      targets: violation.nodes.map(node => node.target)
    }));
  console.log(JSON.stringify({violations}));
});

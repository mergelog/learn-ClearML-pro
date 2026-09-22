import {expect, test} from '@playwright/test';
import {loginViaClearmlWeb, REAL} from './helpers/real-backend';

/**
 * フェーズ2 観点D：タスク一覧のメトリクス列（sm-hyper-param-metric-column）。
 * テンプレートが computed の roundedMetricValues を呼ばずに roundedMetricValues[col.id] と読んでいるため、
 * 丸めた値の全桁を出す展開アイコンとツールチップが出ないかを見る。実バックエンドの既存プロジェクト（読み取りだけ）。
 */
const ACCURACY_VALIDATION = 'm.5d6db9a1dc722586187fc2db530f8388.a617908b172c473cb8e8cda059e55bf0.value.accuracy.validation';

test('丸めて表示されたメトリクスの値に、全桁を出す展開アイコンが出ない', async ({page}) => {
  await loginViaClearmlWeb(page);
  await page.goto(`/projects/${REAL.projectTraining}/tasks?columns=selected&columns=name&columns=status&columns=${ACCURACY_VALIDATION}`);
  await page.waitForTimeout(3000);
  const tip = page.locator('mat-dialog-container', {hasText: 'Don\'t show again'});
  if (await tip.count()) {
    await tip.locator('button').first().click();
  }
  const cells = page.locator('sm-hyper-param-metric-column');
  await expect(cells.first()).toBeVisible();
  const texts = (await cells.allInnerTexts()).slice(0, 6);
  const expandIcons = await page.locator('sm-hyper-param-metric-column .al-ico-line-expand').count();
  const state = await page.evaluate(() => {
    const ng = (window as any).ng;
    const table = ng.getComponent(document.querySelector('sm-experiments-table'));
    const computedValue = table.roundedMetricValues();
    const firstKey = Object.keys(computedValue)[0];
    const column = ng.getComponent(document.querySelector('sm-hyper-param-metric-column'));
    return {
      computedKeys: Object.keys(computedValue),
      roundedTasks: firstKey ? Object.entries(computedValue[firstKey]).filter(([, rounded]) => rounded).length : 0,
      indexedWithoutCall: typeof table.roundedMetricValues[firstKey],
      inputOfCell: column.roundedMetricValue === undefined ? 'undefined' : JSON.stringify(column.roundedMetricValue)
    };
  });
  console.log(JSON.stringify({texts, expandIcons, state}, null, 1));
  expect(state.roundedTasks).toBeGreaterThan(0);
  expect(state.inputOfCell).toBe('undefined');
  expect(expandIcons).toBe(0);
});

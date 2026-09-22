import {expect, test} from '@playwright/test';
import {collectConsole} from './helpers/console-collector';
import {loginViaClearmlWeb, REAL} from './helpers/real-backend';

/** フェーズ2 観点H：旧 compare-experiments の matrix parameter を保ってリダイレクトできるかを確認する。 */
test('旧比較URLの ids がリダイレクトで失われ、詳細画面が例外になる', async ({page}) => {
  test.setTimeout(3 * 60_000);
  await loginViaClearmlWeb(page);
  const entries = collectConsole(page);
  await page.goto(`/projects/${REAL.projectTraining}/compare-experiments;ids=${REAL.taskCompareA},${REAL.taskCompareB}/details`);
  await page.waitForTimeout(4000);

  await expect(page).toHaveURL(new RegExp(`/projects/${REAL.projectTraining}/compare-tasks/details`));
  await expect(page).not.toHaveURL(/;ids=/);
  expect(entries.some(entry => entry.text.includes("Cannot read properties of undefined (reading 'slice')"))).toBe(true);
});

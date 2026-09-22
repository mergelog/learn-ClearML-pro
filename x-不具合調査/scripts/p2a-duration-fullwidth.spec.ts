import {expect, Page, test} from '@playwright/test';
import {cdp, commitComposition, setComposition} from './helpers/ime';
import {loginViaClearmlWeb, REAL} from './helpers/real-backend';

/**
 * フェーズ2 観点A・B：RUN TIME 列のフィルタ（sm-duration-input-list）に、IME をオンにしたまま数字を打つ（全角数字になる）。
 * 実バックエンドの既存プロジェクト（読み取りだけ）。
 */
async function openRunTimeFilter(page: Page) {
  await loginViaClearmlWeb(page);
  await page.goto(`/projects/${REAL.projectTraining}/tasks?columns=selected&columns=name&columns=status&columns=active_duration`);
  await page.waitForTimeout(2500);
  const tip = page.locator('mat-dialog-container', {hasText: 'Don\'t show again'});
  if (await tip.count()) {
    await tip.locator('button').first().click();
  }
  const header = page.locator('th', {hasText: 'RUN TIME'});
  await header.hover();
  await header.locator('[data-id="OpenMenu"] button, button[data-id="OpenMenu"], sm-menu button').first().click({force: true});
  const hours = page.locator('sm-duration-input-list[name="greaterThan"] input').nth(1);
  await expect(hours).toBeVisible();
  return hours;
}

function recordFilters(page: Page): string[] {
  const filters: string[] = [];
  page.on('request', r => {
    if (r.url().endsWith('/tasks.get_all_ex')) {
      filters.push((r.postData() ?? '').match(/"active_duration":\[[^\]]*\]/)?.[0] ?? '(active_duration なし)');
    }
  });
  return filters;
}

for (const [label, digit] of [['半角', '1'], ['全角（IME オン）', '１']] as const) {
  test(`RUN TIME の下限に${label}で「${digit}」時間を入れて Enter`, async ({page}) => {
    const hours = await openRunTimeFilter(page);
    const filters = recordFilters(page);
    await hours.focus();
    if (digit === '1') {
      await page.keyboard.type('1');
    } else {
      const session = await cdp(page);
      await setComposition(session, '１');
      await commitComposition(session, '１');
    }
    const typed = await hours.inputValue();
    await hours.press('Enter');
    await page.waitForTimeout(1500);
    console.log(label, JSON.stringify({typed, after: await hours.inputValue(), filters}));
    if (digit === '１') {
      expect(await hours.inputValue()).toBe('00');
      expect(filters.every(f => !f.includes('3600'))).toBe(true);
    }
  });
}

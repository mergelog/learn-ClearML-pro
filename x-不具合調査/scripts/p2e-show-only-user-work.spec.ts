import {expect, Page, test} from '@playwright/test';
import {mockClearmlApi} from './helpers/mock-api';
import {navigateInApp, recordActions, takeActions} from './helpers/leak';

/**
 * フェーズ2 観点E：ダッシュボードのヘッダーの「My work」（ShowOnlyUserWorkComponent）が、ダッシュボードを離れた後も Store の購読を残し、
 * プロジェクトの一覧で絞り込みの「My Work」を選ぶと、残った購読が URL の filter パラメータを消すこと。
 * モック API（利用者設定をサーバに書き込まないため）。
 */
async function chooseMyWork(page: Page): Promise<{url: string; setFilterByUser: number}> {
  await page.locator('sm-main-pages-header-filter button.cell').click();
  await recordActions(page);
  await takeActions(page);
  await page.locator('[data-id="MyWorkFilterOption"]').click();
  await page.keyboard.press('Escape');
  await page.waitForTimeout(1500);
  const actions = await takeActions(page);
  return {
    url: decodeURIComponent(new URL(page.url()).search),
    setFilterByUser: actions.filter(a => a.endsWith('SET_FILTERED_BY_USER')).length
  };
}

test('ダッシュボードを開いていない場合：My Work を選ぶと URL に filter=myWork:true が残る', async ({page}) => {
  await mockClearmlApi(page);
  await page.goto('/projects');
  await page.locator('sm-main-pages-header-filter').waitFor();
  await page.waitForTimeout(1500);
  const result = await chooseMyWork(page);
  console.log('ダッシュボードなし', JSON.stringify(result));
  expect(result.url).toContain('filter=myWork:true');
});

const VISITS = Number(process.env['DASHBOARD_VISITS'] ?? 1);

test(`ダッシュボードを${VISITS}回開いた後：My Work を選ぶと URL から filter が消える`, async ({page}) => {
  await mockClearmlApi(page);
  await page.goto('/projects');
  await page.locator('sm-main-pages-header-filter').waitFor();
  for (let i = 0; i < VISITS; i++) {
    await navigateInApp(page, '/dashboard');
    await page.locator('sm-header sm-show-only-user-work').waitFor();
    await page.waitForTimeout(1000);
    await navigateInApp(page, '/projects');
    await page.locator('sm-main-pages-header-filter').waitFor();
    await page.waitForTimeout(1000);
  }
  // ヘッダーの ShowOnlyUserWorkComponent はダッシュボードでだけ表示される（userFocus）
  expect(await page.locator('sm-show-only-user-work').count()).toBe(0);
  const result = await chooseMyWork(page);
  console.log(`ダッシュボード${VISITS}回の後`, JSON.stringify(result));
  expect(result.url).not.toContain('filter=');
});

test('ダッシュボードを1回開いた後：タグで絞り込んだ状態で My Work を選ぶと、タグの絞り込みも URL から消える', async ({page}) => {
  await mockClearmlApi(page);
  await page.goto('/projects');
  await page.locator('sm-main-pages-header-filter').waitFor();
  await navigateInApp(page, '/dashboard');
  await page.locator('sm-header sm-show-only-user-work').waitFor();
  await page.waitForTimeout(1000);
  await navigateInApp(page, '/projects?filter=tags:bug-tag');
  await page.locator('sm-main-pages-header-filter').waitFor();
  await page.waitForTimeout(1500);
  const before = decodeURIComponent(new URL(page.url()).search);
  const result = await chooseMyWork(page);
  const storeFilters = await page.evaluate(() => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    let state: any;
    app.store.subscribe((s: unknown) => state = s).unsubscribe();
    return JSON.stringify({tags: state?.rootProjects?.mainPageTagsFilter, myWork: state?.users?.showOnlyUserWork});
  });
  console.log('タグあり', before, '→', JSON.stringify(result), 'Store', storeFilters);
  expect(before).toContain('tags:bug-tag');
  expect(result.url).not.toContain('tags:bug-tag');
  expect(storeFilters).toContain('bug-tag');
});

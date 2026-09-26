import {expect, Page, test} from '@playwright/test';
import {mockClearmlApi, mockProject} from './helpers/mock-api';
import {navigateInApp} from './helpers/leak';

/**
 * フェーズ4（観点の見直し、G・H から回した「レポートの本文の50ms後の遷移」の確認）。
 * report.component.ts の effect() は、レポートの値が変わった50ms後に setTimeout で
 * router.navigate(['.'], {relativeTo: this.route, skipLocationChange: true}) を呼び、この setTimeout を clear しない。
 * レポートが届いてから50ms以内に別の画面へ移ると、移った後にレポートの画面へ引き戻されるかを確かめる。
 * モック API（書き込みなし）。
 */
const company = {id: 'test-company', name: 'Test company'};
const report = {
  id: 'report-1',
  name: '調査用レポート',
  status: 'created',
  company,
  user: {id: 'test-user'},
  comment: '',
  report: '# 見出し\n\n本文',
  tags: [],
  system_tags: ['reports'],
  report_assets: [],
  project: {id: mockProject.id, name: mockProject.name}
};

async function setup(page: Page) {
  return mockClearmlApi(page, {
    overrides: {
      'reports.get_all_ex': () => ({data: {tasks: [report], scroll_id: null}}),
      'reports.get_tags': () => ({data: {tags: [], system_tags: []}})
    }
  });
}

/** レポートが Store に入った瞬間に、同期的に別の画面へ遷移させる */
async function leaveWhenReportArrives(page: Page, target: string): Promise<void> {
  await page.evaluate(to => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    const log: string[] = ((window as any).__navLog = []);
    app.router.events.subscribe((e: any) => {
      if (e.constructor.name === 'NavigationEnd' || e.type === 1) {
        log.push(`${Math.round(performance.now())} end ${e.urlAfterRedirects ?? e.url}`);
      }
    });
    let done = false;
    app.store.subscribe((state: any) => {
      const key = Object.keys(state).find(k => state[k] && 'report' in state[k] && 'editing' in state[k]);
      if (!done && key && state[key].report?.id === 'report-1') {
        done = true;
        log.push(`${Math.round(performance.now())} report arrived, navigate ${to}`);
        app.router.navigateByUrl(to);
      }
    });
  }, target);
}

async function viewState(page: Page) {
  return page.evaluate(() => ({
    location: location.pathname,
    routerUrl: (window as any).ng.getComponent(document.querySelector('sm-app-shell')).router.url,
    reportShown: !!document.querySelector('sm-report'),
    navLog: (window as any).__navLog
  }));
}

test('レポートが届いた直後に一覧へ移ると、50ms後にレポートの画面へ引き戻される', async ({page}) => {
  await setup(page);
  await page.goto(`/reports/${mockProject.id}/reports`);
  await page.locator('sm-reports-page, sm-nested-reports-page, sm-reports-list').first().waitFor();
  await page.waitForTimeout(1500);
  await leaveWhenReportArrives(page, `/reports/${mockProject.id}/reports`);
  await navigateInApp(page, `/reports/${mockProject.id}/${report.id}`);
  await page.waitForTimeout(1500);
  const state = await viewState(page);
  await page.screenshot({path: 'test-results/bug-investigation/p4-report-late-navigate.png'});
  console.log('直後に移る', JSON.stringify(state));
  expect(state.location).toBe(`/reports/${mockProject.id}/reports`);
  expect(state.reportShown).toBe(true);
});

test('対照：レポートが届いて1秒後に一覧へ移ると、一覧のまま', async ({page}) => {
  await setup(page);
  await page.goto(`/reports/${mockProject.id}/reports`);
  await page.locator('sm-reports-page, sm-nested-reports-page, sm-reports-list').first().waitFor();
  await page.waitForTimeout(1500);
  await navigateInApp(page, `/reports/${mockProject.id}/${report.id}`);
  await page.locator('sm-report').waitFor();
  await page.waitForTimeout(1000);
  await navigateInApp(page, `/reports/${mockProject.id}/reports`);
  await page.waitForTimeout(1500);
  const state = await viewState(page);
  console.log('1秒後に移る', JSON.stringify(state));
  expect(state.reportShown).toBe(false);
});

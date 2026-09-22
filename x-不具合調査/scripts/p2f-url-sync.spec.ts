import {test} from '@playwright/test';
import {loginViaClearmlWeb, REAL} from './helpers/real-backend';
import {closeStartupDialogs} from './helpers/leak';

/**
 * フェーズ2 観点F：URL と Store の同期が往復し続けないか。実バックエンド（読み取りだけ）。
 * 並び替え・絞り込み・列を URL に載せた一覧を開き、読み込みの後の8秒間に起きた Router の遷移（NavigationEnd）と URL の変化を数える。
 * 読み込みの直後に URL を正規化する遷移（1〜2回）は往復とみなさない。
 */
const P = REAL.projectTraining;
const ROUTES = [
  `/projects/${P}/tasks`,
  `/projects/${P}/tasks?order=-name&filter=status:completed`,
  `/projects/${P}/tasks?order=-last_update&filter=tags:__$not,x`,
  `/projects/${P}/tasks/${REAL.taskCompareA}/execution?order=name`,
  `/projects/${P}/models?order=-created`,
  `/projects/${P}/compare-tasks;ids=${REAL.taskCompareA},${REAL.taskCompareB}/scalars/graph`,
  `/projects?filter=myWork:true`,
  `/projects/${P}/projects`,
  `/datasets`,
  `/pipelines`,
  `/reports`,
  `/workers-and-queues/queues`,
  `/dashboard`
];

test('読み込み後に遷移が続かない', async ({page}) => {
  test.setTimeout(10 * 60_000);
  await loginViaClearmlWeb(page);
  const results: {route: string; navigations: number; urls: string[]}[] = [];
  for (const route of ROUTES) {
    await page.goto(route);
    await page.waitForTimeout(4000);
    await closeStartupDialogs(page);
    await page.evaluate(() => {
      const w = window as any;
      const app = w.ng.getComponent(document.querySelector('sm-app-shell'));
      w.__navs = [];
      w.__navSub?.unsubscribe();
      w.__navSub = app.router.events.subscribe((e: any) => {
        if (e.constructor?.name === 'NavigationEnd' || e.type === 1) {
          w.__navs.push(e.urlAfterRedirects ?? e.url);
        }
      });
    });
    await page.waitForTimeout(8000);
    const urls: string[] = await page.evaluate(() => (window as any).__navs);
    results.push({route, navigations: urls.length, urls: [...new Set(urls)].slice(0, 3)});
  }
  // 対照：監視中にアプリ内で1回遷移させ、検出が数えることを確かめる
  const control = await page.evaluate(async () => {
    const w = window as any;
    const app = w.ng.getComponent(document.querySelector('sm-app-shell'));
    w.__navs = [];
    await app.router.navigateByUrl('/projects');
    await new Promise(r => setTimeout(r, 1000));
    return w.__navs.length;
  });
  console.log('対照（1回遷移させた）', control);
  for (const r of results) {
    console.log(r.navigations, r.route, JSON.stringify(r.urls));
  }
});

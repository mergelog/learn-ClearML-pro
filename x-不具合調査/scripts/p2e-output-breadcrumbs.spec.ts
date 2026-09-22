import {expect, test} from '@playwright/test';
import {loginViaClearmlWeb, REAL} from './helpers/real-backend';
import {closeStartupDialogs, navigateInApp, recordActions, storeObserverCallbacks, storeObserverCount, takeActions} from './helpers/leak';

/**
 * フェーズ2 観点E：タスクの全画面表示（output）でタブを移るたびに、BaseExperimentOutputComponent が
 * パンくずの設定（setBreadcrumbsOptions）の購読を1つずつ足し、画面を出るまで解除しないこと。
 * 実バックエンド（読み取りだけ）。アプリ内の遷移でタブを移り、Store の購読者のコールバックを数える。
 * 最後に、選択中のプロジェクトを Store に入れ直して（setSelectedProject を同じ値で dispatch）、setBreadcrumbsOptions が何回 dispatch されるかを数える。
 */
const base = `/projects/${REAL.projectBaseline}/tasks/${REAL.taskBaselineV1}/output`;
const TABS = ['execution', 'hyper-params/hyper-param/_all_', 'artifacts', 'general', 'scalars', 'log'];
// base-experiment-output.component.ts の setupBreadcrumbsOptions() が subscribe に渡すコールバックの先頭
const BREADCRUMB_CALLBACK = /^\(\[selectedProject, params\]\) => \{ this\.store\.dispatch\(setBreadcrumbsOptions\(/;

test('全画面表示でタブを移るたびにパンくずの購読が増える', async ({page}) => {
  await loginViaClearmlWeb(page);
  await page.goto(`${base}/execution`);
  await page.locator('sm-experiment-output').waitFor();
  await page.waitForTimeout(4000);
  await closeStartupDialogs(page);

  const countBreadcrumbSubs = async () => {
    const callbacks = await storeObserverCallbacks(page);
    return Object.entries(callbacks).filter(([k]) => BREADCRUMB_CALLBACK.test(k)).reduce((a, [, n]) => a + n, 0);
  };

  const subs = [await countBreadcrumbSubs()];
  const observers = [await storeObserverCount(page)];
  const startCallbacks = await storeObserverCallbacks(page);
  for (let round = 0; round < 2; round++) {
    for (const tab of TABS) {
      await navigateInApp(page, `${base}/${tab}`);
      await page.waitForTimeout(1500);
    }
    subs.push(await countBreadcrumbSubs());
    observers.push(await storeObserverCount(page));
  }

  const endCallbacks = await storeObserverCallbacks(page);
  const grown = Object.entries(endCallbacks)
    .map(([k, n]) => [k, n - (startCallbacks[k] ?? 0)] as const)
    .filter(([, d]) => d > 0);
  console.log('2巡で増えたコールバック', JSON.stringify(grown, null, 1));

  await recordActions(page);
  await takeActions(page);
  await page.evaluate(() => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    let state: any;
    app.store.subscribe((s: unknown) => state = s).unsubscribe();
    const project = state.projects.selectedProject;
    app.store.dispatch({type: '[ROOT_PROJECTS] SET_SELECTED_PROJECT', project: {...project}});
  });
  await page.waitForTimeout(1000);
  const actions = await takeActions(page);
  const breadcrumbDispatches = actions.filter(a => a === '[ROOT_PROJECTS] setBreadcrumbsOptions').length;

  console.log('パンくずの購読数（開始時・1巡後・2巡後）', JSON.stringify(subs), 'Store の購読数', JSON.stringify(observers),
    '選択中のプロジェクトを入れ直したときの setBreadcrumbsOptions', breadcrumbDispatches, JSON.stringify([...new Set(actions)]));
  expect(subs[2]).toBeGreaterThan(subs[0]);
});

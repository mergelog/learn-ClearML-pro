import {expect, test} from '@playwright/test';
import {v5 as uuidv5} from 'uuid';
import {mockClearmlApi} from './helpers/mock-api';
import {navigateInApp, retainedByWeakRef, storeObserverCallbacks, storeObserverCount, trackComponentInstances} from './helpers/leak';

/**
 * フェーズ2 観点E：エンドポイントの詳細（GENERAL）の ServingGeneralInfoComponent が、画面を離れた後も Store の購読を残すこと。
 * takeUntilDestroyed() の後ろに combineLatestWith(store.select(...)) があり、外側が完了しても Store 側の購読が完了しないため。
 * モック API（実バックエンドにエンドポイントが無いため）。エンドポイントの ID は serving.effects.ts と同じく URL から uuidv5 で作る。
 */
const ENDPOINT_URL = 'http://mock-serving/serve/bug-endpoint';
const ENDPOINT_ID = uuidv5(ENDPOINT_URL, uuidv5.URL);
const endpoint = {
  endpoint: 'bug-endpoint',
  url: ENDPOINT_URL,
  model: 'bug-model',
  model_source: 'ClearML',
  model_version: '1',
  preprocess_artifact: '',
  input_type: '',
  input_size: '',
  instances: [],
  uptime_sec: 0,
  requests: 0,
  requests_min: 0,
  latency_ms: 0,
  last_update: '2026-09-22T00:00:00Z'
};
const CALLBACK = /^\(id\) => this\.store\.dispatch\(ServingActions\.getEndpointInfo\(\{ id \}\)\)/;
const CYCLES = 3;

test('エンドポイントの詳細を出入りするたびに Store の購読が残る', async ({page}) => {
  await mockClearmlApi(page, {
    overrides: {
      'serving.get_endpoints': () => ({data: {endpoints: [endpoint]}}),
      'serving.get_endpoint_details': () => ({data: endpoint}),
      'serving.get_loading_instances': () => ({data: {endpoints: []}}),
      'serving.get_endpoint_metrics_history': () => ({data: {computed_interval: 60, total: {dates: [], values: []}, instances: {}}})
    }
  });
  await page.goto('/settings/profile');
  await page.waitForTimeout(3000);

  const leaked = async () => Object.entries(await storeObserverCallbacks(page))
    .filter(([k]) => CALLBACK.test(k)).reduce((a, [, n]) => a + n, 0);
  const counts: {inDetail: number; afterLeave: number; observers: number}[] = [];
  for (let i = 0; i < CYCLES; i++) {
    await navigateInApp(page, `/endpoints/active/${ENDPOINT_ID}/general`);
    await page.locator('sm-serving-general-info').waitFor();
    await page.waitForTimeout(1500);
    const inDetail = await leaked();
    await trackComponentInstances(page, `cycle${i + 1}`);
    await navigateInApp(page, '/settings/profile');
    await page.waitForTimeout(1500);
    counts.push({inDetail, afterLeave: await leaked(), observers: await storeObserverCount(page)});
  }
  const retained = await retainedByWeakRef(page, await page.context().newCDPSession(page));
  const appComponents = Object.fromEntries(Object.entries(retained)
    .map(([label, byName]) => [label, Object.keys(byName).filter(n => n.startsWith('_'))]));
  console.log('ENDPOINT_ID', ENDPOINT_ID, JSON.stringify(counts));
  console.log('GC 後も残るアプリのコンポーネント', JSON.stringify(appComponents));
  expect(await page.locator('sm-serving-general-info').count()).toBe(0);
  expect(counts.map(c => c.afterLeave)).toEqual([1, 2, 3]);
});

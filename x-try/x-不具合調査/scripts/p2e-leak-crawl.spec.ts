import {test} from '@playwright/test';
import {mkdirSync, writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {loginViaClearmlWeb} from './helpers/real-backend';
import {ALL_ROUTES, EXTRA_ROUTES} from './helpers/routes';
import {
  closeStartupDialogs,
  globalListenerCounts,
  navigateInApp,
  retainedByWeakRef,
  storeObserverCallbacks,
  storeObserverCount,
  trackComponentInstances
} from './helpers/leak';

/**
 * フェーズ2 観点E：画面の出入りを繰り返したときに、Store の購読・コンポーネントのインスタンス・window/document のリスナが残るかを調べる。
 * 各ルート A について、中立の画面 B（/settings/profile）とのあいだをアプリ内の遷移で3往復する。
 * - Store の購読数・購読者のコールバック・window/document のリスナ数（zone.js の配列）を B に戻るたびに取り、1往復目と3往復目のあいだで増えたものを報告する
 *   （初回だけ作られるキャッシュや root のサービスの購読を除くため、基準は1往復目にする）
 * - A にいるあいだに画面上のコンポーネントを WeakRef で控え、3往復の後に GC を掛けて、生きていて DOM 上にも無いものを往復ごとに数える
 * 読み取りだけ。LEAK_ROUTES に `|` 区切りでルートを渡すと、そのルートだけを調べる。
 * 結果は test-results/bug-investigation/leak-crawl.json。
 */
const NEUTRAL = '/settings/profile';
const CYCLES = 3;

const diff = (a: Record<string, number>, b: Record<string, number>) =>
  Object.fromEntries(Object.keys({...a, ...b})
    .map(k => [k, (b[k] ?? 0) - (a[k] ?? 0)] as const)
    .filter(([, d]) => d > 0));

test('画面の出入りで購読・インスタンス・リスナが残るか', async ({page}) => {
  test.setTimeout(120 * 60_000);
  const only = process.env['LEAK_ROUTES']?.split('|').filter(Boolean);
  const routes = only ?? [...new Set([...ALL_ROUTES, ...EXTRA_ROUTES])]
    .filter(r => r !== NEUTRAL && !/no-such|\/404$/.test(r));

  await loginViaClearmlWeb(page);
  await page.goto(NEUTRAL);
  await page.waitForTimeout(4000);
  await closeStartupDialogs(page);
  const cdp = await page.context().newCDPSession(page);

  const results: unknown[] = [];
  for (const route of routes) {
    await navigateInApp(page, NEUTRAL);
    await page.waitForTimeout(2000);
    await page.evaluate(() => (window as any).__leakRefs = []);
    const observers: number[] = [await storeObserverCount(page)];
    let firstCallbacks: Record<string, number> = {};
    let firstListeners: Record<string, number> = {};
    let lastCallbacks: Record<string, number> = {};
    let lastListeners: Record<string, number> = {};
    for (let i = 1; i <= CYCLES; i++) {
      await navigateInApp(page, route);
      await page.waitForTimeout(3000);
      await closeStartupDialogs(page);
      await trackComponentInstances(page, `cycle${i}`);
      await navigateInApp(page, NEUTRAL);
      await page.waitForTimeout(2500);
      observers.push(await storeObserverCount(page));
      if (i === 1) {
        firstCallbacks = await storeObserverCallbacks(page);
        firstListeners = await globalListenerCounts(page);
      }
      if (i === CYCLES) {
        lastCallbacks = await storeObserverCallbacks(page);
        lastListeners = await globalListenerCounts(page);
      }
    }
    const retained = await retainedByWeakRef(page, cdp);
    const row = {
      route,
      observers,
      callbackGrowth: diff(firstCallbacks, lastCallbacks),
      listenerGrowth: diff(firstListeners, lastListeners),
      retained
    };
    results.push(row);
    if (observers[CYCLES] > observers[1] || Object.keys(row.listenerGrowth).length || Object.keys(retained).length) {
      console.log(JSON.stringify(row));
    } else {
      console.log('ok', route, JSON.stringify(observers));
    }
  }
  const out = resolve('test-results/bug-investigation');
  mkdirSync(out, {recursive: true});
  writeFileSync(`${out}/leak-crawl${only ? '-partial' : ''}.json`, JSON.stringify(results, null, 2));
});

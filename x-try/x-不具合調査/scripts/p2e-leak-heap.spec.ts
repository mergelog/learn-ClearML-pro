import {test} from '@playwright/test';
import {loginViaClearmlWeb, REAL} from './helpers/real-backend';
import {closeStartupDialogs, navigateInApp, retainedByWeakRef, trackComponentInstances} from './helpers/leak';

/**
 * フェーズ2 観点E：画面を離れても購読が残る画面で、出入りを繰り返すと GC の後の JS ヒープがどれだけ増えるかを測る。
 * モデル詳細の TASKS タブ（model-experiments-table の購読が残る）と、同じモデルの GENERAL タブ（残らない）を、
 * 中立の画面（/settings/profile）とのあいだで10往復ずつし、往復ごとに GC を掛けて Runtime.getHeapUsage の usedSize を取る。
 * あわせて、画面にいるあいだに控えた要素（WeakRef）のうち、画面を離れた後も残っている DOM 要素の数を数える。実バックエンド（読み取りだけ）。
 */
const NEUTRAL = '/settings/profile';
const CYCLES = 10;
const ROUTES = {
  tasksTab: `/projects/${REAL.projectModelComparison}/models/${REAL.model}/tasks`,
  generalTab: `/projects/${REAL.projectModelComparison}/models/${REAL.model}/general`
};

for (const [name, route] of Object.entries(ROUTES)) {
  test(`出入り10回の JS ヒープの増え方：${name}`, async ({page}) => {
    test.setTimeout(10 * 60_000);
    await loginViaClearmlWeb(page);
    await page.goto(NEUTRAL);
    await page.waitForTimeout(4000);
    await closeStartupDialogs(page);
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('HeapProfiler.enable');
    const heap = async () => {
      for (let i = 0; i < 3; i++) {
        await cdp.send('HeapProfiler.collectGarbage');
      }
      return Math.round((await cdp.send('Runtime.getHeapUsage')).usedSize / 1024);
    };

    // 1往復目は遅延読み込みのチャンクやキャッシュが入るため、基準は1往復目の後にする
    const sizes: number[] = [];
    for (let i = 1; i <= CYCLES; i++) {
      await navigateInApp(page, route);
      await page.waitForTimeout(2500);
      if (i === 2) {
        await page.evaluate(() => {
          const w = window as any;
          w.__leakEls = Array.from(document.querySelectorAll('sm-app-shell *')).map(el => new WeakRef(el));
        });
        await trackComponentInstances(page, 'cycle2');
      }
      await navigateInApp(page, NEUTRAL);
      await page.waitForTimeout(2000);
      sizes.push(await heap());
    }
    const detachedEls = await page.evaluate(() => {
      const w = window as any;
      return (w.__leakEls as WeakRef<Element>[]).filter(r => {
        const el = r.deref();
        return el && !el.isConnected;
      }).length;
    });
    const retained = await retainedByWeakRef(page, cdp);
    const perVisit = Math.round((sizes[CYCLES - 1] - sizes[0]) / (CYCLES - 1));
    console.log(name, 'usedSize(KB)', JSON.stringify(sizes), '1往復あたり', perVisit, 'KB',
      '2往復目の要素のうち残っている切り離された要素', detachedEls,
      '2往復目のコンポーネントのうち残っている数', Object.values(retained['cycle2'] ?? {}).reduce((a, b) => a + b, 0));
  });
}

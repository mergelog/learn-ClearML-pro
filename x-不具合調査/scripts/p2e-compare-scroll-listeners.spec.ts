import {expect, test} from '@playwright/test';
import {loginViaClearmlWeb, REAL} from './helpers/real-backend';
import {closeStartupDialogs, elementListenerCounts} from './helpers/leak';

/**
 * フェーズ2 観点E：比較画面の値の表（SCALARS の VALUES など）で、一覧を取り直すたびに表のスクロール領域へ scroll のリスナが1つずつ足され、解除されないこと。
 * 実バックエンド（読み取りだけ）。右上の更新ボタンを押して一覧を取り直し、zone.js が積むリスナの配列の長さで数える（helpers/leak.ts）。
 * あわせて、1回のスクロールでコンポーネントの detectChanges() が何回呼ばれるかを数える。
 */
const ROUTE = `/projects/${REAL.projectTraining}/compare-tasks;ids=${REAL.taskCompareA},${REAL.taskCompareB}/scalars/values`;

// experiment-compare-metric-values.component.ts の startTableScrollListener と同じ要素を選ぶ
const CONTAINER = `(() => {
  const host = document.querySelector('sm-experiment-compare-metric-values');
  return host?.querySelector('.p-scroller') ?? host?.querySelector('.p-datatable-table-container');
})()`;

const REFRESHES = 5;

test('更新のたびに表のスクロール領域の scroll リスナが増える', async ({page}) => {
  await loginViaClearmlWeb(page);
  await page.goto(ROUTE);
  await page.locator('sm-experiment-compare-metric-values').waitFor();
  await page.waitForTimeout(4000);
  await closeStartupDialogs(page);

  await page.evaluate(expr => (window as any).__container = eval(expr), CONTAINER);
  const counts = [(await elementListenerCounts(page, 'window.__container')).scroll ?? 0];
  let getAll = 0;
  page.on('request', req => req.url().includes('tasks.get_all_ex') && getAll++);
  for (let i = 0; i < REFRESHES; i++) {
    await page.locator('sm-refresh-button button.refresh').click();
    await page.waitForTimeout(2000);
    counts.push((await elementListenerCounts(page, 'window.__container')).scroll ?? 0);
  }
  const sameElement = await page.evaluate(expr => eval(expr) === (window as any).__container, CONTAINER);

  // 1回のスクロールで detectChanges() が呼ばれる回数（throttleTime は各購読の最初の1回をすぐ通す）
  const detectChangesPerScroll = await page.evaluate(async () => {
    const w = window as any;
    const inst = w.ng.getComponent(document.querySelector('sm-experiment-compare-metric-values'));
    let calls = 0;
    const orig = inst.changeDetection.detectChanges.bind(inst.changeDetection);
    inst.changeDetection.detectChanges = () => {
      calls++;
      orig();
    };
    w.__container.dispatchEvent(new Event('scroll'));
    await new Promise(r => setTimeout(r, 50));
    inst.changeDetection.detectChanges = orig;
    return calls;
  });

  console.log('scroll listeners', JSON.stringify(counts), 'tasks.get_all_ex', getAll, '同じ要素', sameElement,
    '1回のスクロールでの detectChanges', detectChangesPerScroll);
  expect(sameElement).toBe(true);
  expect(counts.at(-1)).toBe(counts[0] + REFRESHES);
});

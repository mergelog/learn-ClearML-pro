import {expect, Page, test} from '@playwright/test';
import {buildTask, mockClearmlApi} from './helpers/mock-api';

/**
 * フェーズ2 観点F：デバッグ画像の取得（debug-images-effects.ts の fetchDebugImages$）が mergeMap で、応答がどの metric のものかを見ずにタスクごとに上書きするため、
 * metric を続けて切り替えると、遅れて届いた前の metric の画像が、選択欄の metric と食い違ったまま表示されること。
 * 食い違いは、更新ボタンを押すか metric を選び直すまで残る（更新は Store の選択中の metric で取り直すため、更新ボタンで直る）。モック API。
 * 10秒ごとの tick は null を流し、debug-images.component.ts の購読が auto !== null で除くため、この画面の取り直しは更新ボタン（trigger(false)）か、
 * タスクの更新を検知したとき（trigger(true)）に限られる。ここでは更新ボタンを押す。
 */
const METRICS = ['metric-fast', 'metric-slow', 'metric-other'];
const SLOW_MS = 2500;

async function openMetric(page: Page, metric: string) {
  await page.locator('mat-select[data-id="metricDropdownButton"]').click();
  await page.locator('mat-option', {hasText: new RegExp(`^\\s*${metric}\\s*$`)}).click();
}

async function shownVariants(page: Page) {
  return page.evaluate(() => {
    const text = document.querySelector('sm-debug-images')?.textContent ?? '';
    // 画像の URL は存在しないため、読み込みに失敗した欄にファイル名（no-such-{metric}.png）が表示される
    return ['metric-fast', 'metric-slow', 'metric-other'].filter(m => text.includes(`no-such-${m}.png`));
  });
}

test('遅い metric を選んだ直後に別の metric を選ぶと、遅れて届いた前の metric の画像が表示され、更新ボタンを押すまで残る', async ({page}) => {
  test.setTimeout(90_000);
  // 自動更新は実行中のタスクでだけ走る（disableStatusRefreshFilter）
  await mockClearmlApi(page, {
    tasks: [buildTask('task-a', 'Task A', {status: 'in_progress'}), buildTask('task-b', 'Task B')],
    overrides: {
      'events.get_task_metrics': () => ({data: {metrics: [{task: 'task-a', metrics: METRICS}]}})
    }
  });
  const requested: {metric: string; at: number}[] = [];
  const t0 = Date.now();
  // mockClearmlApi より後に登録したルートが先に処理される
  await page.route('**/events.debug_images', async route => {
    const body = route.request().postDataJSON();
    const metric: string = body?.metrics?.[0]?.metric;
    requested.push({metric, at: Date.now() - t0});
    await new Promise(r => setTimeout(r, metric === 'metric-slow' ? SLOW_MS : 100));
    const event = {task: 'task-a', metric, variant: `${metric}-variant`, iter: 1, timestamp: 1, url: `http://127.0.0.1:4200/assets/no-such-${metric}.png`};
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({meta: {result_code: 200}, data: {metrics: [{task: 'task-a', metric, iterations: [{iter: 1, events: [event]}]}], scroll_id: 'scroll'}})
    });
  });

  await page.goto('/projects/bug-project/tasks/task-a/output/debugImages');
  await page.locator('mat-select[data-id="metricDropdownButton"]').waitFor();
  await page.waitForTimeout(1500);
  const initial = await shownVariants(page);

  await openMetric(page, 'metric-slow');
  await page.waitForTimeout(300);
  await openMetric(page, 'metric-other');
  await page.waitForTimeout(500);
  const beforeSlowArrives = await shownVariants(page);
  await page.waitForTimeout(SLOW_MS + 500);
  const afterSlowArrives = await shownVariants(page);
  const selectText = (await page.locator('mat-select[data-id="metricDropdownButton"]').textContent())?.trim();

  // 右上の更新ボタン（refresh.trigger(false) → refreshMetric）
  const n = requested.length;
  await page.locator('sm-refresh-button button').first().click();
  await page.waitForTimeout(2000);
  const refreshRequests = requested.slice(n).map(r => r.metric);
  const afterRefresh = await shownVariants(page);

  console.log('初期表示', JSON.stringify(initial));
  console.log('slow → other と選んだ0.5秒後', JSON.stringify(beforeSlowArrives));
  console.log('slow の応答が届いた後', JSON.stringify(afterSlowArrives), '選択欄', selectText);
  console.log('更新ボタンで要求した metric', JSON.stringify(refreshRequests), '更新後', JSON.stringify(afterRefresh), '選択欄',
    (await page.locator('mat-select[data-id="metricDropdownButton"]').textContent())?.trim());
  console.log('要求', JSON.stringify(requested));

  expect(beforeSlowArrives).toEqual(['metric-other']);
  expect(afterSlowArrives).toEqual(['metric-slow']);
  expect(selectText).toBe('metric-other');
  expect(refreshRequests).toEqual(['metric-other']);
  expect(afterRefresh).toEqual(['metric-other']);
});

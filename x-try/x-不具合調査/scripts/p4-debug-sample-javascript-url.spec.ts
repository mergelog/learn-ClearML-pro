import {expect, test} from '@playwright/test';
import {buildTask, mockClearmlApi} from './helpers/mock-api';

/**
 * フェーズ4（観点の見直し、新しい観点 K「利用者の値を URL・遷移先として扱う箇所」）。
 * デバッグ画像の URL（SDK からイベントとして登録される値）が http で始まらないと、画像の欄はエラー表示（sm-snippet-error）になり、
 * その「Open Image」は blockUserScripts の設定に関係なく window.open(source, '_blank') を呼ぶ。
 * URL が javascript: のとき、開いたウィンドウでアプリと同じオリジンのスクリプトとして実行され、opener（アプリの画面）に触れるかを確かめる。
 * モック API（書き込みなし）。
 */
// opener の location を読めるのは同一オリジンの場合だけ（異なれば SecurityError）
const PAYLOAD = "javascript:window.opener&&(window.opener.__fromDebugSample=window.opener.location.origin+window.opener.location.pathname);'done'";

test('デバッグ画像の URL が javascript: のとき、エラー表示の Open Image でアプリのオリジンのスクリプトとして実行される', async ({page}) => {
  await mockClearmlApi(page, {
    tasks: [buildTask('task-a', 'Task A'), buildTask('task-b', 'Task B')],
    overrides: {
      'events.get_task_metrics': () => ({data: {metrics: [{task: 'task-a', metrics: ['metric']}]}})
    }
  });
  await page.route('**/events.debug_images', route => {
    const event = {task: 'task-a', metric: 'metric', variant: 'variant', iter: 1, timestamp: 1, url: PAYLOAD};
    return route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({meta: {result_code: 200}, data: {metrics: [{task: 'task-a', metric: 'metric', iterations: [{iter: 1, events: [event]}]}], scroll_id: 'scroll'}})
    });
  });

  await page.goto('/projects/bug-project/tasks/task-a/output/debugImages');
  const snippet = page.locator('sm-snippet-error').first();
  await snippet.waitFor({timeout: 15_000});
  const blockUserScripts = await page.evaluate(() => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    let state: any;
    app.store.subscribe((s: unknown) => state = s).unsubscribe();
    return JSON.stringify(Object.values(state).map((s: any) => s?.blockUserScript).filter(v => v !== undefined));
  });
  await snippet.screenshot({path: 'test-results/bug-investigation/p4-debug-sample-javascript-url.png'});

  await page.evaluate(() => {
    const original = window.open;
    (window as any).__openCalls = [];
    window.open = function (...args: Parameters<typeof window.open>) {
      (window as any).__openCalls.push(String(args[0]));
      const w = original.apply(window, args);
      (window as any).__openReturned = w === null ? 'null' : 'window';
      return w;
    };
  });
  const popupPromise = page.waitForEvent('popup', {timeout: 5_000}).catch(() => null);
  // 下部のボタンは hover したときだけ表示される
  await snippet.hover();
  const openImage = snippet.locator('.buttons-footer .clickable-icon').nth(1);
  await expect(openImage).toBeVisible();
  await openImage.click();
  const popup = await popupPromise;
  await page.waitForTimeout(1500);
  const flag = await page.evaluate(() => (window as any).__fromDebugSample);
  const openCalls = await page.evaluate(() => ({calls: (window as any).__openCalls, returned: (window as any).__openReturned}));
  console.log('javascript: の URL', JSON.stringify({blockUserScripts, openCalls, popupUrl: popup?.url(), flag}));
  expect(flag).toBe('http://127.0.0.1:4200/projects/bug-project/tasks/task-a/output/debugImages');
});

test('ブラウザの挙動：target=_blank の a 要素に javascript: の href を代入してクリックすると、アプリのオリジンで実行されるか', async ({page}) => {
  await mockClearmlApi(page);
  await page.goto('/projects/bug-project/tasks');
  await page.waitForTimeout(2000);
  const popupPromise = page.waitForEvent('popup', {timeout: 3_000}).catch(() => null);
  await page.evaluate(() => {
    localStorage.removeItem('__fromAnchor');
    const a = document.createElement('a');
    a.target = '_blank';
    a.href = "javascript:localStorage.setItem('__fromAnchor', String(location.origin) + '|opener=' + String(!!window.opener));'done'";
    a.click();
  });
  const popup = await popupPromise;
  await page.waitForTimeout(1500);
  const stored = await page.evaluate(() => localStorage.getItem('__fromAnchor'));
  console.log('a 要素', JSON.stringify({popup: popup?.url(), stored}));
});


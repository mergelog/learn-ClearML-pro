import {test} from '@playwright/test';
import {collectConsole} from './helpers/console-collector';
import {loginViaClearmlWeb, REAL} from './helpers/real-backend';

/** 任意のルートを開き、失敗したリクエストとコンソールを出す汎用の調査スクリプト。PROBE_ROUTES に | 区切りで渡す。 */
test('probe routes', async ({page}) => {
  test.setTimeout(10 * 60_000);
  await loginViaClearmlWeb(page);
  const entries = collectConsole(page);
  page.on('response', r => { if (r.status() >= 400) console.log('HTTP', r.status(), r.url()); });
  page.on('requestfailed', r => console.log('FAILED', r.url(), r.failure()?.errorText));
  const routes = (process.env.PROBE_ROUTES ?? '/dashboard').split('|').map(r => r.replace(/\{(\w+)\}/g, (_, k) => (REAL as Record<string, string>)[k]));
  for (const route of routes) {
    console.log('== ROUTE', route);
    await page.goto(route);
    await page.waitForTimeout(Number(process.env.PROBE_WAIT ?? 4000));
    console.log('== URL', page.url());
    if (process.env.PROBE_SHOT) {
      await page.screenshot({path: `test-results/bug-investigation/probe-${routes.indexOf(route)}.png`, fullPage: false});
    }
  }
  for (const e of entries) console.log('CONSOLE', e.type, e.url, e.text.split('\n').slice(0, 3).join(' | '));
});

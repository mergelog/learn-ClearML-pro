import {test} from '@playwright/test';
import {mkdirSync, writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {collectConsole} from './helpers/console-collector';
import {loginViaClearmlWeb} from './helpers/real-backend';
import {ALL_ROUTES} from './helpers/routes';

/**
 * フェーズ0：全ルートを実バックエンドで巡回し、コンソールのエラー・警告と
 * 失敗した API 応答を集める。data-catalog・quality-pipeline は対象外（プラン §1.2）。
 */

test('crawl all routes on the real backend', async ({page}) => {
  test.setTimeout(30 * 60_000);
  await loginViaClearmlWeb(page);

  const consoleEntries = collectConsole(page);
  const failedApi: {url: string; route: string; status: number; code?: number; msg?: string}[] = [];
  let currentRoute = '';
  page.on('response', async response => {
    const url = response.url();
    if (!url.includes('/service/')) {
      return;
    }
    let code: number | undefined;
    let msg: string | undefined;
    try {
      const body = await response.json();
      code = body?.meta?.result_code;
      msg = body?.meta?.result_msg;
    } catch {
      // 本文が JSON でない応答は status だけ見る
    }
    if (response.status() >= 400 || (code !== undefined && code !== 200)) {
      failedApi.push({url, route: currentRoute, status: response.status(), code, msg});
    }
  });

  const visited: {route: string; finalUrl: string; title: string}[] = [];
  for (const route of ALL_ROUTES) {
    currentRoute = route;
    await page.goto(route);
    await page.waitForTimeout(4000);
    visited.push({route, finalUrl: page.url(), title: await page.title()});
  }

  // リポジトリ直下から実行する前提（gitignore 済みの test-results に書く）
  const out = resolve('test-results/bug-investigation');
  mkdirSync(out, {recursive: true});
  writeFileSync(`${out}/route-crawl.json`, JSON.stringify({visited, consoleEntries, failedApi}, null, 2));
});

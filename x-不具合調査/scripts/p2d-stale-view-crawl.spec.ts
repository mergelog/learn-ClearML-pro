import {test} from '@playwright/test';
import {mkdirSync, writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {loginViaClearmlWeb} from './helpers/real-backend';
import {ALL_ROUTES, EXTRA_ROUTES} from './helpers/routes';
import {componentsWithoutChangeDetection, findStaleViews, StaleView} from './helpers/stale-view';

/**
 * フェーズ2 観点D：全ルートを実バックエンドで開き、changeDetection の指定が無い109コンポーネントの表示が古いままになっていないかを調べる。
 * 各ルートで読み込みを待ってから、helpers/stale-view.ts の findStaleViews を掛ける。読み取りだけ。
 * 結果は test-results/bug-investigation/stale-view-crawl.json。
 */
test('全ルートで、changeDetection の指定が無いコンポーネントの表示が古いままか', async ({page}) => {
  test.setTimeout(30 * 60_000);
  const names = componentsWithoutChangeDetection();
  console.log('対象のコンポーネント数', names.length);
  await loginViaClearmlWeb(page);

  const results: {route: string; stale: StaleView[]}[] = [];
  for (const route of [...ALL_ROUTES, ...EXTRA_ROUTES]) {
    await page.goto(route);
    await page.waitForTimeout(4000);
    const tip = page.locator('mat-dialog-container', {hasText: 'Don\'t show again'});
    if (await tip.count()) {
      await tip.locator('button').first().click();
      await page.waitForTimeout(500);
    }
    const stale = await findStaleViews(page, names);
    results.push({route, stale});
    if (stale.length) {
      console.log(route, JSON.stringify(stale.map(s => `${s.name}: ${JSON.stringify(s.before.slice(0, 60))} → ${JSON.stringify(s.after.slice(0, 60))}`)));
    }
  }
  const out = resolve('test-results/bug-investigation');
  mkdirSync(out, {recursive: true});
  writeFileSync(`${out}/stale-view-crawl.json`, JSON.stringify(results, null, 2));
});

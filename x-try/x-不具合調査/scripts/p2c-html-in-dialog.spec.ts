import {expect, test} from '@playwright/test';
import {mockClearmlApi} from './helpers/mock-api';

/**
 * フェーズ2 観点C：プロジェクト削除の「Unable to Delete Project」ダイアログは、プロジェクト名をエスケープせずに本文へ埋め込み、
 * confirm-dialog が `[innerHTML]="body | purify"`（DOMPurify）で描画する。
 * 削除の検証 API の応答まで模擬すると大きくなるため、モック API の画面で、開発モードの ng API から
 * ダイアログを開くメソッド（showConfirmDialog）を直接呼び、本文の DOM を調べる。入力経路は資料の再現手順に書く。
 */
// プロジェクト名は `/` を階層の区切りに使うため、`/` を含まない名前にする（`</b>` のような閉じタグは書けない）
const NAME = 'score<best の比較 <i>斜体 <img src="x" onerror="window.__xss=1"> & 記号';

test('プロジェクト名の HTML が本文で解釈され、`<` から `>` までの文字が消える（スクリプトは DOMPurify が除く）', async ({page}) => {
  await mockClearmlApi(page);
  await page.goto('/projects');
  await page.waitForTimeout(2000);
  await page.evaluate(name => {
    const ng = (window as any).ng;
    const comp = ng.getComponent(document.querySelector('sm-projects-page'));
    const stats = {total: 1, archived: 0, unarchived: 1};
    comp.showConfirmDialog({
      project: {id: 'p-html', name},
      experiments: stats, models: {total: 0, archived: 0, unarchived: 0}, reports: {total: 0, archived: 0, unarchived: 0},
      pipelines: {total: 0, unarchived: 0}, datasets: {total: 0, unarchived: 0}
    });
  }, NAME);
  const body = page.locator('sm-confirm-dialog .body');
  await expect(body).toBeVisible();
  const result = await body.evaluate(el => ({
    text: (el as HTMLElement).innerText.split('\n')[0],
    boldTexts: Array.from(el.querySelectorAll('b')).map(b => b.textContent),
    italic: Array.from(el.querySelectorAll('i')).map(i => i.textContent),
    unknownTags: Array.from(el.querySelectorAll('best')).length,
    images: el.querySelectorAll('img').length,
    onerrorKept: Array.from(el.querySelectorAll('img')).some(img => img.hasAttribute('onerror')),
    xss: (window as any).__xss ?? 0
  }));
  console.log(JSON.stringify(result, null, 1));
  expect(result.text).not.toContain('の比較');
  // `<best の比較 <i>` までが1つの（未知の）タグとして解釈されて消えるため、斜体の要素も作られない
  expect(result.images).toBe(1);
  expect(result.onerrorKept).toBe(false);
  expect(result.xss).toBe(0);
});

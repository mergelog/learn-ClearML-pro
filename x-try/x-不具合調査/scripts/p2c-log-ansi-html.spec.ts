import {expect, test} from '@playwright/test';
import {mockClearmlApi} from './helpers/mock-api';

/**
 * フェーズ2 観点C：CONSOLE（ログ）の行のうち ANSI の色コードを含む行は、ansi-to-html（escapeXML: false）で HTML にしてから
 * `[innerHTML]="line.entry | purify"` で描画する。ログ本文の `<` が HTML として解釈されるかを見る。
 * 色コードを含まない行は補間（{{ }}）で描画するため、比較のために同じ本文の行を並べる。モック API。
 */
const ESC = String.fromCharCode(27);
const lines = [
  `${ESC}[31m  File "train.py", line 3, in <module>${ESC}[0m`,
  '  File "train.py", line 3, in <module>',
  `${ESC}[33mloss<best_loss: 0.12 (improved)${ESC}[0m`,
  `${ESC}[36mpreview: <img src="x" onerror="window.__xss=1"> done${ESC}[0m`
];

test('色コードを含むログ行で、`<module>` などの `<` で始まる語が消え、img 要素が作られる', async ({page}) => {
  await mockClearmlApi(page, {
    overrides: {
      'events.get_task_log': () => ({data: {
        events: lines.map((msg, i) => ({timestamp: 1758500000000 + i * 1000, msg, type: 'log', task: 'task-a', worker: 'w'})).reverse(),
        total: lines.length, returned: lines.length
      }})
    }
  });
  await page.goto('/projects/bug-project/tasks/task-a/output/log');
  const entries = page.locator('[data-id="logLine"] .entry');
  await expect(entries.first()).toBeVisible();
  await page.waitForTimeout(500);
  const shown = await entries.allInnerTexts();
  const images = await page.locator('[data-id="logLine"] .entry img').count();
  const xss = await page.evaluate(() => (window as any).__xss ?? 0);
  console.log(JSON.stringify({shown, images, xss}, null, 1));
  // 色なしの行だけに `<module>` が残る
  expect(shown.filter(t => t.includes('<module>'))).toHaveLength(1);
  // `<best_loss: 0.12 (improved)` は1つの（未知の）タグとして解釈され、`loss` だけが残る
  expect(shown).toContain('loss');
  // img 要素は作られるが、onerror は DOMPurify が除く
  expect(images).toBe(1);
  expect(xss).toBe(0);
});

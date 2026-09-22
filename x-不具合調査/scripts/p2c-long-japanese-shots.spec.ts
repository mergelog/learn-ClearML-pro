import {Page, test} from '@playwright/test';
import {mkdirSync} from 'node:fs';
import {INVESTIGATION, loginViaClearmlWeb} from './helpers/real-backend';

/**
 * フェーズ2 観点C：空白を含まない長い日本語名・絵文字・HTML の記号を含む名前の表示を、主要な画面で撮る（読み取りだけ）。
 * 出力は test-results/bug-investigation/p2c-shots/。はみ出し・省略記号・重なりを目で確かめ、あわせて
 * 名前の要素が親からはみ出していないか（scrollWidth > clientWidth で ellipsis が効いていない要素）を数える。
 */
const I = INVESTIGATION;
const OUT = 'test-results/bug-investigation/p2c-shots';

async function prepare(page: Page, url: string) {
  await page.goto(url);
  await page.waitForTimeout(3000);
  const tip = page.locator('mat-dialog-container', {hasText: 'Don\'t show again'});
  if (await tip.count()) {
    await tip.locator('button').first().click();
    await page.waitForTimeout(500);
  }
}

async function overflowReport(page: Page) {
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const out: string[] = [];
    for (const el of Array.from(document.querySelectorAll('body *')) as HTMLElement[]) {
      const text = el.childNodes.length === 1 && el.firstChild?.nodeType === 3 ? el.textContent?.trim() ?? '' : '';
      if (!/とても長い日本語/.test(text)) {
        continue;
      }
      const r = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      const clipped = el.scrollWidth > el.clientWidth + 1;
      const ellipsis = style.textOverflow === 'ellipsis' && style.overflow !== 'visible';
      if (r.width === 0) {
        continue;
      }
      if (r.right > vw + 1 || (clipped && !ellipsis)) {
        out.push(`${el.tagName.toLowerCase()}.${el.className.toString().slice(0, 40)} right=${Math.round(r.right)} vw=${vw} clipped=${clipped} ellipsis=${ellipsis} ws=${style.whiteSpace}`);
      }
    }
    return out;
  });
}

const pages: [string, string][] = [
  ['01-tasks-table', `/projects/${I.project}/tasks`],
  ['02-task-detail-panel', `/projects/${I.project}/tasks/${I.taskLongJapanese}/execution`],
  ['03-task-detail-full', `/projects/${I.project}/tasks/${I.taskLongJapanese}/output/execution`],
  ['04-compare', `/projects/${I.project}/compare-tasks;ids=${I.taskLongJapanese},${I.taskEmoji}/details`],
  ['05-projects', '/projects'],
  ['06-dashboard', '/dashboard']
];

for (const [name, url] of pages) {
  test(`撮影：${name}`, async ({page}) => {
    mkdirSync(OUT, {recursive: true});
    await page.setViewportSize({width: 1366, height: 800});
    await loginViaClearmlWeb(page);
    await prepare(page, url);
    await page.screenshot({path: `${OUT}/${name}.png`});
    console.log(name, JSON.stringify(await overflowReport(page)));
  });
}

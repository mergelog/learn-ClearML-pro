import {expect, Page, test} from '@playwright/test';
import {mockClearmlApi} from './helpers/mock-api';
import {cdp, setComposition} from './helpers/ime';

/**
 * フェーズ2 観点A・J：タグ追加メニュー（sm-tags-menu）の (keyup.arrowDown)。
 * - 入力欄で↓を押すと、Create ボタンまたはタグの一覧へフォーカスが移るはずだが、TypeError で移らない
 * - 参考：変換中に↓で候補を選んだとき（keyup は元のキーで届く）の挙動。現状はフォーカスが移らないため、IME の操作は妨げられない
 * モック API。
 */
async function openTagsMenu(page: Page, errors: string[]) {
  page.on('console', m => m.type() === 'error' && errors.push(m.text().slice(0, 200)));
  page.on('pageerror', e => errors.push(e.message.slice(0, 200)));
  const api = await mockClearmlApi(page, {overrides: {
    'projects.get_task_tags': () => ({data: {tags: ['alpha', 'beta'], system_tags: []}})
  }});
  await page.goto('/projects/bug-project/tasks/task-a/execution');
  await page.locator('sm-experiment-info-header .middle-col').hover();
  await page.locator('sm-experiment-info-header sm-user-tag[data-id="addTag"]').click({force: true});
  const input = page.locator('.tags-menu input.filter');
  await expect(input).toBeFocused();
  return {api, input};
}

function activeElement(page: Page) {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement;
    return `${el?.tagName} ${el?.innerText?.trim().slice(0, 60) ?? ''}`;
  });
}

test('入力欄で↓を押しても、Create ボタン・タグの一覧へ移れず、TypeError が出る', async ({page}) => {
  const errors: string[] = [];
  const {input} = await openTagsMenu(page, errors);
  const results: string[] = [];
  // 空（タグの一覧だけ）、新しいタグ名（Create ボタンだけ）、既存タグに一致（Create ボタンとタグ）
  for (const text of ['', 'v2-', 'al']) {
    await input.fill(text);
    await page.waitForTimeout(300);
    await input.focus();
    await page.keyboard.press('ArrowDown');
    await page.waitForTimeout(300);
    const buttons = await page.locator('.tags-menu .buttons-container button').allInnerTexts();
    results.push(`[${text}] focus=${await activeElement(page)} buttons=${JSON.stringify(buttons.slice(0, 3))}`);
  }
  console.log(JSON.stringify({results, errors}, null, 1));
  expect(results.every(r => r.includes('focus=INPUT'))).toBe(true);
  expect(errors.filter(e => e.includes('TypeError'))).toHaveLength(3);
});

test('参考：変換中に↓で候補を選んだとき（keydown は 229、keyup は ArrowDown）', async ({page}) => {
  const errors: string[] = [];
  const {input} = await openTagsMenu(page, errors);
  await page.keyboard.type('v2-');
  const session = await cdp(page);
  await setComposition(session, 'じっけん');
  await page.waitForTimeout(100);
  await input.evaluate(el => {
    el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Process', code: 'ArrowDown', keyCode: 229, which: 229, isComposing: true, bubbles: true, cancelable: true}));
    el.dispatchEvent(new KeyboardEvent('keyup', {key: 'ArrowDown', code: 'ArrowDown', keyCode: 40, which: 40, isComposing: true, bubbles: true, cancelable: true}));
  });
  await page.waitForTimeout(300);
  console.log(JSON.stringify({focus: await activeElement(page), value: await input.inputValue(), errors}));
});

test('参考：Tab でのフォーカスの移動先（回避手段になるか）', async ({page}) => {
  const errors: string[] = [];
  const {input} = await openTagsMenu(page, errors);
  const results: string[] = [];
  for (const text of ['', 'al']) {
    await input.fill(text);
    await page.waitForTimeout(300);
    await input.focus();
    const trail: string[] = [];
    for (let i = 0; i < 4; i++) {
      await page.keyboard.press('Tab');
      await page.waitForTimeout(150);
      trail.push(await activeElement(page));
    }
    results.push(`[${text}] ${JSON.stringify(trail)} menuOpen=${await page.locator('.tags-menu').count()}`);
    if (!(await page.locator('.tags-menu').count())) {
      break;
    }
  }
  console.log(JSON.stringify({results, errors}, null, 1));
});

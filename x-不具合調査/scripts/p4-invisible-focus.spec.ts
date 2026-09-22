import {test} from '@playwright/test';
import {writeFileSync} from 'node:fs';
import {INVESTIGATION, loginViaClearmlWeb, REAL} from './helpers/real-backend';
import {closeStartupDialogs} from './helpers/leak';

/**
 * フェーズ4（観点の見直し、§3 J の「hover でしか出ないボタン」の確認）。
 * 主要な画面で Tab を順に押し、フォーカスが当たった要素が見えないもの（祖先を含めた opacity の積が0.05未満、
 * visibility: hidden、大きさ0）を集める。hover でだけ opacity を1にするボタンは Tab で届くが、フォーカスしても見えない。
 * 実バックエンドを読み取るだけ（クリックも入力もしない）。
 */
const I = INVESTIGATION;
const ROUTES = (process.env.FOCUS_ROUTES?.split('|')) ?? [
  `/projects/${I.project}/tasks/${I.taskA}/execution`,
  `/projects/${I.project}/tasks/${I.taskA}/hyper-params/hyper-param/General`,
  `/projects/${I.project}/tasks/${I.taskA}/general`,
  `/projects/${I.project}/tasks`,
  `/projects/${REAL.projectTraining}/compare-tasks;ids=${REAL.taskCompareA},${REAL.taskCompareB}/details`,
  `/projects/${REAL.projectModelComparison}/models/${REAL.model}/general`,
  '/projects',
  '/workers-and-queues/queues',
  '/settings/workspace-configuration'
];
const MAX_TABS = Number(process.env.FOCUS_MAX_TABS ?? 160);

interface FocusInfo {
  key: string;
  label: string;
  opacity: number;
  hidden: boolean;
  zeroSize: boolean;
}

test('Tab で見えない要素にフォーカスが当たる箇所', async ({page}) => {
  test.setTimeout(20 * 60_000);
  await loginViaClearmlWeb(page);
  const result: Record<string, FocusInfo[]> = {};
  for (const route of ROUTES) {
    await page.goto(route);
    await page.waitForTimeout(4000);
    await closeStartupDialogs(page);
    await page.waitForTimeout(500);
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
    const seen = new Map<string, FocusInfo>();
    let firstKey: string | null = null;
    for (let i = 0; i < MAX_TABS; i++) {
      await page.keyboard.press('Tab');
      const info = await page.evaluate((): FocusInfo | null => {
        const el = document.activeElement as HTMLElement | null;
        if (!el || el === document.body) {
          return null;
        }
        let opacity = 1;
        let hidden = false;
        for (let node: HTMLElement | null = el; node; node = node.parentElement) {
          const style = getComputedStyle(node);
          opacity *= Number(style.opacity);
          if (style.visibility === 'hidden') {
            hidden = true;
          }
        }
        const rect = el.getBoundingClientRect();
        const host = el.closest('[class*="sm-"], sm-editable-section, sm-inline-edit') as HTMLElement | null;
        const path: string[] = [];
        for (let node: Element | null = el; node && path.length < 4; node = node.parentElement) {
          if (node.tagName.includes('-')) {
            path.push(node.tagName.toLowerCase());
          }
        }
        const label = (el.getAttribute('aria-label') || el.getAttribute('data-id') || el.getAttribute('mattooltip') ||
          el.textContent?.trim().replace(/\s+/g, ' ').slice(0, 40) || el.className?.toString().slice(0, 40) || '').toString();
        return {
          key: `${el.tagName.toLowerCase()}#${el.id}|${el.getAttribute('data-id') ?? ''}|${path.join('<')}|${label}`,
          label: `${el.tagName.toLowerCase()} ${label} @ ${path.join(' < ')}${host ? '' : ''}`,
          opacity: Math.round(opacity * 100) / 100,
          hidden,
          zeroSize: rect.width === 0 || rect.height === 0
        };
      });
      if (!info) {
        continue;
      }
      if (info.key === firstKey) {
        break;
      }
      firstKey ??= info.key;
      if (info.opacity < 0.05 || info.hidden || info.zeroSize) {
        seen.set(info.key, info);
      }
    }
    result[route] = [...seen.values()];
    console.log('== ROUTE', route);
    for (const item of result[route]) {
      console.log('  INVISIBLE', JSON.stringify({label: item.label, opacity: item.opacity, hidden: item.hidden, zeroSize: item.zeroSize}));
    }
  }
  writeFileSync('test-results/bug-investigation/invisible-focus.json', JSON.stringify(result, null, 2));
});

test('EDIT ボタン：Tab でフォーカスしても見えず、Enter で編集モードに入る（保存せず CANCEL で抜ける）', async ({page}) => {
  test.setTimeout(3 * 60_000);
  await loginViaClearmlWeb(page);
  const writes: string[] = [];
  page.on('request', r => { if (/tasks\.(edit|update)/.test(r.url())) writes.push(r.url()); });
  await page.goto(`/projects/${I.project}/tasks/${I.taskA}/execution`);
  await page.waitForTimeout(4000);
  await closeStartupDialogs(page);
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  let found = false;
  for (let i = 0; i < 120 && !found; i++) {
    await page.keyboard.press('Tab');
    found = await page.evaluate(() => document.activeElement?.getAttribute('data-id') === 'editSectionButton');
  }
  const sectionIndex = await page.evaluate(() => [...document.querySelectorAll('sm-editable-section')].indexOf(document.activeElement!.closest('sm-editable-section')!));
  const section = page.locator('sm-editable-section').nth(sectionIndex);
  await page.mouse.move(5, 700);
  await section.screenshot({path: 'test-results/bug-investigation/p4-invisible-focus-edit-button.png'});
  const opacity = await page.evaluate(() => {
    let o = 1;
    for (let n = document.activeElement as HTMLElement | null; n; n = n.parentElement) o *= Number(getComputedStyle(n).opacity);
    return o;
  });
  await page.keyboard.press('Enter');
  await page.waitForTimeout(800);
  const inEdit = await section.locator('[data-id="SaveButton"]').isVisible();
  await section.screenshot({path: 'test-results/bug-investigation/p4-invisible-focus-edit-mode.png'});
  await section.locator('[data-id="CancelButton"]').click();
  await page.waitForTimeout(800);
  console.log('EDIT', JSON.stringify({found, opacity, inEdit, writes}));
});

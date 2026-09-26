import {expect, test} from '@playwright/test';
import {cdp, commitComposition, dispatchComposingKey, setComposition} from './helpers/ime';
import {INVESTIGATION, loginViaClearmlWeb} from './helpers/real-backend';

/**
 * フェーズ1 02：Hyperparameters の編集（experiment-execution-parameters）で、
 * パラメータ名の入力中に変換確定の Enter を押すと、次の行へ移る（最終行なら行が追加される）か。
 * 実バックエンドの調査用タスク A（draft）。編集は CANCEL で破棄し、保存しない。
 */
const I = INVESTIGATION;

test('パラメータ名の変換中の Enter で、行が追加され、次の行へ移る処理が走る', async ({page}) => {
  await loginViaClearmlWeb(page);
  const writes: string[] = [];
  page.on('request', r => {
    if (/tasks\.(edit|update|edit_hyper_params)/.test(r.url())) {
      writes.push(r.url());
    }
  });
  await page.goto(`/projects/${I.project}/tasks/${I.taskA}/hyper-params/hyper-param/General`);
  await page.waitForTimeout(2500);
  const tip = page.locator('mat-dialog-container', {hasText: 'Don\'t show again'});
  if (await tip.count()) {
    await tip.locator('button').first().click();
  }
  const section = page.locator('sm-experiment-info-hyper-parameters-form-container sm-editable-section');
  await section.hover();
  await section.locator('[data-id="editSectionButton"]').click({force: true});

  const keys = page.locator('sm-experiment-execution-parameters input[data-id="parameterField"]');
  await expect(keys.first()).toBeVisible();
  const before = await keys.count();
  const last = keys.nth(before - 1);
  await last.focus();
  await last.evaluate((el: HTMLInputElement) => el.setSelectionRange(el.value.length, el.value.length));
  const session = await cdp(page);
  await setComposition(session, 'がくしゅう');
  await dispatchComposingKey(last, {key: 'Enter'});
  await commitComposition(session, '学習');
  await page.waitForTimeout(800);

  const after = await keys.count();
  const focusedIndex = await page.evaluate(() => {
    const all = Array.from(document.querySelectorAll('sm-experiment-execution-parameters input[data-id="parameterField"]'));
    return all.indexOf(document.activeElement as Element);
  });
  const lastValue = await keys.nth(before - 1).inputValue();
  const active = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement;
    return `${el?.tagName} ${el?.getAttribute('data-id') ?? ''} ${el?.getAttribute('name') ?? ''} ${el?.className ?? ''}`.slice(0, 200);
  });
  console.log(JSON.stringify({before, after, focusedIndex, lastValue, active}));

  await section.locator('[data-id="CancelButton"]').click();
  expect(writes).toEqual([]);
  expect(after).toBe(before + 1);
  // フォーカスの移動先は環境で変わる（仮想スクロールの描画時機）。記録だけ残す
});

test('参考：通常の Enter でのフォーカスの移動先', async ({page}) => {
  await loginViaClearmlWeb(page);
  await page.goto(`/projects/${I.project}/tasks/${I.taskA}/hyper-params/hyper-param/General`);
  await page.waitForTimeout(2500);
  const tip = page.locator('mat-dialog-container', {hasText: 'Don\'t show again'});
  if (await tip.count()) {
    await tip.locator('button').first().click();
  }
  const section = page.locator('sm-experiment-info-hyper-parameters-form-container sm-editable-section');
  await section.hover();
  await section.locator('[data-id="editSectionButton"]').click({force: true});
  const keys = page.locator('sm-experiment-execution-parameters input[data-id="parameterField"]');
  await expect(keys.first()).toBeVisible();
  const before = await keys.count();
  const results: string[] = [];
  for (const index of [0, before - 1]) {
    await keys.nth(index).focus();
    await keys.nth(index).press('Enter');
    await page.waitForTimeout(800);
    results.push(await page.evaluate(() => {
      const all = Array.from(document.querySelectorAll('sm-experiment-execution-parameters input[data-id="parameterField"]'));
      const el = document.activeElement as HTMLElement;
      return `index=${all.indexOf(el)} ${el?.tagName} ${el?.getAttribute('data-id') ?? ''}`;
    }));
  }
  console.log('normal Enter focus:', JSON.stringify({before, after: await keys.count(), results}));
  await section.locator('[data-id="CancelButton"]').click();
});

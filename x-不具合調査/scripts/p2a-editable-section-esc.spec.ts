import {expect, Locator, Page, test} from '@playwright/test';
import {cdp, dispatchComposingKey, setComposition} from './helpers/ime';
import {INVESTIGATION, loginViaClearmlWeb} from './helpers/real-backend';

/**
 * フェーズ2 観点A：編集セクション（sm-editable-section）の document:keydown の Esc。
 * 実バックエンドの調査用タスク A（draft）。どのテストも保存せず、書き込みが無いことを確かめる。
 * - Hyperparameters の編集中に、変換取消の Esc でセクションの編集全体が取り消されるか
 * - Execution の SOURCE CODE の編集中に、mat-select の一覧を Esc で閉じると、セクションの編集全体が取り消されるか
 */
const I = INVESTIGATION;

async function closeTipIfShown(page: Page) {
  await page.waitForTimeout(2500);
  const tip = page.locator('mat-dialog-container', {hasText: 'Don\'t show again'});
  if (await tip.count()) {
    await tip.locator('button').first().click();
    await expect(tip).toHaveCount(0);
  }
}

function recordWrites(page: Page): string[] {
  const writes: string[] = [];
  page.on('request', r => {
    if (/tasks\.(edit|update|edit_hyper_params|delete_hyper_params)/.test(r.url())) {
      writes.push(r.url());
    }
  });
  return writes;
}

async function startEdit(section: Locator) {
  await section.hover();
  await section.locator('[data-id="editSectionButton"]').click({force: true});
  await expect(section.locator('[data-id="SaveButton"]')).toBeVisible();
}

test('Hyperparameters：変換取消の Esc で、ほかの行で入力済みの変更ごと編集が取り消される', async ({page}) => {
  await loginViaClearmlWeb(page);
  const writes = recordWrites(page);
  await page.goto(`/projects/${I.project}/tasks/${I.taskA}/hyper-params/hyper-param/General`);
  await closeTipIfShown(page);
  const section = page.locator('sm-experiment-info-hyper-parameters-form-container sm-editable-section');
  await startEdit(section);

  const values = page.locator('sm-experiment-execution-parameters input[data-id="valueField"]');
  const original = await values.first().inputValue();
  // 1行目の値を書き換えてから、2行目の値で日本語を変換中に Esc を押す
  await values.first().click();
  await page.keyboard.press('End');
  await page.keyboard.type('-edited');
  const second = values.nth(1);
  await second.click();
  await page.keyboard.press('End');
  const session = await cdp(page);
  await setComposition(session, 'がくしゅう');
  await dispatchComposingKey(second, {key: 'Escape'});
  await page.waitForTimeout(800);

  const inEditMode = await section.locator('[data-id="SaveButton"]').isVisible();
  const firstValueAfter = await values.first().inputValue({timeout: 1000}).catch(() => '(入力欄なし)');
  const firstValueText = await section.innerText();
  console.log(JSON.stringify({original, inEditMode, firstValueAfter, containsEdited: firstValueText.includes('-edited'), writes}));
  if (inEditMode) {
    await section.locator('[data-id="CancelButton"]').click();
  }
  expect(writes).toEqual([]);
  expect(inEditMode).toBe(false);
  expect(firstValueText.includes('-edited')).toBe(false);
});

test('Execution の SOURCE CODE：Type の一覧を Esc で閉じると、入力済みの変更ごと編集が取り消される', async ({page}) => {
  await loginViaClearmlWeb(page);
  const writes = recordWrites(page);
  await page.goto(`/projects/${I.project}/tasks/${I.taskA}/execution`);
  await closeTipIfShown(page);
  const section = page.locator('sm-editable-section', {has: page.locator('sm-section-header[label="SOURCE CODE"]')});
  await startEdit(section);

  const scriptPath = section.locator('input[data-id="scriptPathField"]');
  await scriptPath.fill('train_edited.py');
  await section.locator('mat-select[data-id="commitDropdownButton"]').click();
  await expect(page.locator('mat-option').first()).toBeVisible();
  await page.keyboard.press('Escape');
  await page.waitForTimeout(800);

  const panelOpen = await page.locator('mat-option').count();
  const inEditMode = await section.locator('[data-id="SaveButton"]').isVisible();
  const sectionText = await section.innerText();
  console.log(JSON.stringify({panelOpen, inEditMode, containsEdited: sectionText.includes('train_edited.py'), writes}));
  if (inEditMode) {
    await section.locator('[data-id="CancelButton"]').click();
  }
  expect(writes).toEqual([]);
  expect(panelOpen).toBe(0);
  expect(inEditMode).toBe(false);
});

test('参考：変換中でない通常の Esc では、編集が取り消される（設計どおりの挙動）', async ({page}) => {
  await loginViaClearmlWeb(page);
  await page.goto(`/projects/${I.project}/tasks/${I.taskA}/hyper-params/hyper-param/General`);
  await closeTipIfShown(page);
  const section = page.locator('sm-experiment-info-hyper-parameters-form-container sm-editable-section');
  await startEdit(section);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
  expect(await section.locator('[data-id="SaveButton"]').isVisible()).toBe(false);
});

import {expect, Locator, Page, test} from '@playwright/test';
import {mockClearmlApi, MockHandle} from './helpers/mock-api';
import {cdp, commitComposition, dispatchComposingKey, setComposition} from './helpers/ime';

/**
 * フェーズ1：実験名のインライン編集（詳細ヘッダー）の既出不具合を、モック API で再現する。
 * 対象：01 変換確定 Enter / 03 変換取消 Esc / 04 通常 Enter の二重保存 / 06 長さの下限 / 08 保存失敗後の食い違い
 */

const URL = '/projects/bug-project/tasks/task-a/execution';

function nameEdit(page: Page) {
  const root = page.locator('sm-experiment-info-header sm-inline-edit');
  return {
    root,
    input: root.locator('input.inline-edit-input'),
    approve: root.locator('button.inline-edit-approve'),
    editing: root.locator('.editable-div.edit-mode'),
    label: page.locator('sm-experiment-info-header .experiment-name span')
  };
}

async function openNameEdit(page: Page) {
  const edit = nameEdit(page);
  await edit.root.locator('.value').click();
  await expect(edit.editing).toHaveCount(1);
  await expect(edit.input).toBeFocused();
  return edit;
}

async function lastUpdateNames(api: MockHandle) {
  return api.callsTo('tasks.update').map(c => (c.body as {name?: string}).name);
}

async function selectAll(input: Locator) {
  await input.evaluate((el: HTMLInputElement) => el.setSelectionRange(0, el.value.length));
}

test.describe('01 変換確定の Enter', () => {
  test('元の名前を選択して上書き変換中に Enter → 編集が取り消される', async ({page}) => {
    const api = await mockClearmlApi(page);
    await page.goto(URL);
    const edit = await openNameEdit(page);
    const session = await cdp(page);

    await selectAll(edit.input);
    await setComposition(session, 'じっけん');
    await expect(edit.input).toHaveValue('じっけん');
    // 変換確定の Enter（Chromium で報告の多い届き方：compositionend より前、isComposing: true）
    await dispatchComposingKey(edit.input, {key: 'Enter'});
    await commitComposition(session, '実験');
    await page.waitForTimeout(300);

    await expect(edit.editing).toHaveCount(0);
    expect(await lastUpdateNames(api)).toEqual([]);
    await expect(edit.label).toHaveText('Task A');
  });

  test('確定済みの変更がある状態で変換中に Enter → 変換中の文字を含まない名前で保存される', async ({page}) => {
    const api = await mockClearmlApi(page);
    await page.goto(URL);
    const edit = await openNameEdit(page);
    const session = await cdp(page);

    await edit.input.press('End');
    await page.keyboard.type(' v2 ');
    await setComposition(session, 'じっけん');
    await dispatchComposingKey(edit.input, {key: 'Enter'});
    await commitComposition(session, '実験');
    await page.waitForTimeout(500);

    await expect(edit.editing).toHaveCount(0);
    expect(await lastUpdateNames(api)).toContain('Task A v2 ');
    expect((await lastUpdateNames(api)).some(n => n?.includes('実験'))).toBe(false);
  });

  test('未確定のまま Tab → 同じく保存・取消が走る', async ({page}) => {
    const api = await mockClearmlApi(page);
    await page.goto(URL);
    const edit = await openNameEdit(page);
    const session = await cdp(page);

    await edit.input.press('End');
    await page.keyboard.type('-x');
    await setComposition(session, 'じっけん');
    await dispatchComposingKey(edit.input, {key: 'Tab'});
    await page.waitForTimeout(500);

    await expect(edit.editing).toHaveCount(0);
    expect(await lastUpdateNames(api)).toContain('Task A-x');
  });

  test('参考：CDP の変換確定だけ（keydown なし）では編集は続く', async ({page}) => {
    const api = await mockClearmlApi(page);
    await page.goto(URL);
    const edit = await openNameEdit(page);
    const session = await cdp(page);

    await selectAll(edit.input);
    await setComposition(session, 'じっけん');
    await commitComposition(session, '実験');
    await page.waitForTimeout(300);

    await expect(edit.editing).toHaveCount(1);
    await expect(edit.input).toHaveValue('実験');
    expect(await lastUpdateNames(api)).toEqual([]);
  });
});

test.describe('03 変換取消の Esc', () => {
  test('変換中に Esc → 編集全体が取り消され、確定済みの入力も消える', async ({page}) => {
    const api = await mockClearmlApi(page);
    await page.goto(URL);
    const edit = await openNameEdit(page);
    const session = await cdp(page);

    await edit.input.press('End');
    await page.keyboard.type(' renamed');
    await setComposition(session, 'じっけん');
    await dispatchComposingKey(edit.input, {key: 'Escape'});
    await page.waitForTimeout(300);

    await expect(edit.editing).toHaveCount(0);
    expect(await lastUpdateNames(api)).toEqual([]);
    // 再度編集を開くと、確定済みだった ' renamed' も失われている
    const again = await openNameEdit(page);
    await expect(again.input).toHaveValue('Task A');
  });
});

test.describe('04 通常の Enter', () => {
  test('✓ボタンが有効なときの Enter で tasks.update が2回送られる', async ({page}) => {
    const api = await mockClearmlApi(page);
    await page.goto(URL);
    const edit = await openNameEdit(page);

    await selectAll(edit.input);
    await page.keyboard.type('Renamed task');
    await expect(edit.approve).toBeEnabled();
    const clicks: string[] = [];
    await edit.approve.evaluate(el => el.addEventListener('click', () => (window as any).__approveClicks = ((window as any).__approveClicks ?? 0) + 1));
    await edit.input.press('Enter');
    await page.waitForTimeout(1000);
    clicks.push(String(await page.evaluate(() => (window as any).__approveClicks)));

    console.log('approve clicks by implicit submission:', clicks[0]);
    console.log('tasks.update names:', JSON.stringify(await lastUpdateNames(api)));
    expect(await lastUpdateNames(api)).toEqual(['Renamed task', 'Renamed task']);
  });

  test('参考：✓ボタンのクリックでは1回', async ({page}) => {
    const api = await mockClearmlApi(page);
    await page.goto(URL);
    const edit = await openNameEdit(page);

    await selectAll(edit.input);
    await page.keyboard.type('Renamed task');
    await edit.approve.click();
    await page.waitForTimeout(1000);
    expect(await lastUpdateNames(api)).toEqual(['Renamed task']);
  });
});

test.describe('06 名前の長さの下限', () => {
  for (const [label, value, how] of [
    ['2文字（Enter）', '実験', 'enter'],
    ['2文字（✓）', '実験', 'approve'],
    ['前後の空白で2文字以上にした名前（Enter）', ' 実験 ', 'enter'],
    ['3文字', 'abc', 'enter']
  ] as const) {
    test(label, async ({page}) => {
      const api = await mockClearmlApi(page);
      await page.goto(URL);
      const edit = await openNameEdit(page);
      await selectAll(edit.input);
      await page.keyboard.insertText(value);
      const approveEnabled = await edit.approve.isEnabled();
      if (how === 'enter') {
        await edit.input.press('Enter');
      } else {
        await edit.approve.click();
      }
      await page.waitForTimeout(800);
      const toast = await page.locator('.notifier__notification, simple-notifications, .notifier__container').allInnerTexts();
      console.log(JSON.stringify({label, approveEnabled, editing: await edit.editing.count(), updates: await lastUpdateNames(api), toast}));
    });
  }
});

test.describe('08 保存失敗後の食い違い', () => {
  test('tasks.update が失敗すると、次の編集の初期値が失敗した名前になる', async ({page}) => {
    const api = await mockClearmlApi(page, {
      overrides: {
        'tasks.update': () => ({status: 400, resultCode: 400, msg: 'Update failed (mock)'})
      }
    });
    await page.goto(URL);
    const edit = await openNameEdit(page);
    await selectAll(edit.input);
    await page.keyboard.type('Failed name');
    await edit.approve.click();
    await page.waitForTimeout(1500);

    expect(await lastUpdateNames(api)).toEqual(['Failed name']);
    // 'Update task failed' のエラーダイアログを閉じる
    await page.getByRole('button', {name: 'OK'}).click();
    await expect(edit.label).toHaveText('Task A');
    const listText = await page.locator('sm-experiments-table').innerText();
    console.log('list contains Task A:', listText.includes('Task A'), 'Failed name:', listText.includes('Failed name'));

    const again = await openNameEdit(page);
    const initial = await again.input.inputValue();
    console.log('initial value of the next edit:', initial);
    // 何も変えずに Enter → 取消扱いになり、再送されない
    await again.input.press('Enter');
    await page.waitForTimeout(800);
    console.log('tasks.update names after Enter without change:', JSON.stringify(await lastUpdateNames(api)));
    console.log('get_by_id_ex after failure:', api.callsTo('tasks.get_by_id_ex').length);
    expect(initial).toBe('Failed name');
  });
});

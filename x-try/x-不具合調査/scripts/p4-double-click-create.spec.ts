import {expect, Page, test} from '@playwright/test';
import {mockClearmlApi} from './helpers/mock-api';

/**
 * フェーズ4（観点の見直し、§3 G・J の「保存中の二度押し」「連打したときの二重実行」の確認）。
 * プロジェクトとキューの作成ダイアログは、作成の要求中も作成ボタンが有効なままで、
 * 要求の完了後にダイアログを閉じる。ボタンをダブルクリックすると作成の要求が2回出るかを確かめる。
 * サーバはどちらも名前を会社内で一意にするため、モックは2回目以降を「既に存在する」で失敗させる。
 * モック API（書き込みなし）。応答は400ms 遅らせる（実際の遅延の代わり）。
 */
function uniqueNameServer(endpoint: string, created: unknown) {
  let count = 0;
  return () => {
    count++;
    return count === 1 ?
      {data: created} :
      {status: 400, resultCode: 400, msg: `${endpoint}: name already exists`};
  };
}

async function messages(page: Page): Promise<string[]> {
  return page.locator('mat-snack-bar-container, sm-notifier, simple-snack-bar, .p-toast-message').allInnerTexts();
}

test('プロジェクトの作成：CREATE PROJECT のダブルクリックで projects.create が2回出て、失敗の通知が出る', async ({page}) => {
  const api = await mockClearmlApi(page, {
    delays: {'projects.create': 400},
    overrides: {'projects.create': uniqueNameServer('projects.create', {id: 'new-project'})}
  });
  await page.goto('/projects');
  await page.locator('[data-id="New Project"]').click();
  const dialog = page.locator('mat-dialog-container');
  await dialog.locator('input[formcontrolname="name"]').fill('二度押しのプロジェクト');
  const button = dialog.locator('[data-id="Create Project"]');
  await expect(button).toBeEnabled();
  await button.dblclick();
  await page.waitForTimeout(2000);
  const creates = api.callsTo('projects.create').length;
  const msg = await messages(page);
  const dialogOpen = await dialog.count();
  await page.screenshot({path: 'test-results/bug-investigation/p4-double-click-create-project.png'});
  console.log('プロジェクト', JSON.stringify({creates, dialogOpen, msg}));
  expect(creates).toBe(2);
});

test('キューの作成：NEW QUEUE のダイアログで作成ボタンのダブルクリックで queues.create が2回出る', async ({page}) => {
  const api = await mockClearmlApi(page, {
    delays: {'queues.create': 400},
    overrides: {
      'queues.create': uniqueNameServer('queues.create', {id: 'new-queue'}),
      'queues.get_all_ex': () => ({data: {queues: []}}),
      'queues.get_all': () => ({data: {queues: []}})
    }
  });
  await page.goto('/workers-and-queues/queues');
  await page.getByRole('button', {name: 'NEW QUEUE'}).click();
  const dialog = page.locator('mat-dialog-container');
  await dialog.locator('input[formcontrolname="name"]').fill('二度押しのキュー');
  const button = dialog.locator('button[mat-flat-button]').last();
  await expect(button).toBeEnabled();
  await button.dblclick();
  await page.waitForTimeout(2000);
  const creates = api.callsTo('queues.create').length;
  const msg = await messages(page);
  const dialogOpen = await dialog.count();
  await page.screenshot({path: 'test-results/bug-investigation/p4-double-click-create-queue.png'});
  console.log('キュー', JSON.stringify({creates, dialogOpen, msg}));
  expect(creates).toBe(2);
});

test('資格情報の作成：Create new credentials のダブルクリックで、作成直後の資格情報のダイアログが閉じるか', async ({page}) => {
  const api = await mockClearmlApi(page, {
    delays: {'auth.create_credentials': 400},
    overrides: {
      'auth.get_credentials': () => ({data: {credentials: []}}),
      'auth.create_credentials': () => ({data: {credentials: {access_key: 'AK-TEST', secret_key: 'SK-TEST'}}})
    }
  });
  await page.goto('/settings/workspace-configuration');
  const button = page.getByRole('button', {name: /Create new credentials/});
  await button.waitFor();
  await page.waitForTimeout(1000);
  await button.dblclick();
  await page.waitForTimeout(2000);
  const creates = api.callsTo('auth.create_credentials').length;
  const dialogs = await page.locator('mat-dialog-container').allInnerTexts();
  await page.screenshot({path: 'test-results/bug-investigation/p4-double-click-create-credentials.png'});
  console.log('資格情報', JSON.stringify({creates, dialogs: dialogs.map(d => d.slice(0, 120))}));
});

test('対照：Create new credentials の1回のクリックでは、作成した資格情報のダイアログが残る', async ({page}) => {
  const api = await mockClearmlApi(page, {
    delays: {'auth.create_credentials': 400},
    overrides: {
      'auth.get_credentials': () => ({data: {credentials: []}}),
      'auth.create_credentials': () => ({data: {credentials: {access_key: 'AK-TEST', secret_key: 'SK-TEST'}}})
    }
  });
  await page.goto('/settings/workspace-configuration');
  const button = page.getByRole('button', {name: /Create new credentials/});
  await button.waitFor();
  await page.waitForTimeout(1000);
  await button.click();
  await page.waitForTimeout(2000);
  const dialogs = await page.locator('mat-dialog-container').allInnerTexts();
  console.log('資格情報（1回）', JSON.stringify({creates: api.callsTo('auth.create_credentials').length, dialogs: dialogs.map(d => d.replace(/\s+/g, ' ').slice(0, 160))}));
  expect(dialogs.length).toBe(1);
});

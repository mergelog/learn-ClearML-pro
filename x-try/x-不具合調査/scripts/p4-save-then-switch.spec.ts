import {expect, Page, test} from '@playwright/test';
import {mockClearmlApi} from './helpers/mock-api';

/**
 * フェーズ4（観点の見直し、§4.1「保存中の切替」の確認）。
 * 詳細ヘッダーで Task A の名前を保存し、tasks.update の応答が届く前に一覧で Task B を選ぶ。
 * updateExperimentDetails$ は保存時点の選択（A）で updateExperimentInfoData を出すかを決め、
 * 成功後の experimentUpdatedSuccessfully({id: A}) が A の詳細を取り直すため、
 * B を選んでいるのに A の詳細が表示されるかを確かめる。モック API（tasks.update を遅らせる）。
 */
const START = '/projects/bug-project/tasks/task-a/execution';

async function storeInfo(page: Page) {
  return page.evaluate(() => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    let state: any;
    app.store.subscribe((s: unknown) => state = s).unsubscribe();
    const key = Object.keys(state).find(k => state[k]?.info?.infoData !== undefined);
    const s = key ? state[key].info : undefined;
    return {infoData: s?.infoData && {id: s.infoData.id, name: s.infoData.name}, selected: s?.selectedExperiment && {id: s.selectedExperiment.id, name: s.selectedExperiment.name}};
  });
}

async function renameInHeader(page: Page, name: string) {
  const root = page.locator('sm-experiment-info-header sm-inline-edit');
  await root.locator('.value').click();
  const input = root.locator('input.inline-edit-input');
  await expect(input).toBeFocused();
  await input.fill(name);
  await input.press('Enter');
}

test('名前の保存の応答が届く前に Task B を選ぶと、B の URL で A の詳細が表示され、セクションの保存が A に送られる', async ({page}) => {
  const api = await mockClearmlApi(page, {delays: {'tasks.update': 2000}});
  await page.goto(START);
  await page.locator('sm-experiment-info-header .experiment-name').waitFor();
  await page.waitForTimeout(1500);

  await renameInHeader(page, 'Task A renamed');
  const rowB = page.locator('sm-experiments-table, sm-table').getByText('Task B', {exact: true}).first();
  await rowB.click();
  await page.waitForURL(/task-b/);
  await page.waitForTimeout(600);
  const beforeResponse = {url: new URL(page.url()).pathname, header: await page.locator('sm-experiment-info-header .experiment-name').innerText(), store: await storeInfo(page)};

  await page.waitForTimeout(3500);
  const afterResponse = {url: new URL(page.url()).pathname, header: await page.locator('sm-experiment-info-header .experiment-name').innerText(), store: await storeInfo(page)};
  await page.screenshot({path: 'test-results/bug-investigation/p4-save-then-switch.png'});

  const getById = api.callsTo('tasks.get_by_id_ex').map(c => ({ids: (c.body as any)?.id, fields: (c.body as any)?.only_fields?.length}));
  console.log('応答前', JSON.stringify(beforeResponse));
  console.log('応答後', JSON.stringify(afterResponse));
  console.log('tasks.get_by_id_ex', JSON.stringify(getById));

  // 続けて、表示中（URL は B）の Execution の CONTAINER を編集して保存する
  const container = page.locator('sm-editable-section', {has: page.locator('sm-section-header[label="CONTAINER"]')});
  await container.scrollIntoViewIfNeeded();
  await container.hover();
  await container.locator('[data-id="editSectionButton"]').click({force: true});
  const imageBefore = await container.locator('[data-id="imageFieldId"]').inputValue();
  await container.locator('[data-id="imageFieldId"]').fill('Bのつもりのイメージ');
  await container.locator('[data-id="SaveButton"]').click();
  await page.waitForTimeout(2000);
  const edits = api.callsTo('tasks.edit').map(c => ({task: (c.body as any)?.task, container: (c.body as any)?.container}));
  console.log('CONTAINER の編集前の表示', imageBefore, 'tasks.edit', JSON.stringify(edits));

  // 続けて、表示中の詳細ヘッダーで名前を変える
  await renameInHeader(page, 'Bのつもりの名前');
  await page.waitForTimeout(3000);
  const updates = api.callsTo('tasks.update').map(c => ({task: (c.body as any)?.task, name: (c.body as any)?.name}));
  console.log('tasks.update', JSON.stringify(updates));

  expect(afterResponse.url).toContain('task-b');
  expect(afterResponse.store.infoData?.id).toBe('task-a');
  expect(imageBefore).toBe('image-task-a');
  expect(edits.at(-1)?.task).toBe('task-a');
});

test('対照：応答が届いてから Task B を選ぶと、B の詳細が表示される', async ({page}) => {
  const api = await mockClearmlApi(page, {delays: {'tasks.update': 300}});
  await page.goto(START);
  await page.locator('sm-experiment-info-header .experiment-name').waitFor();
  await page.waitForTimeout(1500);
  await renameInHeader(page, 'Task A renamed');
  await page.waitForTimeout(2000);
  await page.locator('sm-experiments-table, sm-table').getByText('Task B', {exact: true}).first().click();
  await page.waitForURL(/task-b/);
  await page.waitForTimeout(2500);
  const state = {url: new URL(page.url()).pathname, header: await page.locator('sm-experiment-info-header .experiment-name').innerText(), store: await storeInfo(page)};
  console.log('対照', JSON.stringify(state), JSON.stringify(api.callsTo('tasks.update').map(c => (c.body as any)?.task)));
  expect(state.store.infoData?.id).toBe('task-b');
});

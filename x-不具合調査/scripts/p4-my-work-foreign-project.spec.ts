import {expect, Page, test} from '@playwright/test';
import {mockClearmlApi, MockHandle} from './helpers/mock-api';
import {navigateInApp} from './helpers/leak';

/**
 * フェーズ4（観点の見直し、H から回した「存在しないプロジェクトの表題が All Tasks になる」の確認）。
 * My Work を有効にしたまま、自分のタスク・モデルが無い他人のプロジェクトを開くと、
 * projects.get_all_ex（active_users 付き）が空を返し、選択中プロジェクトが All Tasks（id '*'）に置き換わること。
 * そのまま NEW TASK で下書きを保存すると、tasks.create に project: '*' が渡ること。
 * モック API（利用者設定をサーバに書き込まないため）。
 */
const company = {id: 'test-company', name: 'Test company'};
const otherProject = {id: 'other-project', name: '他人のプロジェクト', basename: '他人のプロジェクト', company};

async function setup(page: Page): Promise<MockHandle> {
  return mockClearmlApi(page, {
    tasks: [],
    overrides: {
      'projects.get_all_ex': body => {
        if (Array.isArray(body?.id) && body.id.includes(otherProject.id)) {
          // サーバは active_users があると、その利用者が作ったプロジェクトか、その利用者のタスク・モデルを含むプロジェクトだけを返す
          return {data: {projects: body.active_users ? [] : [otherProject]}};
        }
        return undefined;
      },
      'tasks.create': body => body?.project === '*' ?
        {status: 400, resultCode: 400, msg: 'Invalid project id'} :
        {data: {id: 'new-task'}}
    }
  });
}

async function chooseMyWork(page: Page): Promise<void> {
  await page.goto('/projects');
  await page.locator('sm-main-pages-header-filter').waitFor();
  await page.waitForTimeout(1500);
  await page.locator('sm-main-pages-header-filter button.cell').click();
  await page.locator('[data-id="MyWorkFilterOption"]').click();
  await page.keyboard.press('Escape');
  await page.waitForTimeout(1000);
}

async function selectedProjectInStore(page: Page): Promise<unknown> {
  return page.evaluate(() => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    let state: any;
    app.store.subscribe((s: unknown) => state = s).unsubscribe();
    const key = Object.keys(state ?? {}).find(k => state[k] && 'selectedProject' in state[k]);
    return {selected: key && state[key].selectedProject?.id, myWork: state?.users?.showOnlyUserWork};
  });
}

async function saveDraft(page: Page): Promise<void> {
  await page.locator('[data-id="New Experiment"]').click();
  const dialog = page.locator('mat-dialog-container');
  await dialog.locator('[data-id="taskNameField"]').fill('日本語のタスク');
  await dialog.locator('input[formcontrolname="binary"]').fill('python3');
  await dialog.locator('input[formcontrolname="script"]').first().fill('train.py');
  await dialog.getByRole('button', {name: 'SAVE AS DRAFT'}).click();
  await page.waitForTimeout(1500);
}

test('My Work なし：他人のプロジェクトの表題はプロジェクト名で、下書きはそのプロジェクトに作られる', async ({page}) => {
  const api = await setup(page);
  await page.goto(`/projects/${otherProject.id}/tasks`);
  await page.locator('[data-id="New Experiment"]').waitFor();
  await page.waitForTimeout(1500);
  const header = await page.locator('sm-header').innerText();
  const store = await selectedProjectInStore(page);
  await saveDraft(page);
  const created = api.callsTo('tasks.create').map(c => (c.body as any)?.project);
  console.log('My Work なし', JSON.stringify({header: header.split('\n').slice(0, 3), store, created}));
  expect(header).toContain(otherProject.name);
  expect(created).toEqual([otherProject.id]);
});

test('My Work あり：他人のプロジェクトの表題が All Tasks になり、下書きの作成に project: * が渡る', async ({page}) => {
  const api = await setup(page);
  await chooseMyWork(page);
  await navigateInApp(page, `/projects/${otherProject.id}/tasks`);
  await page.locator('[data-id="New Experiment"]').waitFor();
  await page.waitForTimeout(1500);
  const header = await page.locator('sm-header').innerText();
  const store = await selectedProjectInStore(page);
  const getAllEx = api.callsTo('projects.get_all_ex')
    .map(c => c.body as any)
    .filter(b => Array.isArray(b?.id) && b.id.includes(otherProject.id))
    .map(b => ({id: b.id, active_users: b.active_users}));
  await page.screenshot({path: 'test-results/bug-investigation/p4-my-work-foreign-project.png'});
  await saveDraft(page);
  const created = api.callsTo('tasks.create').map(c => (c.body as any)?.project);
  const errorDialog = await page.locator('mat-dialog-container, mat-snack-bar-container, simple-snack-bar').allInnerTexts();
  await page.screenshot({path: 'test-results/bug-investigation/p4-my-work-foreign-project-after-save.png'});
  console.log('My Work あり', JSON.stringify({url: page.url(), header: header.split('\n').slice(0, 3), store, getAllEx, created, errorDialog}));
  expect(header).toContain('All Tasks');
  expect(created).toEqual(['*']);
});

import {Page, test} from '@playwright/test';
import {buildTask, mockClearmlApi, mockProject} from './helpers/mock-api';
import {navigateInApp} from './helpers/leak';

/**
 * フェーズ2 観点F：画面を移ったとき、新しい応答が届くまでのあいだに前の画面の値が表示されるか。
 * 応答を遅らせたモック API で、移った直後と応答後の表示を記録する（期待値は置かず、記録だけ）。
 */
const projectB = {id: 'project-b', name: 'Project B'};
const DELAY = 2500;

function taskRows(page: Page) {
  return page.locator('sm-experiments-table').evaluate(el => Array.from(el.querySelectorAll('tr')).map(tr => tr.textContent ?? '')
    .filter(t => /Task [A-D]/.test(t)).map(t => t.match(/Task [A-D]/)![0]));
}

test('プロジェクトAの一覧からプロジェクトBの一覧へ移った直後', async ({page}) => {
  const tasksA = [buildTask('task-a', 'Task A'), buildTask('task-b', 'Task B')];
  const tasksB = [buildTask('task-c', 'Task C', {project: projectB}), buildTask('task-d', 'Task D', {project: projectB})];
  let delayOn = false;
  await mockClearmlApi(page, {
    tasks: [...tasksA, ...tasksB],
    overrides: {
      'projects.get_all_ex': body => ({data: {projects: body?.id?.includes('project-b') ? [projectB] : [mockProject, projectB]}}),
      'projects.get_by_id': body => ({data: {project: body?.project === 'project-b' ? projectB : mockProject}})
    }
  });
  await page.route('**/tasks.get_all_ex', async route => {
    const body = route.request().postDataJSON();
    const inB = JSON.stringify(body?.project ?? '').includes('project-b');
    if (delayOn && inB) {
      await new Promise(r => setTimeout(r, DELAY));
    }
    const list = body?.id?.length ? [...tasksA, ...tasksB].filter(t => body.id.includes(t.id)) : (inB ? tasksB : tasksA);
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({meta: {result_code: 200}, data: {tasks: list, scroll_id: null}})});
  });

  await page.goto('/projects/bug-project/tasks');
  await page.locator('sm-experiments-table').waitFor();
  await page.waitForTimeout(1500);
  const onA = await taskRows(page);
  delayOn = true;
  await navigateInApp(page, '/projects/project-b/tasks');
  await page.waitForTimeout(500);
  const justAfter = {
    rows: [...new Set(await taskRows(page).catch(() => [] as string[]))],
    spinner: await page.locator('sm-spinner .loader-container').count(),
    tableLoading: await page.locator('sm-experiments-table .p-datatable-loading-overlay, sm-experiments-table mat-spinner').count()
  };
  await page.screenshot({path: 'test-results/bug-investigation/p2f-stale-project-switch.png'});
  await page.waitForTimeout(DELAY + 1000);
  const later = [...new Set(await taskRows(page))];
  console.log('Aの一覧', JSON.stringify([...new Set(onA)]));
  console.log('Bへ移った0.5秒後', JSON.stringify(justAfter));
  console.log('応答後', JSON.stringify(later));
});

test('詳細でタスクAからタスクBの行を選んだ直後', async ({page}) => {
  let delayOn = false;
  await mockClearmlApi(page);
  await page.route('**/tasks.get_by_id_ex', async (route, request) => {
    const body = request.postDataJSON();
    if (delayOn && body?.id?.includes('task-b')) {
      await new Promise(r => setTimeout(r, DELAY));
    }
    return route.fallback();
  });
  await page.goto('/projects/bug-project/tasks/task-a/execution');
  const header = page.locator('sm-experiment-info-header .experiment-name span');
  await header.waitFor();
  await page.waitForTimeout(1500);
  const repo = () => page.locator('sm-experiment-info-execution').textContent().then(t => (t ?? '').match(/repository-task-[ab]/)?.[0] ?? null).catch(() => null);
  const onA = {header: await header.textContent(), repo: await repo()};
  delayOn = true;
  await page.locator('sm-experiments-table tr', {hasText: 'Task B'}).first().click();
  await page.waitForTimeout(700);
  const justAfter = {url: new URL(page.url()).pathname, header: await header.textContent().catch(() => null), repo: await repo()};
  await page.waitForTimeout(DELAY + 1000);
  const later = {url: new URL(page.url()).pathname, header: await header.textContent().catch(() => null), repo: await repo()};
  console.log('タスクA', JSON.stringify(onA));
  console.log('タスクBを選んだ0.7秒後', JSON.stringify(justAfter));
  console.log('応答後', JSON.stringify(later));
});

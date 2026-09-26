import {expect, Page, test} from '@playwright/test';
import {mockClearmlApi} from './helpers/mock-api';
import {closeStartupDialogs, recordActions, takeActions} from './helpers/leak';
import {loginViaClearmlWeb, REAL} from './helpers/real-backend';

/**
 * フェーズ2 観点F：Effect の catchError の位置による停止。
 * - 外側の pipe に catchError がある Effect は、1回の失敗で完了し、以後その action に反応しない（再読み込みまで）
 * - catchError が無い Effect は、NgRx が再購読するが、回数はセッションの累計で10回までで、11回目の失敗で止まる
 * 作成・削除の API はモック API で失敗させる。比較画面の自動更新は実バックエンド（読み取りだけ）で、該当の要求だけを page.route で失敗させる。
 */

async function dispatch(page: Page, action: Record<string, unknown>) {
  await page.evaluate(a => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    app.store.dispatch(a);
  }, action);
}

const createTaskData = (name: string) => ({
  name, taskType: 'training', repo: '', type: 'branch', branch: 'main', directory: '.', binary: 'python3', script: 'train.py',
  requirements: 'skip', pip: '', args: [], output: '', docker: {image: '', script: '', args: ''},
  taskInit: true, poetry: false, venvType: 'discover', venv: null, vars: [], queue: null
});

test('タスクの作成：1回目の tasks.create が失敗すると、2回目以降は要求も通知も出ない', async ({page}) => {
  let createCalls = 0;
  const api = await mockClearmlApi(page, {
    overrides: {
      'tasks.create': () => (++createCalls === 1 ? {status: 500, resultCode: 500, msg: 'Internal server error'} : {data: {id: 'created-task'}})
    }
  });
  await page.goto('/projects/bug-project/tasks');
  await page.locator('sm-experiments-table').waitFor();
  await page.waitForTimeout(1500);
  await recordActions(page);

  // ダイアログ（CreateExperimentDialogComponent）を閉じた後に experiments.component.ts:787 が dispatch するものと同じ action
  await dispatch(page, {type: 'EXPERIMENTS_ [create experiment]', data: createTaskData('first try')});
  await page.waitForTimeout(1500);
  const afterFirst = {calls: api.callsTo('tasks.create').length, actions: await takeActions(page)};
  await page.locator('.mat-mdc-snack-bar-container, sm-notifier, .notifier').first().waitFor({timeout: 3000}).catch(() => undefined);

  await dispatch(page, {type: 'EXPERIMENTS_ [create experiment]', data: createTaskData('second try')});
  await page.waitForTimeout(1500);
  const afterSecond = {calls: api.callsTo('tasks.create').length, actions: await takeActions(page)};
  await dispatch(page, {type: 'EXPERIMENTS_ [create experiment]', data: createTaskData('third try')});
  await page.waitForTimeout(1500);
  const afterThird = {calls: api.callsTo('tasks.create').length, actions: await takeActions(page)};

  console.log('1回目', JSON.stringify(afterFirst));
  console.log('2回目', JSON.stringify(afterSecond));
  console.log('3回目', JSON.stringify(afterThird));
  expect(afterFirst.calls).toBe(1);
  expect(afterFirst.actions.some(a => a.includes('ADD_MESSAGE') || a.toLowerCase().includes('message'))).toBe(true);
  expect(afterSecond.calls).toBe(1);
  expect(afterThird.calls).toBe(1);
  expect(afterThird.actions.some(a => a.toLowerCase().includes('create experiment success'))).toBe(false);
});

test('レポートの作成：1回目の reports.create が失敗すると、2回目は要求が出ず、全画面のスピナーが消えない', async ({page}) => {
  let createCalls = 0;
  const api = await mockClearmlApi(page, {
    overrides: {
      'reports.get_all_ex': () => ({data: {tasks: [], scroll_id: null}}),
      'reports.get_tags': () => ({data: {tags: []}}),
      'reports.create': () => (++createCalls === 1 ? {status: 500, resultCode: 500, msg: 'Internal server error'} : {data: {id: 'r1', project_id: 'bug-project'}})
    }
  });
  await page.goto('/reports');
  await page.waitForTimeout(3000);
  const spinner = page.locator('sm-spinner .loader-container');

  // レポートのダイアログを閉じた後に reports-page.component.ts:94 が dispatch するものと同じ action（既存のプロジェクトを指定）
  await dispatch(page, {type: 'REPORTS_CREATE_REPORT', reportsCreateRequest: {name: 'first report', project: 'bug-project'}});
  await page.waitForTimeout(1500);
  const first = {calls: api.callsTo('reports.create').length, spinner: await spinner.count()};

  await dispatch(page, {type: 'REPORTS_CREATE_REPORT', reportsCreateRequest: {name: 'second report', project: 'bug-project'}});
  await page.waitForTimeout(5000);
  const second = {calls: api.callsTo('reports.create').length, spinner: await spinner.count(), url: page.url()};

  console.log('1回目', JSON.stringify(first), '2回目', JSON.stringify(second));
  expect(first).toEqual({calls: 1, spinner: 0});
  expect(second.calls).toBe(1);
  expect(second.spinner).toBe(1);
});

test('キューの削除：1回目の queues.delete が失敗すると、2回目は確認ダイアログも開かない', async ({page}) => {
  let deleteCalls = 0;
  const queue = {
    id: 'queue-1', name: 'queue-1', caption: 'queue-1', entries: [], created: '2026-09-01T00:00:00Z',
    workers: [], tags: [], system_tags: [], company: {id: 'test-company'}, user: {id: 'test-user'}
  };
  await mockClearmlApi(page, {
    overrides: {
      'queues.get_all_ex': () => ({data: {queues: [queue]}}),
      'queues.get_all': () => ({data: {queues: [queue]}}),
      'queues.get_queue_metrics': () => ({data: {queues: []}}),
      'workers.get_all': () => ({data: {workers: []}}),
      'queues.delete': () => (++deleteCalls === 1 ?
        {status: 400, resultCode: 400, msg: 'Queue is not empty: use force=true to delete'} :
        {data: {deleted: 1}})
    }
  });
  await page.goto('/workers-and-queues/queues');
  const row = page.locator('sm-queues-table tr', {hasText: 'queue-1'}).first();
  await row.waitFor();
  await page.waitForTimeout(1000);

  const confirmDialog = page.locator('mat-dialog-container', {hasText: 'Delete Queue'});
  const openDeleteFromMenu = async () => {
    await row.click({button: 'right'});
    await page.locator('sm-menu-item', {hasText: 'Delete'}).first().click();
    await page.waitForTimeout(800);
    return confirmDialog.count();
  };

  const firstDialog = await openDeleteFromMenu();
  if (firstDialog) {
    await confirmDialog.locator('button', {hasText: /^\s*Delete\s*$/i}).click();
  }
  await page.waitForTimeout(1500);
  const secondDialog = await openDeleteFromMenu();

  console.log('確認ダイアログ 1回目', firstDialog, '2回目', secondDialog, 'queues.delete', deleteCalls);
  expect(firstDialog).toBe(1);
  expect(deleteCalls).toBe(1);
  expect(secondDialog).toBe(0);
});

test('比較画面の自動更新：refreshIfNeeded の要求が累計11回失敗すると、以後は要求が出ない（実バックエンド）', async ({page}) => {
  test.setTimeout(120_000);
  let failing = false;
  let lastChangeRequests = 0;
  await page.route('**/tasks.get_all_ex', async route => {
    const body = route.request().postDataJSON();
    const isRefreshIfNeeded = JSON.stringify(body?.only_fields) === JSON.stringify(['last_change']);
    if (isRefreshIfNeeded) {
      lastChangeRequests++;
      if (failing) {
        return route.fulfill({status: 500, contentType: 'application/json', body: JSON.stringify({meta: {result_code: 500, result_msg: 'Internal server error'}, data: {}})});
      }
    }
    return route.fallback();
  });
  await loginViaClearmlWeb(page);
  await page.goto(`/projects/${REAL.projectTraining}/compare-tasks;ids=${REAL.taskCompareA},${REAL.taskCompareB}/details`);
  await page.locator('sm-experiment-compare-header').waitFor();
  await page.waitForTimeout(3000);
  await closeStartupDialogs(page);

  const refresh = () => dispatch(page, {type: 'EXPERIMENTS_COMPARE_SELECT_EXPERIMENT_REFRESH_IF_NEEDED', payload: true, autoRefresh: true, entityType: 'task'});
  const errors: string[] = [];
  page.on('console', m => m.type() === 'error' && errors.push(m.text().slice(0, 80)));

  const before = lastChangeRequests;
  await refresh();
  await page.waitForTimeout(800);
  const control = lastChangeRequests - before;

  // 要求が出なくなるまで dispatch を繰り返し、失敗させた要求の累計を数える（10秒ごとの自動更新の分も含む）
  failing = true;
  const failStart = lastChangeRequests;
  const perAttempt: number[] = [];
  for (let i = 0; i < 15; i++) {
    const n = lastChangeRequests;
    await refresh();
    await page.waitForTimeout(600);
    perAttempt.push(lastChangeRequests - n);
    if (perAttempt.at(-1) === 0) {
      break;
    }
  }
  const failedTotal = lastChangeRequests - failStart;
  failing = false;
  const n = lastChangeRequests;
  await refresh();
  await page.waitForTimeout(800);
  const afterRecovery = lastChangeRequests - n;
  // 10秒ごとの自動更新（refresh.tick → refreshIfNeeded）も要求を出さないこと
  const m = lastChangeRequests;
  await page.waitForTimeout(12_000);
  const autoAfter = lastChangeRequests - m;

  console.log('失敗前', control, 'dispatch ごとの要求数', JSON.stringify(perAttempt), '失敗させた要求の累計', failedTotal,
    '復旧後', afterRecovery, '自動更新12秒', autoAfter, 'コンソールのエラー', errors.length);
  expect(control).toBe(1);
  expect(perAttempt.at(-1)).toBe(0);
  expect(failedTotal).toBe(11);
  expect(afterRecovery).toBe(0);
  expect(autoAfter).toBe(0);
});

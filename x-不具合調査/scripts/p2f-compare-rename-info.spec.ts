import {expect, Page, test} from '@playwright/test';
import {buildTask, mockClearmlApi} from './helpers/mock-api';
import {navigateInApp, recordActions, takeActions} from './helpers/leak';

/**
 * フェーズ2 観点F：experimentDetailsUpdated の reducer が action.id を見ずに info.infoData へ変更をマージし、
 * 成功後の experimentUpdatedSuccessfully({id}) から getExperiment({experimentId: id}) が出て、詳細の状態（info）が名前を変えたタスクに置き換わること。
 * 比較画面の名前変更（experiments-compare.component.ts:240）と同じ action を dispatch する。モック API。
 */

async function infoState(page: Page) {
  return page.evaluate(() => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    let s: any;
    app.store.subscribe((v: any) => s = v).unsubscribe();
    const info = s.experiments?.info;
    return {
      selected: info?.selectedExperiment?.id ?? null,
      selectedName: info?.selectedExperiment?.name ?? null,
      infoDataId: info?.infoData?.id ?? null,
      infoDataName: info?.infoData?.name ?? null,
      url: location.pathname
    };
  });
}

async function dispatch(page: Page, action: Record<string, unknown>) {
  await page.evaluate(a => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    app.store.dispatch(a);
  }, action);
}

test('詳細でタスクAを見た後、比較画面でタスクBの名前を変えると、詳細の状態がタスクBに置き換わる', async ({page}) => {
  const api = await mockClearmlApi(page, {tasks: [buildTask('task-a', 'Task A'), buildTask('task-b', 'Task B')]});
  await page.goto('/projects/bug-project/tasks/task-a/execution');
  await page.locator('sm-experiment-info-header').waitFor();
  await page.waitForTimeout(2000);
  const onDetails = await infoState(page);

  await navigateInApp(page, '/projects/bug-project/compare-tasks;ids=task-a,task-b/details');
  await page.waitForTimeout(3000);
  const onCompare = await infoState(page);

  await recordActions(page);
  const getByIdBefore = api.callsTo('tasks.get_by_id_ex').length;
  // 比較画面の凡例の「Rename」でダイアログを閉じた後の dispatch（experiments-compare.component.ts:240）
  await dispatch(page, {type: '[Experiments Info ]EXPERIMENT_DETAILS_UPDATED', id: 'task-b', changes: {name: 'Task B renamed'}});
  const justAfter = await infoState(page);
  await page.waitForTimeout(3000);
  const afterRename = await infoState(page);
  const actions = (await takeActions(page)).filter(a => a.includes('Experiments Info') || a.includes('EXPERIMENTS'));
  const getByIdForB = api.calls.slice(0).filter(c => c.endpoint === 'tasks.get_by_id_ex' && (c.body as any)?.id?.includes('task-b')).length;

  // ブラウザの戻るでタスクAの詳細へ
  await page.goBack();
  const header = page.locator('sm-experiment-info-header .experiment-name span');
  await header.waitFor();
  const headerRightAfterBack = await header.textContent();
  const stateRightAfterBack = await infoState(page);
  await page.waitForTimeout(3000);
  const headerLater = await header.textContent();
  const stateLater = await infoState(page);

  console.log('詳細（タスクA）', JSON.stringify(onDetails));
  console.log('比較画面に移った後', JSON.stringify(onCompare));
  console.log('dispatch 直後', JSON.stringify(justAfter));
  console.log('3秒後', JSON.stringify(afterRename), 'task-b の get_by_id_ex', getByIdForB, '（dispatch 前の get_by_id_ex 累計', getByIdBefore, '）');
  console.log('actions', JSON.stringify(actions));
  console.log('戻った直後', headerRightAfterBack, JSON.stringify(stateRightAfterBack));
  console.log('戻って3秒後', headerLater, JSON.stringify(stateLater));

  expect(onDetails.infoDataId ?? onDetails.selected).toBe('task-a');
  expect(afterRename.selected).toBe('task-b');
});

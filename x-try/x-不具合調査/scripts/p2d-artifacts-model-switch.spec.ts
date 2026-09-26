import {expect, test} from '@playwright/test';
import {buildTask, mockClearmlApi} from './helpers/mock-api';

/**
 * フェーズ2 観点D：ARTIFACTS の入力モデル（experiment-info-model、changeDetection の指定なし）。
 * 同じタスクの入力モデルを切り替えたとき、表示が新しいモデルに追随するかを見る。
 * 実バックエンドに入力モデルを2つ持つタスクが無いため、モック API で作る。
 */
const models = [
  {id: 'model-1', name: 'モデル一号', uri: 's3://bucket/model-1.pkl', framework: 'scikit-learn', design: {design: 'design-of-model-1'}, labels: {}, project: {id: 'bug-project', name: 'Bug project'}, task: {id: 'task-x', name: 'Source X'}, user: {id: 'test-user', name: 'Test User'}, created: '2026-09-01T00:00:00Z', ready: true, tags: [], system_tags: []},
  {id: 'model-2', name: 'モデル二号', uri: 's3://bucket/model-2.pkl', framework: 'scikit-learn', design: {design: 'design-of-model-2'}, labels: {}, project: {id: 'bug-project', name: 'Bug project'}, task: {id: 'task-y', name: 'Source Y'}, user: {id: 'test-user', name: 'Test User'}, created: '2026-09-02T00:00:00Z', ready: true, tags: [], system_tags: []}
];

test('同じタスクで入力モデルを切り替えても、表示が前のモデルのまま残る', async ({page}) => {
  const task = buildTask('task-a', 'Task A', {
    models: {input: [{name: 'in-a', model: models[0]}, {name: 'in-b', model: models[1]}], output: []}
  } as any);
  const api = await mockClearmlApi(page, {
    tasks: [task, buildTask('task-b', 'Task B')],
    overrides: {
      'models.get_all_ex': body => ({data: {models: models.filter(m => !body?.id || body.id.includes(m.id))}}),
      'models.get_all': body => ({data: {models: models.filter(m => !body?.id || body.id.includes(m.id))}}),
      'models.get_by_id': body => ({data: {model: models.find(m => m.id === body?.model)}})
    }
  });
  await page.goto('/projects/bug-project/tasks/task-a/artifacts/input-model/model-1');
  await page.waitForTimeout(2500);
  const view = page.locator('sm-experiment-info-model');
  const first = (await view.innerText()).replace(/\s+/g, ' ');
  await page.getByText('in-b', {exact: false}).first().click();
  await page.waitForTimeout(2000);
  const url = page.url();
  const second = (await view.innerText()).replace(/\s+/g, ' ');
  await page.evaluate(() => {
    const ng = (window as any).ng;
    ng.applyChanges(ng.getComponent(document.querySelector('sm-experiment-info-model')));
  });
  await page.waitForTimeout(300);
  const afterApply = (await view.innerText()).replace(/\s+/g, ' ');
  const endpoints = [...new Set(api.calls.map(c => c.endpoint))].filter(e => /model|artifact/.test(e));
  console.log(JSON.stringify({url, first: first.slice(0, 300), second: second.slice(0, 300), afterApply: afterApply.slice(0, 300), endpoints}, null, 1));
  expect(url).toContain('model-2');
  expect(second).toContain('モデル一号');
  expect(afterApply).toContain('モデル二号');
});

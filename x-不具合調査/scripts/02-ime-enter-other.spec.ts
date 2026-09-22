import {expect, test} from '@playwright/test';
import {mockClearmlApi} from './helpers/mock-api';
import {cdp, commitComposition, dispatchComposingKey, setComposition} from './helpers/ime';

/**
 * フェーズ1 02：インライン編集以外で、変換確定の Enter により確定処理が走る箇所。
 * - 詳細ヘッダーのタグ追加（モック）
 * 比較画面の名前変更ダイアログは 02b-compare-rename.spec.ts、Hyperparameters は 02c-execution-parameters.spec.ts（どちらも実バックエンド）。
 */

test('タグ追加：変換中の Enter で、変換前に確定していた文字列だけがタグとして追加される', async ({page}) => {
  const api = await mockClearmlApi(page);
  await page.goto('/projects/bug-project/tasks/task-a/execution');
  await page.locator('sm-experiment-info-header .middle-col').hover();
  await page.locator('sm-experiment-info-header sm-user-tag[data-id="addTag"]').click({force: true});
  const input = page.locator('.tags-menu input.filter');
  await expect(input).toBeFocused();
  await page.keyboard.type('v2');
  const session = await cdp(page);
  await setComposition(session, 'てすと');
  await dispatchComposingKey(input, {key: 'Enter'});
  await commitComposition(session, 'テスト');
  await page.waitForTimeout(1000);

  const tagWrites = api.callsTo('tasks.update_tags');
  console.log('tag writes:', JSON.stringify(tagWrites.map(c => c.body)));
  expect(tagWrites.map(c => c.body)).toEqual([{ids: ['task-a'], add_tags: ['v2']}]);
});

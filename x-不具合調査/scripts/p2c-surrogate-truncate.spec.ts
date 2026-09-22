import {expect, test} from '@playwright/test';
import {buildTask, mockClearmlApi} from './helpers/mock-api';

/**
 * フェーズ2 観点C：名前を UTF-16 の文字位置で切り詰める箇所で、絵文字（サロゲートペア）の途中で切れるか。
 * クローンのダイアログは、名前が80を超えると `slice:0:77` + '...' で表示する。77番目の位置に絵文字の前半が来る名前を使う。
 * モック API。
 */
const NAME = 'あ'.repeat(76) + '😀' + 'い'.repeat(10);

test('クローンのダイアログの見出しで、絵文字の前半だけが残り、置換文字（�）として表示される', async ({page}) => {
  await mockClearmlApi(page, {tasks: [buildTask('task-a', NAME), buildTask('task-b', 'Task B')]});
  await page.goto('/projects/bug-project/tasks/task-a/execution');
  await page.locator('sm-experiment-info-header sm-experiment-menu-extended button').first().click();
  await page.locator('[data-id="Clone Option"]').click();
  const reference = page.locator('mat-dialog-container .reference b').first();
  await expect(reference).toBeVisible();
  const text = await reference.innerText();
  const codes = [...text.slice(-6)].map(c => c.codePointAt(0)!.toString(16));
  const loneSurrogate = /[\uD800-\uDBFF](?![\uDC00-\uDFFF])/.test(text);
  await reference.screenshot({path: 'test-results/bug-investigation/p2c-surrogate-clone.png'});
  console.log(JSON.stringify({length: NAME.length, tail: text.slice(-6), codes, loneSurrogate}));
  expect(loneSurrogate).toBe(true);
});

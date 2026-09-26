import {expect, Page, test} from '@playwright/test';
import {loginViaClearmlWeb} from './helpers/real-backend';

/**
 * フェーズ2 観点D：CONFIGURATION > 設定オブジェクト（experiment-info-task-model、changeDetection の指定なし）。
 * formData を subscribe の中で書き換え、markForCheck を呼ばない。読み込み完了や切り替えが表示に反映されるかを見る。
 * 実バックエンドの既存タスク（読み取りだけ）。
 */
const HPO = {project: '53f9b62a0687460290bac474f2ec8c77', task: '6287d954f8db44d98acd877fad386470'};
const DATASET = {project: '6c5385bf7f9644a8bb766c6800889811', task: '3c913ea3f35549199d94e98cb3c64917'};

async function closeTip(page: Page) {
  await page.waitForTimeout(2500);
  const tip = page.locator('mat-dialog-container', {hasText: 'Don\'t show again'});
  if (await tip.count()) {
    await tip.locator('button').first().click();
  }
}

async function snapshot(page: Page) {
  const host = page.locator('sm-experiment-info-task-model');
  return {
    rows: (await host.locator('sm-labeled-row').allInnerTexts()).map(t => t.replace(/\s+/g, ' ').slice(0, 80)),
    spinner: await host.locator('mat-spinner, mat-progress-spinner, .spinner, sm-spinner').count(),
    text: (await host.locator('sm-scroll-textarea').innerText().catch(() => '')).replace(/\s+/g, ' ').slice(0, 120)
  };
}

test('設定オブジェクトを URL で直接開く', async ({page}) => {
  await loginViaClearmlWeb(page);
  const calls: string[] = [];
  page.on('response', r => r.url().includes('get_configurations') && calls.push(`${r.status()}`));
  await page.goto(`/projects/${HPO.project}/tasks/${HPO.task}/hyper-params/configuration/General`);
  await closeTip(page);
  await page.waitForTimeout(1500);
  const before = await snapshot(page);
  // 開発モードの ng API で、コンポーネントのフィールドの値を読み、変更検知を手動で走らせる
  const formData = await page.evaluate(() => {
    const comp = (window as any).ng.getComponent(document.querySelector('sm-experiment-info-task-model'));
    return JSON.stringify(comp.formData)?.slice(0, 160);
  });
  await page.screenshot({path: 'test-results/bug-investigation/p2d-config-direct.png'});
  await page.evaluate(() => {
    const ng = (window as any).ng;
    ng.applyChanges(ng.getComponent(document.querySelector('sm-experiment-info-task-model')));
  });
  await page.waitForTimeout(500);
  const after = await snapshot(page);
  console.log('direct', JSON.stringify({calls, before, formData, afterApplyChanges: after}, null, 1));
  expect(before.spinner).toBe(1);
  expect(formData).toContain('value');
  expect(after.spinner).toBe(0);
});

test('同じタスクで設定オブジェクトを切り替える', async ({page}) => {
  await loginViaClearmlWeb(page);
  await page.goto(`/projects/${DATASET.project}/tasks/${DATASET.task}/hyper-params/configuration/Dataset%20Struct`);
  await closeTip(page);
  await page.waitForTimeout(1500);
  const first = await snapshot(page);
  await page.getByText('Dataset Content', {exact: true}).first().click();
  await page.waitForTimeout(2500);
  const second = await snapshot(page);
  console.log('switch', JSON.stringify({url: decodeURIComponent(page.url()).split('/hyper-params/')[1], first, second}, null, 1));
  await page.screenshot({path: 'test-results/bug-investigation/p2d-config-switch.png'});
});

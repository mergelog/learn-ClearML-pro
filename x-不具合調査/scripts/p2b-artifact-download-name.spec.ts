import {expect, test} from '@playwright/test';
import {loginViaClearmlWeb, REAL} from './helpers/real-backend';

/**
 * フェーズ2 観点B：成果物のダウンロード（500MB 未満はメモリに読んでから保存する経路）のファイル名。
 * フロントエンドは Content-Disposition を `;` で区切った2番目の `=` の右をファイル名にする。
 * fileserver（Flask / Werkzeug 3.1.5）は、ASCII でない名前に `filename=<ASCII の代替>; filename*=UTF-8''<名前>` を返す
 * （fileserver コンテナで Werkzeug の send_file を読んで確認）。
 * 実バックエンドの既存タスクの成果物を開き、fileserver の応答のヘッダだけを Werkzeug と同じ形に差し替えて、保存名を見る。
 */
const cases: [string, string][] = [
  ['日本語の名前（結果.csv）', 'inline; filename=.csv; filename*=UTF-8\'\'%E7%B5%90%E6%9E%9C.csv'],
  ['空白を含む名前（my report.csv）', 'inline; filename="my report.csv"'],
  ['ASCII の名前（report.csv）', 'inline; filename=report.csv']
];

for (const [label, header] of cases) {
  test(`成果物のダウンロードの保存名：${label}`, async ({page}) => {
    await loginViaClearmlWeb(page);
    await page.route(/:8081\//, route => route.fulfill({
      status: 200,
      headers: {'Content-Type': 'text/csv', 'Content-Disposition': header, 'Access-Control-Allow-Origin': 'http://127.0.0.1:4200', 'Access-Control-Allow-Credentials': 'true', 'Access-Control-Expose-Headers': 'Content-Disposition'},
      body: 'a,b\n1,2\n'
    }));
    await page.goto(`/projects/${REAL.projectTraining}/tasks/${REAL.taskCompareA}/artifacts/other/evaluation/output`);
    await page.waitForTimeout(2500);
    const tip = page.locator('mat-dialog-container', {hasText: 'Don\'t show again'});
    if (await tip.count()) {
      await tip.locator('button').first().click();
    }
    const button = page.locator('sm-experiment-artifact-item-view button', {has: page.locator('mat-icon[fonticon*="download"], .al-ico-download')}).first();
    await expect(button).toBeVisible();
    const [download] = await Promise.all([page.waitForEvent('download', {timeout: 15000}), button.click()]);
    console.log(label, JSON.stringify({header, suggested: download.suggestedFilename()}));
  });
}

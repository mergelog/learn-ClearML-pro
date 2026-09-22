import AxeBuilder from '@axe-core/playwright';
import {expect, test} from '@playwright/test';
import {loginViaClearmlWeb, REAL} from './helpers/real-backend';

const R = REAL;

async function closeTipIfShown(page) {
  await page.waitForTimeout(1200);
  const tip = page.locator('mat-dialog-container', {hasText: "Don't show again"});
  if (await tip.count()) {
    await tip.locator('button').first().click();
    await expect(tip).toHaveCount(0);
  }
}

function collectPageProblems(page) {
  const problems: string[] = [];
  page.on('pageerror', error => problems.push(`pageerror: ${error.message}`));
  page.on('console', message => {
    if (message.type() === 'error' && !message.text().startsWith('Failed to load resource')) {
      problems.push(`console: ${message.text()}`);
    }
  });
  page.on('response', response => {
    if (response.status() >= 500) {
      problems.push(`http ${response.status()}: ${response.url()}`);
    }
  });
  return problems;
}

function simplifyAxe(results) {
  return results.violations
    .filter(violation => violation.impact === 'critical' || violation.impact === 'serious')
    .map(violation => ({
      id: violation.id,
      impact: violation.impact,
      targets: violation.nodes.map(node => node.target)
    }));
}

test('フェーズ3-5：プロジェクト、ダッシュボード、全体検索、ヘッダーの主要表示と履歴', async ({page}) => {
  const problems = collectPageProblems(page);
  await loginViaClearmlWeb(page);
  const targets = [
    ['/dashboard', 'sm-dashboard'],
    ['/projects', 'sm-projects-page'],
    [`/projects/${R.projectBaseline}/overview`, 'sm-project-info'],
    [`/projects/${R.projectBaseline}/workloads`, 'sm-workloads-page'],
  ] as const;

  for (const [url, selector] of targets) {
    await page.goto(url);
    await closeTipIfShown(page);
    await expect(page.locator(selector)).toBeVisible();
  }

  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`/projects/${R.projectBaseline}/overview`));
  await expect(page.locator('sm-project-info')).toBeVisible();
  await page.goForward();
  await expect(page).toHaveURL(new RegExp(`/projects/${R.projectBaseline}/workloads`));
  await expect(page.locator('sm-workloads-page')).toBeVisible();

  await page.locator('[data-id="globalSearchButton"]').click();
  const dialog = page.locator('mat-dialog-container:has(sm-global-search-dialog)');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('input[data-id="searchInputField"]')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  console.log(JSON.stringify({problems}));
  expect(problems).toEqual([]);
});

test('フェーズ3-6：パイプライン、データセット、レポートの主要表示と履歴', async ({page}) => {
  const problems = collectPageProblems(page);
  await loginViaClearmlWeb(page);
  const targets = [
    ['/pipelines', 'sm-pipelines-page'],
    [`/pipelines/${R.pipelineProject}/tasks`, 'sm-controllers'],
    [`/pipelines/${R.pipelineProject}/tasks/${R.pipelineRun}`, 'sm-pipeline-info'],
    ['/datasets', 'sm-open-datasets'],
    [`/datasets/simple/${R.datasetProject}/tasks`, 'sm-open-dataset-versions'],
    [`/datasets/simple/${R.datasetProject}/tasks/${R.datasetVersion}`, 'sm-open-dataset-version-info'],
    ['/reports', 'sm-reports-page'],
  ] as const;

  for (const [url, selector] of targets) {
    await page.goto(url);
    await closeTipIfShown(page);
    await expect(page.locator(selector)).toBeVisible();
  }

  await page.goBack();
  await expect(page).toHaveURL(/\/datasets\/simple\/.*\/tasks\/.*$/);
  await expect(page.locator('sm-open-dataset-version-info')).toBeVisible();
  await page.goForward();
  await expect(page).toHaveURL(/\/reports(?:\?.*)?$/);
  await expect(page.locator('sm-reports-page')).toBeVisible();
  console.log(JSON.stringify({problems}));
  expect(problems).toEqual([]);
});

test('フェーズ3-7：ワーカー、エンドポイント、設定、enterprise、404 の主要表示と直接 URL', async ({page}) => {
  const problems = collectPageProblems(page);
  await loginViaClearmlWeb(page);
  const targets = [
    ['/workers-and-queues/workers', 'sm-workers'],
    ['/workers-and-queues/queues', 'sm-queues'],
    ['/endpoints/active', 'sm-serving'],
    ['/settings/profile', 'sm-settings'],
    ['/settings/webapp-configuration', 'sm-settings'],
    ['/settings/workspace-configuration', 'sm-settings'],
    ['/settings/storage-credentials', 'sm-settings'],
    ['/enterprise', 'sm-resource-management'],
    ['/404', 'sm-not-found'],
    ['/no-such-route', 'sm-not-found'],
  ] as const;

  for (const [url, selector] of targets) {
    await page.goto(url);
    await closeTipIfShown(page);
    await expect(page.locator(selector)).toBeVisible();
  }

  await page.goto('/endpoints');
  await closeTipIfShown(page);
  const endpointPage = page.locator('sm-serving');
  console.log(JSON.stringify({
    endpointUrl: page.url(),
    endpointPageCount: await endpointPage.count(),
    problems
  }));
  await expect(endpointPage).toHaveCount(0);
  expect(problems).toEqual([]);
});

test('フェーズ3-5〜7：主要なヘッダーと固有画面の axe の critical・serious 違反を記録する', async ({page}) => {
  await loginViaClearmlWeb(page);
  const pages = [
    ['/dashboard', 'sm-header'],
    ['/reports', 'sm-reports-page'],
    ['/workers-and-queues/workers', 'sm-workers'],
    ['/endpoints/active', 'sm-serving'],
    ['/settings/profile', 'sm-settings'],
    ['/enterprise/resource-management', 'sm-enterprise'],
    ['/404', 'sm-not-found'],
  ] as const;
  const results = {};

  for (const [url, selector] of pages) {
    await page.goto(url);
    await closeTipIfShown(page);
    await expect(page.locator(selector)).toBeVisible();
    results[url] = simplifyAxe(await new AxeBuilder({page}).include(selector).analyze());
  }
  console.log(JSON.stringify(results));
});

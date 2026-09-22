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
  const clientErrors: string[] = [];
  page.on('pageerror', error => problems.push(`pageerror: ${error.message}`));
  page.on('console', message => {
    if (message.type() === 'error') {
      problems.push(`console: ${message.text()}`);
    }
  });
  page.on('response', response => {
    if (response.status() >= 400 && response.status() < 500) {
      clientErrors.push(`http ${response.status()}: ${response.url()}`);
    }
    if (response.status() >= 500) {
      problems.push(`http ${response.status()}: ${response.url()}`);
    }
  });
  return {problems, clientErrors};
}

test('実質差分の導線：サイドナビとモデル・データセットの Data Catalog リンクが遷移できる', async ({page}) => {
  const {problems, clientErrors} = collectPageProblems(page);
  await loginViaClearmlWeb(page);

  await page.goto(`/projects/${R.projectModelComparison}/models/${R.model}/general`);
  await closeTipIfShown(page);
  const modelLink = page.locator('[data-id="modelCatalogLink"]');
  await expect(modelLink).toBeVisible();
  await modelLink.click();
  await expect(page).toHaveURL(new RegExp(`/data-catalog/model/${R.model}(?:\\?|$)`));
  await expect(page.locator('sm-catalog-asset-detail-page')).toBeVisible();

  await page.goto(`/datasets/simple/${R.datasetProject}/tasks/${R.datasetVersion}`);
  await expect(page.locator('[data-id="datasetCatalogLink"]')).toBeVisible();
  await page.locator('[data-id="datasetCatalogLink"]').click();
  await expect(page).toHaveURL(new RegExp(`/data-catalog/dataset/${R.datasetVersion}(?:\\?|$)`));
  await expect(page.locator('sm-catalog-asset-detail-page')).toBeVisible();

  await page.locator('[data-id="qualityPipelineIcon"]').click();
  await expect(page).toHaveURL(/\/quality-pipeline(?:\?|$)/);
  await expect(page.locator('sm-quality-pipeline-page')).toBeVisible();

  await page.locator('[data-id="dataCatalogIcon"]').click();
  await expect(page).toHaveURL(/\/data-catalog(?:\?|$)/);
  await expect(page.locator('sm-data-catalog-page')).toBeVisible();
  console.log(JSON.stringify({problems, clientErrors}));
  // 新 feature の API は調査対象外のため、導線・画面生成までを確認対象にする。
});

test('モデルと比較：主要な直接 URL を開いて戻る・進む後も対応する画面を表示する', async ({page}) => {
  const {problems, clientErrors} = collectPageProblems(page);
  await loginViaClearmlWeb(page);
  const modelBase = `/projects/${R.projectModelComparison}/models/${R.model}`;
  const taskCompare = `/projects/${R.projectTraining}/compare-tasks;ids=${R.taskCompareA},${R.taskCompareB}`;
  const modelCompare = `/projects/${R.projectModelComparison}/compare-models;ids=${R.model},${R.modelB}`;
  const targets = [
    [`${modelBase}/general`, 'sm-model-info-general'],
    [`${modelBase}/network`, 'sm-model-info-network'],
    [`${modelBase}/labels`, 'sm-model-info-labels'],
    [`${modelBase}/metadata`, 'sm-model-info-metadata'],
    [`${modelBase}/tasks`, 'sm-model-info-experiments'],
    [`${modelBase}/scalars`, 'sm-model-info-scalars'],
    [`${taskCompare}/details`, 'sm-experiment-compare-details'],
    [`${taskCompare}/hyper-params/values`, 'sm-experiment-compare-params'],
    [`${taskCompare}/scalars/values`, 'sm-experiment-compare-metric-values'],
    [`${taskCompare}/metrics-plots`, 'sm-experiment-compare-plots'],
    [`${modelCompare}/models-details`, 'sm-model-compare-details'],
    [`${modelCompare}/network`, 'sm-experiment-compare-params'],
    [`${modelCompare}/scalars/graph`, 'sm-experiment-compare-scalar-charts']
  ] as const;

  for (const [url, selector] of targets) {
    await page.goto(url);
    await closeTipIfShown(page);
    await expect(page.locator(selector)).toBeVisible();
  }

  await page.goBack();
  await expect(page).toHaveURL(new RegExp('/compare-models;ids=.*?/network(?:\\?|$)'));
  await expect(page.locator('sm-experiment-compare-params')).toBeVisible();
  await page.goForward();
  await expect(page).toHaveURL(new RegExp('/compare-models;ids=.*?/scalars/graph(?:\\?|$)'));
  await expect(page.locator('sm-experiment-compare-scalar-charts')).toBeVisible();
  console.log(JSON.stringify({problems, clientErrors}));
  expect(problems.filter(problem => !problem.includes('Failed to load resource'))).toEqual([]);
});

test('モデルと比較：主要領域の axe の critical・serious 違反を記録する', async ({page}) => {
  await loginViaClearmlWeb(page);
  await page.goto(`/projects/${R.projectModelComparison}/models`);
  await closeTipIfShown(page);
  await expect(page.locator('sm-models-table')).toBeVisible();
  const models = await new AxeBuilder({page}).include('sm-models-table').analyze();

  await page.goto(`/projects/${R.projectTraining}/compare-tasks;ids=${R.taskCompareA},${R.taskCompareB}/details`);
  await expect(page.locator('sm-experiment-compare-details')).toBeVisible();
  const compare = await new AxeBuilder({page}).include('sm-experiments-compare').analyze();

  const simplify = results => results.violations
    .filter(violation => violation.impact === 'critical' || violation.impact === 'serious')
    .map(violation => ({
      id: violation.id,
      impact: violation.impact,
      targets: violation.nodes.map(node => node.target)
    }));
  console.log(JSON.stringify({models: simplify(models), compare: simplify(compare)}));
});

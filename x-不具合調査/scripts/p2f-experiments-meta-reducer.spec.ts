import {expect, Page, test} from '@playwright/test';
import {mockClearmlApi} from './helpers/mock-api';
import {navigateInApp} from './helpers/leak';

/**
 * フェーズ2 観点F：experiments の feature state が3箇所で provideState され、タスク一覧のルート（experiment-routes.ts の commonExperimentsProviders）が
 * metaReducers なしの reducer で置き換えるため、以後、比較モードの表示（scalars/plots）と選んだ指標が localStorage に保存されなくなること。
 * モック API。localStorage のキーは experiments.providers.ts の '_saved_experiment_state_'。
 */
const KEY = '_saved_experiment_state_';

async function dispatch(page: Page, action: Record<string, unknown>) {
  await page.evaluate(a => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    app.store.dispatch(a);
  }, action);
}

async function saved(page: Page) {
  return page.evaluate(k => JSON.parse(localStorage.getItem(k) ?? 'null')?.view?.tableCompareView ?? null, KEY);
}

async function storeCompareView(page: Page) {
  return page.evaluate(() => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    let s: any;
    app.store.subscribe((v: any) => s = v).unsubscribe();
    return s.experiments?.view?.tableCompareView ?? null;
  });
}

const setCompareView = (mode: 'scalars' | 'plots') => ({type: 'EXPERIMENTS_[set table compare view]', mode});

test('タスク一覧に入る前は保存され、入った後は保存されない', async ({page}) => {
  await mockClearmlApi(page);
  await page.goto('/dashboard');
  await page.waitForTimeout(2000);
  await page.evaluate(k => localStorage.removeItem(k), KEY);

  await dispatch(page, setCompareView('plots'));
  const beforeTasks = await saved(page);

  await navigateInApp(page, '/projects/bug-project/tasks');
  await page.locator('sm-experiments-table').waitFor();
  await page.waitForTimeout(1500);
  await dispatch(page, setCompareView('scalars'));
  const afterTasks = {store: await storeCompareView(page), saved: await saved(page)};

  // 再読み込みすると、最後に選んだ scalars ではなく、保存されていた plots に戻る
  await page.reload();
  await page.locator('sm-experiments-table').waitFor();
  await page.waitForTimeout(1500);
  const afterReload = await storeCompareView(page);

  console.log('タスク一覧に入る前に plots を選ぶ → 保存', beforeTasks);
  console.log('タスク一覧に入った後に scalars を選ぶ → Store', afterTasks.store, '保存', afterTasks.saved);
  console.log('再読み込み後の Store', afterReload);
  expect(beforeTasks).toBe('plots');
  expect(afterTasks).toEqual({store: 'scalars', saved: 'plots'});
  expect(afterReload).toBe('plots');
});

test('タスク一覧を直接開いた場合も保存されない', async ({page}) => {
  await mockClearmlApi(page);
  await page.goto('/projects/bug-project/tasks');
  await page.locator('sm-experiments-table').waitFor();
  await page.waitForTimeout(1500);
  await page.evaluate(k => localStorage.removeItem(k), KEY);
  await dispatch(page, setCompareView('plots'));
  const result = {store: await storeCompareView(page), saved: await saved(page)};
  console.log('タスク一覧で plots を選ぶ → Store', result.store, '保存', result.saved);
  expect(result).toEqual({store: 'plots', saved: null});
});

test('画面の操作：比較モードで Plots を選んでも保存されず、一覧を開き直して比較モードに入ると Scalars で開く', async ({page}) => {
  await mockClearmlApi(page);
  await page.goto('/projects/bug-project/tasks');
  await page.locator('sm-experiments-table').waitFor();
  await page.waitForTimeout(1500);
  await page.evaluate(k => localStorage.removeItem(k), KEY);

  // ヘッダーのチェックボックスで全件を選び、表示モードの切り替えで比較モード（compare）にして Plots を選ぶ
  const enterCompare = async () => {
    await page.locator('sm-experiments-table mat-checkbox.header-checkbox').click();
    await page.waitForTimeout(500);
    await page.locator('mat-button-toggle[data-id="compare"] button').click();
    await page.locator('mat-select[data-id="compareViewDropdown"]').waitFor();
    await page.waitForTimeout(1000);
  };
  await enterCompare();
  await page.locator('mat-select[data-id="compareViewDropdown"]').click();
  await page.locator('mat-option[data-id="plotsCompare"]').click();
  await page.waitForTimeout(1500);
  const afterSelect = {url: new URL(page.url()).pathname, store: await storeCompareView(page), saved: await saved(page)};

  // 新しいタブでプロジェクトの一覧を開き直した場合と同じく、比較モードの URL を持たずに読み込み直す
  await page.goto('/projects/bug-project/tasks');
  await page.locator('sm-experiments-table').waitFor();
  await page.waitForTimeout(1500);
  await enterCompare();
  const reenter = {url: new URL(page.url()).pathname, store: await storeCompareView(page),
    select: (await page.locator('mat-select[data-id="compareViewDropdown"]').textContent())?.trim()};

  console.log('Plots を選んだ後', JSON.stringify(afterSelect));
  console.log('一覧を開き直して比較モードに入った後', JSON.stringify(reenter));
  expect(afterSelect).toMatchObject({store: 'plots', saved: null});
  expect(reenter.url).toContain('/compare/scalars');
});

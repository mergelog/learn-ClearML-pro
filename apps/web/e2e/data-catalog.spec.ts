import {expect, test} from '@playwright/test';
import {CATALOG_MODEL, DATASET_TASK, mockDataCatalogApi} from './fixtures/data-catalog.fixture';

/**
 * 台帳が縦に繋がっていることだけを確かめる。
 *
 * **E2Eは上限に近い**（`test-pyramid.json` の `e2e.max`）。だからここには
 * 「下の層では確かめられないこと」だけを置く。絞り込みの組み立て方は
 * `data-catalog.query.spec.ts`、送る条件は `data-catalog-api.service.spec.ts`、
 * 表示の判断は各componentのspecにある。
 *
 * この1本が見るのは、**route → URLのクエリ → 一覧 → 詳細 → lineage** が
 * 1本に繋がっていることである。どこか1つでも外れると、単体は全部緑のまま
 * 画面だけが動かない。
 */
test.describe('data catalog', () => {
  test('opens, filters through the URL, and follows an asset to where it came from', async ({
    page,
  }) => {
    const calls = await mockDataCatalogApi(page);

    // 1. 条件つきURLで開く。絞り込みの操作を経由せずに一覧が絞られること。
    const response = await page.goto('/data-catalog?q=semiconductor-quality&kind=dataset');

    expect(response?.ok()).toBe(true);
    await expect(page.getByRole('heading', {name: 'Data catalog', level: 1})).toBeVisible();

    // 2. 条件は入力欄へ書き戻され、ClearMLへも渡っている。
    await expect(page.getByLabel('Name contains')).toHaveValue('semiconductor-quality');
    await expect.poll(() => calls.countOf('tasks.get_all_ex')).toBeGreaterThan(0);
    expect(calls.bodiesOf('tasks.get_all_ex')[0]['name']).toBe('semiconductor-quality');

    // 3. 種別を絞ったのでModelは引いていない。
    expect(calls.countOf('models.get_all_ex')).toBe(0);

    const table = page.locator('[data-id="catalogAssetsTable"]');
    await expect(table.getByRole('link', {name: DATASET_TASK.name})).toBeVisible();

    // 4. 資産を開くと詳細が出る。
    await table.getByRole('link', {name: DATASET_TASK.name}).click();

    await expect(page.getByRole('heading', {name: DATASET_TASK.name, level: 1})).toBeVisible();
    await expect(page.locator('[data-id="catalogAssetFacts"]')).toContainText('1.0.0');

    // 5. 出所が辿れている。ここがこの feature の存在理由である。
    const lineage = page.locator('[data-id="catalogLineage"]');
    await expect(lineage).toContainText('Dataset');
    await expect(lineage).toContainText('Run');
    await expect(lineage.getByRole('link', {name: CATALOG_MODEL.name})).toBeVisible();

    // 6. 深い情報は既存のClearML画面へ渡す。台帳は置き換えではない。
    await expect(page.locator('[data-id="catalogVendorLink"]')).toHaveAttribute(
      'href',
      `/datasets/simple/${DATASET_TASK.project.id}/tasks/${DATASET_TASK.id}`
    );
  });
});

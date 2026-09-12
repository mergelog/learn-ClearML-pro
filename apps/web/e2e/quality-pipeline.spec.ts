import {expect, test} from '@playwright/test';
import {
  CLONED_TASK_ID,
  FAILURE_MESSAGE,
  mockQualityPipelineApi,
} from './fixtures/quality-pipeline.fixture';

/** 走っている実行を読み直す間隔（`quality-pipeline.consts.ts`）。 */
const REFRESH_INTERVAL_MS = 5_000;

/**
 * この画面が「開けること」と「何を出すか」を確かめる。
 *
 * ここで確かめないのは、Pipelineが本当に走ることである。それは
 * `docs/_archive/runbooks/002_20260908_training_pipeline.md` の手順で確かめる範囲で、
 * ブラウザから起動すると1回あたり数分かかるためE2Eには載せない。
 *
 * ここで確かめるのは、ClearMLの応答をどう画面へ写すか、そして
 * 起動できる状態とできない状態が正しく出るかである。
 */
test.describe('quality pipeline page', () => {
  test('opens and explains what it is for', async ({page}) => {
    await mockQualityPipelineApi(page);

    const response = await page.goto('/quality-pipeline');

    expect(response?.ok()).toBe(true);
    await expect(page.getByRole('heading', {name: 'Quality pipeline', level: 1})).toBeVisible();
  });

  test('shows every part of the flow', async ({page}) => {
    await mockQualityPipelineApi(page);
    await page.goto('/quality-pipeline');

    await expect(page.getByRole('heading', {name: 'Start a run', level: 2})).toBeVisible();
    await expect(page.getByRole('heading', {name: 'Latest run', level: 2})).toBeVisible();
    await expect(page.getByRole('heading', {name: 'Evaluation', level: 2})).toBeVisible();
    await expect(page.getByRole('heading', {name: 'Serving now', level: 2})).toBeVisible();
  });

  test('asks for the dataset version before anything can be started', async ({page}) => {
    await mockQualityPipelineApi(page);
    await page.goto('/quality-pipeline');

    await expect(page.getByLabel('Dataset version')).toHaveValue('1.0.0');
  });

  test('can be started once there is a pipeline to clone from', async ({page}) => {
    await mockQualityPipelineApi(page);
    await page.goto('/quality-pipeline');

    await expect(page.getByRole('button', {name: 'Start'})).toBeEnabled();
  });

  test('will not start on a value that is not a version', async ({page}) => {
    // 押せてしまうと、Pipelineが実行時にDatasetを見つけられずに落ちるまで
    // 誤りが分からない。押す前に断る。
    await mockQualityPipelineApi(page);
    await page.goto('/quality-pipeline');

    await page.getByLabel('Dataset version').fill('abc');

    await expect(page.getByRole('button', {name: 'Start'})).toBeDisabled();
    await expect(page.getByText('Use a version like 1.0.0.')).toBeVisible();
  });

  test('is reachable from the side navigation', async ({page}) => {
    // URLを直接入力しないと到達できない画面は、無いのとほとんど変わらない。
    await mockQualityPipelineApi(page);
    await page.goto('/quality-pipeline');

    const link = page.getByRole('link', {name: 'Quality pipeline'});

    await expect(link).toBeVisible();
    await expect(link).toHaveClass(/active/);
  });

  test('refuses to start when nothing has been submitted yet', async ({page}) => {
    await mockQualityPipelineApi(page, {withTemplate: false});
    await page.goto('/quality-pipeline');

    // 押せてしまうと、何も起きないボタンになる。
    await expect(page.getByRole('button', {name: 'Start'})).toBeDisabled();
    await expect(page.getByText('No pipeline to start from.')).toBeVisible();
  });

  test('names the model that is serving right now', async ({page}) => {
    await mockQualityPipelineApi(page);
    await page.goto('/quality-pipeline');

    await expect(page.getByText('1.0.0-20260908T043015Z-abcdef01')).toBeVisible();
    await expect(page.getByText('the trial went well')).toBeVisible();
  });

  test('says so plainly when no model has been promoted', async ({page}) => {
    await mockQualityPipelineApi(page, {withProductionModel: false});
    await page.goto('/quality-pipeline');

    await expect(
      page.getByText('No model has been promoted to production yet.')
    ).toBeVisible();
  });

  test('shows the steps and the scores the run reported', async ({page}) => {
    await mockQualityPipelineApi(page);
    await page.goto('/quality-pipeline');

    // 開いた直後の実行はもう終わっているので、追跡は始まらない。
    // 指標は実行を読み直したときに読むため、Refreshで読み直しを起こす。
    await expect(page.getByText('No scores yet.')).toBeVisible();

    await page.getByRole('button', {name: 'Refresh'}).click();

    const steps = page.getByRole('table').filter({hasText: 'Steps'});
    await expect(steps.getByRole('row').filter({hasText: 'evaluate'})).toBeVisible();

    // ClearMLは指標を `指標 -> 系列 -> 値` の入れ子で返す。
    // splitごとの1行に組み直せていれば、ここに値が出る。
    const scores = page
      .getByRole('table')
      .filter({hasText: 'Validation decides which model is chosen'});

    await expect(scores.getByRole('row').filter({hasText: 'validation'})).toContainText('0.81');
    await expect(scores.getByRole('row').filter({hasText: 'validation'})).toContainText('0.72');
    await expect(scores.getByRole('row').filter({hasText: 'test'})).toContainText('0.79');
    await expect(page.getByText('No scores yet.')).toBeHidden();
  });

  test('says the clone source and the latest run are the same task', async ({page}) => {
    // Python側はPipelineを走らせるたびに同じ名前で制御役のTaskを作るので、
    // 複製元と直近の実行が同じ1つのTaskになることがある。それを隠さない。
    await mockQualityPipelineApi(page);
    await page.goto('/quality-pipeline');

    await expect(page.getByText('This is the same task as the latest run below')).toBeVisible();
  });

  test('can always be reloaded', async ({page}) => {
    await mockQualityPipelineApi(page);
    await page.goto('/quality-pipeline');

    await expect(page.getByRole('button', {name: 'Reload'})).toBeEnabled();
  });

  test('clones the pipeline and puts the clone on the queue when started', async ({page}) => {
    // 画面の見た目だけでは「起動した」と言えない。ClearML上で複製され、
    // Queueへ入って初めて誰かが拾う。送った要求そのものを見る。
    const calls = await mockQualityPipelineApi(page);
    await page.goto('/quality-pipeline');

    await page.getByLabel('Dataset version').fill('2.0.0');
    await page.getByRole('button', {name: 'Start'}).click();

    await expect.poll(() => calls.countOf('tasks.enqueue')).toBe(1);

    const cloned = calls.bodyOf('tasks.clone');
    const hyperparams = cloned['new_task_hyperparams'] as Record<
      string,
      Record<string, {value: string}>
    >;

    expect(hyperparams['Dataset']['dataset_version'].value).toBe('2.0.0');

    // 複製しただけでは走らない。複製したそのTaskがQueueへ入っていること。
    expect(calls.bodyOf('tasks.enqueue')).toMatchObject({
      task: CLONED_TASK_ID,
      queue_name: 'semiconductor-pipeline',
    });
  });

  test('says what went wrong when ClearML cannot answer', async ({page}) => {
    // 黙って空の画面を出すと、まだ何も無いのか繋がっていないのかが分からない。
    await mockQualityPipelineApi(page, {failing: ['models.get_all_ex']});
    await page.goto('/quality-pipeline');

    await expect(page.getByRole('alert')).toHaveText(FAILURE_MESSAGE);
  });

  test('stops reading the run back once it has finished', async ({page}) => {
    // 終わった実行を叩き続けても状態は変わらない。実行のたびに積み上がる
    // 問い合わせを止められていることを、要求の回数で見る。
    const calls = await mockQualityPipelineApi(page, {
      latestRunStatus: 'in_progress',
      refreshedRunStatus: 'completed',
    });
    await page.goto('/quality-pipeline');

    await expect(page.locator('[data-status="completed"]').first()).toBeVisible();

    const readsAfterFinishing = calls.countOf('tasks.get_by_id_ex');
    await page.waitForTimeout(REFRESH_INTERVAL_MS * 2);

    expect(calls.countOf('tasks.get_by_id_ex')).toBe(readsAfterFinishing);
  });

  test('keeps reading the run back while it is still going', async ({page}) => {
    // 止まる側だけを確かめると、そもそも読み直していなくてもテストは通る。
    const calls = await mockQualityPipelineApi(page, {latestRunStatus: 'in_progress'});
    await page.goto('/quality-pipeline');

    await expect.poll(() => calls.countOf('tasks.get_by_id_ex'), {
      timeout: REFRESH_INTERVAL_MS * 3,
    }).toBeGreaterThan(1);
  });
});

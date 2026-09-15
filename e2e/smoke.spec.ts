import {expect, test} from '@playwright/test';
import {
  CANDIDATE_MODEL_VERSION,
  CANDIDATE_RUN,
  DATASET_NAME,
  DATASET_VERSION,
  DATASET_VERSIONS_URL,
  MODELS_URL,
  MODEL_NAME,
  PIPELINE_QUEUE,
  PROMOTED_MODEL_VERSION,
  SERVING_RUN,
  TRAINING_QUEUE,
  compareUrl,
  mockSmokeApi,
} from './fixtures/smoke.fixture';

/**
 * 1本の流れが縦に繋がっているかだけを見る。
 *
 * Dataset登録 → Queue学習 → 比較 → 昇格 → 推論への受け渡し。5つの節目を
 * それぞれ1件で見る。**業務ルールはここで確かめない**。桁の書式も、しきい値も、
 * 失敗時にどちらへ倒すかも、下の層に置いてある
 * （`docs/_archive/adr/005_20260911_test_pyramid.md`）。ここに足すと、同じ判断が
 * 2か所に書かれて、遅いほうだけが残る。
 *
 * 最後の節目が「推論そのもの」ではなく「受け渡し点」なのは、画面が
 * 推論サービスを呼んでいないからである。消費者は runbook 004 の curl と
 * `services/tests` だけで、ブラウザからは到達できない。画面が言える最後のことは
 * **どのモデルのどのバージョンが提供されるか**であり、それが
 * `prediction_api` の読むものと同じ文字列かどうかが繋がりの証拠になる。
 * 推論が実際に答えるかは `services/tests` と `scripts/serving-smoke.sh` が見る。
 */
test.describe('smoke: from dataset to serving', () => {
  test.beforeEach(async ({page}) => {
    await mockSmokeApi(page);
  });

  test('1. the dataset version that training will read is registered', async ({page}) => {
    await page.goto(DATASET_VERSIONS_URL);

    await expect(page.getByText(`${DATASET_NAME} v${DATASET_VERSION}`).first()).toBeVisible();

    // 学習の実行がここに並ぶなら、一覧が「Datasetの版」を引けていない。
    // 版を選ぶ画面で学習が選べてしまうと、何で学習したかが追えなくなる。
    await expect(page.getByText(CANDIDATE_RUN.name)).toHaveCount(0);
  });

  test('2. the training run waits on a queue an agent is listening to', async ({page}) => {
    // Queueに入っただけでは走らない。拾うAgentが繋がっている行に入っていること。
    await page.goto('/workers-and-queues/queues');

    const training = page.getByRole('row').filter({hasText: TRAINING_QUEUE});
    const pipeline = page.getByRole('row').filter({hasText: PIPELINE_QUEUE});

    await expect(training).toContainText(CANDIDATE_RUN.name);
    // 別のQueueにも同じ実行が出るなら、行と実行の対応が取れていない。
    await expect(pipeline).not.toContainText(CANDIDATE_RUN.name);
  });

  test('3. the candidate and the serving run are compared side by side', async ({page}) => {
    await page.goto(compareUrl([CANDIDATE_RUN.id, SERVING_RUN.id]));

    // 実行は毎回同じ名前で作られるので、名前では区別できない。並んだのが
    // 本当にこの2つかどうかは、行が指しているTaskのidで見る。
    await expect(page.locator(`a[href$="/tasks/${CANDIDATE_RUN.id}"]`)).toBeVisible();
    await expect(page.locator(`a[href$="/tasks/${SERVING_RUN.id}"]`)).toBeVisible();

    // 指標の値そのものはここで見ない。どちらが良いかの読み方は評価側
    // （ml-unit）と画面側（web-unit）に置いてある。ここが答えるのは
    // 「比較へ辿り着けるか」だけである。
  });

  test('4. exactly one model carries the production stage', async ({page}) => {
    await page.goto(MODELS_URL);

    // 候補（`stage:staging`）も同じ名前で並んでいる。昇格したものが
    // 1つに定まっていなければ、推論サービスはどちらを読むか決められない。
    // 一覧そのものを見る。絞り込みのメニューにも同じ文字列が出るので、
    // 画面全体から数えると「並んでいるモデル」を数えたことにならない。
    const table = page.locator('sm-models-table');

    await expect(table.getByText(MODEL_NAME).first()).toBeVisible();
    await expect(table.getByText('stage:production')).toHaveCount(1);
    await expect(table.getByText('stage:staging')).toHaveCount(1);
  });

  test('5. the promoted model version is what the screen says is serving', async ({page}) => {
    await page.goto('/quality-pipeline');

    await expect(page.getByText(PROMOTED_MODEL_VERSION)).toBeVisible();

    // 候補（`stage:staging`）のバージョンが出るなら、画面は昇格したものを
    // 選べていない。推論サービスは `stage:production` しか読まないので、
    // 画面とサービスが別のモデルを指すことになる。
    await expect(page.getByText(CANDIDATE_MODEL_VERSION)).toHaveCount(0);
  });
});

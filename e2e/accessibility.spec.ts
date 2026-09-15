import AxeBuilder from '@axe-core/playwright';
import {expect, test} from '@playwright/test';
import {FAILURE_MESSAGE, mockQualityPipelineApi} from './fixtures/quality-pipeline.fixture';
import {mockDataCatalogApi} from './fixtures/data-catalog.fixture';

/**
 * 自作画面が、支援技術から使える形で組み上がっているかを見る。
 *
 * 対象は自作の `sm-quality-pipeline-page` の中だけである。取り込んだ
 * ClearML Web の外枠（左のナビ・ヘッダ）には違反が残っているが、そこは
 * 凍結領域で、直すと取り込み直しのたびに消える（`web-boundaries.json` と
 * 同じ扱い）。**自分たちが書いた範囲は baseline を作らず0件で固定する**
 * （Stage 1-B3 と同じ決め方）。
 *
 * 規則そのもの（属性の付け方・要素の選び方）は lint と単体テストでも見られる。
 * ここへ置くのは、**画面として組み上がったときにだけ分かること**である。
 * 部品ごとには正しくても、重なった結果として名前が消える・読み上げ順が崩れる・
 * キーボードで辿り着けない、という壊れ方はここでしか見えない。
 */

/** 自作画面の根。ここから外は凍結領域なので対象にしない。 */
const OWN_SCREEN = 'sm-quality-pipeline-page';
const CATALOG_SCREEN = 'sm-data-catalog-page';

async function violationsOf(page: Parameters<typeof mockQualityPipelineApi>[0], screen: string) {
  const results = await new AxeBuilder({page}).include(screen).analyze();

  // 何件あったかだけでは直せない。どの規則がどの要素で落ちたかまで出す。
  return results.violations.map(
    (violation) =>
      `${violation.impact}: ${violation.id} (${violation.nodes.length}) ` +
      violation.nodes.map((node) => node.target.join(' ')).join(', ')
  );
}

const violationsOfOwnScreen = (page: Parameters<typeof mockQualityPipelineApi>[0]) =>
  violationsOf(page, OWN_SCREEN);

test.describe('accessibility of the screens we wrote', () => {
  test('the quality pipeline screen has no violations', async ({page}) => {
    await mockQualityPipelineApi(page);
    await page.goto('/quality-pipeline');
    await page.getByRole('heading', {name: 'Quality pipeline', level: 1}).waitFor();

    expect(await violationsOfOwnScreen(page)).toEqual([]);
  });

  test('the empty screen has no violations either', async ({page}) => {
    // 何も無い状態は別の文言と別の要素で描かれる。埋まった状態だけを見ると、
    // 空のときにだけ出る「名前の無いボタン」を見逃す。
    await mockQualityPipelineApi(page, {withTemplate: false, withProductionModel: false});
    await page.goto('/quality-pipeline');
    await page.getByText('No model has been promoted to production yet.').waitFor();

    expect(await violationsOfOwnScreen(page)).toEqual([]);
  });

  test('what went wrong reaches assistive technology', async ({page}) => {
    // 目で見えるだけでは足りない。読み上げる側へ届かない失敗の説明は、
    // 画面を見ていない利用者にとって「黙って空になった」のと同じである。
    await mockQualityPipelineApi(page, {failing: ['models.get_all_ex']});
    await page.goto('/quality-pipeline');

    await expect(page.getByRole('alert')).toHaveText(FAILURE_MESSAGE);
    expect(await violationsOfOwnScreen(page)).toEqual([]);
  });

  test('the data catalog screen has no violations', async ({page}) => {
    // 台帳は入力欄が多い（検索・種別・タグ・期間）。ラベルと入力の結び付きが
    // 外れていても目では分からず、組み上がった画面でしか見えない。
    await mockDataCatalogApi(page);
    await page.goto('/data-catalog');
    await page.getByRole('heading', {name: 'Data catalog', level: 1}).waitFor();

    expect(await violationsOf(page, CATALOG_SCREEN)).toEqual([]);
  });

  test('the run can be started with the keyboard alone', async ({page}) => {
    // 起動はこの画面の唯一の操作である。マウスでしか押せないなら、
    // 規則に適合していても使えない。
    const calls = await mockQualityPipelineApi(page);
    await page.goto('/quality-pipeline');

    const version = page.getByLabel('Dataset version');
    await version.focus();
    await version.fill('2.0.0');

    // 版の入力の次に来る操作可能な要素が起動でなければ、辿り着くまでに
    // 何度Tabを押せばよいかは画面を見ないと分からない。
    await page.keyboard.press('Tab');
    await expect(page.getByRole('button', {name: 'Start'})).toBeFocused();

    await page.keyboard.press('Enter');

    await expect.poll(() => calls.countOf('tasks.enqueue')).toBe(1);
  });
});

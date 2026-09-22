import type {Page} from '@playwright/test';

/** 起動中の Compose プロジェクト learn01-clearml の標準画面。 */
export const CLEARML_WEB = 'http://127.0.0.1:8080';

/** 既存のユーザ。名前だけでログインする（basic 認証は無効な構成）。 */
export const LOGIN_USER = 'testerX';

/**
 * 8080 の標準画面でログインし、同じホスト名の 4200 で使える cookie を得る。
 * 4200 のログイン画面は使えない設計（x-todo.md）。
 */
export async function loginViaClearmlWeb(page: Page): Promise<void> {
  await page.goto(`${CLEARML_WEB}/login`);
  const name = page.locator('input[formcontrolname="name"]');
  await name.waitFor();
  await name.fill(LOGIN_USER);
  await page.getByRole('button', {name: /start/i}).click();
  await page.waitForURL(url => !url.pathname.startsWith('/login'), {timeout: 30_000});
}

/** 調査で使う実データの ID（2026-09-22 時点の learn01-clearml）。 */
export const REAL = {
  projectBaseline: '29d78da443cd471a8d4c7a1b2e0d130d',
  projectTraining: '37d14cf85a97476489b532343bb9d0e6',
  projectModelComparison: '86e7f25d52984336881b8f139219accc',
  projectPipelineTop: '3a4f2b5eeff6444eb5f21283df6cab8e',
  pipelineProject: 'bb855ced28a54f0495f89416fe8c4f7a',
  pipelineRun: 'a5ed88bc5479463a8c1cdfad2d8f5f55',
  datasetProject: '6c5385bf7f9644a8bb766c6800889811',
  datasetVersion: '3c913ea3f35549199d94e98cb3c64917',
  taskBaselineV1: '824c1d1e07694a69ae7d7abc0d169be2',
  taskBaselineV2: 'feeaa915ed4f435aaea2e2a2a5410fa7',
  taskCompareA: 'c97f6b21f565488f9850a1d5d20f6897',
  taskCompareB: 'c186a154c9cb4979bdbbe6a6d2f64826',
  model: '0cdc0b3dfc9e44bea922f8680e2433a4',
  modelB: 'abec7c0527e54570a1295fee2d5b61af',
  queue: 'e46302bdc7934a638b6f2046bb55fbad'
} as const;

/**
 * 調査専用プロジェクト `zz-不具合調査`（ユーザの了承を得て 2026-09-22 に投入）。
 * すべて draft（created）の training タスク。書き込みを伴う再現はここで行う。
 */
export const INVESTIGATION = {
  project: '6f4a8bb5a0de46dea535e475fa9bf844',
  taskA: '20e617a143ee401a95f6cea9495436f1',
  taskB: 'e6242b9fd4ab4a9dbf12efc89c7f7bf2',
  taskLongJapanese: '3ad9589146af42a78e10639cf2a81c85',
  taskEmoji: '75c1915c64b54aafb8f21b3bd7348fae',
  taskHtmlChars: 'b89dafe364b84b129024094e2e93be4a',
  taskFullWidthSpace: 'a0f3674f0dae42d09d1b07bd7d55e52f'
} as const;

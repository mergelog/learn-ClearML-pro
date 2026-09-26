import {defineConfig, devices} from '@playwright/test';
import {resolve} from 'node:path';

/**
 * 不具合調査用の Playwright 設定。
 *
 * e2e/ の設定とは別にしてある。調査用のスクリプトを e2e/ に混ぜないためと、
 * webServer を持たせないためである。開発サーバ（ng serve --host 0.0.0.0 --port 4200）は
 * 先に起動しておく。`pnpm start` は src/credentials.json を書き換えるため使わない。
 *
 * 実行例:
 *   npx playwright test -c x-不具合調査/scripts/playwright.config.ts 00-route-crawl
 */
export default defineConfig({
  testDir: '.',
  outputDir: '../../test-results/bug-investigation',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:4200',
    // WSL の Chromium には和文フォントが無いため、Windows のメイリオ・游ゴシックを読ませる（fontconfig/fonts.conf）
    launchOptions: {
      env: {...process.env, FONTCONFIG_FILE: resolve('x-不具合調査/scripts/fontconfig/fonts.conf')}
    },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  },
  projects: [
    {
      name: 'chromium',
      use: {...devices['Desktop Chrome']}
    }
  ]
});

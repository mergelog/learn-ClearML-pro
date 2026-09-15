import {defineConfig, devices} from '@playwright/test';

const isCi = Boolean(process.env['CI']);

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  fullyParallel: true,
  forbidOnly: isCi,
  retries: 0,
  reporter: [
    ['list'],
    ['junit', {outputFile: 'reports/e2e/playwright.xml'}],
    ['html', {outputFolder: 'playwright-report', open: 'never'}]
  ],
  use: {
    baseURL: 'http://127.0.0.1:4200',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure'
  },
  webServer: {
    command: 'corepack pnpm start',
    url: 'http://127.0.0.1:4200',
    reuseExistingServer: !isCi,
    // CI では `.angular` のキャッシュが無い状態から dev server を立てるため、
    // 手元よりも初回ビルドに時間がかかる。待ち時間が足りずに落ちると、
    // 「E2E が失敗した」と読める形で「まだ立ち上がっていない」が報告される。
    timeout: isCi ? 180_000 : 120_000
  },
  projects: [
    {
      name: 'chromium',
      use: {...devices['Desktop Chrome']}
    }
  ]
});

#!/usr/bin/env node

/**
 * Generates `src/credentials.json`, the runtime credentials the webapp fetches
 * on start-up (see `BaseLoginService.initCredentials`).
 *
 * The file is deliberately untracked: it is written on every `start`/`build`
 * from the same sources the Python tooling uses, so an API key never has to be
 * committed to the repository.
 *
 * Resolution order:
 *   1. `CLEARML_API_ACCESS_KEY` / `CLEARML_API_SECRET_KEY`
 *   2. the `api.credentials` block of the ClearML SDK configuration file
 *   3. blank credentials, which leave the webapp on its unauthenticated path
 *
 * The same rule as `scripts/clearml-run.sh` applies to step 1: the root
 * `web:*` scripts run through it, so the environment variables only survive
 * when `CLEARML_ALLOW_ENV_CREDENTIALS=1` says they were meant.
 *
 * Step 2 falls back to this repository's `./clearml.conf`, never to
 * `~/clearml.conf`. The home directory holds the configuration of another
 * project on this host, and reading it here would serve the webapp with
 * someone else's keys — a failure that shows up as an unexplained 401.
 */

import {existsSync, readFileSync, writeFileSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const PROJECT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const REPOSITORY_ROOT = resolve(PROJECT_ROOT, '..', '..');
const OUTPUT_PATH = join(PROJECT_ROOT, 'src', 'credentials.json');
const DEFAULT_CONFIGURATION_PATH = join(REPOSITORY_ROOT, 'clearml.conf');

const DEFAULT_COMPANY_ID = 'd1bd92a3b039400cbafc60a7a5b1e52b';

const readEnvironmentCredentials = () => {
  const accessKey = (process.env.CLEARML_API_ACCESS_KEY ?? '').trim();
  const secretKey = (process.env.CLEARML_API_SECRET_KEY ?? '').trim();

  if (!accessKey && !secretKey) {
    return null;
  }

  if (!accessKey || !secretKey) {
    throw new Error('CLEARML_API_ACCESS_KEY and CLEARML_API_SECRET_KEY must be set together');
  }

  return {accessKey, secretKey, source: 'environment'};
};

const configurationFilePath = () =>
  process.env.CLEARML_CONFIG_FILE?.trim() || DEFAULT_CONFIGURATION_PATH;

const readConfigurationFileCredentials = () => {
  const path = configurationFilePath();
  if (!existsSync(path)) {
    return null;
  }

  const contents = readFileSync(path, 'utf8');
  const accessKey = contents.match(/"access_key"\s*[:=]\s*"([^"]+)"/)?.[1];
  const secretKey = contents.match(/"secret_key"\s*[:=]\s*"([^"]+)"/)?.[1];

  if (!accessKey || !secretKey) {
    return null;
  }

  return {accessKey, secretKey, source: path};
};

const resolveCredentials = () =>
  readEnvironmentCredentials() ??
  readConfigurationFileCredentials() ?? {
    accessKey: '',
    secretKey: '',
    source: null
  };

const main = () => {
  const credentials = resolveCredentials();

  writeFileSync(
    OUTPUT_PATH,
    `${JSON.stringify(
      {
        userKey: credentials.accessKey,
        userSecret: credentials.secretKey,
        companyID: (process.env.CLEARML_WEB_COMPANY_ID ?? '').trim() || DEFAULT_COMPANY_ID
      },
      null,
      2
    )}\n`,
    'utf8'
  );

  if (credentials.source === null) {
    console.warn(
      'credentials.json: 認証情報が見つかりませんでした。' +
        'CLEARML_API_ACCESS_KEY / CLEARML_API_SECRET_KEY を設定するか、' +
        `${configurationFilePath()} を用意してください。`
    );
    return;
  }

  console.log(`credentials.json: ${credentials.source} の認証情報を書き出しました。`);
};

try {
  main();
} catch (error) {
  console.error(`credentials.json の生成に失敗しました: ${error.message}`);
  process.exit(1);
}

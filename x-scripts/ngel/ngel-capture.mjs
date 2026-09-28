import { readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { writeTransformedHtml } from './ng-el.mjs';

const SCRIPT_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const DEFAULT_TIMEOUT = 15000;
const DEFAULT_SETTLE = 500;
const CDP_PROBE_TIMEOUT = 2000;
const IGNORED_PAGE_SCHEMES = ['devtools://', 'chrome://', 'chrome-extension://', 'about:'];

// 引数の指定順がそのまま操作順になるので、ステップは配列で保持する。
const STEP_ARITY = new Map([
  ['--goto', 1],
  ['--click', 1],
  ['--hover', 1],
  ['--press', 1],
  ['--wait', 1],
  ['--fill', 2],
]);
const VALUE_ARITY = new Map([
  ['--cdp', 1],
  ['--page', 1],
  ['--label', 1],
  ['--select', 1],
  ['--settle', 1],
  ['--timeout', 1],
  ['--out-dir', 1],
  ['--raw', 1],
]);

export class UsageError extends Error {}
export class ConnectionError extends Error {}
export class TargetError extends Error {}

export function parseArguments(argv) {
  const steps = [];
  const options = { keep: false, reuse: false, settle: DEFAULT_SETTLE, timeout: DEFAULT_TIMEOUT };

  for (let index = 0; index < argv.length; index++) {
    const flag = argv[index];
    const arity = STEP_ARITY.get(flag) ?? VALUE_ARITY.get(flag) ?? 0;
    const values = argv.slice(index + 1, index + 1 + arity);
    if (values.length !== arity || values.some((value) => value === undefined)) {
      throw new UsageError(`Missing value for ${flag}`);
    }
    index += arity;

    if (STEP_ARITY.has(flag)) {
      steps.push({ kind: flag.slice(2), values });
      continue;
    }

    switch (flag) {
      case '--cdp': options.cdp = values[0]; break;
      case '--page': options.page = values[0]; break;
      case '--label': options.label = values[0]; break;
      case '--select': options.select = values[0]; break;
      case '--out-dir': options.outDirectory = values[0]; break;
      case '--raw': options.raw = values[0]; break;
      case '--settle': options.settle = toPositiveNumber(flag, values[0]); break;
      case '--timeout': options.timeout = toPositiveNumber(flag, values[0]); break;
      case '--keep': options.keep = true; break;
      case '--reuse': options.reuse = true; break;
      default: throw new UsageError(`Unknown option: ${flag}`);
    }
  }

  if (!options.label) {
    throw new UsageError('--label <text> is required');
  }
  return { steps, options };
}

function toPositiveNumber(flag, value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) {
    throw new UsageError(`${flag} expects a non-negative number, got ${value}`);
  }
  return number;
}

async function defaultGatewayAddress() {
  // WSL から Windows 側の Chrome を見るときのフォールバック。
  const table = await readFile('/proc/net/route', 'utf8').catch(() => '');
  const gateway = table
    .split('\n')
    .slice(1)
    .map((line) => line.split(/\s+/))
    .find((columns) => columns[1] === '00000000' && columns[2] && columns[2] !== '00000000')?.[2];
  if (!gateway) return undefined;

  const octets = gateway.match(/../g).reverse().map((byte) => parseInt(byte, 16));
  return octets.join('.');
}

export async function resolveCdpEndpoint(explicit) {
  const gateway = explicit ? undefined : await defaultGatewayAddress();
  const candidates = explicit
    ? [explicit]
    : [process.env.NGEL_CDP_URL, 'http://127.0.0.1:9222', gateway && `http://${gateway}:9222`].filter(Boolean);
  const failures = [];

  for (const candidate of candidates) {
    try {
      const response = await fetch(new URL('/json/version', candidate), {
        signal: AbortSignal.timeout(CDP_PROBE_TIMEOUT),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const { Browser: browser } = await response.json();
      return { endpoint: candidate, browser };
    } catch (error) {
      failures.push(`${candidate}: ${error.message}`);
    }
  }

  throw new ConnectionError(
    `No Chrome DevTools endpoint reachable.\n${failures.map((failure) => `  ${failure}`).join('\n')}\n` +
      'Start Chrome with --remote-debugging-port=9222, or pass --cdp <url>.',
  );
}

function appPages(context) {
  return context.pages().filter((page) => !IGNORED_PAGE_SCHEMES.some((scheme) => page.url().startsWith(scheme)));
}

export function pickAppPage(pages, hint) {
  const matching = hint ? pages.filter((page) => page.url().includes(hint)) : pages;
  if (matching.length === 0) {
    const known = pages.length === 0 ? 'none' : pages.map((page) => page.url()).join(', ');
    throw new TargetError(`No page matches ${hint ? `--page ${hint}` : 'an http(s) URL'}. Open pages: ${known}`);
  }
  return matching[0];
}

async function runStep(page, step, { timeout, baseUrl }) {
  const [first, second] = step.values;

  switch (step.kind) {
    case 'goto':
      await page.goto(new URL(first, baseUrl).href, { timeout, waitUntil: 'domcontentloaded' });
      return;
    case 'click':
      await page.locator(first).first().click({ timeout });
      return;
    case 'hover':
      await page.locator(first).first().hover({ timeout });
      return;
    case 'fill':
      await page.locator(first).first().fill(second, { timeout });
      return;
    case 'press':
      await page.keyboard.press(first);
      return;
    case 'wait':
      if (/^\d+$/.test(first)) {
        await page.waitForTimeout(Number(first));
      } else {
        await page.locator(first).first().waitFor({ state: 'visible', timeout });
      }
      return;
    default:
      throw new UsageError(`Unsupported step: ${step.kind}`);
  }
}

async function captureHtml(page, selector, timeout) {
  if (!selector) {
    return page.evaluate(() => document.documentElement.outerHTML);
  }

  const locator = page.locator(selector).first();
  await locator.waitFor({ state: 'attached', timeout });
  return locator.evaluate((element) => element.outerHTML);
}

export async function capture({ steps, options }) {
  const { endpoint, browser: browserVersion } = await resolveCdpEndpoint(options.cdp);
  const browser = await chromium.connectOverCDP(endpoint);
  const notes = [`cdp: ${endpoint} (${browserVersion})`];
  let openedPage;

  try {
    const context = browser.contexts()[0];
    if (!context) throw new TargetError('The connected browser exposes no browser context.');

    const existing = pickAppPage(appPages(context), options.page);
    const baseUrl = existing.url();
    notes.push(`base: ${baseUrl}`);

    // 既存タブと同じオリジンの新規タブなら Cookie と localStorage を共有するので、再ログインは要らない。
    const page = options.reuse ? existing : (openedPage = await context.newPage());
    notes.push(options.reuse ? 'target: existing tab (reused)' : 'target: new tab');
    page.setDefaultTimeout(options.timeout);

    if (!options.reuse && !steps.some((step) => step.kind === 'goto')) {
      steps = [{ kind: 'goto', values: [baseUrl] }, ...steps];
    }

    for (const step of steps) {
      await runStep(page, step, { timeout: options.timeout, baseUrl });
      notes.push(`step: ${step.kind} ${step.values.join(' ')}`);
    }

    if (options.settle > 0) await page.waitForTimeout(options.settle);
    notes.push(`url: ${page.url()}`);

    const html = await captureHtml(page, options.select, options.timeout);
    if (options.raw) {
      await writeFile(resolve(SCRIPT_DIRECTORY, options.raw), html);
      notes.push(`raw: ${resolve(SCRIPT_DIRECTORY, options.raw)}`);
    }

    const outputDirectory = resolve(SCRIPT_DIRECTORY, options.outDirectory ?? 'x-ngel');
    const outputPath = await writeTransformedHtml(html, outputDirectory, { label: options.label });
    return { outputPath, notes };
  } finally {
    if (openedPage && !options.keep) await openedPage.close().catch(() => {});
    // CDP 接続では close() が切断で、ユーザの Chrome は落ちない。
    await browser.close().catch(() => {});
  }
}

const USAGE = `Usage: node x-scripts/ngel/ngel-capture.mjs --label <text> [options]

Connection
  --cdp <url>           DevTools endpoint (default: $NGEL_CDP_URL, http://127.0.0.1:9222, WSL gateway)
  --page <substring>    pick the open tab whose URL contains this, as the origin to work in
  --reuse               drive that open tab instead of opening a new one
  --keep                leave the opened tab open

Steps (applied in the order given)
  --goto <url|path>     navigate (a path resolves against the picked tab's URL)
  --click <selector>    click the first match
  --hover <selector>    hover the first match
  --fill <selector> <value>
  --press <key>         keyboard.press, e.g. Escape
  --wait <ms|selector>  sleep, or wait until the selector is visible

Capture
  --select <selector>   capture that element instead of the whole document
  --settle <ms>         wait before capturing (default ${DEFAULT_SETTLE})
  --timeout <ms>        per-step timeout (default ${DEFAULT_TIMEOUT})
  --out-dir <path>      output directory (default x-ngel)
  --raw <path>          also save the untransformed HTML`;

async function main() {
  const { steps, options } = parseArguments(process.argv.slice(2));
  const { outputPath, notes } = await capture({ steps, options });
  for (const note of notes) console.error(note);
  console.log(outputPath);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    if (error instanceof UsageError) console.error(`\n${USAGE}`);
    process.exitCode = error instanceof ConnectionError ? 2
      : error instanceof TargetError ? 4
      : error instanceof UsageError ? 3
      : 1;
  });
}

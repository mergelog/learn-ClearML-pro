import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { JSDOM } from 'jsdom';
import { toFileLabel, transformHtml, writeTransformedHtml } from './ng-el.mjs';

test('removes div wrappers while preserving descendants, attributes, comments, and text', () => {
  const source = '<!doctype html><html><body><sm-parent id="a"><div class="wrapper"><!--slot--><unknown-card data-x="a&amp;b"><div><button aria-label="Go">A &amp; B</button></div></unknown-card></div></sm-parent></body></html>';
  const output = transformHtml(source);
  const document = new JSDOM(output).window.document;

  assert.match(output, /^<!--\nhtml\/\n├── head\n└── body\n    └── sm-parent \[ns\]\n        └── unknown-card\n-->\n<!DOCTYPE html>\n<html>/);
  assert.match(output, /<sm-parent id="a">\n\s+<!--slot-->\n\s+<unknown-card/);
  assert.equal(document.querySelectorAll('div').length, 0);
  assert.equal(document.querySelector('sm-parent').firstElementChild.tagName, 'UNKNOWN-CARD');
  assert.equal(document.querySelector('unknown-card').getAttribute('data-x'), 'a&b');
  assert.equal(document.querySelector('button').getAttribute('aria-label'), 'Go');
  assert.match(document.querySelector('button').textContent, /A & B/);
  assert.equal(document.querySelectorAll('button').length, 1);
});

test('accepts a selected element, removes style content, and preserves template descendants', () => {
  const source = '<sm-root><div><p>Hello <b>world</b>!</p><template><div><new-widget x="1"></new-widget></div></template><style>.a > .b { color: red }</style></div></sm-root>';
  const output = transformHtml(source);
  const fragment = JSDOM.fragment(output);

  assert.equal(fragment.querySelectorAll('div').length, 0);
  assert.match(fragment.querySelector('p').textContent, /Hello[\s\S]*world[\s\S]*!/);
  assert.equal(fragment.querySelector('template').content.querySelectorAll('div').length, 0);
  assert.equal(fragment.querySelector('template').content.querySelector('new-widget').getAttribute('x'), '1');
  assert.equal(fragment.querySelectorAll('style').length, 0);
  assert.doesNotMatch(output, /\.a > \.b \{ color: red \}/);
});

test('keeps the component path readable when a document container has text', () => {
  const source = '<html><body><sm-root><sm-shell><sm-card></sm-card></sm-shell></sm-root><div>footer text</div></body></html>';
  const output = transformHtml(source);

  assert.match(output, /<body>\n    <sm-root>\n      <sm-shell>\n        <sm-card><\/sm-card>/);
  assert.match(output, /footer text/);
});

test('puts adjacent nodes on separate lines and keeps empty elements on one line', () => {
  const output = transformHtml('<sm-root><!--before--><span class="mdc-tab-indicator__content mdc-tab-indicator__content--underline"></span><i x="1"></i><pre>code</pre><!--container--><!--container--><sm-child></sm-child></sm-root>');

  assert.match(output, /<sm-root>\n  <!--before-->\n  <span class="mdc-tab-indicator__content mdc-tab-indicator__content--underline"><\/span>\n  <i x="1"><\/i>/);
  assert.match(output, /<\/pre>\n  <!--container-->\n  <!--container-->\n  <sm-child><\/sm-child>/);
});

test('preserves the body element and its attributes when copied alone', () => {
  const output = transformHtml('<body class="view" style="height: 100vh"><div><sm-page></sm-page></div></body>');
  const body = new JSDOM(output).window.document.body;

  assert.match(output, /^<!--\nbody\n└── sm-page \[ns\]\n-->\n<body class="view" style="height: 100vh">\n/);
  assert.equal(body.getAttribute('class'), 'view');
  assert.equal(body.getAttribute('style'), 'height: 100vh');
  assert.equal(body.firstElementChild.localName, 'sm-page');
});

test('summarizes relevant element paths and marks missing selectors and Material context', () => {
  const source = '<html><head></head><body><sm-root><div><sm-missing><a data-id="plain">A</a><mat-card><button data-id="insideMat">B</button><mat-icon data-id="icon"></mat-icon><sm-root><span data-id="afterComponent">C</span></sm-root></mat-card><button mat-icon-button data-id="materialAttribute">D</button></sm-missing></div></sm-root></body></html>';
  const output = transformHtml(source);
  const summary = output.slice(0, output.indexOf('-->') + 3);

  assert.equal(summary, [
    '<!--',
    'html/',
    '├── head',
    '└── body',
    '    └── sm-root',
    '        └── sm-missing [ns]',
    '            ├── a: data-id="plain"',
    '            ├── button: data-id="insideMat" in mat',
    '            ├── mat-icon: data-id="icon"',
    '            ├── sm-root',
    '            │   └── span: data-id="afterComponent"',
    '            └── button: data-id="materialAttribute" in mat',
    '-->',
  ].join('\n'));
  assert.equal(new JSDOM(output).window.document.querySelector('sm-missing button').getAttribute('data-id'), 'insideMat');
});

test('uses the largest existing sequence number and never overwrites a file', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'ng-el-'));
  const existing = 'ngel-004-earlier-format-20260927-120000.html';

  try {
    await writeFile(join(directory, existing), 'existing');
    const now = new Date('2026-09-28T03:00:00Z');
    const first = await writeTransformedHtml('<sm-a><div><sm-b></sm-b></div></sm-a>', directory, { label: 'export button', now });
    const second = await writeTransformedHtml('<sm-c></sm-c>', directory, { now });

    assert.equal(first, join(directory, 'ngel-005-export-button-20260928-120000.html'));
    assert.equal(second, join(directory, 'ngel-006-unlabeled-20260928-120000.html'));
    assert.equal(await readFile(join(directory, existing), 'utf8'), 'existing');
    assert.match(await readFile(first, 'utf8'), /<sm-a>\n  <sm-b><\/sm-b>\n<\/sm-a>/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test('keeps file labels usable as a single path segment', () => {
  assert.equal(toFileLabel('実験詳細 ヘッダーの Export'), '実験詳細-ヘッダーの-Export');
  assert.equal(toFileLabel('a/b\\c:d*e?"<>|'), 'a-b-c-d-e');
  assert.equal(toFileLabel('  --trimmed--  '), 'trimmed');
  assert.equal(toFileLabel(Array.from({ length: 60 }, (_, index) => index % 10).join('')).length, 40);
  assert.equal(toFileLabel('🙂'.repeat(50)), '🙂'.repeat(40));
  assert.equal(toFileLabel(undefined), 'unlabeled');
  assert.equal(toFileLabel('///'), 'unlabeled');
});

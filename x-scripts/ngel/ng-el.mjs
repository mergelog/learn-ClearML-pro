import { readFile, mkdir, readdir, writeFile } from 'node:fs/promises';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const SCRIPT_DIRECTORY = dirname(fileURLToPath(import.meta.url));
export const PROJECT_ROOT = resolve(SCRIPT_DIRECTORY, '../..');
const OUTPUT_NAME = /^ngel-(\d+)-.*\.html$/;
const LABEL_LENGTH = 40;
const FALLBACK_LABEL = 'unlabeled';
let smSelectors;

export function toFileLabel(label) {
  const printable = String(label ?? '')
    .replace(/[\u0000-\u001f\u007f<>:"/\\|?*]+/g, ' ')
    .trim();
  const compact = Array.from(printable.replace(/\s+/g, '-'))
    .slice(0, LABEL_LENGTH)
    .join('')
    .replace(/^-+|-+$/g, '');

  return compact || FALLBACK_LABEL;
}

function knownSmSelectors() {
  if (smSelectors) return smSelectors;

  const selectors = new Set();
  const visit = (directory) => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === '_old') continue;
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) {
        visit(path);
      } else if (entry.isFile() && entry.name.endsWith('.ts')) {
        const source = readFileSync(path, 'utf8');
        if (!source.includes('@Component')) continue;
        for (const match of source.matchAll(/\bselector\s*:\s*(['"`])(sm-[\w-]+)\1/g)) {
          selectors.add(match[2]);
        }
      }
    }
  };

  visit(resolve(PROJECT_ROOT, 'src'));
  smSelectors = selectors;
  return selectors;
}

function removeUnwantedElements(parent) {
  for (const child of Array.from(parent.childNodes)) {
    if (child.nodeType !== 1) continue;

    if (child.tagName === 'STYLE') {
      child.remove();
      continue;
    }

    removeUnwantedElements(child.tagName === 'TEMPLATE' ? child.content : child);

    if (child.tagName === 'DIV') {
      child.replaceWith(...child.childNodes);
    }
  }
}

function formatNode(node, depth) {
  const indent = '  '.repeat(depth);

  if (node.nodeType === 3) {
    if (node.parentNode?.tagName === 'SCRIPT') {
      return indent + node.textContent;
    }

    const holder = node.ownerDocument.createElement('span');
    holder.append(node.cloneNode(true));
    return indent + holder.innerHTML;
  }

  if (node.nodeType === 8) {
    return `${indent}<!--${node.data}-->`;
  }

  if (node.nodeType === 10) {
    const identifiers = node.publicId
      ? ` PUBLIC "${node.publicId}" "${node.systemId}"`
      : node.systemId ? ` SYSTEM "${node.systemId}"` : '';
    return `${indent}<!DOCTYPE ${node.name}${identifiers}>`;
  }

  const shallowHtml = node.cloneNode(false).outerHTML;
  const closingTag = `</${node.localName}>`;
  if (!shallowHtml.endsWith(closingTag)) {
    return indent + shallowHtml;
  }

  const openingTag = shallowHtml.slice(0, -closingTag.length);
  const children = Array.from(node.tagName === 'TEMPLATE' ? node.content.childNodes : node.childNodes);
  const formattedChildren = children
    .filter((child) => child.nodeType !== 3 || /\S/.test(child.textContent))
    .map((child) => formatNode(child, depth + 1));

  if (formattedChildren.length === 0) {
    return indent + shallowHtml;
  }

  return [indent + openingTag, ...formattedChildren, indent + closingTag].join('\n');
}

function summaryChildren(node, inMat = false, afterHyphenTag = false, selectors = knownSmSelectors()) {
  const result = [];
  const children = node.tagName === 'TEMPLATE' ? node.content.childNodes : node.childNodes;

  for (const child of children) {
    if (child.nodeType !== 1) continue;

    const tag = child.localName;
    const isHyphenTag = tag.includes('-') && !tag.startsWith('mat-');
    const isMatTag = tag.startsWith('mat-');
    const hasMatAttribute = Array.from(child.attributes).some((attribute) => attribute.name.startsWith('mat-'));
    const dataId = child.getAttribute('data-id');
    const include = isHyphenTag || dataId !== null || ['html', 'head', 'body'].includes(tag);
    const withinMat = (isHyphenTag ? false : inMat) || isMatTag || hasMatAttribute;
    const label = [
      tag === 'html' ? 'html/' : tag,
      dataId === null ? '' : `: data-id="${dataId}"`,
      tag.startsWith('sm-') && !selectors.has(tag) ? ' [ns]' : '',
      dataId !== null && !tag.includes('-') && afterHyphenTag && withinMat ? ' in mat' : '',
    ].join('');
    const descendants = summaryChildren(child, withinMat, afterHyphenTag || isHyphenTag, selectors);

    if (include) {
      result.push({ label, children: descendants });
    } else {
      result.push(...descendants);
    }
  }

  return result;
}

function formatSummary(nodes) {
  const root = { childNodes: nodes };
  const branches = summaryChildren(root);
  const lines = [];
  const append = (items, prefix = '') => {
    items.forEach((item, index) => {
      const last = index === items.length - 1;
      lines.push(`${prefix}${last ? '└── ' : '├── '}${item.label}`);
      append(item.children, `${prefix}${last ? '    ' : '│   '}`);
    });
  };

  if (branches.length === 1) {
    lines.push(branches[0].label);
    append(branches[0].children);
  } else {
    append(branches);
  }
  return `<!--\n${lines.join('\n')}\n-->\n`;
}

export function transformHtml(source) {
  // DevTools can copy the full document, body/head, or another selected element.
  const isDocument = /^\s*(?:<!doctype\b|<html\b)/i.test(source);
  const documentElement = /^\s*<(body|head)\b/i.exec(source)?.[1]?.toLowerCase();
  const root = isDocument || documentElement
    ? new JSDOM(source).window.document
    : JSDOM.fragment(source);
  removeUnwantedElements(root);

  const selectedNodes = documentElement ? [root[documentElement]] : Array.from(root.childNodes);
  const nodes = selectedNodes.filter(
    (node) => node.nodeType !== 3 || /\S/.test(node.textContent),
  );

  return formatSummary(nodes) + nodes.map((node) => formatNode(node, 0)).join('\n') + '\n';
}

function timestampInTokyo(date) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Tokyo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date);
  const value = (type) => parts.find((part) => part.type === type).value;
  return `${value('year')}${value('month')}${value('day')}-${value('hour')}${value('minute')}${value('second')}`;
}

export async function writeTransformedHtml(source, outputDirectory, { label, now = new Date() } = {}) {
  await mkdir(outputDirectory, { recursive: true });
  const names = await readdir(outputDirectory);
  const largestNumber = names.reduce((largest, name) => {
    const match = OUTPUT_NAME.exec(name);
    return match ? Math.max(largest, Number(match[1])) : largest;
  }, 0);
  const html = transformHtml(source);
  const timestamp = timestampInTokyo(now);
  const fileLabel = toFileLabel(label);

  for (let number = largestNumber + 1; ; number++) {
    const filename = `ngel-${String(number).padStart(3, '0')}-${fileLabel}-${timestamp}.html`;
    const path = resolve(outputDirectory, filename);

    try {
      await writeFile(path, html, { flag: 'wx' });
      return path;
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
    }
  }
}

async function main() {
  const [, , inputPath, label] = process.argv;
  if (!inputPath || process.argv.length > 4) {
    throw new Error('Usage: node x-scripts/ngel/ng-el.mjs <DevTools HTML file> [label]');
  }

  const source = await readFile(resolve(SCRIPT_DIRECTORY, inputPath), 'utf8');
  const outputPath = await writeTransformedHtml(source, resolve(SCRIPT_DIRECTORY, 'x-ngel'), { label });
  console.log(outputPath);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}

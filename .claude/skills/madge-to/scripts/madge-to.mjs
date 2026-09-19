#!/usr/bin/env node
// 指定ファイルを import している側（親方向）を madge の依存グラフから辿り、
// プロジェクト直下に madge-rdeps-{名前}.md（Mermaid + ファイル一覧）を出力する。
//
// 使い方: node madge-to.mjs <対象ファイル> [--depth <n>]
//   対象ファイル: src/app 配下の .ts（プロジェクトルートからの相対 / 絶対パス）
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const PROJECT_ROOT = process.cwd();
const SRC_ROOT = path.join(PROJECT_ROOT, 'src/app');
const TS_CONFIG = path.join(PROJECT_ROOT, 'tsconfig.app.json');

function fail(message, code = 1) {
  console.error(`error: ${message}`);
  process.exit(code);
}

function parseArgs(argv) {
  let target, depth = Infinity;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--depth') {
      depth = Number(argv[++i]);
      if (!Number.isInteger(depth) || depth < 1) fail('--depth には 1 以上の整数を指定する', 3);
    } else if (!target) target = argv[i];
    else fail(`不明な引数: ${argv[i]}`, 3);
  }
  if (!target) fail('対象ファイルを指定する', 3);
  return { target, depth };
}

// vscode:// リンク用の WSL ディストリビューション名。取れなければ null（クリックリンクを付けない）
function wslDistro() {
  if (process.env.WSL_DISTRO_NAME) return process.env.WSL_DISTRO_NAME;
  try {
    const out = execFileSync('/mnt/c/Windows/System32/wsl.exe', ['-l', '-v']).toString('utf16le');
    return out.split(/\r?\n/).find(l => l.trim().startsWith('*'))?.trim().split(/\s+/)[1] ?? null;
  } catch {
    return null;
  }
}

// ノードのリンク先: クラス宣言の行。無ければ export const/function の行、それも無ければ 1 行目
function declaration(absPath) {
  const lines = fs.readFileSync(absPath, 'utf8').split('\n');
  const classIdx = lines.findIndex(l => /^export (default )?(abstract )?class /.test(l));
  const idx = classIdx >= 0 ? classIdx : lines.findIndex(l => /^export (const|function) /.test(l));
  const className = classIdx >= 0 ? lines[classIdx].match(/class (\w+)/)[1] : null;
  return { line: (idx >= 0 ? idx : 0) + 1, className };
}

function hasCommand(cmd) {
  try {
    execFileSync('which', [cmd], { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

const { target, depth } = parseArgs(process.argv.slice(2));
const targetAbs = path.resolve(PROJECT_ROOT, target);
if (!fs.existsSync(targetAbs)) fail(`ファイルが見つからない: ${target}`);
const targetId = path.relative(SRC_ROOT, targetAbs);
if (targetId.startsWith('..')) fail(`src/app 配下のファイルを指定する: ${target}`, 3);
if (!hasCommand('madge')) fail('madge が見つからない（npm i -g madge）', 4);

// madge はパイプ出力だと書き切る前に終了して JSON が途中で切れるため、ファイルへ直接書かせる
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'madge-to-'));
const jsonPath = path.join(tmpDir, 'deps.json');
const jsonFd = fs.openSync(jsonPath, 'w');
try {
  execFileSync('madge', [
    '--json', '--extensions', 'ts', '--ts-config', TS_CONFIG, '--exclude', '\\.spec\\.ts$', SRC_ROOT,
  ], { stdio: ['ignore', jsonFd, 'ignore'] });
} finally {
  fs.closeSync(jsonFd);
}
const tree = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
fs.rmSync(tmpDir, { recursive: true, force: true });
if (!(targetId in tree)) fail(`madge の依存グラフに含まれていない: ${targetId}`);

// 逆引き表を作り、対象から親方向へ幅優先で辿る
const parents = {};
for (const [file, deps] of Object.entries(tree)) for (const d of deps) (parents[d] ??= []).push(file);
const edges = [], seen = new Set([targetId]);
let frontier = [targetId];
for (let level = 0; level < depth && frontier.length; level++) {
  const next = [];
  for (const f of frontier) for (const p of parents[f] ?? []) {
    edges.push([p, f]);
    if (!seen.has(p)) { seen.add(p); next.push(p); }
  }
  frontier = next;
}

const files = [...seen];
const decl = new Map(files.map(f => [f, declaration(path.join(SRC_ROOT, f))]));
const name = decl.get(targetId).className ?? path.basename(targetId, '.ts');
const outPath = path.join(PROJECT_ROOT, `madge-rdeps-${name}.md`);
const rel = f => path.relative(PROJECT_ROOT, path.join(SRC_ROOT, f));
const label = f => path.basename(f, '.ts');
const distro = wslDistro();

// Mermaid（ノードは n0, n1... の ID にしてラベルでファイル名を出す）
const ids = new Map(files.map((f, i) => [f, `n${i}`]));
const mermaid = ['flowchart LR'];
mermaid.push(...files.map(f => `  ${ids.get(f)}["${label(f)}"]`));
mermaid.push(...edges.map(([p, f]) => `  ${ids.get(p)} --> ${ids.get(f)}`));
if (distro) {
  mermaid.push(...files.map(f => {
    const abs = path.join(SRC_ROOT, f);
    return `  click ${ids.get(f)} href "vscode://vscode-remote/wsl+${distro}${abs}:${decl.get(f).line}" "${rel(f)}"`;
  }));
}
mermaid.push(`  style ${ids.get(targetId)} stroke:#d97706,stroke-width:3px`);

// Mermaid のツールチップは背景色 #ffffde だけがインライン指定され、文字色はページから継承する。
// ダークテーマでは薄い文字色になり読みにくいため、文字色を固定する
const tooltipStyle = '<style>.mermaidTooltip { color: #1f2937 !important; }</style>';

const md = [
  `# ${name} の参照元（madge 逆依存）`,
  '',
  tooltipStyle,
  '',
  `起点: \`${rel(targetId)}\`（オレンジの太枠）  `,
  `矢印: import する側 → される側。\`*.spec.ts\` は除外${Number.isFinite(depth) ? `。深さ ${depth} まで` : ''}  `,
  distro ? 'ノードのクリック: VSCode で宣言行を開く（ブラウザ表示時のみ。VSCode のプレビューでは下のファイル一覧を使う）' : '',
  '',
  '```mermaid',
  ...mermaid,
  '```',
  '',
  '## ファイル一覧',
  '',
  ...files.map(f => `- [${label(f)}](${rel(f)}#L${decl.get(f).line})`),
  '',
].join('\n');
fs.writeFileSync(outPath, md);
console.log(`Saved: ${path.relative(PROJECT_ROOT, outPath)}`);
if (!distro) console.log('warning: WSL ディストリビューション名が取れないため、図のクリックリンクは付けない');
console.log(`${files.length} files, ${edges.length} edges`);

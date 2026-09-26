// フェーズ2 観点F：src/app の createEffect を TypeScript の構文木で分類し、TSV で標準出力に出す。
// 列：file・line・クラス名・Effect 名・dispatch・ofType の action・外側の pipe の演算子・外側の catchError の位置・
//     平坦化の演算子（外側の pipe のもの）・その内側の API 呼び出し・その内側の catchError の有無・判定
// 判定：
//   OUTER_CATCH   外側の pipe で平坦化の後ろに catchError がある。1回の失敗で Effect が完了し、以後その action に反応しない
//   NO_CATCH_API  平坦化の内側で API を呼ぶが、内側にも外側にも catchError が無い。失敗すると Effect ごと再購読される（上限10回）
//   ok            上のどちらでもない
// 実行：node x-不具合調査/scripts/p2f-classify-effects.cjs > effects.tsv
const ts = require('typescript');
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../../src/app');
const EXCL = /business-logic\/model|report-widgets|features\/data-catalog|features\/quality-pipeline|_old|\.spec\.ts$/;
const FLAT = ['switchMap', 'mergeMap', 'concatMap', 'exhaustMap', 'flatMap', 'switchMapTo', 'mergeMapTo'];
// API とみなす呼び出し：this.xxxApi.、this.http.、this.api.、xxxService.（ストアとルータを除く）
const API_RE = /this\.(\w*[Aa]pi\w*|http|httpClient|\w+Service)\.\w+\(/g;

function walk(dir, out = []) {
  for (const f of fs.readdirSync(dir)) {
    const p = path.join(dir, f);
    const st = fs.statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (p.endsWith('.ts') && !EXCL.test(p)) out.push(p);
  }
  return out;
}

function calleeName(node) {
  if (!ts.isCallExpression(node)) return node.getText().replace(/\s+/g, ' ').slice(0, 30);
  const e = node.expression;
  if (ts.isIdentifier(e)) return e.text;
  if (ts.isPropertyAccessExpression(e)) return e.name.text;
  return e.getText().slice(0, 30);
}

// 式の中の .pipe( の鎖をたどり、外側から見た演算子の並び（呼び出しの節点）を返す
function pipeChain(expr) {
  const ops = [];
  let cur = expr;
  let root = '';
  for (let i = 0; i < 20 && cur; i++) {
    if (ts.isParenthesizedExpression(cur)) { cur = cur.expression; continue; }
    if (ts.isCallExpression(cur) && ts.isPropertyAccessExpression(cur.expression) && cur.expression.name.text === 'pipe') {
      ops.unshift(...cur.arguments);
      cur = cur.expression.expression;
      continue;
    }
    root = cur.getText().replace(/\s+/g, ' ').slice(0, 60);
    break;
  }
  return {ops, root};
}

function returnedExpr(fn) {
  if (!fn) return null;
  if (ts.isArrowFunction(fn) || ts.isFunctionExpression(fn)) {
    if (!ts.isBlock(fn.body)) return fn.body;
    let ret = null;
    fn.body.forEachChild(function f(n) {
      if (ts.isReturnStatement(n) && !ret) ret = n.expression;
      else if (!ts.isFunctionLike(n)) n.forEachChild(f);
    });
    return ret;
  }
  return null;
}

function containsCall(node, names) {
  let found = false;
  (function f(n) {
    if (found) return;
    if (ts.isCallExpression(n) && names.includes(calleeName(n))) { found = true; return; }
    n.forEachChild(f);
  })(node);
  return found;
}

const rows = [];
for (const file of walk(ROOT)) {
  const text = fs.readFileSync(file, 'utf8');
  if (!text.includes('createEffect')) continue;
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
  const rel = path.relative(ROOT, file);

  (function visit(node) {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'createEffect') {
      const line = sf.getLineAndCharacterOfPosition(node.getStart()).line + 1;
      let cls = node;
      while (cls && !ts.isClassDeclaration(cls)) cls = cls.parent;
      let prop = node.parent;
      const name = prop && ts.isPropertyDeclaration(prop) ? prop.name.getText() : '(' + ts.SyntaxKind[prop?.kind] + ')';
      const cfg = node.arguments[1] ? node.arguments[1].getText().replace(/\s+/g, ' ') : '';
      const dispatch = /dispatch:\s*false/.test(cfg) ? 'false' : 'true';
      const body = returnedExpr(node.arguments[0]);
      const {ops, root} = body ? pipeChain(body) : {ops: [], root: '?'};
      const names = ops.map(calleeName);
      const ofTypeNode = ops.find(o => calleeName(o) === 'ofType');
      const ofTypeArgs = ofTypeNode ? ofTypeNode.arguments.map(a => a.getText()).join(',') : '';
      const flatIdx = names.findIndex(n => FLAT.includes(n));
      const catchIdx = names.lastIndexOf('catchError');
      const outerCatch = catchIdx < 0 ? '-' : (flatIdx >= 0 && catchIdx > flatIdx ? 'after-flat' : (flatIdx < 0 ? 'no-flat' : 'before-flat'));
      // 外側の平坦化の演算子すべてについて、内側の API と catchError を調べる
      const flats = [];
      let apis = new Set();
      let innerCatch = 'n/a';
      ops.forEach((o, i) => {
        const n = names[i];
        if (!FLAT.includes(n)) return;
        flats.push(n);
        const inner = o.arguments[0];
        if (!inner) return;
        const t = inner.getText();
        for (const m of t.matchAll(API_RE)) apis.add(m[0].replace(/^this\./, '').replace(/\($/, ''));
        const hasCatch = containsCall(inner, ['catchError']);
        innerCatch = innerCatch === 'yes' || hasCatch ? 'yes' : 'no';
      });
      // 平坦化の外（tap・map など）で API を呼んでいるもの
      ops.forEach((o, i) => {
        if (FLAT.includes(names[i])) return;
        for (const m of o.getText().matchAll(API_RE)) apis.add('(outer)' + m[0].replace(/^this\./, '').replace(/\($/, ''));
      });
      let verdict = 'ok';
      if (outerCatch === 'after-flat') verdict = 'OUTER_CATCH';
      else if (apis.size && innerCatch !== 'yes' && catchIdx < 0) verdict = 'NO_CATCH_API';
      rows.push([rel, line, cls?.name?.text || '?', name, dispatch, ofTypeArgs.replace(/\s+/g, ''), names.join('>'),
        outerCatch, flats.join(',') || '-', [...apis].join(',') || '-', innerCatch, verdict, root].join('\t'));
    }
    node.forEachChild(visit);
  })(sf);
}

console.log(['file', 'line', 'class', 'effect', 'dispatch', 'ofType', 'ops', 'outerCatch', 'flat', 'api', 'innerCatch', 'verdict', 'root'].join('\t'));
for (const r of rows) console.log(r);

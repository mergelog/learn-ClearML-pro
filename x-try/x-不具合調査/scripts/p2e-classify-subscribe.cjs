// フェーズ2 観点E：src/app の .subscribe( の呼び出しを TypeScript の構文木で分類し、TSV で標準出力に出す。
// 列：file・line・クラス名・種類（component/directive/service-root など）・メソッド・購読元の式・pipe の演算子・解除の演算子・
//     解除の演算子の後ろの演算子・保持先（=this.x、add:this.subs など）・保持先の unsubscribe の有無・subscribe の入れ子か
// 実行：node x-不具合調査/scripts/p2e-classify-subscribe.cjs > subs.tsv
const ts = require('typescript');
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../../src/app');
const EXCL = /business-logic\/model|report-widgets|features\/data-catalog|features\/quality-pipeline|_old|\.spec\.ts$/;

function walk(dir, out = []) {
  for (const f of fs.readdirSync(dir)) {
    const p = path.join(dir, f);
    const st = fs.statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (p.endsWith('.ts') && !EXCL.test(p)) out.push(p);
  }
  return out;
}

const GUARDS = ['takeUntilDestroyed', 'takeUntil', 'take', 'first', 'takeWhile'];
const rows = [];

for (const file of walk(ROOT)) {
  const text = fs.readFileSync(file, 'utf8');
  if (!text.includes('.subscribe(')) continue;
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
  const rel = path.relative(ROOT, file);

  function classInfo(node) {
    let n = node;
    while (n && !ts.isClassDeclaration(n)) n = n.parent;
    if (!n) return {cls: '-', kind: 'none', clsNode: null};
    const decos = (ts.getDecorators ? ts.getDecorators(n) : n.decorators) || [];
    let kind = 'plain';
    for (const d of decos) {
      const e = d.expression;
      const name = ts.isCallExpression(e) ? e.expression.getText() : e.getText();
      if (name === 'Injectable') {
        const arg = ts.isCallExpression(e) && e.arguments[0] ? e.arguments[0].getText() : '';
        kind = /providedIn:\s*['"]root['"]/.test(arg) ? 'service-root' : 'service';
      } else if (['Component', 'Directive', 'Pipe'].includes(name)) kind = name.toLowerCase();
    }
    if (kind === 'plain' && /Effects?$/.test(n.name?.text || '')) kind = 'effects';
    return {cls: n.name?.text || '?', kind, clsNode: n};
  }

  function memberName(node) {
    let n = node;
    while (n) {
      if (ts.isConstructorDeclaration(n)) return 'constructor';
      if (ts.isMethodDeclaration(n) || ts.isGetAccessor(n) || ts.isSetAccessor(n)) return n.name.getText();
      if (ts.isPropertyDeclaration(n)) return 'prop:' + n.name.getText();
      if (ts.isFunctionDeclaration(n)) return 'fn:' + (n.name?.text || '?');
      n = n.parent;
    }
    return '-';
  }

  // subscribe の受け手の鎖をたどり、pipe の演算子と元の式を得る
  function chain(expr) {
    const ops = [];
    let cur = expr;
    let root = '';
    for (let i = 0; i < 20 && cur; i++) {
      if (ts.isCallExpression(cur) && ts.isPropertyAccessExpression(cur.expression) && cur.expression.name.text === 'pipe') {
        const names = cur.arguments.map(a => ts.isCallExpression(a) ? a.expression.getText() : a.getText());
        ops.unshift(...names);
        cur = cur.expression.expression;
        continue;
      }
      root = cur.getText().replace(/\s+/g, ' ');
      break;
    }
    return {ops, root};
  }

  function nestedInSubscribe(node) {
    let n = node.parent;
    while (n) {
      if (ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression) && n.expression.name.text === 'subscribe') return true;
      if (ts.isClassDeclaration(n)) return false;
      n = n.parent;
    }
    return false;
  }

  function holder(call) {
    // 代入先・add 先
    let p = call.parent;
    if (p && ts.isBinaryExpression(p) && p.operatorToken.kind === ts.SyntaxKind.EqualsToken) return '=' + p.left.getText();
    if (p && ts.isPropertyDeclaration(p)) return '=this.' + p.name.getText();
    if (p && ts.isVariableDeclaration(p)) return 'var:' + p.name.getText();
    if (p && ts.isCallExpression(p) && ts.isPropertyAccessExpression(p.expression) && ['add', 'push'].includes(p.expression.name.text)) return p.expression.name.text + ':' + p.expression.expression.getText();
    if (p && ts.isArrayLiteralExpression(p)) {
      const pp = p.parent;
      if (pp && ts.isCallExpression(pp)) return 'arr-in:' + pp.expression.getText();
      if (pp && ts.isBinaryExpression(pp)) return 'arr=' + pp.left.getText();
    }
    if (p && ts.isArrowFunction(p)) return 'arrow-return';
    if (p && ts.isReturnStatement(p)) return 'return';
    return '';
  }

  function visit(node) {
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) && node.expression.name.text === 'subscribe') {
      const {line} = sf.getLineAndCharacterOfPosition(node.getStart());
      const ci = classInfo(node);
      const {ops, root} = chain(node.expression.expression);
      const guardIdx = ops.map((o, i) => GUARDS.includes(o) ? i : -1).filter(i => i >= 0);
      const guards = guardIdx.map(i => ops[i]);
      const lastGuard = guardIdx.length ? guardIdx[guardIdx.length - 1] : -1;
      const afterGuard = lastGuard >= 0 ? ops.slice(lastGuard + 1) : [];
      const h = holder(node);
      let released = '';
      const clsText = ci.clsNode ? ci.clsNode.getText() : text;
      const field = h.replace(/^(=|add:|push:|arr=)/, '');
      if (field && /^this\./.test(field)) {
        const f = field.replace(/^this\./, '').replace(/[.[].*$/, '');
        const re = new RegExp(`this\\.${f}\\??\\.(unsubscribe|forEach)|this\\.${f}\\]?.*unsubscribe`);
        released = re.test(clsText) ? 'unsub' : 'NO-unsub';
      }
      rows.push({
        file: rel, line: line + 1, cls: ci.cls, kind: ci.kind, member: memberName(node),
        root: root.slice(0, 120), ops: ops.join('>'), guards: guards.join(','),
        afterGuard: afterGuard.join('>'), holder: h, released, nested: nestedInSubscribe(node) ? 'nested' : ''
      });
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
}

const cols = ['file', 'line', 'cls', 'kind', 'member', 'root', 'ops', 'guards', 'afterGuard', 'holder', 'released', 'nested'];
console.log(cols.join('\t'));
for (const r of rows) console.log(cols.map(c => r[c]).join('\t'));

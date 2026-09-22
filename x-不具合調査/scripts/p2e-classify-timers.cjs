// フェーズ2 観点E：src/app の setTimeout / setInterval を、待ち時間・保持先・clear の有無・コールバックの先頭で一覧にし、TSV で標準出力に出す。
// 実行：node x-不具合調査/scripts/p2e-classify-timers.cjs > timers.tsv
const ts = require('typescript');
const fs = require('fs'), path = require('path');
const ROOT = path.resolve(__dirname, '../../src/app');
const EXCL = /business-logic\/model|report-widgets|features\/data-catalog|features\/quality-pipeline|_old|\.spec\.ts$/;
const files = [];
(function walk(d){ for (const f of fs.readdirSync(d)) { const p = path.join(d,f); fs.statSync(p).isDirectory() ? walk(p) : (p.endsWith('.ts') && !EXCL.test(p) && files.push(p)); } })(ROOT);
console.log(['loc','kind','member','delay','holder','cleared','body'].join('\t'));
for (const file of files) {
  const text = fs.readFileSync(file, 'utf8');
  if (!/set(Timeout|Interval)\(/.test(text)) continue;
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
  const rel = path.relative(ROOT, file);
  const kindOf = n => { while (n && !ts.isClassDeclaration(n)) n = n.parent; if (!n) return ['none', null];
    const d = (ts.getDecorators(n) || []).map(x => x.expression.getText().split('(')[0]); return [d[0] || 'plain', n]; };
  const memberOf = n => { while (n) { if (ts.isConstructorDeclaration(n)) return 'constructor'; if (ts.isMethodDeclaration(n) || ts.isPropertyDeclaration(n) || ts.isGetAccessor(n) || ts.isSetAccessor(n)) return n.name.getText(); n = n.parent; } return '-'; };
  (function v(n) {
    if (ts.isCallExpression(n)) {
      const callee = n.expression.getText();
      if (/(^|\.)set(Timeout|Interval)$/.test(callee)) {
        const [kind, cls] = kindOf(n);
        const delay = n.arguments[1] ? n.arguments[1].getText() : '(none)';
        const p = n.parent;
        let holder = '';
        if (ts.isBinaryExpression(p) && p.operatorToken.kind === ts.SyntaxKind.EqualsToken) holder = p.left.getText();
        else if (ts.isVariableDeclaration(p)) holder = 'var:' + p.name.getText();
        else if (ts.isPropertyDeclaration(p)) holder = 'this.' + p.name.getText();
        let cleared = '';
        if (holder) { const h = holder.replace(/^var:|^this\./, ''); cleared = new RegExp(`clear(Timeout|Interval)\\(\\s*(this\\.)?${h.replace(/[.$]/g, '\\$&')}`).test(cls ? cls.getText() : text) ? 'cleared' : 'NOT'; }
        const body = n.arguments[0] ? n.arguments[0].getText().replace(/\s+/g, ' ').slice(0, 110) : '';
        const {line} = sf.getLineAndCharacterOfPosition(n.getStart());
        console.log([rel + ':' + (line + 1), kind, memberOf(n), delay, holder, cleared, body].join('\t'));
      }
    }
    ts.forEachChild(n, v);
  })(sf);
}

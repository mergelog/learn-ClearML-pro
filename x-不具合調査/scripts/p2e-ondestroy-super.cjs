// フェーズ2 観点E：ngOnDestroy を上書きして super.ngOnDestroy() を呼ばないサブクラス（基底の解除が走らない）を探す。
// 実行：node x-不具合調査/scripts/p2e-ondestroy-super.cjs（該当なしなら何も出さない）
const ts = require('typescript');
const fs = require('fs'), path = require('path');
const ROOT = path.resolve(__dirname, '../../src/app');
const EXCL = /business-logic\/model|report-widgets|features\/data-catalog|features\/quality-pipeline|_old|\.spec\.ts$/;
const files = [];
(function walk(d){ for (const f of fs.readdirSync(d)) { const p = path.join(d,f); fs.statSync(p).isDirectory() ? walk(p) : (p.endsWith('.ts') && !EXCL.test(p) && files.push(p)); } })(ROOT);
const classes = {};
for (const file of files) {
  const text = fs.readFileSync(file, 'utf8');
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
  ts.forEachChild(sf, function v(n) {
    if (ts.isClassDeclaration(n) && n.name) {
      const ext = n.heritageClauses?.find(h => h.token === ts.SyntaxKind.ExtendsKeyword)?.types[0]?.expression.getText();
      const od = n.members.find(m => ts.isMethodDeclaration(m) && m.name.getText() === 'ngOnDestroy');
      classes[n.name.text] = classes[n.name.text] || [];
      classes[n.name.text].push({file: path.relative(ROOT, file), ext, hasOD: !!od, callsSuper: od ? /super\.ngOnDestroy\(/.test(od.getText()) : null, line: od ? sf.getLineAndCharacterOfPosition(od.getStart()).line + 1 : 0});
    }
    ts.forEachChild(n, v);
  });
}
const hasODInChain = (name, seen = new Set()) => {
  if (!name || seen.has(name)) return false; seen.add(name);
  const c = (classes[name] || [])[0]; if (!c) return false;
  return c.hasOD || hasODInChain(c.ext, seen);
};
for (const [name, list] of Object.entries(classes)) for (const c of list) {
  if (c.ext && c.hasOD && !c.callsSuper && hasODInChain(c.ext)) console.log(`OVERRIDE-NO-SUPER\t${c.file}:${c.line}\t${name} extends ${c.ext}`);
}

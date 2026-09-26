import {test} from '@playwright/test';
import {buildTask, mockClearmlApi} from './helpers/mock-api';

/**
 * フェーズ4（観点の見直し、§3 C の「プロジェクトのカード・パンくずでの長い日本語名」の確認。フェーズ2では調査用プロジェクトの名前が短く確かめていない）。
 * 空白を含まない長い日本語名のプロジェクト（親子あり）を、プロジェクトの一覧・サブプロジェクトの一覧・タスク一覧のパンくずで撮影する。
 * モック API（書き込みなし）。1366×800。
 */
const company = {id: 'test-company', name: 'Test company'};
const PARENT = '機械学習基盤チームの画像分類モデル改善のための長期間にわたる検証用プロジェクト';
const CHILD = '推論速度と精度の両立を目指した量子化および蒸留の比較実験を記録するサブプロジェクト';
const parent = {id: 'long-parent', name: PARENT, basename: PARENT, company, sub_projects: [{id: 'long-child', name: `${PARENT}/${CHILD}`}],
  stats: {active: {status_count: {created: 1, queued: 0, in_progress: 0, stopped: 0, published: 0, closed: 0, failed: 0, completed: 0, unknown: 0}, total_runtime: 0, total_tasks: 1}}};
const child = {id: 'long-child', name: `${PARENT}/${CHILD}`, basename: CHILD, company, parent: {id: 'long-parent', name: PARENT},
  stats: parent.stats};

test.use({viewport: {width: 1366, height: 800}});

test('長い日本語名のプロジェクトのカードとパンくず', async ({page}) => {
  await mockClearmlApi(page, {
    tasks: [buildTask('task-a', 'Task A', {project: {id: 'long-child', name: `${PARENT}/${CHILD}`}} as any)],
    overrides: {
      'projects.get_all_ex': body => {
        const ids: string[] | undefined = body?.id;
        if (ids?.length) {
          return {data: {projects: [parent, child].filter(p => ids.includes(p.id))}};
        }
        if (body?.parent?.[0] === 'long-parent') {
          return {data: {projects: [child]}};
        }
        return {data: {projects: [parent]}};
      }
    }
  });
  const shots: [string, string][] = [
    ['/projects', 'p4-long-project-name-cards.png'],
    ['/projects/long-parent/projects', 'p4-long-project-name-subprojects.png'],
    ['/projects/long-child/tasks', 'p4-long-project-name-breadcrumbs.png']
  ];
  for (const [url, file] of shots) {
    await page.goto(url);
    await page.waitForTimeout(3000);
    const overflow = await page.evaluate(() => {
      const res: string[] = [];
      document.querySelectorAll('sm-header *, sm-project-card *, sm-nested-card *, sm-card *').forEach(el => {
        const e = el as HTMLElement;
        if (e.children.length === 0 && e.textContent?.includes('プロジェクト')) {
          const r = e.getBoundingClientRect();
          const parentRect = e.parentElement!.getBoundingClientRect();
          res.push(`${e.tagName.toLowerCase()}.${e.className} w=${Math.round(r.width)} scroll=${e.scrollWidth} client=${e.clientWidth} right=${Math.round(r.right)} parentRight=${Math.round(parentRect.right)} vw=${innerWidth}`);
        }
      });
      return res.slice(0, 12);
    });
    console.log('==', url);
    overflow.forEach(o => console.log('  ', o));
    await page.screenshot({path: `test-results/bug-investigation/${file}`});
  }
});

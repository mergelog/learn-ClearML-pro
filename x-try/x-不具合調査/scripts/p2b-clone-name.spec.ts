import {expect, test} from '@playwright/test';
import {mockClearmlApi} from './helpers/mock-api';

/**
 * フェーズ2 観点B：クローンのダイアログのタスク名。入力欄は required だけで、下限と空白だけの名前を見ない。
 * サーバ（apiserver の Task.name は StrippedStringField(min_length=3)）は前後の空白を除いて3文字未満を拒否する。
 * モック API で、ダイアログが短い名前・空白だけの名前をそのまま送るか、失敗時に何が出るかを見る。
 */
for (const [label, name] of [['2文字', '実験'], ['全角空白だけ', '　　　']] as const) {
  test(`クローンのダイアログは${label}の名前をそのまま送る`, async ({page}) => {
    const api = await mockClearmlApi(page, {
      overrides: {
        // 既定のモックのプロジェクトは company を持たず読み取り専用として扱われ、クローン先にできないため差し替える
        'projects.get_all_ex': () => ({data: {projects: [{id: 'bug-project', name: 'Bug project', company: {id: 'test-company'}}]}}),
        'tasks.clone': () => ({status: 400, resultCode: 400, msg: 'Validation error (string value is too short: name)'})
      }
    });
    await page.goto('/projects/bug-project/tasks/task-a/execution');
    await page.locator('sm-experiment-info-header sm-experiment-menu-extended button').first().click();
    await page.locator('[data-id="Clone Option"]').click();
    const nameInput = page.locator('mat-dialog-container input[name="ExperimentName"]');
    await expect(nameInput).toBeVisible();
    // モックでは既定のプロジェクトが選ばれないため、一覧から選ぶ
    const projectInput = page.locator('mat-dialog-container sm-paginated-entity-selector input');
    await projectInput.click();
    await projectInput.fill('Bug');
    await page.locator('mat-option', {hasText: 'Bug project'}).first().click();
    await nameInput.fill(name);
    const formState = await page.evaluate(() => {
      const ng = (window as any).ng;
      const host = document.querySelector('mat-dialog-container [class*="clone"], sm-clone-dialog') ?? document.querySelector('mat-dialog-container');
      let el: Element | null = host;
      let comp: any = null;
      while (el && !comp) { comp = ng.getComponent(el); el = el.firstElementChild; }
      const form = comp?.cloneForm;
      return form ? Object.fromEntries(Object.entries(form.controls).map(([k, c]: [string, any]) => [k, {status: c.status, errors: c.errors, value: c.value}])) : 'no form';
    });
    console.log('form', JSON.stringify(formState));
    const cloneButton = page.locator('mat-dialog-container [data-id="CloneButton"]');
    const enabled = await cloneButton.isEnabled();
    if (enabled) {
      await cloneButton.click();
    }
    await page.waitForTimeout(1500);
    const sent = api.callsTo('tasks.clone').map(c => (c.body as any)?.new_task_name);
    const dialogOpen = await page.locator('mat-dialog-container input[name="ExperimentName"]').count();
    const notices = await page.locator('simple-snack-bar, mat-snack-bar-container, .mat-mdc-snack-bar-container').allInnerTexts();
    console.log(label, JSON.stringify({enabled, sent, dialogOpen, notices}));
    expect(enabled).toBe(true);
    expect(sent).toEqual([name]);
  });
}

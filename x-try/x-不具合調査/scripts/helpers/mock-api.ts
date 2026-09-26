import type {Page, Route} from '@playwright/test';

/**
 * 調査用の ClearML API モック。e2e/fixtures/clearml-api.fixture.ts と同じ形で
 * `**\/service/**` を横取りし、次を足してある。
 * - tasks.update などの書き込みを記録し、名前の変更をモック内のタスクに反映する
 * - エンドポイントごとに応答を差し替えられる（失敗の再現用）
 */

export interface MockTask {
  id: string;
  name: string;
  project: {id: string; name: string};
  company: {id: string; name: string};
  user: {id: string; name: string};
  status: string;
  type: string;
  runtime: Record<string, never>;
  last_change: string;
  last_update: string;
  system_tags: string[];
  tags: string[];
  comment?: string;
  script?: Record<string, unknown>;
  execution?: Record<string, unknown>;
  container?: Record<string, unknown>;
  hyperparams?: Record<string, unknown>;
  output: {destination: string};
}

export const mockProject = {id: 'bug-project', name: 'Bug project'};
const company = {id: 'test-company', name: 'Test company'};
const user = {id: 'test-user', name: 'Test User', company};

export function buildTask(id: string, name: string, extra: Partial<MockTask> = {}): MockTask {
  return {
    id,
    name,
    project: mockProject,
    company,
    user,
    status: 'created',
    type: 'training',
    runtime: {},
    last_change: '2026-09-05T00:00:00Z',
    last_update: '2026-09-05T00:00:00Z',
    system_tags: [],
    tags: [],
    script: {
      repository: `repository-${id}`,
      entry_point: 'train.py',
      working_dir: '.',
      binary: 'python',
      branch: 'main',
      requirements: {pip: [`package-${id}`]},
      diff: ''
    },
    execution: {queue: null},
    container: {image: `image-${id}`, arguments: ''},
    output: {destination: `s3://${id}`},
    ...extra
  };
}

export interface ApiCall {
  endpoint: string;
  body: unknown;
  at: number;
}

export type Override = (body: any, route: Route) => {status?: number; data?: unknown; resultCode?: number; msg?: string} | undefined;

export interface MockOptions {
  tasks?: MockTask[];
  overrides?: Record<string, Override>;
  /** 応答を遅らせる（ms）。エンドポイントごと */
  delays?: Record<string, number>;
}

export interface MockHandle {
  calls: ApiCall[];
  tasks: MockTask[];
  overrides: Record<string, Override>;
  callsTo(endpoint: string): ApiCall[];
}

export async function mockClearmlApi(page: Page, options: MockOptions = {}): Promise<MockHandle> {
  const tasks = options.tasks ?? [
    buildTask('task-a', 'Task A'),
    buildTask('task-b', 'Task B')
  ];
  const overrides: Record<string, Override> = {...(options.overrides ?? {})};
  const calls: ApiCall[] = [];

  const defaultData = (endpoint: string, body: any): unknown => {
    switch (endpoint) {
      case 'login.supported_modes':
        return {authenticated: true};
      case 'users.get_current_user':
        return {user, settings: {}};
      case 'users.get_preferences':
        return {preferences: {version: 1, views: {neverShowPopupAgain: ['tip-of-the-day']}}};
      case 'projects.get_user_names':
        return {users: []};
      case 'projects.get_task_tags':
      case 'projects.get_model_tags':
        return {tags: [], system_tags: []};
      case 'projects.get_task_parents':
        return {parents: []};
      case 'projects.get_all_ex':
        return {projects: [mockProject]};
      case 'projects.get_by_id':
        return {project: mockProject};
      case 'tasks.get_types':
        return {types: []};
      case 'tasks.get_by_id_ex': {
        const ids: string[] = body?.id ?? [];
        return {tasks: tasks.filter(task => ids.includes(task.id))};
      }
      case 'tasks.get_all_ex': {
        const ids: string[] | undefined = body?.id;
        return {tasks: ids?.length ? tasks.filter(task => ids.includes(task.id)) : tasks, scroll_id: null};
      }
      case 'tasks.get_configuration_names':
        return {configurations: [{task: body?.id?.[0], names: []}]};
      case 'tasks.update': {
        const task = tasks.find(t => t.id === body?.task);
        const {task: _id, ...fields} = body ?? {};
        if (task) {
          Object.assign(task, fields);
          task.last_change = new Date().toISOString();
        }
        return {updated: 1, fields};
      }
      case 'tasks.edit':
        return {updated: 1, fields: {}};
      default:
        return {};
    }
  };

  await page.route('https://api.github.com/**', route => route.fulfill({status: 200, contentType: 'application/json', body: '{}'}));

  await page.route('**/service/**', async route => {
    const endpoint = new URL(route.request().url()).pathname.split('/').at(-1) ?? '';
    let body: any = null;
    try {
      body = route.request().postDataJSON();
    } catch {
      body = route.request().postData();
    }
    calls.push({endpoint, body, at: Date.now()});

    const delay = options.delays?.[endpoint];
    if (delay) {
      await new Promise(resolve => setTimeout(resolve, delay));
    }

    const override = overrides[endpoint]?.(body, route);
    if (override) {
      const status = override.status ?? 200;
      const resultCode = override.resultCode ?? status;
      return route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify({meta: {result_code: resultCode, result_msg: override.msg ?? 'OK'}, data: override.data ?? {}})
      });
    }

    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({meta: {result_code: 200}, data: defaultData(endpoint, body)})
    });
  });

  return {
    calls,
    tasks,
    overrides,
    callsTo: (endpoint: string) => calls.filter(c => c.endpoint === endpoint)
  };
}

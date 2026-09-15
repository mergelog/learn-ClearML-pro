import type {Page, Route} from '@playwright/test';

/**
 * データカタログが読むものだけを返すClearML API。
 *
 * 実際のClearML Serverを立てないのは、E2Eで確かめたいのが「サーバが正しいか」
 * ではなく「応答をどう画面に写すか」だからである。
 *
 * 応答の形は実際のClearML APIに合わせる。ここで形を単純化すると、画面が
 * 読めない形の応答を返されても気付けないテストになる。とくに `project` は
 * `{id, name}` に展開された形で返す。IDだけの形に直すと、プロジェクト名が
 * 空でも通るテストになる。
 */

const company = {id: 'test-company', name: 'Test company'};
const user = {id: 'test-user', name: 'Test User', company};

const catalogProject = {id: 'catalog-project', name: 'Semiconductor Quality Prediction'};

export const DATASET_TASK = {
  id: 'dataset-task',
  name: 'semiconductor-quality',
  type: 'data_processing',
  status: 'completed',
  project: catalogProject,
  company,
  user,
  system_tags: ['dataset'],
  tags: ['seed'],
  last_update: '2026-09-10T00:00:00Z',
  created: '2026-09-10T00:00:00Z',
  runtime: {version: '1.0.0'},
  comment: 'Basic synthetic process measurements.',
};

export const RUN_TASK = {
  id: 'run-task',
  name: 'semiconductor-quality-training 1.0.0',
  type: 'controller',
  status: 'completed',
  project: catalogProject,
  company,
  user,
  system_tags: [],
  tags: [],
  last_update: '2026-09-11T00:00:00Z',
  created: '2026-09-11T00:00:00Z',
  started: '2026-09-11T00:00:00Z',
  completed: '2026-09-11T00:05:00Z',
  hyperparams: {Dataset: {dataset_version: {value: '1.0.0'}}},
  comment: '',
};

export const CATALOG_MODEL = {
  id: 'catalog-model',
  name: 'semiconductor-quality-classifier',
  project: catalogProject,
  company,
  user,
  system_tags: [],
  tags: ['stage:production'],
  ready: true,
  task: RUN_TASK.id,
  last_update: '2026-09-12T00:00:00Z',
  created: '2026-09-12T00:00:00Z',
  comment: 'the trial went well',
  framework: 'scikit-learn',
  metadata: {
    model_version: {value: '1.0.0-20260908T043015Z-abcdef01'},
    dataset_version: {value: '1.0.0'},
  },
};

interface Options {
  /** 台帳に何も無い環境。「まだ無い」と「条件に合わない」の出し分けを見る。 */
  empty?: boolean;
  /** 失敗させるエンドポイント。 */
  failing?: string[];
}

/** 失敗させたときにClearMLが返す説明。画面がこれを出せているかを見る。 */
export const FAILURE_MESSAGE = 'the catalog index is unavailable';

type RequestBody = Record<string, unknown>;

export interface RecordedCalls {
  endpoints(): string[];
  countOf(endpoint: string): number;
  bodiesOf(endpoint: string): RequestBody[];
}

/**
 * 送られた条件で返すものを変える。
 *
 * 名前で絞られたら絞った結果を返す。ここを無視して常に同じものを返すと、
 * 「絞り込みをサーバへ渡している」ことをE2Eでは何も確かめられなくなる。
 */
function tasksFor(body: RequestBody, options: Options): unknown[] {
  if (options.empty) {
    return [];
  }

  const systemTags = (body['system_tags'] as string[] | undefined) ?? [];
  const candidates = systemTags.includes('dataset') ? [DATASET_TASK] : [RUN_TASK];
  const name = body['name'] as string | undefined;

  if (typeof body['runtime.version'] === 'object') {
    return [DATASET_TASK];
  }
  if (body['hyperparams.Dataset.dataset_version.value'] !== undefined) {
    return [RUN_TASK];
  }
  if (name === undefined || name === '') {
    return candidates;
  }
  return candidates.filter((task) => task.name.includes(name));
}

function responseData(
  endpoint: string,
  options: Options,
  body: RequestBody
): Record<string, unknown> {
  switch (endpoint) {
    case 'login.supported_modes':
      return {authenticated: true};
    case 'users.get_current_user':
      return {user};
    case 'users.get_preferences':
      return {preferences: {version: 1, views: {neverShowPopupAgain: ['tip-of-the-day']}}};
    case 'projects.get_all_ex':
      return {projects: [catalogProject]};
    case 'projects.get_task_tags':
      return {tags: ['seed']};
    case 'projects.get_model_tags':
      return {tags: ['stage:production']};
    case 'tasks.get_all_ex':
      return {tasks: tasksFor(body, options)};
    case 'tasks.get_by_id_ex': {
      const id = (body['id'] as string[] | undefined)?.[0];
      return {tasks: [id === DATASET_TASK.id ? DATASET_TASK : RUN_TASK]};
    }
    case 'tasks.update':
      return {updated: 1};
    case 'models.get_all_ex':
      return {models: options.empty ? [] : [CATALOG_MODEL]};
    case 'models.update':
      return {updated: 1};
    default:
      return {};
  }
}

function readBody(route: Route): RequestBody {
  try {
    return (route.request().postDataJSON() as RequestBody | null) ?? {};
  } catch {
    return {};
  }
}

export async function mockDataCatalogApi(
  page: Page,
  options: Options = {}
): Promise<RecordedCalls> {
  const calls: {endpoint: string; body: RequestBody}[] = [];

  await page.route('https://api.github.com/**', (route: Route) =>
    route.fulfill({status: 200, contentType: 'application/json', body: '{}'})
  );

  await page.route('**/service/**', (route: Route) => {
    const endpoint = new URL(route.request().url()).pathname.split('/').at(-1) ?? '';
    const body = readBody(route);

    calls.push({endpoint, body});

    if (options.failing?.includes(endpoint)) {
      // ClearMLは失敗も `meta` で説明する。状態コードだけを返すと、
      // 画面が説明を読めているのかどうかが分からないテストになる。
      return route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({meta: {result_code: 500, result_msg: FAILURE_MESSAGE}}),
      });
    }

    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        meta: {result_code: 200},
        data: responseData(endpoint, options, body),
      }),
    });
  });

  return {
    endpoints: () => calls.map((call) => call.endpoint),
    countOf: (endpoint) => calls.filter((call) => call.endpoint === endpoint).length,
    bodiesOf: (endpoint) =>
      calls.filter((call) => call.endpoint === endpoint).map((call) => call.body),
  };
}

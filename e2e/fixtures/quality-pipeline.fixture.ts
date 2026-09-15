import type {Page, Route} from '@playwright/test';

/**
 * Quality pipeline画面が読むものだけを返すClearML API。
 *
 * 既存の `clearml-api.fixture.ts` はTask詳細画面のための応答を持っている。
 * ここでは同じ仕組みで、この画面が必要とする最小限だけを返す。
 * 実際のClearML Serverを立てないのは、E2Eで確かめたいのが
 * 「サーバが正しいか」ではなく「応答をどう画面に写すか」だからである。
 *
 * 応答の形は実際のClearML APIに合わせる。ここで形を単純化すると、
 * 画面が読めない形の応答を返されても気付けないテストになる。
 */

const company = {id: 'test-company', name: 'Test company'};
const user = {id: 'test-user', name: 'Test User', company};

const pipelineProject = {
  id: 'pipeline-project',
  name: 'Semiconductor Quality Prediction/Pipeline',
};

export const PIPELINE_TEMPLATE_TASK = {
  id: 'pipeline-template',
  name: 'semiconductor-quality-training',
  project: pipelineProject,
  company,
  user,
  status: 'completed',
  type: 'controller',
  runtime: {},
  system_tags: [],
  tags: [],
  started: '2026-09-08T00:00:00Z',
  completed: '2026-09-08T00:05:00Z',
  hyperparams: {Dataset: {dataset_version: {value: '1.0.0'}}},
};

/** 1回の実行に属するステップ。制御役のTaskを親として持つ。 */
export const PIPELINE_STEP_TASKS = [
  {id: 'step-validate', name: 'validate', status: 'completed'},
  {id: 'step-preprocess', name: 'preprocess', status: 'completed'},
  {id: 'step-train', name: 'train', status: 'completed'},
  {id: 'step-evaluate', name: 'evaluate', status: 'completed'},
  {id: 'step-register-candidate', name: 'register-candidate', status: 'completed'},
].map((step) => ({
  ...step,
  parent: PIPELINE_TEMPLATE_TASK.id,
  project: pipelineProject,
  company,
  user,
  type: 'training',
  system_tags: [],
  tags: [],
  started: '2026-09-08T00:00:30Z',
  completed: '2026-09-08T00:04:30Z',
}));

/**
 * 評価ステップが記録したスカラー。
 *
 * ClearMLは `指標 -> 系列 -> 値` の入れ子で返す。Python側が
 * `report_scalar(title=指標名, series=split名)` で書くためである。
 * 平らな一覧に直して置かない。それをすると、画面が入れ子を読めなくても
 * このテストは通ってしまう。
 */
export const EVALUATION_SCALARS = [
  {
    name: 'accuracy',
    variants: [
      {name: 'validation', last_value: 0.81, last_100_value: 0.81},
      {name: 'test', last_value: 0.79, last_100_value: 0.79},
    ],
  },
  {
    name: 'precision',
    variants: [
      {name: 'validation', last_value: 0.85, last_100_value: 0.85},
      {name: 'test', last_value: 0.82, last_100_value: 0.82},
    ],
  },
  {
    name: 'recall',
    variants: [
      {name: 'validation', last_value: 0.63, last_100_value: 0.63},
      {name: 'test', last_value: 0.61, last_100_value: 0.61},
    ],
  },
  {
    name: 'f1',
    variants: [
      {name: 'validation', last_value: 0.72, last_100_value: 0.72},
      {name: 'test', last_value: 0.7, last_100_value: 0.7},
    ],
  },
];

export const PRODUCTION_MODEL = {
  id: 'model-id',
  name: 'semiconductor-quality-classifier',
  tags: ['stage:production'],
  metadata: {
    model_version: {value: '1.0.0-20260908T043015Z-abcdef01'},
    dataset_version: {value: '1.0.0'},
    train_task_id: {value: 'train-task'},
    promoted_by: {value: 'reviewer'},
    promoted_at: {value: '2026-09-08T04:30:15Z'},
    promotion_reason: {value: 'the trial went well'},
  },
};

interface Options {
  /** 複製元のPipeline Taskがあるかどうか。無い環境の画面も確かめる。 */
  withTemplate?: boolean;
  /** 提供中のモデルがあるかどうか。 */
  withProductionModel?: boolean;
  /**
   * 画面を開いた時点での実行の状態。
   *
   * 追跡を始めるかどうかがこれで決まるため、既定の `completed` のままでは
   * 読み直しの経路そのものが動かない。
   */
  latestRunStatus?: string;
  /**
   * 読み直したときに返す状態。
   *
   * 開いた時点の状態と分けてあるのは、「走っていた実行が終わったら
   * 読み直しが止まる」ことを確かめるためである。
   */
  refreshedRunStatus?: string;
  /**
   * 失敗させるエンドポイント。
   *
   * ClearMLが答えられないときに画面が何を出すかは、成功のときと同じくらい
   * 決まっていなければならない。
   */
  failing?: string[];
}

/** 失敗させたときにClearMLが返す説明。画面がこれを出せているかを見る。 */
export const FAILURE_MESSAGE = 'the model registry is unavailable';

/** ClearMLへ送られた要求の中身。何で絞ったかによって返すものが変わる。 */
type RequestBody = Record<string, unknown>;

/**
 * 画面がClearMLへ何を送ったか。
 *
 * 画面の見た目だけでは、起動が「ClearML上で複製されてQueueへ入った」ことまでは
 * 確かめられない。送った要求そのものを見る。
 */
export interface RecordedCalls {
  /** 呼ばれたエンドポイントを、呼ばれた順に。 */
  endpoints(): string[];
  /** そのエンドポイントが呼ばれた回数。読み直しが止まったかを見るのに使う。 */
  countOf(endpoint: string): number;
  /** 最初に送られた要求の中身。 */
  bodyOf(endpoint: string): RequestBody;
}

/** 起動要求が複製したTaskのid。Queueへ入れる要求がこれを指しているかを見る。 */
export const CLONED_TASK_ID = 'cloned-pipeline-task';

const runTask = (status: string) => ({...PIPELINE_TEMPLATE_TASK, status});

function responseData(
  endpoint: string,
  options: Options,
  body: RequestBody
): Record<string, unknown> {
  const latestRunStatus = options.latestRunStatus ?? 'completed';

  switch (endpoint) {
    case 'login.supported_modes':
      return {authenticated: true};
    case 'users.get_current_user':
      return {user};
    case 'users.get_preferences':
      return {preferences: {version: 1, views: {neverShowPopupAgain: ['tip-of-the-day']}}};
    case 'projects.get_all_ex':
      return {projects: [pipelineProject]};
    case 'tasks.get_all_ex':
      // 親で絞っているのは「この実行のステップ」の問い合わせ。
      // 名前で絞っているのは複製元と直近の実行の問い合わせである。
      if (typeof body['parent'] === 'string') {
        return {tasks: PIPELINE_STEP_TASKS};
      }
      return {tasks: options.withTemplate === false ? [] : [runTask(latestRunStatus)]};
    case 'tasks.get_by_id_ex':
      return {tasks: [runTask(options.refreshedRunStatus ?? latestRunStatus)]};
    case 'tasks.clone':
      return {id: CLONED_TASK_ID};
    case 'tasks.enqueue':
      return {queued: 1};
    case 'tasks.stop':
      return {updated: 1};
    case 'events.get_task_latest_scalar_values':
      return {metrics: EVALUATION_SCALARS};
    case 'models.get_all_ex':
      return {models: options.withProductionModel === false ? [] : [PRODUCTION_MODEL]};
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

export async function mockQualityPipelineApi(
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
    bodyOf: (endpoint) => {
      const call = calls.find((sent) => sent.endpoint === endpoint);
      if (!call) {
        throw new Error(
          `${endpoint} was never called. Sent: ${calls.map((sent) => sent.endpoint).join(', ')}`
        );
      }
      return call.body;
    },
  };
}

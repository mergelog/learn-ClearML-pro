import type {Page, Route} from '@playwright/test';

/**
 * 1本の流れ（Dataset登録 → Queue学習 → 比較 → 昇格 → 推論の受け渡し）を
 * 1つの世界として返すClearML API。
 *
 * 既存の2つのfixtureは画面ごとに必要な応答を返す。ここが違うのは、
 * **すべての画面が同じ1つの世界を見る**ことである。Dataset版 1.0.0 で学習した
 * 実行が、比較で選ばれ、その結果が `stage:production` のモデルになり、
 * そのモデルのバージョン文字列が提供中として画面に出る。
 * どこか1か所で取り違えが起きれば、後ろの画面が別のものを出す。
 *
 * 絞り込みは実際に読む。`type` や `project` や `id` を無視して常に全部返すと、
 * 画面が誤った条件で問い合わせていても気付けないテストになる。
 *
 * ClearML Serverは立てない。E2Eが答えるのは「縦に繋がっているか」であって、
 * サーバが正しいかではない（`docs/_archive/adr/005_20260911_test_pyramid.md`）。
 */

const company = {id: 'test-company', name: 'Test company'};
const user = {id: 'test-user', name: 'Test User', company};

/** Python側の既定値（`ml/semiconductor_quality/config.py` ほか）と揃える。 */
export const DATASET_NAME = 'semiconductor-quality-data';
export const DATASET_VERSION = '1.0.0';
export const TRAINING_QUEUE = 'semiconductor-training';
export const PIPELINE_QUEUE = 'semiconductor-pipeline';
export const MODEL_NAME = 'semiconductor-quality-classifier';

/**
 * 昇格したモデルのバージョン。
 *
 * これが推論サービスとの受け渡し点である。`prediction_api` は
 * `stage:production` のモデルを読み、この文字列を `/ready` で名乗る
 * （`services/prediction_api/model_source.py`）。画面とサービスが同じものを
 * 指しているかどうかは、この文字列が一致するかで決まる。
 */
export const PROMOTED_MODEL_VERSION = '1.0.0-20260908T043015Z-abcdef01';

const datasetProject = {
  id: 'dataset-project',
  name: `Semiconductor Quality Prediction/${DATASET_NAME}`,
  basename: DATASET_NAME,
  company,
  user,
  system_tags: ['dataset'],
  tags: [],
  created: '2026-09-08T00:00:00Z',
  last_update: '2026-09-08T00:00:00Z',
  default_output_destination: null,
};

const trainingProject = {
  id: 'training-project',
  name: 'Semiconductor Quality Prediction/Training',
  basename: 'Training',
  company,
  user,
  system_tags: [],
  tags: [],
  created: '2026-09-08T00:00:00Z',
  last_update: '2026-09-08T00:05:00Z',
};

const pipelineProject = {
  id: 'pipeline-project',
  name: 'Semiconductor Quality Prediction/Pipeline',
  basename: 'Pipeline',
  company,
  user,
  system_tags: [],
  tags: [],
  created: '2026-09-08T00:00:00Z',
  last_update: '2026-09-08T00:05:00Z',
};

const times = {
  started: '2026-09-08T00:00:00Z',
  completed: '2026-09-08T00:05:00Z',
  last_update: '2026-09-08T00:05:00Z',
  last_change: '2026-09-08T00:05:00Z',
};

/** 1. 登録された Dataset の版。ClearMLはこれをTaskとして持つ。 */
const datasetVersionTask = {
  id: 'dataset-version-1',
  name: DATASET_NAME,
  project: {id: datasetProject.id, name: datasetProject.name},
  company,
  user,
  status: 'completed',
  type: 'data_processing',
  system_tags: ['dataset'],
  tags: [],
  runtime: {version: DATASET_VERSION, ds_file_count: 1, ds_total_size: 1024},
  ...times,
};

/**
 * 2〜3. Queueで走った学習の実行。比較されるのはこの2つである。
 *
 * 名前はPython側の既定（`DEFAULT_TASK_NAME`）のままにしてある。ClearMLは
 * 実行のたびに同じ名前のTaskを作るので、**比較は名前では区別できない**。
 * 区別は指標と、どのDataset版で学習したかによる。
 */
const runs = [
  {id: 'run-candidate', accuracy: 0.91, datasetVersion: '2.0.0'},
  {id: 'run-serving', accuracy: 0.81, datasetVersion: DATASET_VERSION},
].map((run) => ({
  id: run.id,
  name: 'random-forest-quality-classifier',
  project: {id: trainingProject.id, name: trainingProject.name},
  company,
  user,
  status: 'completed',
  type: 'training',
  runtime: {},
  system_tags: [],
  tags: [],
  execution: {queue: TRAINING_QUEUE},
  output: {destination: ''},
  hyperparams: {
    Dataset: {
      dataset_version: {
        section: 'Dataset',
        name: 'dataset_version',
        type: 'str',
        value: run.datasetVersion,
        description: '',
      },
    },
  },
  // ClearMLは直近の指標を `指標 -> 系列 -> 値` の入れ子で返す。
  last_metrics: {
    accuracy: {
      validation: {
        metric: 'accuracy',
        variant: 'validation',
        value: run.accuracy,
        min_value: run.accuracy,
        max_value: run.accuracy,
        last_value: run.accuracy,
      },
    },
  },
  ...times,
}));

/** 候補の実行。比較で選ばれた側。 */
export const CANDIDATE_RUN = runs[0];
/** いま提供されているモデルを作った実行。 */
export const SERVING_RUN = runs[1];

/** Pipelineの制御役。Quality pipeline画面が複製元として読む。 */
const pipelineTask = {
  id: 'pipeline-run',
  name: 'semiconductor-quality-training',
  project: {id: pipelineProject.id, name: pipelineProject.name},
  company,
  user,
  status: 'completed',
  type: 'controller',
  runtime: {},
  system_tags: [],
  tags: [],
  hyperparams: {Dataset: {dataset_version: {value: DATASET_VERSION}}},
  ...times,
};

/** 4. 昇格したモデル。`stage:production` が付いているのはこれだけである。 */
const promotedModel = {
  id: 'model-production',
  name: MODEL_NAME,
  project: {id: trainingProject.id, name: trainingProject.name},
  company,
  user,
  tags: ['stage:production'],
  system_tags: [],
  ready: true,
  framework: 'scikit-learn',
  uri: 's3://models/semiconductor-quality-classifier',
  created: '2026-09-08T04:30:15Z',
  last_update: '2026-09-08T04:30:15Z',
  metadata: {
    model_version: {key: 'model_version', type: 'str', value: PROMOTED_MODEL_VERSION},
    dataset_version: {key: 'dataset_version', type: 'str', value: DATASET_VERSION},
    train_task_id: {key: 'train_task_id', type: 'str', value: SERVING_RUN.id},
    promoted_by: {key: 'promoted_by', type: 'str', value: 'reviewer'},
    promoted_at: {key: 'promoted_at', type: 'str', value: '2026-09-08T04:30:15Z'},
    promotion_reason: {key: 'promotion_reason', type: 'str', value: 'the trial went well'},
  },
};

/** 昇格していない候補のバージョン。画面がこちらを出したら選び違えている。 */
export const CANDIDATE_MODEL_VERSION = '2.0.0-20260910T101500Z-fedcba09';

/** 候補のモデル。昇格していない側が混ざっても取り違えないことを見るために置く。 */
const candidateModel = {
  ...promotedModel,
  id: 'model-candidate',
  tags: ['stage:staging'],
  metadata: {
    ...promotedModel.metadata,
    model_version: {
      key: 'model_version',
      type: 'str',
      value: CANDIDATE_MODEL_VERSION,
    },
  },
};

const queues = [
  {
    id: 'queue-training',
    name: TRAINING_QUEUE,
    display_name: TRAINING_QUEUE,
    tags: [],
    last_update: '2026-09-08T00:00:00Z',
    workers: [{key: 'training-agent', name: 'training-agent'}],
    entries: [{task: {id: CANDIDATE_RUN.id, name: CANDIDATE_RUN.name}, added: '2026-09-08T00:00:00Z'}],
  },
  {
    id: 'queue-pipeline',
    name: PIPELINE_QUEUE,
    display_name: PIPELINE_QUEUE,
    tags: [],
    last_update: '2026-09-08T00:00:00Z',
    workers: [],
    entries: [],
  },
];

const allTasks = [datasetVersionTask, ...runs, pipelineTask];

type RequestBody = Record<string, unknown>;

/** 続きの問い合わせに使われる目印。 */
const SCROLL_ID = 'smoke-scroll';

/** 2回目以降（続きを取りに来た）問い合わせかどうか。 */
function continued(body: RequestBody): boolean {
  return body['scroll_id'] === SCROLL_ID || (body['page'] as number | undefined ?? 0) > 0;
}

function matchesName(task: {name: string}, pattern: unknown): boolean {
  if (typeof pattern !== 'string') {
    return true;
  }
  return new RegExp(pattern).test(task.name);
}

/**
 * Task問い合わせの絞り込みを、実際に当てる。
 *
 * 画面は `id` / `project` / `type` / `name`（正規表現）/ `parent` で絞る。
 * ここで無視すると、Dataset版の一覧に学習の実行が並ぶような応答を返しても
 * テストが通ってしまう。
 */
function selectTasks(body: RequestBody): typeof allTasks {
  const ids = body['id'] as string[] | undefined;
  const projects = body['project'] as string[] | undefined;
  const types = body['type'] as string[] | undefined;

  if (typeof body['parent'] === 'string') {
    // この実行のステップ。smokeでは個々のステップまでは見ない。
    return [];
  }

  return allTasks.filter((task) => {
    if (ids?.length && !ids.includes(task.id)) {
      return false;
    }
    if (projects?.length && !projects.includes(task.project.id)) {
      return false;
    }
    if (types?.length && !types.includes(task.type)) {
      return false;
    }
    return matchesName(task, body['name']);
  });
}

function selectModels(body: RequestBody): (typeof promotedModel)[] {
  const tags = body['tags'] as string[] | undefined;
  const models = [promotedModel, candidateModel];

  return models.filter((model) => {
    if (tags?.length && !tags.every((tag) => model.tags.includes(tag))) {
      return false;
    }
    return matchesName(model, body['name']);
  });
}

function responseData(endpoint: string, body: RequestBody): Record<string, unknown> {
  switch (endpoint) {
    case 'login.supported_modes':
      return {authenticated: true};
    case 'users.get_current_user':
      return {user};
    case 'users.get_preferences':
      return {preferences: {version: 1, views: {neverShowPopupAgain: ['tip-of-the-day']}}};
    case 'users.get_all_ex':
      return {users: [user]};
    case 'projects.get_all_ex': {
      const ids = body['id'] as string[] | undefined;
      const projects = [datasetProject, trainingProject, pipelineProject];
      return {projects: ids?.length ? projects.filter((project) => ids.includes(project.id)) : projects};
    }
    case 'projects.get_user_names':
      return {users: [user]};
    case 'projects.get_project_tags':
    case 'projects.get_task_tags':
      return {tags: []};
    case 'projects.get_model_tags':
      return {tags: ['stage:production', 'stage:staging']};
    case 'projects.get_task_parents':
      return {parents: []};
    case 'tasks.get_types':
      return {types: ['training', 'data_processing', 'controller']};
    case 'tasks.get_all_ex':
      // 一覧は尽きるまで続きを取りに来る。2回目以降に同じものを返すと、
      // 画面には同じ行が積み上がる。続きが無いことは空で答える。
      return continued(body) ? {tasks: [], scroll_id: SCROLL_ID} : {tasks: selectTasks(body), scroll_id: SCROLL_ID};
    case 'tasks.get_by_id_ex':
      return {tasks: selectTasks(body)};
    case 'tasks.clone':
      return {id: 'cloned-pipeline-task'};
    case 'tasks.enqueue':
      return {queued: 1};
    case 'queues.get_all_ex':
      return {queues};
    case 'queues.get_queue_metrics':
      return {queues: []};
    case 'workers.get_all':
      return {
        workers: [
          {
            id: 'training-agent',
            key: 'training-agent',
            ip: '127.0.0.1',
            queues: [queues[0]],
            task: null,
            register_time: '2026-09-08T00:00:00Z',
            last_activity_time: '2026-09-08T00:00:00Z',
          },
        ],
      };
    case 'workers.get_activity_report':
      return {total: [], workers: []};
    case 'models.get_all_ex':
      return continued(body) ? {models: [], scroll_id: SCROLL_ID} : {models: selectModels(body), scroll_id: SCROLL_ID};
    case 'models.get_frameworks':
      return {frameworks: ['scikit-learn']};
    case 'events.get_task_latest_scalar_values':
      return {metrics: []};
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

export async function mockSmokeApi(page: Page): Promise<void> {
  await page.route('https://api.github.com/**', (route: Route) =>
    route.fulfill({status: 200, contentType: 'application/json', body: '{}'})
  );

  await page.route('**/service/**', (route: Route) => {
    const endpoint = new URL(route.request().url()).pathname.split('/').at(-1) ?? '';

    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        meta: {result_code: 200},
        data: responseData(endpoint, readBody(route)),
      }),
    });
  });
}

/** 比較画面のURL。行列パラメータで比べる実行を渡す（ClearML Webの決まり）。 */
export function compareUrl(taskIds: string[]): string {
  return `/projects/${trainingProject.id}/compare-tasks;ids=${taskIds.join(',')}/scalars/values`;
}

/** Dataset版の一覧のURL。 */
export const DATASET_VERSIONS_URL = `/datasets/simple/${datasetProject.id}/tasks`;
/** 昇格したモデルが並ぶ一覧のURL。 */
export const MODELS_URL = `/projects/${trainingProject.id}/models`;

import {Task} from '~/business-logic/model/tasks/task';
import {ParamsItem} from '~/business-logic/model/tasks/paramsItem';
import {Model} from '~/business-logic/model/models/model';
import {
  CatalogAsset,
  CatalogAssetDetail,
  CatalogAssetState,
  CatalogFact,
  CatalogProject,
} from '@features/data-catalog/data-catalog.model';

/**
 * ClearML APIの応答を、台帳の語彙へ移す境界。
 *
 * 台帳が並べるのは Dataset / Model / Run の3つで、ClearML側ではそれぞれ
 * 別の実体である。にもかかわらず1つの表に並ぶ以上、**同じ7項目に揃える**
 * 責任がどこかに要る。それがここである。
 *
 * `quality-pipeline.adapter.ts` と同じ4つの方針を引き継ぐ。
 *
 * 入口の型は生成済みモデルから導く（生成サービスの戻り値は `Observable<any>`
 * なので、手書きの応答型はコンパイラに検査されない）。知らない状態は捨てずに
 * `unknown` として残す。無い値は既定値で埋めず `null` のままにする。
 * 変換は一方向にしか行わない。
 *
 * ここに **Dataset Version の読み取りが再び現れる**（`readDatasetVersion`）。
 * 同じ場所を `quality-pipeline.adapter.ts` も読んでいる。2箇所目が出たことは
 * 分かったうえで、まだ `shared/` へ寄せない。2つを見比べてから寄せる判断を
 * するためである（プランの §4.3 / チェックリスト P-2）。
 */

/** ClearMLのTask状態から、台帳が区別したい状態への対応。 */
const STATE_BY_TASK_STATUS: Readonly<Record<string, CatalogAssetState>> = {
  created: 'draft',
  queued: 'running',
  in_progress: 'running',
  completed: 'completed',
  closed: 'completed',
  published: 'published',
  failed: 'failed',
  stopped: 'stopped',
  unknown: 'unknown',
};

/**
 * 学習Runが「どのDataset版数で走ったか」を書いている場所。
 *
 * `ml/pipeline/steps.py` が `Dataset` 節の `dataset_version` に書く。
 * lineage はここを起点に Dataset へ戻る。
 */
export const DATASET_SECTION = 'Dataset';
export const DATASET_VERSION_PARAMETER = 'dataset_version';

/** ClearMLがDatasetの版数を置く場所。Taskの `runtime` の中にある。 */
export const DATASET_VERSION_RUNTIME_KEY = 'version';

/**
 * APIのTask。必要な部分だけを生成済みの `Task` から取る。
 *
 * `hyperparams` と `runtime` は `Task` 側が `any` なので、ここで読む形を
 * 明示する。`any` のままだと、節やパラメータ名を書き間違えても気付けない。
 *
 * `project` は生成型では `string`（ID）だが、`*.get_all_ex` は
 * `{id, name}` に展開して返す。台帳は名前を出しつつIDでリンクを組むため、
 * 両方の形を受けられるようにしてある。**どちらか片方だけを想定すると、
 * 一覧か詳細のどちらかでプロジェクト名が空になる。**
 */
export type ApiTask = Pick<
  Task,
  'id' | 'name' | 'status' | 'comment' | 'tags' | 'system_tags' | 'started' | 'completed'
> & {
  type?: string;
  project?: string | {id?: string; name?: string};
  last_update?: string | Date;
  created?: string;
  hyperparams?: Record<string, Record<string, ParamsItem>>;
  runtime?: Record<string, string>;
};

/** APIのModel。必要な部分だけを生成済みの `Model` から取る。 */
export type ApiModel = Pick<
  Model,
  'id' | 'name' | 'comment' | 'tags' | 'system_tags' | 'framework' | 'ready' | 'task' | 'uri'
> & {
  project?: string | {id?: string; name?: string};
  last_update?: string | Date;
  created?: string;
  metadata?: Record<string, {value?: string}>;
};

export const toTaskState = (status: string | undefined): CatalogAssetState =>
  STATE_BY_TASK_STATUS[(status ?? '').toLowerCase()] ?? 'unknown';

/**
 * Modelの状態。
 *
 * Modelには実行状態が無い。当てにしてよいかを決めるのは `ready` で、
 * これは「学習が最後まで終わって成果物が確定した」ことを意味する。
 * 未確定のものを `completed` として並べると、まだ書き換わりうるモデルを
 * 使ってよいものとして見せることになる。
 */
export const toModelState = (model: ApiModel): CatalogAssetState =>
  model.ready === true ? 'completed' : 'draft';

/** Datasetの1版。ClearMLでは `data_processing` のTaskとして登録されている。 */
export const toDatasetAsset = (task: ApiTask): CatalogAsset => ({
  ...baseTaskAsset(task),
  kind: 'dataset',
});

/** 1回の実行。 */
export const toRunAsset = (task: ApiTask): CatalogAsset => ({
  ...baseTaskAsset(task),
  kind: 'run',
});

export const toModelAsset = (model: ApiModel): CatalogAsset => ({
  kind: 'model',
  id: model.id ?? '',
  name: model.name ?? '',
  project: toProject(model.project),
  updatedAt: toTimestamp(model.last_update) ?? model.created ?? null,
  tags: model.tags ?? [],
  state: toModelState(model),
});

/**
 * Datasetの詳細。
 *
 * 版数を最初に出す。台帳から既存のDataset画面へ渡したあと、利用者が
 * 突き合わせるのはこの値だからである。
 */
export const toDatasetDetail = (task: ApiTask): CatalogAssetDetail => ({
  asset: toDatasetAsset(task),
  description: task.comment ?? '',
  facts: definedFacts([
    {label: 'Version', value: readRuntimeVersion(task)},
    {label: 'Registered', value: task.created ?? ''},
    {label: 'Task id', value: task.id ?? ''},
  ]),
});

/** 実行の詳細。どのDataset版数で走ったかが、ここで初めて見える。 */
export const toRunDetail = (task: ApiTask): CatalogAssetDetail => ({
  asset: toRunAsset(task),
  description: task.comment ?? '',
  facts: definedFacts([
    {label: 'Dataset version', value: readDatasetVersion(task)},
    {label: 'Started', value: task.started ?? ''},
    {label: 'Finished', value: task.completed ?? ''},
    {label: 'Task id', value: task.id ?? ''},
  ]),
});

/** モデルの詳細。 */
export const toModelDetail = (model: ApiModel): CatalogAssetDetail => ({
  asset: toModelAsset(model),
  description: model.comment ?? '',
  facts: definedFacts([
    {label: 'Model version', value: readMetadata(model, 'model_version')},
    {label: 'Dataset version', value: readMetadata(model, 'dataset_version')},
    {label: 'Framework', value: model.framework ?? ''},
    {label: 'Created by run', value: model.task ?? ''},
    {label: 'Model id', value: model.id ?? ''},
  ]),
});

/** 実行が使ったDatasetの版数。無ければ空文字（lineage はそこで止まる）。 */
export const readDatasetVersion = (task: ApiTask): string =>
  task.hyperparams?.[DATASET_SECTION]?.[DATASET_VERSION_PARAMETER]?.value ?? '';

/** Dataset Taskが持つ版数。 */
export const readRuntimeVersion = (task: ApiTask): string =>
  task.runtime?.[DATASET_VERSION_RUNTIME_KEY] ?? '';

const readMetadata = (model: ApiModel, key: string): string => model.metadata?.[key]?.value ?? '';

const baseTaskAsset = (task: ApiTask): Omit<CatalogAsset, 'kind'> => ({
  id: task.id ?? '',
  name: task.name ?? '',
  project: toProject(task.project),
  updatedAt: toTimestamp(task.last_update) ?? task.created ?? null,
  tags: task.tags ?? [],
  state: toTaskState(task.status),
});

/**
 * プロジェクト。展開された形とIDだけの形の両方を受ける。
 *
 * IDしか無いときに名前を空のままにするのは、IDを名前として出さないためである。
 * IDを名前の位置に出すと、利用者はそれをプロジェクト名だと思って検索する。
 */
const toProject = (project: string | {id?: string; name?: string} | undefined): CatalogProject => {
  if (typeof project === 'string') {
    return {id: project, name: ''};
  }
  return {id: project?.id ?? '', name: project?.name ?? ''};
};

/**
 * 更新日時をISO8601の文字列に揃える。
 *
 * 生成型は `string | Date` で、実際に返ってくるのは文字列である。
 * `Date` のまま state に入れると、同じ時刻が別のオブジェクトとして
 * 比較され続け、変わっていない一覧が変わったものとして再描画される。
 */
const toTimestamp = (value: string | Date | undefined): string | null => {
  if (value === undefined) {
    return null;
  }
  return value instanceof Date ? value.toISOString() : value;
};

/**
 * 値のある事実だけを残す。
 *
 * 空欄の行を並べると、「その資産には無い情報」と「読めなかった情報」が
 * 同じ見た目になる。出せるものだけを出し、無いものは行ごと出さない。
 */
const definedFacts = (facts: readonly CatalogFact[]): CatalogFact[] =>
  facts.filter((fact) => fact.value !== '');

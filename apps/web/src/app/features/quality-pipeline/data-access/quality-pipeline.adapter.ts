import {Task} from '~/business-logic/model/tasks/task';
import {ParamsItem} from '~/business-logic/model/tasks/paramsItem';
import {Model} from '~/business-logic/model/models/model';
import {EventsGetTaskLatestScalarValuesResponseMetrics} from '~/business-logic/model/events/eventsGetTaskLatestScalarValuesResponseMetrics';
import {
  EvaluationScore,
  PipelineRun,
  PipelineRunStatus,
  PipelineStep,
  PipelineTemplate,
  ProductionModel,
} from '~/features/quality-pipeline/quality-pipeline.model';

/**
 * ClearML APIの応答を、画面が扱う形へ移す境界。
 *
 * ここが1か所にまとまっていることが大事で、APIの応答は「あるはずのフィールドが
 * 無い」「型が違う」「知らない値が入っている」ことが普通にある。
 * その扱いをコンポーネントやEffectsに散らすと、同じ欠損に対して画面ごとに
 * 違う振る舞いをするようになる。
 *
 * 方針は4つ。
 *
 * 入口の型は生成済みモデルから導く。生成サービスの戻り値は `Observable<any>`
 * なので、応答の形を手で書き起こすと、実際とどれだけ違っていても
 * コンパイルは通ってしまう。`Task` や `Model` から `Pick` することで、
 * 「必要な部分だけ宣言する」ことと「実際の形から外れない」ことを両立させる。
 *
 * 知らない状態は捨てずに `unknown` として残す。落とすと「動いているのか
 * 終わったのか分からない」ことすら分からなくなる。
 *
 * 無い値は既定値で埋めず、`null` として残す。0や空文字で埋めると、
 * 「測っていない」と「0だった」が区別できなくなる。
 *
 * 変換は一方向にしか行わない。画面用の形からAPIの形へ戻す必要はない。
 */

/** ClearMLのTask状態から、画面が区別したい状態への対応。 */
const STATUS_BY_API_VALUE: Readonly<Record<string, PipelineRunStatus>> = {
  created: 'created',
  queued: 'queued',
  in_progress: 'running',
  completed: 'completed',
  closed: 'completed',
  published: 'completed',
  failed: 'failed',
  stopped: 'stopped',
  unknown: 'unknown',
};

export const DATASET_VERSION_PARAMETER = 'dataset_version';
export const DATASET_SECTION = 'Dataset';

const EVALUATION_METRICS = ['accuracy', 'precision', 'recall', 'f1'] as const;

type MetricName = (typeof EVALUATION_METRICS)[number];

/**
 * splitを並べる順。
 *
 * 応答は「指標ごとに系列が並ぶ」形なので、splitの出現順はPython側が
 * 指標を書いた順に引きずられる。そのまま表にすると、行の並びが実行ごとに
 * 変わり得る。
 *
 * 採用の可否を決めるのは validation で、test はその判断を一度だけ
 * 確かめるためのものである。読む順序に意味があるので、ここで固定する。
 * ここに無いsplitは、判断に使う2つの後ろへ出現順のまま置く。
 */
const SPLIT_ORDER: readonly string[] = ['validation', 'test'];

/**
 * APIのTask。必要な部分だけを生成済みの `Task` から取る。
 *
 * `hyperparams` だけは `Task` 側が `any` なので、ここで読む形を明示する。
 * `any` のままだと、節やパラメータ名を書き間違えても気付けない。
 */
export type ApiTask = Pick<
  Task,
  'id' | 'name' | 'status' | 'status_reason' | 'started' | 'completed'
> & {
  hyperparams?: Record<string, Record<string, ParamsItem>>;
};

/** APIのModel。必要な部分だけを生成済みの `Model` から取る。 */
export type ApiModel = Pick<Model, 'id' | 'name' | 'metadata'>;

/**
 * APIのスカラー値。evaluateステップが記録した指標を読む。
 *
 * 生成済みの応答型をそのまま使う。ClearMLは `指標 -> 系列 -> 値` の
 * 入れ子で返すのであって、平らな一覧では返さない。
 */
export type ApiScalarMetric = EventsGetTaskLatestScalarValuesResponseMetrics;

export const toStatus = (status: string | undefined): PipelineRunStatus =>
  STATUS_BY_API_VALUE[(status ?? '').toLowerCase()] ?? 'unknown';

export const toTemplate = (task: ApiTask): PipelineTemplate => ({
  taskId: task.id ?? '',
  name: task.name ?? '',
});

export const toRun = (task: ApiTask): PipelineRun => ({
  taskId: task.id ?? '',
  name: task.name ?? '',
  status: toStatus(task.status),
  statusReason: task.status_reason ?? '',
  datasetVersion: readDatasetVersion(task),
  startedAt: task.started ?? null,
  finishedAt: task.completed ?? null,
});

export const toStep = (task: ApiTask): PipelineStep => ({
  name: stepNameOf(task.name ?? ''),
  taskId: task.id ?? '',
  status: toStatus(task.status),
  startedAt: task.started ?? null,
  finishedAt: task.completed ?? null,
});

export const toProductionModel = (model: ApiModel): ProductionModel => ({
  modelId: model.id ?? '',
  modelVersion: readMetadata(model, 'model_version'),
  datasetVersion: readMetadata(model, 'dataset_version'),
  trainTaskId: readMetadata(model, 'train_task_id'),
  promotedBy: readMetadata(model, 'promoted_by'),
  promotedAt: readMetadata(model, 'promoted_at'),
  promotionReason: readMetadata(model, 'promotion_reason'),
});

/**
 * 評価ステップが記録したスカラーを、splitごとにまとめ直す。
 *
 * ClearMLが返すのは `指標 -> 系列 -> 値` の入れ子である。Python側は
 * `report_scalar(title=指標名, series=split名)` で記録しているので
 * （`ml/pipeline/steps.py`）、指標が外側、splitが内側になる。
 *
 * 読む人が知りたいのは「validationはどうだったか」「testはどうだったか」
 * なので、内と外を入れ替えてsplitごとの1行にする。
 *
 * 読むのは `last_value` である。評価は1イテレーションで1回だけ記録するため、
 * 最後の値がその実行の値になる。
 */
export const toScores = (metrics: readonly ApiScalarMetric[]): EvaluationScore[] => {
  const bySplit = new Map<string, EvaluationScore>();

  for (const metric of metrics) {
    const name = (metric.name ?? '').toLowerCase();
    if (!isEvaluationMetric(name)) {
      continue;
    }

    for (const variant of metric.variants ?? []) {
      const split = variant.name ?? '';
      if (!split) {
        continue;
      }

      const score = bySplit.get(split) ?? emptyScore(split);
      bySplit.set(split, {...score, [name]: variant.last_value ?? null});
    }
  }

  return [...bySplit.values()].sort(
    (left, right) => splitRank(left.split) - splitRank(right.split)
  );
};

/** 並び順の中での位置。知らないsplitは、順序を決めてあるものすべての後ろに来る。 */
const splitRank = (split: string): number => {
  const rank = SPLIT_ORDER.indexOf(split);
  return rank === -1 ? SPLIT_ORDER.length : rank;
};

const isEvaluationMetric = (metric: string): metric is MetricName =>
  (EVALUATION_METRICS as readonly string[]).includes(metric);

const emptyScore = (split: string): EvaluationScore => ({
  split,
  accuracy: null,
  precision: null,
  recall: null,
  f1: null,
});

const readDatasetVersion = (task: ApiTask): string =>
  task.hyperparams?.[DATASET_SECTION]?.[DATASET_VERSION_PARAMETER]?.value ?? '';

const readMetadata = (model: ApiModel, key: string): string => model.metadata?.[key]?.value ?? '';

/**
 * ステップTaskの名前から、Pipeline上のステップ名を取り出す。
 *
 * Pipelineが作るTaskは `<step name> #<run>` のような名前になるため、
 * 表示にはその先頭だけを使う。
 */
const stepNameOf = (taskName: string): string => taskName.split('#')[0].trim();

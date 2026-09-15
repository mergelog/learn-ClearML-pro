/**
 * 画面が扱う形。ClearML APIの応答そのものではない。
 *
 * APIの応答は「Taskという汎用の入れ物」で、どのフィールドが何を意味するかは
 * 呼び出し側の文脈で決まる。画面がそれを直接扱うと、APIの都合が
 * コンポーネントとテンプレートまで漏れていく。
 *
 * ここに置くのは「品質判定パイプラインを操作する人が見るもの」だけである。
 * APIの形からここへの変換は quality-pipeline.adapter.ts が引き受ける。
 */

/** Pipelineが動いているかどうか。APIの status 文字列をここへ寄せる。 */
export type PipelineRunStatus =
  | 'created'
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'stopped'
  | 'unknown';

/**
 * キューに入っているか、走っている状態。
 *
 * `created` を含めない。ClearMLの `created` はdraftで、Queueへ入れるまで
 * 誰も動かさない。draftを「実行中」と呼ぶと、止められないものに停止ボタンが
 * 出て、進まないものを進行中として見せることになる。
 */
export const RUNNING_STATUSES: readonly PipelineRunStatus[] = ['queued', 'running'];

export const isRunning = (status: PipelineRunStatus): boolean => RUNNING_STATUSES.includes(status);

/**
 * まだ終端に達していない状態。読み直す価値があるのはこの状態だけである。
 *
 * `isRunning` と分けているのは、2つの問いが別だからである。
 * 「止められるか」は `isRunning`、「読み直す意味があるか」はこちらで決める。
 *
 * ここに `created` を含めるのは、自分でQueueへ入れた直後の実行が、
 * ClearMLの側でまだ `created` のまま見えることがあるためである。そこで
 * 追跡をやめてしまうと、起動した本人が起動の結果を見られない。
 *
 * `unknown` は含めない。何が起きているか言えない相手を読み続けても、
 * 言えないままである。消されたTaskを永久に叩き続けるのもこれで防ぐ。
 */
export const UNFINISHED_STATUSES: readonly PipelineRunStatus[] = ['created', 'queued', 'running'];

export const isUnfinished = (status: PipelineRunStatus): boolean =>
  UNFINISHED_STATUSES.includes(status);

/** 複製して起動する元になるPipeline Task。 */
export interface PipelineTemplate {
  taskId: string;
  name: string;
}

/** 1回の実行。 */
export interface PipelineRun {
  taskId: string;
  name: string;
  status: PipelineRunStatus;
  statusReason: string;
  datasetVersion: string;
  startedAt: string | null;
  finishedAt: string | null;
}

/** 実行の中の1ステップ。 */
export interface PipelineStep {
  name: string;
  taskId: string;
  status: PipelineRunStatus;
  startedAt: string | null;
  finishedAt: string | null;
}

/** 1つのsplitに対する評価結果。 */
export interface EvaluationScore {
  split: string;
  accuracy: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
}

/** いま提供されているモデル。 */
export interface ProductionModel {
  modelId: string;
  modelVersion: string;
  datasetVersion: string;
  trainTaskId: string;
  promotedBy: string;
  promotedAt: string;
  promotionReason: string;
}

/** 画面全体が持つ状態。 */
export interface QualityPipelineState {
  /** 起動元のPipeline Task。無ければ起動操作そのものができない。 */
  template: PipelineTemplate | null;
  /** いま追跡している実行。 */
  run: PipelineRun | null;
  steps: PipelineStep[];
  /** ステップが上限で打ち切られたか。打ち切ったことを黙っていないために持つ。 */
  stepsTruncated: boolean;
  scores: EvaluationScore[];
  productionModel: ProductionModel | null;
  /** 一覧の読み込み中。 */
  loading: boolean;
  /** 起動要求の送信中。二重起動を防ぐためにloadingとは分けている。 */
  starting: boolean;
  /** 停止要求の送信中。応答が返るまで停止ボタンを押させないために持つ。 */
  cancelling: boolean;
  /** 直前の失敗の理由。成功したら消す。 */
  error: string | null;
}

export const initialQualityPipelineState: QualityPipelineState = {
  template: null,
  run: null,
  steps: [],
  stepsTruncated: false,
  scores: [],
  productionModel: null,
  loading: false,
  starting: false,
  cancelling: false,
  error: null,
};

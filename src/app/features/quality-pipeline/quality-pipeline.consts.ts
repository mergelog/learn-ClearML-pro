/**
 * この画面がClearML上の何を指しているか。
 *
 * プロジェクト名やモデル名は、Python側（`ml/pipeline/domain.py`、
 * `ml/semiconductor_quality/domain.py`）と同じ文字列でなければならない。
 * 片方だけ変えると、画面は何も見つけられないまま「実行がありません」と
 * 表示する。変えるときは必ず両方を直す。
 */

export const PIPELINE_PROJECT = 'Semiconductor Quality Prediction/Pipeline';
export const PIPELINE_NAME = 'semiconductor-quality-training';

/** Pipelineの制御役を載せるQueue。ステップ用とは別である。 */
export const PIPELINE_QUEUE = 'semiconductor-pipeline';

export const MODEL_NAME = 'semiconductor-quality-classifier';
export const PRODUCTION_STAGE_TAG = 'stage:production';

/** 評価ステップの名前。指標を読む相手を決めるのに使う。 */
export const EVALUATE_STEP_NAME = 'evaluate';

/**
 * 走っている実行を読み直す間隔。
 *
 * 短くすると画面はよく動くが、Pipelineは分単位で進むため、得られる情報は
 * 増えないままサーバへの問い合わせだけが増える。
 */
export const REFRESH_INTERVAL_MS = 5_000;

/**
 * 一度に読むステップ数の上限。
 *
 * 現在のPipelineは5ステップなので届かないが、上限そのものは必要である。
 * 上限を置かないと、親を取り違えた問い合わせがそのままTaskの全件取得になる。
 *
 * 届いたときに黙って捨てない。何件かは分からないまま表だけが短くなると、
 * 「そのステップは走らなかった」と読めてしまう。上限に達したことは
 * state に持ち、表に書く。
 */
export const MAXIMUM_STEPS = 50;

/**
 * Dataset Versionとして受け付ける書式。
 *
 * ClearMLに登録されているDatasetの版数は `MAJOR.MINOR.PATCH`
 * （`tools/semiconductor_seed/generator.py`）。書式の違う値でも起動要求は
 * 通ってしまい、Pipelineが実行時にDatasetを見つけられずに落ちるまで
 * 誤りが分からない。押す前に画面側で断る。
 */
export const DATASET_VERSION_PATTERN = /^\d+\.\d+\.\d+$/;

/** 書式に外れたときに出す説明。正規表現をそのまま見せても伝わらない。 */
export const DATASET_VERSION_FORMAT_HINT = 'Use a version like 1.0.0.';

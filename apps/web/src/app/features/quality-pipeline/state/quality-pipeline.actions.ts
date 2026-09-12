import {createActionGroup, emptyProps, props} from '@ngrx/store';
import {
  EvaluationScore,
  PipelineRun,
  PipelineStep,
  PipelineTemplate,
  ProductionModel,
} from '~/features/quality-pipeline/quality-pipeline.model';

/**
 * この画面で起こりうることの一覧。
 *
 * 「何が起きたか」を書き、「次に何をするか」は書かない。`startRun` は
 * 利用者が起動を押したという事実で、`runStarted` はClearMLが受け付けたという
 * 事実である。どちらを受けて何をするかはEffectsとreducerが決める。
 *
 * 失敗は成功と同じ重みで宣言する。失敗を1つのactionにまとめないのは、
 * 「一覧の取得に失敗した」と「起動に失敗した」で画面の戻し方が違うためである。
 */
export const qualityPipelineActions = createActionGroup({
  source: 'Quality Pipeline',
  events: {
    /** 画面を開いた、または再読込を押した。 */
    'open page': emptyProps(),
    'overview loaded': props<{
      template: PipelineTemplate | null;
      run: PipelineRun | null;
      productionModel: ProductionModel | null;
    }>(),
    'overview failed': props<{reason: string}>(),

    /** 起動を押した。 */
    'start run': props<{datasetVersion: string}>(),
    'run started': props<{run: PipelineRun}>(),
    'start failed': props<{reason: string}>(),

    /** 実行中の状態を読み直す。 */
    'refresh run': emptyProps(),
    'run refreshed': props<{
      run: PipelineRun;
      steps: PipelineStep[];
      /** ステップが上限で打ち切られたか。 */
      stepsTruncated: boolean;
    }>(),
    'refresh failed': props<{reason: string}>(),

    /** 評価ステップが終わったので指標を読む。 */
    'scores loaded': props<{scores: EvaluationScore[]}>(),

    /** 実行を止める。 */
    'cancel run': emptyProps(),
    'run cancelled': props<{taskId: string}>(),
    'cancel failed': props<{reason: string}>(),

    /** 画面を離れた。追跡をやめ、状態を捨てる。 */
    'leave page': emptyProps(),
  },
});

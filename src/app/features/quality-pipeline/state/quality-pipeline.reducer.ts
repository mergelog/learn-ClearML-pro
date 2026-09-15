import {createFeature, createReducer, on} from '@ngrx/store';
import {qualityPipelineActions} from '@features/quality-pipeline/state/quality-pipeline.actions';
import {
  QualityPipelineState,
  initialQualityPipelineState,
} from '@features/quality-pipeline/quality-pipeline.model';

export const QUALITY_PIPELINE_FEATURE = 'qualityPipeline';

/**
 * 画面の状態遷移。
 *
 * 4つの決めごとがある。
 *
 * 読み込み中・起動中・停止中を別のフラグで持つ。一覧の再読込中でも起動ボタンを
 * 押せてよいが、起動中に二度押しはできてはいけない。停止も同じで、応答が
 * 返るまでの間に押し直せると `tasks.stop` が何度も飛ぶ。1つのフラグで
 * すべてを表すと、どれかが必ず不自然になる。
 *
 * 成功したら失敗を消す。前の失敗が残ったままだと、画面は成功しているのに
 * 赤い文字が出続ける。
 *
 * 失敗しても直前の結果は消さない。取得に失敗したからといって、それまで
 * 見えていた実行結果まで消える必要はない。消すのは離脱したときだけである。
 *
 * 派生した問い（起動できるか、止められるか）はここに書かない。
 * それは `quality-pipeline.selectors.ts` の仕事である。ここで持つのは
 * 「何が起きたら state がどう変わるか」だけに留める。
 */
export const qualityPipelineFeature = createFeature({
  name: QUALITY_PIPELINE_FEATURE,
  reducer: createReducer<QualityPipelineState>(
    initialQualityPipelineState,

    on(qualityPipelineActions.openPage, (state): QualityPipelineState => ({
      ...state,
      loading: true,
      error: null,
    })),
    on(
      qualityPipelineActions.overviewLoaded,
      (state, {template, run, productionModel}): QualityPipelineState => ({
        ...state,
        template,
        run,
        productionModel,
        // 追跡する実行が変わったら、前の実行のステップと指標は持ち越さない。
        steps: run?.taskId === state.run?.taskId ? state.steps : [],
        stepsTruncated: run?.taskId === state.run?.taskId ? state.stepsTruncated : false,
        scores: run?.taskId === state.run?.taskId ? state.scores : [],
        loading: false,
        error: null,
      })
    ),
    on(qualityPipelineActions.overviewFailed, (state, {reason}): QualityPipelineState => ({
      ...state,
      loading: false,
      error: reason,
    })),

    on(qualityPipelineActions.startRun, (state): QualityPipelineState => ({
      ...state,
      starting: true,
      error: null,
    })),
    on(qualityPipelineActions.runStarted, (state, {run}): QualityPipelineState => ({
      ...state,
      run,
      steps: [],
      stepsTruncated: false,
      scores: [],
      starting: false,
      // 新しい実行に対して、前の実行の停止要求は関係が無い。
      cancelling: false,
      error: null,
    })),
    on(qualityPipelineActions.startFailed, (state, {reason}): QualityPipelineState => ({
      ...state,
      starting: false,
      error: reason,
    })),

    on(
      qualityPipelineActions.runRefreshed,
      (state, {run, steps, stepsTruncated}): QualityPipelineState => ({
        ...state,
        run,
        steps,
        stepsTruncated,
        error: null,
      })
    ),
    on(qualityPipelineActions.refreshFailed, (state, {reason}): QualityPipelineState => ({
      ...state,
      error: reason,
    })),

    on(qualityPipelineActions.scoresLoaded, (state, {scores}): QualityPipelineState => ({
      ...state,
      scores,
    })),

    // 止める相手がいないときは送信も起きない。立てたままにすると、
    // 降ろす相手（runCancelled / cancelFailed）が来ずボタンが戻らなくなる。
    on(qualityPipelineActions.cancelRun, (state): QualityPipelineState => ({
      ...state,
      cancelling: state.run !== null,
      error: null,
    })),
    on(qualityPipelineActions.runCancelled, (state): QualityPipelineState => ({
      ...state,
      cancelling: false,
    })),
    on(qualityPipelineActions.cancelFailed, (state, {reason}): QualityPipelineState => ({
      ...state,
      cancelling: false,
      error: reason,
    })),

    on(qualityPipelineActions.leavePage, (): QualityPipelineState => initialQualityPipelineState)
  ),
});

export const {
  selectQualityPipelineState,
  selectTemplate,
  selectRun,
  selectSteps,
  selectStepsTruncated,
  selectScores,
  selectProductionModel,
  selectLoading,
  selectStarting,
  selectCancelling,
  selectError,
} = qualityPipelineFeature;

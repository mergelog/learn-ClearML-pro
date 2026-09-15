import {createSelector} from '@ngrx/store';
import {
  selectCancelling,
  selectRun,
  selectStarting,
  selectTemplate,
} from '@features/quality-pipeline/state/quality-pipeline.reducer';
import {isRunning} from '@features/quality-pipeline/quality-pipeline.model';

/**
 * state から導かれる問い。
 *
 * reducer が答えるのは「いま何が入っているか」までで、「起動できるか」
 * 「止められるか」はそこから導かれる別の問いである。導出をここへ集めておくと、
 * 同じ判断が component と template に散らばらない。
 *
 * どの selector も state しか見ない。入力途中の文字のような、まだ誰にも
 * 共有していない値は component 側の関心であり、ここには現れない。
 */

/** 起動できるのは、複製元があって、いま起動中でもない場合だけである。 */
export const selectCanStart = createSelector(
  selectTemplate,
  selectStarting,
  (template, starting) => template !== null && !starting
);

/**
 * キューに入っているか走っている実行があるか。
 *
 * 再取得を続けるかどうかの判断はここではしない。それはEffects側が、
 * 読み直した結果（`isUnfinished`）で決める。ここで見ているのは
 * 「利用者が止められる相手がいるか」だけである。
 */
export const selectRunInProgress = createSelector(
  selectRun,
  (run) => run !== null && isRunning(run.status)
);

/**
 * 止められるのは、走っている実行があって、まだ停止要求を送っていないときだけ。
 *
 * 送信中を含めるのは、停止の応答が返るまでに間があるためである。その間ボタンを
 * 押せたままにすると、同じ実行へ `tasks.stop` が何度も飛ぶ。
 */
export const selectCanCancel = createSelector(
  selectRunInProgress,
  selectCancelling,
  (inProgress, cancelling) => inProgress && !cancelling
);

/**
 * 直近の実行が、複製元として出しているTaskそのものかどうか。
 *
 * Python側はPipelineを走らせるたびに、同じ名前・同じプロジェクトで制御役の
 * Taskを作る（`ml/pipeline/controller.py`）。専用のテンプレートTaskは無い。
 * そのため「複製元」と「直近の実行」が同じ1つのTaskを指すことがある。
 *
 * 画面はそれを隠さない。同じものを2か所に出しておいて別物のように見せると、
 * 起動を押したときに何が複製されるのかが分からなくなる。
 */
export const selectRunIsTemplate = createSelector(
  selectTemplate,
  selectRun,
  (template, run) => template !== null && run !== null && template.taskId === run.taskId
);

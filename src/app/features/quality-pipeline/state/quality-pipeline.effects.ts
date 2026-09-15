import {inject, Injectable} from '@angular/core';
import {Actions, createEffect, ofType} from '@ngrx/effects';
import {concatLatestFrom} from '@ngrx/operators';
import {Action, Store} from '@ngrx/store';
import {EMPTY, forkJoin, Observable, of, timer} from 'rxjs';
import {
  catchError,
  distinctUntilChanged,
  exhaustMap,
  filter,
  map,
  switchMap,
  takeUntil,
  takeWhile,
} from 'rxjs/operators';
import {qualityPipelineActions} from '@features/quality-pipeline/state/quality-pipeline.actions';
import {QualityPipelineApiService} from '@features/quality-pipeline/data-access/quality-pipeline-api.service';
import {
  EVALUATE_STEP_NAME,
  MODEL_NAME,
  PIPELINE_NAME,
  PIPELINE_PROJECT,
  PIPELINE_QUEUE,
  PRODUCTION_STAGE_TAG,
  REFRESH_INTERVAL_MS,
} from '@features/quality-pipeline/quality-pipeline.consts';
import {selectRun, selectTemplate} from '@features/quality-pipeline/state/quality-pipeline.reducer';
import {
  PipelineRun,
  PipelineStep,
  isUnfinished,
} from '@features/quality-pipeline/quality-pipeline.model';
import {describeClearmlFailure} from '~/shared/clearml/clearml-failure';

/**
 * この画面が外の世界に触れる唯一の場所。
 *
 * Effectsは、更新する state と同じ feature の下に置いてある。どの state が
 * どこから書き換わるのかを、ディレクトリを見れば追えるようにするためである。
 *
 * 決めごとが6つある。
 *
 * 失敗はactionとして流す。例外をそのまま投げると、そのeffectは以後
 * 何も受け取らなくなる。画面が「押しても無反応」になるのはこれが原因になりやすい。
 *
 * 走っている間だけ再取得する。終わった実行を叩き続けても状態は変わらず、
 * サーバへの負荷と画面のちらつきだけが残る。止める判断は、読み直した結果が
 * 終端に達したかどうかで行う。
 *
 * 画面を離れたら再取得を止める。`takeUntil` を付けないと、別の画面へ移った後も
 * 裏で問い合わせが続く。
 *
 * サーバの状態を変える操作は打ち切らない。読み取りは新しい要求で置き換えて
 * よいが、起動と停止は途中で捨てるとClearML側に中途半端なものが残る。
 * 読み取りは `switchMap`、書き込みは `exhaustMap` を使う。
 *
 * 複数の読み取りをまとめるときは `forkJoin` を使う。ここで欲しいのは
 * 「それぞれが1回ずつ答えたら、揃った結果を1つ」であって、そのあとどれかが
 * 再びemitしたときの組み合わせではない。`combineLatest` は後者まで拾うので、
 * 取得元をキャッシュ付きに変えた途端に余分なactionが流れ始める。
 *
 * stateはactionが来てから読む。`concatLatestFrom` はactionが届くまでstoreを
 * 購読しないため、effectを組み立てた時点の購読が残らない。
 */
@Injectable()
export class QualityPipelineEffects {
  private readonly actions = inject(Actions);
  private readonly store = inject(Store);
  private readonly api = inject(QualityPipelineApiService);

  /** 画面を開いたら、起動元・直近の実行・提供中のモデルをまとめて読む。 */
  readonly loadOverview = createEffect(() =>
    this.actions.pipe(
      ofType(qualityPipelineActions.openPage),
      switchMap(() =>
        forkJoin([
          this.api.getTemplate(PIPELINE_PROJECT, PIPELINE_NAME),
          this.api.getLatestRun(PIPELINE_PROJECT, PIPELINE_NAME),
          this.api.getProductionModel(MODEL_NAME, PRODUCTION_STAGE_TAG),
        ]).pipe(
          map(([template, run, productionModel]) =>
            qualityPipelineActions.overviewLoaded({template, run, productionModel})
          ),
          catchError((error: unknown) =>
            of(qualityPipelineActions.overviewFailed({reason: describeClearmlFailure(error)}))
          )
        )
      )
    )
  );

  /**
   * 起動は「複製して、値を変えて、Queueへ入れる」までを1つの操作として扱う。
   *
   * `exhaustMap` にしているのは、送信中の要求を後から来た要求で置き換えないため
   * である。`switchMap` だと、複製が済んでQueueへ入れる前に打ち切られたときに、
   * 誰も拾わないTaskだけがClearMLに残る。送信中の押下は捨ててよい。
   */
  readonly startRun = createEffect(() =>
    this.actions.pipe(
      ofType(qualityPipelineActions.startRun),
      concatLatestFrom(() => this.store.select(selectTemplate)),
      exhaustMap(([{datasetVersion}, template]) => {
        if (template === null) {
          return of(
            qualityPipelineActions.startFailed({
              reason:
                'There is no pipeline to start from. Submit one first with ' +
                '`pnpm ml:pipeline -- --dataset-version <version> --submit`.',
            })
          );
        }

        return this.api
          .startRun({
            templateTaskId: template.taskId,
            runName: `${PIPELINE_NAME} ${datasetVersion}`,
            datasetVersion,
            queueName: PIPELINE_QUEUE,
            reason: `Started from the quality pipeline page for dataset ${datasetVersion}`,
          })
          .pipe(
            switchMap((taskId) => this.api.getRun(taskId)),
            map((run) => qualityPipelineActions.runStarted({run})),
            catchError((error: unknown) =>
              of(qualityPipelineActions.startFailed({reason: describeClearmlFailure(error)}))
            )
          );
      })
    )
  );

  /**
   * 起動した実行を、終わるまで追いかける。
   *
   * 一定間隔で読み直し、終端に達したら止める。画面を離れたときも止める。
   */
  readonly followRun = createEffect(() =>
    this.actions.pipe(
      ofType(qualityPipelineActions.runStarted, qualityPipelineActions.overviewLoaded),
      map((action) => runToFollow(action)),
      filter((run): run is PipelineRun => run !== null),
      switchMap((run) => this.follow(run.taskId))
    )
  );

  /** 再読込を押したときの1回だけの読み直し。 */
  readonly refreshRun = createEffect(() =>
    this.actions.pipe(
      ofType(qualityPipelineActions.refreshRun),
      concatLatestFrom(() => this.store.select(selectRun)),
      switchMap(([, run]) => (run === null ? EMPTY : this.refresh(run.taskId)))
    )
  );

  /**
   * 評価ステップが終わったら、その指標を読む。
   *
   * 追跡中は `runRefreshed` が一定間隔で流れてくるが、指標は評価ステップが
   * 終わった時点で確定している。同じステップを見ている限り読み直さない。
   */
  readonly loadScores = createEffect(() =>
    this.actions.pipe(
      ofType(qualityPipelineActions.runRefreshed),
      map(({steps}) => finishedEvaluateStep(steps)),
      filter((step): step is PipelineStep => step !== null),
      distinctUntilChanged((previous, current) => previous.taskId === current.taskId),
      switchMap((step) =>
        this.api.getScores(step.taskId).pipe(
          map((scores) => qualityPipelineActions.scoresLoaded({scores})),
          // 指標が読めないことは、実行そのものの失敗ではない。
          // 画面全体を失敗にせず、指標だけ空のままにしておく。
          catchError(() => EMPTY)
        )
      )
    )
  );

  /** 止める。止めた後の状態は、次の再取得が拾う。 */
  readonly cancelRun = createEffect(() =>
    this.actions.pipe(
      ofType(qualityPipelineActions.cancelRun),
      concatLatestFrom(() => this.store.select(selectRun)),
      exhaustMap(([, run]) => {
        if (run === null) {
          return EMPTY;
        }
        return this.api.stopRun(run.taskId, 'Stopped from the quality pipeline page').pipe(
          map((taskId) => qualityPipelineActions.runCancelled({taskId})),
          catchError((error: unknown) =>
            of(qualityPipelineActions.cancelFailed({reason: describeClearmlFailure(error)}))
          )
        );
      })
    )
  );

  /** 止めた直後は、状態が変わっているはずなので読み直す。 */
  readonly refreshAfterCancel = createEffect(() =>
    this.actions.pipe(
      ofType(qualityPipelineActions.runCancelled),
      switchMap(({taskId}) => this.refresh(taskId))
    )
  );

  /**
   * 1つの実行を、終端に達するまで読み直し続ける。
   *
   * 止める条件を「読み直した結果が終端だった」に置いている。実行の状態は
   * 追跡を始めた時点のものしか手元に無いので、開始時の状態で判断すると
   * いつまでも止まらない。
   */
  private follow(taskId: string): Observable<Action> {
    return timer(0, REFRESH_INTERVAL_MS).pipe(
      switchMap(() => this.refresh(taskId)),
      // 終端に達したものも1つ流してから止める。そうしないと最後の状態が画面に出ない。
      takeWhile((action) => keepFollowing(action), true),
      takeUntil(this.actions.pipe(ofType(qualityPipelineActions.leavePage)))
    );
  }

  private refresh(taskId: string): Observable<Action> {
    return forkJoin([this.api.getRun(taskId), this.api.getSteps(taskId)]).pipe(
      map(([run, steps]) =>
        qualityPipelineActions.runRefreshed({
          run,
          steps: steps.steps,
          stepsTruncated: steps.truncated,
        })
      ),
      catchError((error: unknown) =>
        of(qualityPipelineActions.refreshFailed({reason: describeClearmlFailure(error)}))
      )
    );
  }
}

/**
 * 追跡を始める対象の実行。
 *
 * 自分でQueueへ入れた直後の実行は、状態を見ずに追う。ClearMLが `queued` を
 * 返すまでにわずかな間があり、そこで見送ると、起動した本人が起動の結果を
 * 見られなくなる。
 *
 * 読み込みで見つけた実行は、まだ終わっていないものだけを追う。終わった実行を
 * 読み直しても状態は変わらない。
 */
const runToFollow = (
  action:
    | ReturnType<typeof qualityPipelineActions.runStarted>
    | ReturnType<typeof qualityPipelineActions.overviewLoaded>
): PipelineRun | null => {
  if (action.type === qualityPipelineActions.runStarted.type) {
    return action.run;
  }
  return action.run !== null && isUnfinished(action.run.status) ? action.run : null;
};

/**
 * 読み直しを続けるかどうか。
 *
 * 終端に達したことが分かったときだけ止める。読み直しに失敗しただけでは
 * 止めない。一度の通信の失敗で追跡が終わると、繋がり直しても画面は
 * 止まったままになる。
 */
const keepFollowing = (action: Action): boolean =>
  !isRunRefreshed(action) || isUnfinished(action.run.status);

const isRunRefreshed = (
  action: Action
): action is ReturnType<typeof qualityPipelineActions.runRefreshed> =>
  action.type === qualityPipelineActions.runRefreshed.type;

/** 終わった評価ステップ。指標が出そろっているのはこの後だけである。 */
const finishedEvaluateStep = (steps: readonly PipelineStep[]): PipelineStep | null =>
  steps.find((step) => step.name === EVALUATE_STEP_NAME && step.status === 'completed') ?? null;

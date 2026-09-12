import {TestBed} from '@angular/core/testing';
import {HttpErrorResponse} from '@angular/common/http';
import {provideMockActions} from '@ngrx/effects/testing';
import {MockStore, provideMockStore} from '@ngrx/store/testing';
import {Observable, of, throwError} from 'rxjs';
import {take, toArray} from 'rxjs/operators';
import {Action} from '@ngrx/store';
import {qualityPipelineActions} from '~/features/quality-pipeline/state/quality-pipeline.actions';
import {QualityPipelineEffects} from '~/features/quality-pipeline/state/quality-pipeline.effects';
import {
  PipelineStepPage,
  QualityPipelineApiService,
} from '~/features/quality-pipeline/data-access/quality-pipeline-api.service';
import {
  QUALITY_PIPELINE_FEATURE,
  qualityPipelineFeature,
} from '~/features/quality-pipeline/state/quality-pipeline.reducer';
import {
  PipelineRun,
  PipelineStep,
  PipelineTemplate,
  QualityPipelineState,
  initialQualityPipelineState,
} from '~/features/quality-pipeline/quality-pipeline.model';

const template: PipelineTemplate = {
  taskId: 'template-id',
  name: 'semiconductor-quality-training',
};

const run = (overrides: Partial<PipelineRun> = {}): PipelineRun => ({
  taskId: 'run-id',
  name: 'semiconductor-quality-training 1.0.0',
  status: 'completed',
  statusReason: '',
  datasetVersion: '1.0.0',
  startedAt: null,
  finishedAt: null,
  ...overrides,
});

const evaluateStep: PipelineStep = {
  name: 'evaluate',
  taskId: 'evaluate-task',
  status: 'completed',
  startedAt: null,
  finishedAt: null,
};

/** テスト用のAPI境界。呼ばれた回数と引数を覚える。 */
class StubApi {
  templateResponse: Observable<PipelineTemplate | null> = of(template);
  latestRunResponse: Observable<PipelineRun | null> = of(null);
  productionModelResponse = of(null);
  runResponse: Observable<PipelineRun> = of(run());
  stepsResponse: Observable<PipelineStepPage> = of({steps: [], truncated: false});
  scoresResponse = of([]);
  startResponse: Observable<string> = of('new-run-id');
  stopResponse: Observable<string> = of('run-id');

  readonly started: unknown[] = [];
  readonly stopped: string[] = [];

  getTemplate = () => this.templateResponse;
  getLatestRun = () => this.latestRunResponse;
  getProductionModel = () => this.productionModelResponse;
  getRun = () => this.runResponse;
  getSteps = () => this.stepsResponse;
  getScores = () => this.scoresResponse;

  startRun = (request: unknown) => {
    this.started.push(request);
    return this.startResponse;
  };

  stopRun = (taskId: string) => {
    this.stopped.push(taskId);
    return this.stopResponse;
  };
}

const setUpEffects = (
  action: Action,
  state: Partial<QualityPipelineState> = {},
  configure: (api: StubApi) => void = () => undefined
): {effects: QualityPipelineEffects; api: StubApi; store: MockStore} => {
  const actions = of(action);
  const api = new StubApi();
  configure(api);

  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      QualityPipelineEffects,
      provideMockActions(() => actions),
      provideMockStore({
        initialState: {
          [QUALITY_PIPELINE_FEATURE]: {...initialQualityPipelineState, ...state},
        },
      }),
      {provide: QualityPipelineApiService, useValue: api},
    ],
  });

  return {
    effects: TestBed.inject(QualityPipelineEffects),
    api,
    store: TestBed.inject(MockStore),
  };
};

const runEffect = (
  effectOf: (effects: QualityPipelineEffects) => Observable<Action>,
  action: Action,
  state: Partial<QualityPipelineState> = {},
  configure: (api: StubApi) => void = () => undefined
): Promise<Action[]> => {
  const {effects} = setUpEffects(action, state, configure);

  return new Promise((resolve) => {
    effectOf(effects).pipe(take(1), toArray()).subscribe(resolve);
  });
};

/**
 * 一定時間だけeffectを購読し、流れたactionと、その間に終わったかを見る。
 *
 * 追跡は「止まること」自体が仕様なので、`take(1)` では確かめられない。
 * 止まらないeffectは完了しないため、時間で区切って完了の有無を見る。
 */
const observeEffect = (
  effect: Observable<Action>,
  windowMs = 200
): Promise<{actions: Action[]; completed: boolean}> =>
  new Promise((resolve) => {
    const actions: Action[] = [];
    let completed = false;

    const subscription = effect.subscribe({
      next: (action) => actions.push(action),
      complete: () => {
        completed = true;
      },
    });

    setTimeout(() => {
      subscription.unsubscribe();
      resolve({actions, completed});
    }, windowMs);
  });

describe('quality pipeline effects', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('opening the page', () => {
    it('reports what it found', async () => {
      const [action] = await runEffect(
        (effects) => effects.loadOverview,
        qualityPipelineActions.openPage()
      );

      expect(action.type).toBe(qualityPipelineActions.overviewLoaded.type);
    });

    it('turns a failure into an action rather than throwing', async () => {
      const emitted = await runEffect(
        (effects) => effects.loadOverview,
        qualityPipelineActions.openPage(),
        {},
        (api) => {
          api.templateResponse = throwError(() => new Error('the server refused'));
        }
      );

      expect(emitted[0].type).toBe(qualityPipelineActions.overviewFailed.type);
      expect(emitted[0]).toMatchObject({reason: 'the server refused'});
    });

    it('repeats what ClearML said when it explained itself', async () => {
      const emitted = await runEffect(
        (effects) => effects.loadOverview,
        qualityPipelineActions.openPage(),
        {},
        (api) => {
          api.templateResponse = throwError(
            () =>
              new HttpErrorResponse({
                status: 400,
                statusText: 'Bad Request',
                error: {meta: {result_msg: 'project not found'}},
              })
          );
        }
      );

      expect(emitted[0]).toMatchObject({reason: 'project not found'});
    });

    it('names the status when the failure carried no explanation', async () => {
      // HttpErrorResponse は Error を継承していないので、Error として扱うと
      // ここが固定文言に落ちる。502も接続断も同じ見た目になってしまう。
      const emitted = await runEffect(
        (effects) => effects.loadOverview,
        qualityPipelineActions.openPage(),
        {},
        (api) => {
          api.templateResponse = throwError(
            () => new HttpErrorResponse({status: 502, statusText: 'Bad Gateway'})
          );
        }
      );

      expect(emitted[0]).toMatchObject({reason: '502 Bad Gateway'});
    });

    it('describes the connection itself when the request never reached the server', async () => {
      const emitted = await runEffect(
        (effects) => effects.loadOverview,
        qualityPipelineActions.openPage(),
        {},
        (api) => {
          api.templateResponse = throwError(
            () => new HttpErrorResponse({status: 0, url: 'https://clearml.test/tasks.get_all_ex'})
          );
        }
      );

      const {reason} = emitted[0] as unknown as {reason: string};

      expect(reason).not.toBe('0 Unknown Error');
      expect(reason.length).toBeGreaterThan(0);
    });
  });

  describe('starting a run', () => {
    it('refuses to start when there is nothing to clone from', async () => {
      const [action] = await runEffect(
        (effects) => effects.startRun,
        qualityPipelineActions.startRun({datasetVersion: '1.0.0'}),
        {template: null}
      );

      expect(action.type).toBe(qualityPipelineActions.startFailed.type);
    });

    it('reports the started run when a template exists', async () => {
      const [action] = await runEffect(
        (effects) => effects.startRun,
        qualityPipelineActions.startRun({datasetVersion: '2.0.0'}),
        {template}
      );

      expect(action.type).toBe(qualityPipelineActions.runStarted.type);
    });
  });

  describe('refreshing', () => {
    it('does nothing when there is no run to refresh', async () => {
      const emitted = await Promise.race([
        runEffect((effects) => effects.refreshRun, qualityPipelineActions.refreshRun(), {run: null}),
        new Promise<Action[]>((resolve) => setTimeout(() => resolve([]), 50)),
      ]);

      expect(emitted).toEqual([]);
    });

    it('reads the run and its steps back', async () => {
      const [action] = await runEffect(
        (effects) => effects.refreshRun,
        qualityPipelineActions.refreshRun(),
        {run: run({status: 'running'})}
      );

      expect(action.type).toBe(qualityPipelineActions.runRefreshed.type);
    });

    it('carries over that the steps were cut off at the limit', async () => {
      // 切り捨てを state まで運ばないと、表は短くなった理由を言えない。
      const [action] = await runEffect(
        (effects) => effects.refreshRun,
        qualityPipelineActions.refreshRun(),
        {run: run({status: 'running'})},
        (api) => {
          api.stepsResponse = of({steps: [evaluateStep], truncated: true});
        }
      );

      expect(action).toEqual(
        qualityPipelineActions.runRefreshed({
          run: run(),
          steps: [evaluateStep],
          stepsTruncated: true,
        })
      );
    });
  });

  describe('scores', () => {
    it('reads the metrics once the evaluation step has finished', async () => {
      const [action] = await runEffect(
        (effects) => effects.loadScores,
        qualityPipelineActions.runRefreshed({
          run: run(),
          steps: [evaluateStep],
          stepsTruncated: false,
        })
      );

      expect(action.type).toBe(qualityPipelineActions.scoresLoaded.type);
    });

    it('waits while the evaluation step is still running', async () => {
      const emitted = await Promise.race([
        runEffect(
          (effects) => effects.loadScores,
          qualityPipelineActions.runRefreshed({
            run: run({status: 'running'}),
            steps: [{...evaluateStep, status: 'running'}],
            stepsTruncated: false,
          })
        ),
        new Promise<Action[]>((resolve) => setTimeout(() => resolve([]), 50)),
      ]);

      expect(emitted).toEqual([]);
    });
  });

  describe('following a run', () => {
    it('stops reading once the run has reached an end state', async () => {
      const {effects} = setUpEffects(
        qualityPipelineActions.runStarted({run: run({status: 'running'})}),
        {},
        (api) => {
          api.runResponse = of(run({status: 'completed'}));
        }
      );

      const {actions, completed} = await observeEffect(effects.followRun);

      // 終わった状態も1つ流してから止める。最後の状態が画面に残らないと困る。
      expect(actions).toHaveLength(1);
      expect(actions[0].type).toBe(qualityPipelineActions.runRefreshed.type);
      expect(completed).toBe(true);
    });

    it('keeps reading while the run is still going', async () => {
      const {effects} = setUpEffects(
        qualityPipelineActions.runStarted({run: run({status: 'running'})}),
        {},
        (api) => {
          api.runResponse = of(run({status: 'running'}));
        }
      );

      const {actions, completed} = await observeEffect(effects.followRun);

      expect(actions).toHaveLength(1);
      expect(completed).toBe(false);
    });

    it('follows a run it just started, even before ClearML reports it as queued', async () => {
      // 起動直後はまだ created のまま見えることがある。
      // ここで見送ると、起動した本人が起動の結果を見られない。
      const {effects} = setUpEffects(
        qualityPipelineActions.runStarted({run: run({status: 'created'})}),
        {},
        (api) => {
          api.runResponse = of(run({status: 'created'}));
        }
      );

      const {actions} = await observeEffect(effects.followRun);

      expect(actions).toHaveLength(1);
    });

    it('does not follow a run that had already finished when the page opened', async () => {
      const {effects} = setUpEffects(
        qualityPipelineActions.overviewLoaded({
          template,
          run: run({status: 'completed'}),
          productionModel: null,
        })
      );

      const {actions} = await observeEffect(effects.followRun);

      expect(actions).toEqual([]);
    });

    it('keeps following after one read fails', async () => {
      // 一度の通信の失敗で追跡が終わると、繋がり直しても画面は止まったままになる。
      const {effects} = setUpEffects(
        qualityPipelineActions.runStarted({run: run({status: 'running'})}),
        {},
        (api) => {
          api.runResponse = throwError(() => new Error('the request timed out'));
        }
      );

      const {actions, completed} = await observeEffect(effects.followRun);

      expect(actions[0].type).toBe(qualityPipelineActions.refreshFailed.type);
      expect(completed).toBe(false);
    });
  });

  describe('cancelling', () => {
    it('does nothing when there is no run', async () => {
      const emitted = await Promise.race([
        runEffect((effects) => effects.cancelRun, qualityPipelineActions.cancelRun(), {run: null}),
        new Promise<Action[]>((resolve) => setTimeout(() => resolve([]), 50)),
      ]);

      expect(emitted).toEqual([]);
    });

    it('reports the cancelled run', async () => {
      const [action] = await runEffect(
        (effects) => effects.cancelRun,
        qualityPipelineActions.cancelRun(),
        {run: run({status: 'running'})}
      );

      expect(action.type).toBe(qualityPipelineActions.runCancelled.type);
    });

    it('reads the state back after cancelling', async () => {
      const [action] = await runEffect(
        (effects) => effects.refreshAfterCancel,
        qualityPipelineActions.runCancelled({taskId: 'run-id'})
      );

      expect(action.type).toBe(qualityPipelineActions.runRefreshed.type);
    });
  });

  describe('the feature is registered under its own name', () => {
    it('keeps the state key and the feature in step', () => {
      expect(qualityPipelineFeature.name).toBe(QUALITY_PIPELINE_FEATURE);
    });
  });

  describe('set up', () => {
    it('provides the effects with a store and an api', () => {
      const {api, store} = setUpEffects(qualityPipelineActions.openPage());

      expect(api).toBeTruthy();
      expect(store).toBeTruthy();
    });
  });
});

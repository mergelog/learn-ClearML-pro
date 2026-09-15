import {qualityPipelineActions} from '@features/quality-pipeline/state/quality-pipeline.actions';
import {qualityPipelineFeature} from '@features/quality-pipeline/state/quality-pipeline.reducer';
import {
  EvaluationScore,
  PipelineRun,
  PipelineStep,
  PipelineTemplate,
  ProductionModel,
  QualityPipelineState,
  initialQualityPipelineState,
} from '@features/quality-pipeline/quality-pipeline.model';

const reducer = qualityPipelineFeature.reducer;

const template: PipelineTemplate = {
  taskId: 'template-id',
  name: 'semiconductor-quality-training',
};

const run = (overrides: Partial<PipelineRun> = {}): PipelineRun => ({
  taskId: 'run-id',
  name: 'semiconductor-quality-training 1.0.0',
  status: 'running',
  statusReason: '',
  datasetVersion: '1.0.0',
  startedAt: null,
  finishedAt: null,
  ...overrides,
});

const step: PipelineStep = {
  name: 'validate',
  taskId: 'step-id',
  status: 'completed',
  startedAt: null,
  finishedAt: null,
};

const score: EvaluationScore = {
  split: 'validation',
  accuracy: 0.81,
  precision: 0.85,
  recall: 0.63,
  f1: 0.72,
};

const productionModel: ProductionModel = {
  modelId: 'model-id',
  modelVersion: '1.0.0-20260908T043015Z-abcdef01',
  datasetVersion: '1.0.0',
  trainTaskId: 'train-task',
  promotedBy: 'reviewer',
  promotedAt: '2026-09-08T04:30:15Z',
  promotionReason: 'the trial went well',
};

const loaded = (overrides: Partial<QualityPipelineState> = {}): QualityPipelineState => ({
  ...initialQualityPipelineState,
  template,
  run: run(),
  steps: [step],
  scores: [score],
  productionModel,
  ...overrides,
});

describe('quality pipeline reducer', () => {
  describe('opening the page', () => {
    it('starts loading and clears whatever failed last time', () => {
      const before = loaded({error: 'the previous attempt failed'});

      const after = reducer(before, qualityPipelineActions.openPage());

      expect(after.loading).toBe(true);
      expect(after.error).toBeNull();
    });

    it('keeps showing what it already had while it loads', () => {
      const after = reducer(loaded(), qualityPipelineActions.openPage());

      expect(after.run).not.toBeNull();
      expect(after.productionModel).not.toBeNull();
    });

    it('stops loading once the overview arrives', () => {
      const after = reducer(
        loaded({loading: true}),
        qualityPipelineActions.overviewLoaded({template, run: run(), productionModel})
      );

      expect(after.loading).toBe(false);
      expect(after.template).toEqual(template);
    });

    it('drops the steps and scores when it starts following another run', () => {
      const after = reducer(
        loaded(),
        qualityPipelineActions.overviewLoaded({
          template,
          run: run({taskId: 'another-run'}),
          productionModel,
        })
      );

      expect(after.steps).toEqual([]);
      expect(after.scores).toEqual([]);
    });

    it('keeps the steps and scores when it is the same run', () => {
      const after = reducer(
        loaded(),
        qualityPipelineActions.overviewLoaded({template, run: run(), productionModel})
      );

      expect(after.steps).toEqual([step]);
      expect(after.scores).toEqual([score]);
    });

    it('reports why loading failed without hiding what it already showed', () => {
      const after = reducer(
        loaded({loading: true}),
        qualityPipelineActions.overviewFailed({reason: 'the server refused'})
      );

      expect(after.loading).toBe(false);
      expect(after.error).toBe('the server refused');
      expect(after.run).not.toBeNull();
    });
  });

  describe('starting a run', () => {
    it('marks the request in flight without blocking the rest of the page', () => {
      const after = reducer(loaded(), qualityPipelineActions.startRun({datasetVersion: '2.0.0'}));

      expect(after.starting).toBe(true);
      expect(after.loading).toBe(false);
    });

    it('follows the new run and forgets the previous results', () => {
      const started = run({taskId: 'new-run', status: 'queued'});

      const after = reducer(
        loaded({starting: true}),
        qualityPipelineActions.runStarted({run: started})
      );

      expect(after.starting).toBe(false);
      expect(after.run).toEqual(started);
      expect(after.steps).toEqual([]);
      expect(after.scores).toEqual([]);
    });

    it('drops a stop request that belonged to the run it replaced', () => {
      const after = reducer(
        loaded({starting: true, cancelling: true}),
        qualityPipelineActions.runStarted({run: run({taskId: 'new-run', status: 'queued'})})
      );

      expect(after.cancelling).toBe(false);
    });

    it('lets the button be pressed again after a failed start', () => {
      const after = reducer(
        loaded({starting: true}),
        qualityPipelineActions.startFailed({reason: 'the queue does not exist'})
      );

      expect(after.starting).toBe(false);
      expect(after.error).toBe('the queue does not exist');
    });
  });

  describe('following a run', () => {
    it('replaces the run and its steps with what was read', () => {
      const finished = run({status: 'completed', finishedAt: '2026-09-08T05:00:00Z'});

      const after = reducer(
        loaded(),
        qualityPipelineActions.runRefreshed({
          run: finished,
          steps: [step],
          stepsTruncated: false,
        })
      );

      expect(after.run).toEqual(finished);
      expect(after.steps).toEqual([step]);
      expect(after.error).toBeNull();
    });

    it('remembers that the steps it was given are not all of them', () => {
      // 表が短いのは「走らなかった」からではない、と言えるようにしておく。
      const after = reducer(
        loaded(),
        qualityPipelineActions.runRefreshed({
          run: run(),
          steps: [step],
          stepsTruncated: true,
        })
      );

      expect(after.stepsTruncated).toBe(true);
    });

    it('forgets the cut-off once a new run is started', () => {
      const before = reducer(
        loaded(),
        qualityPipelineActions.runRefreshed({run: run(), steps: [step], stepsTruncated: true})
      );

      const after = reducer(before, qualityPipelineActions.runStarted({run: run()}));

      expect(after.stepsTruncated).toBe(false);
    });

    it('reports a failed refresh without losing the last known state', () => {
      const after = reducer(
        loaded(),
        qualityPipelineActions.refreshFailed({reason: 'the request timed out'})
      );

      expect(after.error).toBe('the request timed out');
      expect(after.run).not.toBeNull();
      expect(after.steps).toEqual([step]);
    });

    it('keeps the scores it was given', () => {
      const after = reducer(
        loaded({scores: []}),
        qualityPipelineActions.scoresLoaded({scores: [score]})
      );

      expect(after.scores).toEqual([score]);
    });
  });

  describe('cancelling a run', () => {
    it('marks the stop request in flight so it cannot be sent twice', () => {
      const after = reducer(loaded(), qualityPipelineActions.cancelRun());

      expect(after.cancelling).toBe(true);
      expect(after.error).toBeNull();
    });

    it('does not mark anything in flight when there is no run to stop', () => {
      // 送信が起きないので、降ろす相手も来ない。立てたままにすると戻らなくなる。
      const after = reducer(loaded({run: null}), qualityPipelineActions.cancelRun());

      expect(after.cancelling).toBe(false);
    });

    it('lets the button come back once ClearML has taken the stop', () => {
      const after = reducer(
        loaded({cancelling: true}),
        qualityPipelineActions.runCancelled({taskId: 'run-id'})
      );

      expect(after.cancelling).toBe(false);
    });

    it('reports a cancel that could not be carried out', () => {
      const after = reducer(
        loaded({cancelling: true}),
        qualityPipelineActions.cancelFailed({reason: 'the run had already finished'})
      );

      expect(after.cancelling).toBe(false);
      expect(after.error).toBe('the run had already finished');
    });
  });

  describe('leaving the page', () => {
    it('forgets everything, so the next visit does not show a stale run', () => {
      const after = reducer(loaded({error: 'something'}), qualityPipelineActions.leavePage());

      expect(after).toEqual(initialQualityPipelineState);
    });
  });
});

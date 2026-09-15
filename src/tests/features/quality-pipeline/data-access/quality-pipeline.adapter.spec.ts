import {
  ApiModel,
  ApiScalarMetric,
  ApiTask,
  toProductionModel,
  toRun,
  toScores,
  toStatus,
  toStep,
  toTemplate,
} from '@features/quality-pipeline/data-access/quality-pipeline.adapter';

const taskWithDataset = (version: string): ApiTask => ({
  id: 'task-id',
  name: 'semiconductor-quality-training',
  status: 'in_progress',
  hyperparams: {Dataset: {dataset_version: {value: version}}},
});

describe('quality pipeline adapter', () => {
  describe('status', () => {
    it('maps the states ClearML reports onto the ones the page shows', () => {
      expect(toStatus('created')).toBe('created');
      expect(toStatus('queued')).toBe('queued');
      expect(toStatus('in_progress')).toBe('running');
      expect(toStatus('completed')).toBe('completed');
      expect(toStatus('failed')).toBe('failed');
      expect(toStatus('stopped')).toBe('stopped');
    });

    it('treats a closed or published task as finished', () => {
      expect(toStatus('closed')).toBe('completed');
      expect(toStatus('published')).toBe('completed');
    });

    it('keeps a state it does not know rather than dropping it', () => {
      expect(toStatus('something-new')).toBe('unknown');
    });

    it('reports a missing state as unknown rather than as finished', () => {
      expect(toStatus(undefined)).toBe('unknown');
    });
  });

  describe('run', () => {
    it('reads the dataset version out of the recorded parameters', () => {
      expect(toRun(taskWithDataset('2.0.0')).datasetVersion).toBe('2.0.0');
    });

    it('reports no dataset version rather than inventing one', () => {
      expect(toRun({id: 'task-id'}).datasetVersion).toBe('');
    });

    it('keeps the times absent instead of filling them in', () => {
      const run = toRun({id: 'task-id', status: 'queued'});

      expect(run.startedAt).toBeNull();
      expect(run.finishedAt).toBeNull();
    });

    it('carries the reason a run stopped', () => {
      const run = toRun({id: 'task-id', status: 'failed', status_reason: 'ValueError'});

      expect(run.status).toBe('failed');
      expect(run.statusReason).toBe('ValueError');
    });
  });

  describe('template', () => {
    it('names the task a run is cloned from', () => {
      const template = toTemplate(taskWithDataset('1.0.0'));

      expect(template.taskId).toBe('task-id');
      expect(template.name).toBe('semiconductor-quality-training');
    });
  });

  describe('step', () => {
    it('shows the step name without the run number ClearML appends', () => {
      expect(toStep({id: 'step-id', name: 'validate #3'}).name).toBe('validate');
    });

    it('leaves a plain step name untouched', () => {
      expect(toStep({id: 'step-id', name: 'register-candidate'}).name).toBe('register-candidate');
    });
  });

  describe('scores', () => {
    /**
     * ClearMLが返すのは `指標 -> 系列 -> 値` の入れ子である。
     * Python側が `report_scalar(title=指標名, series=split名)` で書くので、
     * 指標が外側、splitが内側になる。平らな一覧では返ってこない。
     */
    const metrics: ApiScalarMetric[] = [
      {
        name: 'accuracy',
        variants: [
          {name: 'validation', last_value: 0.81},
          {name: 'test', last_value: 0.79},
        ],
      },
      {
        name: 'recall',
        variants: [{name: 'validation', last_value: 0.63}],
      },
    ];

    it('turns the metric-then-split nesting inside out, one row per split', () => {
      const scores = toScores(metrics);

      expect(scores.map((score) => score.split)).toEqual(['validation', 'test']);
    });

    it('puts every metric of one split on the same row', () => {
      const [validation] = toScores(metrics);

      expect(validation.accuracy).toBe(0.81);
      expect(validation.recall).toBe(0.63);
    });

    it('keeps a metric that was not reported as absent', () => {
      const [validation] = toScores(metrics);

      expect(validation.f1).toBeNull();
    });

    it('reads the last reported value, which is the one the run ended on', () => {
      const scores = toScores([
        {name: 'f1', variants: [{name: 'validation', last_value: 0.72, last_100_value: 0.5}]},
      ]);

      expect(scores[0].f1).toBe(0.72);
    });

    it('ignores metrics that are not part of the evaluation contract', () => {
      const scores = toScores([
        {name: 'training_seconds', variants: [{name: 'validation', last_value: 3}]},
      ]);

      expect(scores).toEqual([]);
    });

    it('puts validation before test however the API happened to order them', () => {
      // 応答の並びは指標を書いた順に引きずられる。表の行順がそれで変わると、
      // 採用の根拠（validation）と確認（test）が入れ替わって見える。
      const scores = toScores([
        {
          name: 'accuracy',
          variants: [
            {name: 'test', last_value: 0.79},
            {name: 'validation', last_value: 0.81},
          ],
        },
      ]);

      expect(scores.map((score) => score.split)).toEqual(['validation', 'test']);
    });

    it('keeps a split it does not know behind the two the decision rests on', () => {
      const scores = toScores([
        {
          name: 'accuracy',
          variants: [
            {name: 'holdout', last_value: 0.7},
            {name: 'test', last_value: 0.79},
            {name: 'validation', last_value: 0.81},
          ],
        },
      ]);

      expect(scores.map((score) => score.split)).toEqual(['validation', 'test', 'holdout']);
    });

    it('ignores a value that names no split', () => {
      expect(toScores([{name: 'recall', variants: [{last_value: 0.5}]}])).toEqual([]);
    });

    it('ignores a metric that carries no series at all', () => {
      expect(toScores([{name: 'accuracy'}])).toEqual([]);
    });
  });

  describe('production model', () => {
    const model: ApiModel = {
      id: 'model-id',
      metadata: {
        model_version: {value: '1.0.0-20260908T043015Z-abcdef01'},
        dataset_version: {value: '1.0.0'},
        train_task_id: {value: 'train-task'},
        promoted_by: {value: 'reviewer'},
        promoted_at: {value: '2026-09-08T04:30:15Z'},
        promotion_reason: {value: 'the trial went well'},
      },
    };

    it('carries everything needed to explain why it is serving', () => {
      const production = toProductionModel(model);

      expect(production.modelVersion).toBe('1.0.0-20260908T043015Z-abcdef01');
      expect(production.trainTaskId).toBe('train-task');
      expect(production.promotedBy).toBe('reviewer');
      expect(production.promotionReason).toBe('the trial went well');
    });

    it('reports missing metadata as empty rather than failing', () => {
      const production = toProductionModel({id: 'model-id'});

      expect(production.modelId).toBe('model-id');
      expect(production.promotedBy).toBe('');
    });
  });
});

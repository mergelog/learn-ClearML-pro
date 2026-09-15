import {
  selectCanCancel,
  selectCanStart,
  selectRunIsTemplate,
  selectRunInProgress,
} from '@features/quality-pipeline/state/quality-pipeline.selectors';
import {
  PipelineRun,
  PipelineTemplate,
} from '@features/quality-pipeline/quality-pipeline.model';

const template: PipelineTemplate = {
  taskId: 'template-id',
  name: 'semiconductor-quality-training',
};

const run = (status: PipelineRun['status']): PipelineRun => ({
  taskId: 'run-id',
  name: 'semiconductor-quality-training 1.0.0',
  status,
  statusReason: '',
  datasetVersion: '1.0.0',
  startedAt: null,
  finishedAt: null,
});

describe('quality pipeline selectors', () => {
  describe('starting', () => {
    it('allows a start when there is something to clone', () => {
      expect(selectCanStart.projector(template, false)).toBe(true);
    });

    it('refuses a start while one is already being sent', () => {
      expect(selectCanStart.projector(template, true)).toBe(false);
    });

    it('refuses a start when nothing has been submitted to clone from', () => {
      expect(selectCanStart.projector(null, false)).toBe(false);
    });
  });

  describe('a run being in progress', () => {
    it('says so only while the run is still going', () => {
      expect(selectRunInProgress.projector(run('running'))).toBe(true);
      expect(selectRunInProgress.projector(run('queued'))).toBe(true);
    });

    it('says nothing for a draft that was never put on a queue', () => {
      // ClearMLの created はdraft。誰も動かしていないので、止める相手がいない。
      expect(selectRunInProgress.projector(run('created'))).toBe(false);
    });

    it('says nothing once the run has ended', () => {
      expect(selectRunInProgress.projector(run('completed'))).toBe(false);
      expect(selectRunInProgress.projector(run('failed'))).toBe(false);
      expect(selectRunInProgress.projector(run('stopped'))).toBe(false);
    });

    it('says nothing when there is no run at all', () => {
      expect(selectRunInProgress.projector(null)).toBe(false);
    });
  });

  describe('cancelling', () => {
    it('allows a cancel while the run is going and nothing has been sent yet', () => {
      expect(selectCanCancel.projector(true, false)).toBe(true);
    });

    it('refuses a second cancel while the first one is still in flight', () => {
      // 連打で tasks.stop が何度も飛ばないようにする。
      expect(selectCanCancel.projector(true, true)).toBe(false);
    });

    it('refuses a cancel when there is nothing running', () => {
      expect(selectCanCancel.projector(false, false)).toBe(false);
    });
  });

  describe('telling the clone source from the latest run', () => {
    it('says so when both point at the same task', () => {
      const sameTask = {...run('completed'), taskId: template.taskId};

      expect(selectRunIsTemplate.projector(template, sameTask)).toBe(true);
    });

    it('says nothing when the latest run is a separate task', () => {
      expect(selectRunIsTemplate.projector(template, run('running'))).toBe(false);
    });

    it('says nothing when either side is missing', () => {
      expect(selectRunIsTemplate.projector(null, run('running'))).toBe(false);
      expect(selectRunIsTemplate.projector(template, null)).toBe(false);
    });
  });
});

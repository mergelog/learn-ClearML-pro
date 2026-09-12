import {ComponentFixture, TestBed} from '@angular/core/testing';
import {PipelineRun} from '~/features/quality-pipeline/quality-pipeline.model';
import {RunSummaryComponent} from './run-summary.component';

/**
 * 1回の実行の状態が読める形で出るか、押下がそのまま親へ返るかを確かめる。
 *
 * 停止は取り消せない操作なので、押せる条件を親から受け取ったとおりに守ることが
 * この component の仕事である。押せるのに何も起きない、あるいは押せないはずの
 * ものが押せる、のどちらも起こしてはならない。
 */

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

interface Harness {
  fixture: ComponentFixture<RunSummaryComponent>;
  text: () => string;
  buttonNamed: (label: string) => HTMLButtonElement;
}

const setUp = async (
  inputs: {run?: PipelineRun; canCancel?: boolean; cancelling?: boolean} = {}
): Promise<Harness> => {
  await TestBed.configureTestingModule({imports: [RunSummaryComponent]}).compileComponents();

  const fixture = TestBed.createComponent(RunSummaryComponent);
  fixture.componentRef.setInput('run', inputs.run ?? run());
  fixture.componentRef.setInput('canCancel', inputs.canCancel ?? false);
  fixture.componentRef.setInput('cancelling', inputs.cancelling ?? false);
  fixture.detectChanges();

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;

  return {
    fixture,
    text: () => element().textContent ?? '',
    buttonNamed: (label) => {
      const button = [...element().querySelectorAll('button')].find((candidate) =>
        (candidate.textContent ?? '').trim().startsWith(label)
      );
      if (!button) {
        throw new Error(`There is no "${label}" button in the summary.`);
      }
      return button;
    },
  };
};

describe('run summary', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('reading the times', () => {
    it('shows the times in UTC, and says which zone that is', async () => {
      // ClearMLが返すのはUTC。基準を書かずにローカル時刻で出すと、
      // 別拠点のログと突き合わせたときに同じ実行が違う時刻に見える。
      const {text} = await setUp({
        run: run({startedAt: '2026-09-08T04:30:15Z', finishedAt: '2026-09-08T05:00:00Z'}),
      });

      expect(text()).toContain('2026-09-08 04:30:15');
      expect(text()).toContain('2026-09-08 05:00:00');
      expect(text()).toContain('GMT');
    });

    it('leaves a time that has not happened yet as a dash', async () => {
      const {text} = await setUp({run: run({startedAt: null, finishedAt: null})});

      expect(text()).toContain('—');
    });
  });

  describe('saying what happened', () => {
    it('shows the status where a style or a test can find it', async () => {
      const {fixture} = await setUp({run: run({status: 'failed'})});

      const statusCell = (fixture.nativeElement as HTMLElement).querySelector('dd[data-status]');

      expect(statusCell?.getAttribute('data-status')).toBe('failed');
    });

    it('shows the reason when the run gave one', async () => {
      const {text} = await setUp({run: run({status: 'failed', statusReason: 'the agent died'})});

      expect(text()).toContain('Reason');
      expect(text()).toContain('the agent died');
    });

    it('leaves the reason out entirely when there is none', async () => {
      // 空の「Reason」欄は、理由が無いのか読めなかったのかを区別できない。
      const {text} = await setUp({run: run({statusReason: ''})});

      expect(text()).not.toContain('Reason');
    });
  });

  describe('stopping a run', () => {
    it('will not offer to stop a run the parent says cannot be stopped', async () => {
      const {buttonNamed} = await setUp({canCancel: false});

      expect(buttonNamed('Cancel').disabled).toBe(true);
    });

    it('asks the parent to stop the run when pressed', async () => {
      const harness = await setUp({canCancel: true});
      let asked = 0;
      harness.fixture.componentInstance.cancelRun.subscribe(() => (asked += 1));

      harness.buttonNamed('Cancel').click();

      expect(asked).toBe(1);
    });

    it('will not send a second stop while the first one is in flight', async () => {
      const {buttonNamed} = await setUp({canCancel: false, cancelling: true});

      expect(buttonNamed('Cancelling').disabled).toBe(true);
    });
  });

  describe('reading the run back', () => {
    it('asks the parent to refresh when pressed', async () => {
      const harness = await setUp();
      let asked = 0;
      harness.fixture.componentInstance.refresh.subscribe(() => (asked += 1));

      harness.buttonNamed('Refresh').click();

      expect(asked).toBe(1);
    });
  });
});

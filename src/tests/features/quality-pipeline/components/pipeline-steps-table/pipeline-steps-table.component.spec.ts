import {ComponentFixture, TestBed} from '@angular/core/testing';
import {PipelineStep} from '@features/quality-pipeline/quality-pipeline.model';
import {MAXIMUM_STEPS} from '@features/quality-pipeline/quality-pipeline.consts';
import {PipelineStepsTableComponent} from '@features/quality-pipeline/components/pipeline-steps-table/pipeline-steps-table.component';

/**
 * 表が「無いこと」と「見せていないこと」を区別して出せるかを確かめる。
 *
 * この表の判断は2つある。1件も無いときに空欄ではなく文を出すことと、
 * 上限で打ち切ったときにそれを黙らないことである。どちらも壊れても
 * 型では気付けず、画面上は「ステップが走らなかった」と読めてしまう。
 */

const step = (overrides: Partial<PipelineStep> = {}): PipelineStep => ({
  name: 'evaluate',
  taskId: 'evaluate-task',
  status: 'completed',
  startedAt: null,
  finishedAt: null,
  ...overrides,
});

const setUp = async (
  inputs: {steps?: readonly PipelineStep[]; truncated?: boolean} = {}
): Promise<{fixture: ComponentFixture<PipelineStepsTableComponent>; text: () => string}> => {
  await TestBed.configureTestingModule({imports: [PipelineStepsTableComponent]}).compileComponents();

  const fixture = TestBed.createComponent(PipelineStepsTableComponent);
  fixture.componentRef.setInput('steps', inputs.steps ?? []);
  fixture.componentRef.setInput('truncated', inputs.truncated ?? false);
  fixture.detectChanges();

  return {
    fixture,
    text: () => (fixture.nativeElement as HTMLElement).textContent ?? '',
  };
};

describe('pipeline steps table', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('saying how much of the run is on screen', () => {
    it('says the list was cut short, and how many it is showing', async () => {
      // 打ち切りを黙ると、表から消えたステップが「走らなかったステップ」に見える。
      const {text} = await setUp({steps: [step()], truncated: true});

      expect(text()).toContain(`showing the first ${MAXIMUM_STEPS}`);
    });

    it('says nothing about a limit when the whole run is on screen', async () => {
      const {text} = await setUp({steps: [step()], truncated: false});

      expect(text()).not.toContain('showing the first');
    });
  });

  describe('showing the steps', () => {
    it('says there are no steps rather than showing an empty table', async () => {
      const {text} = await setUp({steps: []});

      expect(text()).toContain('No steps have run yet.');
    });

    it('keeps the steps in the order it was given them', async () => {
      const {fixture} = await setUp({
        steps: [
          step({name: 'prepare', taskId: 'prepare-task'}),
          step({name: 'train', taskId: 'train-task'}),
          step({name: 'evaluate', taskId: 'evaluate-task'}),
        ],
      });

      const names = [...(fixture.nativeElement as HTMLElement).querySelectorAll('tbody td:first-child')]
        .map((cell) => (cell.textContent ?? '').trim());

      expect(names).toEqual(['prepare', 'train', 'evaluate']);
    });

    it('shows the times in UTC, and says which zone that is', async () => {
      // ローカル時刻へ寄せると、ClearML側の画面やログと突き合わせたときに読み違える。
      const {text} = await setUp({
        steps: [step({startedAt: '2026-09-08T04:30:15Z', finishedAt: '2026-09-08T05:00:00Z'})],
      });

      expect(text()).toContain('04:30 GMT');
      expect(text()).toContain('05:00 GMT');
    });

    it('leaves a time that has not happened yet as a dash', async () => {
      const {text} = await setUp({steps: [step({startedAt: null, finishedAt: null})]});

      expect(text()).toContain('—');
    });

    it('puts the status where a style or a test can find it', async () => {
      const {fixture} = await setUp({steps: [step({status: 'failed'})]});

      const statusCell = (fixture.nativeElement as HTMLElement).querySelector('tbody td[data-status]');

      expect(statusCell?.getAttribute('data-status')).toBe('failed');
    });
  });
});

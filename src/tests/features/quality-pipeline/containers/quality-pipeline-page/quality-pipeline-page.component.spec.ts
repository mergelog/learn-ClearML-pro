import {ComponentFixture, TestBed} from '@angular/core/testing';
import {Action} from '@ngrx/store';
import {MockStore, provideMockStore} from '@ngrx/store/testing';
import {qualityPipelineActions} from '@features/quality-pipeline/state/quality-pipeline.actions';
import {
  QUALITY_PIPELINE_FEATURE,
  qualityPipelineFeature,
} from '@features/quality-pipeline/state/quality-pipeline.reducer';
import {
  EvaluationScore,
  PipelineRun,
  PipelineStep,
  PipelineTemplate,
  ProductionModel,
  QualityPipelineState,
  initialQualityPipelineState,
} from '@features/quality-pipeline/quality-pipeline.model';
import {QualityPipelinePageComponent} from '@features/quality-pipeline/containers/quality-pipeline-page/quality-pipeline-page.component';

/**
 * 画面が state をどう出し、押されたことをどの action にするかを確かめる。
 *
 * storeはMockStoreに差し替える。ここで確かめたいのは reducer や Effects の
 * 中身ではなく、「stateがこうなら画面はこう見える」「押したらこれが流れる」
 * という結線だけである。
 */

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

const score = (overrides: Partial<EvaluationScore> = {}): EvaluationScore => ({
  split: 'validation',
  accuracy: 0.81,
  precision: 0.8,
  recall: 0.63,
  f1: 0.72,
  ...overrides,
});

const step = (overrides: Partial<PipelineStep> = {}): PipelineStep => ({
  name: 'evaluate',
  taskId: 'evaluate-task',
  status: 'completed',
  startedAt: null,
  finishedAt: null,
  ...overrides,
});

const productionModel: ProductionModel = {
  modelId: 'model-id',
  modelVersion: '1.0.0-20260908T043015Z-abcdef01',
  datasetVersion: '1.0.0',
  trainTaskId: 'train-task',
  promotedBy: 'reviewer',
  promotedAt: '2026-09-08T04:30:15Z',
  promotionReason: 'the trial went well',
};

interface Harness {
  fixture: ComponentFixture<QualityPipelinePageComponent>;
  dispatched: Action[];
  text: () => string;
  buttonNamed: (label: string) => HTMLButtonElement;
  versionInput: () => HTMLInputElement;
}

const setUp = async (state: Partial<QualityPipelineState> = {}): Promise<Harness> => {
  TestBed.resetTestingModule();
  await TestBed.configureTestingModule({
    imports: [QualityPipelinePageComponent],
    providers: [
      provideMockStore({
        initialState: {
          [QUALITY_PIPELINE_FEATURE]: {...initialQualityPipelineState, ...state},
        },
      }),
    ],
  }).compileComponents();

  const store = TestBed.inject(MockStore);
  const dispatched: Action[] = [];
  store.scannedActions$.subscribe((action) => dispatched.push(action));

  const fixture = TestBed.createComponent(QualityPipelinePageComponent);
  fixture.detectChanges();

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;

  return {
    fixture,
    dispatched,
    text: () => element().textContent ?? '',
    buttonNamed: (label) => {
      const button = [...element().querySelectorAll('button')].find((candidate) =>
        (candidate.textContent ?? '').trim().startsWith(label)
      );
      if (!button) {
        throw new Error(`There is no "${label}" button on the page.`);
      }
      return button;
    },
    versionInput: () => {
      const input = element().querySelector<HTMLInputElement>('#dataset-version');
      if (!input) {
        throw new Error('The dataset version field is not on the page.');
      }
      return input;
    },
  };
};

const typeVersion = (harness: Harness, value: string): void => {
  const input = harness.versionInput();
  input.value = value;
  input.dispatchEvent(new Event('input'));
  harness.fixture.detectChanges();
};

const typesOf = (dispatched: Action[]): string[] => dispatched.map((action) => action.type);

describe('quality pipeline page', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('the feature is registered under its own name', () => {
    it('keeps the state key and the feature in step', () => {
      expect(qualityPipelineFeature.name).toBe(QUALITY_PIPELINE_FEATURE);
    });
  });

  describe('opening and leaving', () => {
    it('asks for the overview as soon as it is shown', async () => {
      const {dispatched} = await setUp();

      expect(typesOf(dispatched)).toContain(qualityPipelineActions.openPage.type);
    });

    it('stops following the run when it is taken off the screen', async () => {
      const {fixture, dispatched} = await setUp();

      fixture.destroy();

      expect(typesOf(dispatched)).toContain(qualityPipelineActions.leavePage.type);
    });
  });

  describe('showing what the state holds', () => {
    it('shows the reason the last request failed', async () => {
      const harness = await setUp({error: 'the server refused'});

      expect(harness.text()).toContain('the server refused');
    });

    it('says there is no run rather than showing an empty panel', async () => {
      const harness = await setUp();

      expect(harness.text()).toContain('No run yet.');
    });

    it('shows the run and the model that is serving', async () => {
      const harness = await setUp({run: run(), productionModel});

      expect(harness.text()).toContain('running');
      expect(harness.text()).toContain('1.0.0-20260908T043015Z-abcdef01');
    });

    it('rounds the scores so the splits can be read side by side', async () => {
      // 生値のまま出すと桁数が行ごとに変わり、validation と test を見比べられない。
      const harness = await setUp({scores: [score({accuracy: 0.8123456789012345})]});

      expect(harness.text()).toContain('0.812');
      expect(harness.text()).not.toContain('0.8123');
    });

    it('leaves a metric that was never reported as a dash rather than as zero', async () => {
      const harness = await setUp({scores: [score({accuracy: null})]});

      expect(harness.text()).toContain('—');
      expect(harness.text()).not.toContain('0.000');
    });

    it('shows the times of a run in UTC, and says so', async () => {
      // ClearMLが返すのはUTC。基準を書かずにローカル時刻で出すと、
      // 別拠点のログと突き合わせたときに同じ実行が違う時刻に見える。
      const harness = await setUp({
        run: run({startedAt: '2026-09-08T04:30:15Z', finishedAt: '2026-09-08T05:00:00Z'}),
      });

      expect(harness.text()).toContain('2026-09-08 04:30:15');
      expect(harness.text()).toContain('2026-09-08 05:00:00');
      expect(harness.text()).toContain('GMT');
    });

    it('shows the times of a step in UTC, and says so', async () => {
      const harness = await setUp({run: run(), steps: [step({startedAt: '2026-09-08T04:30:15Z'})]});

      expect(harness.text()).toContain('04:30 GMT');
    });
  });

  describe('starting a run', () => {
    it('asks to start with the version that was typed', async () => {
      const harness = await setUp({template});

      typeVersion(harness, '2.0.0');
      harness.buttonNamed('Start').click();

      expect(harness.dispatched).toContainEqual(
        qualityPipelineActions.startRun({datasetVersion: '2.0.0'})
      );
    });

    it('refuses to start when there is nothing to clone from', async () => {
      const harness = await setUp();

      expect(harness.buttonNamed('Start').disabled).toBe(true);
    });

    it('refuses to start on an empty version instead of doing nothing when pressed', async () => {
      // 押せるのに何も起きないボタンを作らない。
      const harness = await setUp({template});

      typeVersion(harness, '');

      expect(harness.buttonNamed('Start').disabled).toBe(true);
    });

    it('refuses a version that is not a version at all', async () => {
      const harness = await setUp({template});

      typeVersion(harness, 'abc');

      expect(harness.buttonNamed('Start').disabled).toBe(true);
    });

    it('says what a version should look like before anything is pressed', async () => {
      const harness = await setUp({template});

      expect(harness.text()).toContain('Use a version like 1.0.0.');
      expect(harness.versionInput().getAttribute('aria-describedby')).toBe(
        'dataset-version-format'
      );
    });

    it('reloads the whole overview when asked', async () => {
      const harness = await setUp({template});

      harness.buttonNamed('Reload').click();

      expect(
        typesOf(harness.dispatched).filter((type) => type === qualityPipelineActions.openPage.type)
      ).toHaveLength(2);
    });
  });

  describe('following and stopping a run', () => {
    it('reads the run back when asked', async () => {
      const harness = await setUp({run: run()});

      harness.buttonNamed('Refresh').click();

      expect(typesOf(harness.dispatched)).toContain(qualityPipelineActions.refreshRun.type);
    });

    it('asks to stop the run that is showing', async () => {
      const harness = await setUp({run: run()});

      harness.buttonNamed('Cancel').click();

      expect(typesOf(harness.dispatched)).toContain(qualityPipelineActions.cancelRun.type);
    });

    it('will not send a second stop while the first one is in flight', async () => {
      const harness = await setUp({run: run(), cancelling: true});

      expect(harness.buttonNamed('Cancelling').disabled).toBe(true);
    });

    it('has nothing to stop once the run has ended', async () => {
      const harness = await setUp({run: run({status: 'completed'})});

      expect(harness.buttonNamed('Cancel').disabled).toBe(true);
    });
  });
});

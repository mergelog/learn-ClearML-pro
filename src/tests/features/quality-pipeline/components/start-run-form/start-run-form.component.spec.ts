import {ComponentFixture, TestBed} from '@angular/core/testing';
import {PipelineTemplate} from '@features/quality-pipeline/quality-pipeline.model';
import {DATASET_VERSION_FORMAT_HINT} from '@features/quality-pipeline/quality-pipeline.consts';
import {StartRunFormComponent} from '@features/quality-pipeline/components/start-run-form/start-run-form.component';

/**
 * 「押せる」と「起動してよい」が一致しているかを確かめる。
 *
 * この component は2つの条件を掛け合わせる。state から見て受け付けられるか
 * （親が渡す `canStart`）と、入力が版数として読めるか（Reactive Forms）である。
 * 片方でも欠けたら起動要求を出してはならない。押せるのに何も起きないボタンも、
 * 押せてしまう不正な版数も、どちらも作らない。
 */

const template: PipelineTemplate = {
  taskId: 'template-id',
  name: 'semiconductor-quality-training',
};

interface Harness {
  fixture: ComponentFixture<StartRunFormComponent>;
  text: () => string;
  started: string[];
  reloaded: () => number;
  input: () => HTMLInputElement;
  buttonNamed: (label: string) => HTMLButtonElement;
  type: (value: string) => void;
  submitForm: () => void;
}

const setUp = async (
  inputs: {
    template?: PipelineTemplate | null;
    canStart?: boolean;
    loading?: boolean;
    starting?: boolean;
    runIsTemplate?: boolean;
  } = {}
): Promise<Harness> => {
  await TestBed.configureTestingModule({imports: [StartRunFormComponent]}).compileComponents();

  const fixture = TestBed.createComponent(StartRunFormComponent);
  fixture.componentRef.setInput('template', inputs.template ?? null);
  fixture.componentRef.setInput('canStart', inputs.canStart ?? false);
  fixture.componentRef.setInput('loading', inputs.loading ?? false);
  fixture.componentRef.setInput('starting', inputs.starting ?? false);
  fixture.componentRef.setInput('runIsTemplate', inputs.runIsTemplate ?? false);

  const started: string[] = [];
  let reloaded = 0;
  fixture.componentInstance.start.subscribe((version) => started.push(version));
  fixture.componentInstance.reload.subscribe(() => (reloaded += 1));

  fixture.detectChanges();

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const input = (): HTMLInputElement => {
    const field = element().querySelector<HTMLInputElement>('#dataset-version');
    if (!field) {
      throw new Error('The dataset version field is not on the form.');
    }
    return field;
  };

  return {
    fixture,
    started,
    reloaded: () => reloaded,
    input,
    text: () => element().textContent ?? '',
    buttonNamed: (label) => {
      const button = [...element().querySelectorAll('button')].find((candidate) =>
        (candidate.textContent ?? '').trim().startsWith(label)
      );
      if (!button) {
        throw new Error(`There is no "${label}" button on the form.`);
      }
      return button;
    },
    type: (value) => {
      const field = input();
      field.value = value;
      field.dispatchEvent(new Event('input'));
      fixture.detectChanges();
    },
    // Enterキーからの送信を再現する。押せない状態でも到達しうる経路である。
    submitForm: () => {
      element().querySelector('form')?.dispatchEvent(new Event('submit'));
      fixture.detectChanges();
    },
  };
};

describe('start run form', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('deciding whether the button can be pressed', () => {
    it('will not start when the state does not accept it yet', async () => {
      const harness = await setUp({template, canStart: false});

      harness.type('2.0.0');

      expect(harness.buttonNamed('Start').disabled).toBe(true);
    });

    it('will not start on a value that is not a version', async () => {
      const harness = await setUp({template, canStart: true});

      harness.type('abc');

      expect(harness.buttonNamed('Start').disabled).toBe(true);
    });

    it('will not start on an empty version', async () => {
      const harness = await setUp({template, canStart: true});

      harness.type('');

      expect(harness.buttonNamed('Start').disabled).toBe(true);
    });

    it('starts once the state accepts it and the version reads as a version', async () => {
      const harness = await setUp({template, canStart: true});

      harness.type('2.0.0');

      expect(harness.buttonNamed('Start').disabled).toBe(false);
    });
  });

  describe('asking the parent to start', () => {
    it('passes on the version that was typed', async () => {
      const harness = await setUp({template, canStart: true});

      harness.type('2.1.3');
      harness.buttonNamed('Start').click();

      expect(harness.started).toEqual(['2.1.3']);
    });

    it('stays silent when submitted from the keyboard while it cannot start', async () => {
      // Enterキーは disabled なボタンを迂回して submit へ届く。
      const harness = await setUp({template, canStart: true});

      harness.type('abc');
      harness.submitForm();

      expect(harness.started).toEqual([]);
    });

    it('says it is starting instead of looking pressable again', async () => {
      const harness = await setUp({template, canStart: false, starting: true});

      expect(harness.text()).toContain('Starting…');
    });
  });

  describe('saying what a version should look like', () => {
    it('shows the accepted format before anything is pressed', async () => {
      const harness = await setUp({template, canStart: true});

      expect(harness.text()).toContain(DATASET_VERSION_FORMAT_HINT);
    });

    it('ties the format to the field so a screen reader reads them together', async () => {
      const harness = await setUp({template, canStart: true});

      expect(harness.input().getAttribute('aria-describedby')).toBe('dataset-version-format');
    });

    it('marks the field invalid while the version cannot be read', async () => {
      const harness = await setUp({template, canStart: true});

      harness.type('abc');

      expect(harness.input().getAttribute('aria-invalid')).toBe('true');
    });

    it('clears the invalid mark once the version reads', async () => {
      const harness = await setUp({template, canStart: true});

      harness.type('abc');
      harness.type('2.0.0');

      expect(harness.input().getAttribute('aria-invalid')).toBe('false');
    });
  });

  describe('explaining where a run comes from', () => {
    it('names the task the run will be cloned from', async () => {
      const harness = await setUp({template});

      expect(harness.text()).toContain('semiconductor-quality-training');
    });

    it('says so when the clone source and the latest run are the same task', async () => {
      const harness = await setUp({template, runIsTemplate: true});

      expect(harness.text()).toContain('the same task as the latest run');
    });

    it('says there is nothing to start from once loading has finished', async () => {
      const harness = await setUp({template: null, loading: false});

      expect(harness.text()).toContain('No pipeline to start from.');
    });

    it('stays quiet about having nothing while it is still loading', async () => {
      const harness = await setUp({template: null, loading: true});

      expect(harness.text()).not.toContain('No pipeline to start from.');
    });
  });

  describe('reloading', () => {
    it('asks the parent to reload when pressed', async () => {
      const harness = await setUp({template});

      harness.buttonNamed('Reload').click();

      expect(harness.reloaded()).toBe(1);
    });

    it('will not ask again while a reload is already in flight', async () => {
      const harness = await setUp({template, loading: true});

      expect(harness.buttonNamed('Reload').disabled).toBe(true);
    });
  });
});

import {ComponentFixture, TestBed} from '@angular/core/testing';
import {ProductionModel} from '@features/quality-pipeline/quality-pipeline.model';
import {ProductionModelCardComponent} from '@features/quality-pipeline/components/production-model-card/production-model-card.component';

/**
 * 「まだ無い」を空白ではなく文で出せるかを確かめる。
 *
 * 空欄のままだと、読み込みに失敗したのか一度も採用されていないのかが
 * 利用者から区別できない。これはこの component の唯一の判断であり、
 * 消えても型では気付けない。
 */

const productionModel: ProductionModel = {
  modelId: 'model-id',
  modelVersion: '1.0.0-20260908T043015Z-abcdef01',
  datasetVersion: '1.0.0',
  trainTaskId: 'train-task',
  promotedBy: 'reviewer',
  promotedAt: '2026-09-08T04:30:15Z',
  promotionReason: 'the trial went well',
};

const setUp = async (
  model: ProductionModel | null = null
): Promise<{fixture: ComponentFixture<ProductionModelCardComponent>; text: () => string}> => {
  await TestBed.configureTestingModule({
    imports: [ProductionModelCardComponent],
  }).compileComponents();

  const fixture = TestBed.createComponent(ProductionModelCardComponent);
  fixture.componentRef.setInput('model', model);
  fixture.detectChanges();

  return {
    fixture,
    text: () => (fixture.nativeElement as HTMLElement).textContent ?? '',
  };
};

describe('production model card', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('when nothing has been promoted', () => {
    it('says so in a sentence rather than leaving the card blank', async () => {
      const {text} = await setUp(null);

      expect(text()).toContain('No model has been promoted to production yet.');
    });

    it('shows none of the fact list', async () => {
      const {fixture} = await setUp(null);

      expect((fixture.nativeElement as HTMLElement).querySelector('dl')).toBeNull();
    });
  });

  describe('when a model is serving', () => {
    it('names the version that is actually serving', async () => {
      const {text} = await setUp(productionModel);

      expect(text()).toContain('1.0.0-20260908T043015Z-abcdef01');
    });

    it('says which dataset it was trained on and who promoted it', async () => {
      // どの版で学習し、誰がどんな理由で採用したかまでが「提供中」の説明になる。
      const {text} = await setUp(productionModel);

      expect(text()).toContain('1.0.0');
      expect(text()).toContain('reviewer');
      expect(text()).toContain('the trial went well');
      expect(text()).toContain('train-task');
    });

    it('leaves a fact the registry never recorded as a dash', async () => {
      const {text} = await setUp({...productionModel, promotedBy: '', promotionReason: ''});

      expect(text()).toContain('—');
    });
  });
});

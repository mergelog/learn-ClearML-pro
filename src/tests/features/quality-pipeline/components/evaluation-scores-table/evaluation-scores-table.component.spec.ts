import {ComponentFixture, TestBed} from '@angular/core/testing';
import {EvaluationScore} from '@features/quality-pipeline/quality-pipeline.model';
import {EvaluationScoresTableComponent} from '@features/quality-pipeline/components/evaluation-scores-table/evaluation-scores-table.component';

/**
 * 指標が「見比べられる形」で出るかを確かめる。
 *
 * この表の judgment は桁揃えにある。生値のまま並べると桁数が行ごとに変わり、
 * validation と test を目で見比べられない。桁が崩れても型では気付けない。
 */

const score = (overrides: Partial<EvaluationScore> = {}): EvaluationScore => ({
  split: 'validation',
  accuracy: 0.81,
  precision: 0.8,
  recall: 0.63,
  f1: 0.72,
  ...overrides,
});

const setUp = async (
  scores: readonly EvaluationScore[] = []
): Promise<{fixture: ComponentFixture<EvaluationScoresTableComponent>; text: () => string}> => {
  await TestBed.configureTestingModule({
    imports: [EvaluationScoresTableComponent],
  }).compileComponents();

  const fixture = TestBed.createComponent(EvaluationScoresTableComponent);
  fixture.componentRef.setInput('scores', scores);
  fixture.detectChanges();

  return {
    fixture,
    text: () => (fixture.nativeElement as HTMLElement).textContent ?? '',
  };
};

describe('evaluation scores table', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('making the splits comparable', () => {
    it('rounds every metric to three decimals', async () => {
      const {text} = await setUp([score({accuracy: 0.8123456789012345})]);

      expect(text()).toContain('0.812');
      expect(text()).not.toContain('0.8123');
    });

    it('pads a short value out to three decimals so the columns line up', async () => {
      // 0.8 を「0.8」と出すと、隣の行の「0.812」と桁が揃わない。
      const {text} = await setUp([score({accuracy: 0.8})]);

      expect(text()).toContain('0.800');
    });

    it('shows validation and test side by side, in the order it was given them', async () => {
      const {fixture} = await setUp([
        score({split: 'validation'}),
        score({split: 'test', accuracy: 0.79}),
      ]);

      const splits = [...(fixture.nativeElement as HTMLElement).querySelectorAll('tbody td:first-child')]
        .map((cell) => (cell.textContent ?? '').trim());

      expect(splits).toEqual(['validation', 'test']);
    });
  });

  describe('metrics that were never reported', () => {
    it('leaves a missing metric as a dash rather than as zero', async () => {
      // 0.000 と出すと「測ったら0だった」と読めてしまう。
      const {text} = await setUp([score({accuracy: null})]);

      expect(text()).toContain('—');
      expect(text()).not.toContain('0.000');
    });
  });

  describe('having nothing to show', () => {
    it('does not fall over on an empty list', async () => {
      const {text} = await setUp([]);

      expect(text()).toContain('No scores yet.');
    });
  });
});

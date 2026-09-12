import {ComponentFixture, TestBed} from '@angular/core/testing';
import {provideRouter} from '@angular/router';
import {CatalogAsset} from '~/features/data-catalog/data-catalog.model';
import {CATALOG_PAGE_SIZE} from '~/features/data-catalog/data-catalog.consts';
import {CatalogAssetsTableComponent} from './catalog-assets-table.component';

/**
 * 表が「無いこと」を言い分けられるかを確かめる。
 *
 * この表の判断は、空である理由・打ち切り・時刻の基準の3つで、どれも壊れても
 * 型では気付けない。画面上は「そういうものが無い」と読めてしまう。
 */

const asset = (overrides: Partial<CatalogAsset> = {}): CatalogAsset => ({
  kind: 'dataset',
  id: 'dataset-id',
  name: 'semiconductor-quality',
  project: {id: 'project-id', name: 'Semiconductor Quality Prediction'},
  updatedAt: '2026-09-12T04:30:00Z',
  tags: ['seed'],
  state: 'completed',
  ...overrides,
});

const setUp = async (
  inputs: {
    assets?: readonly CatalogAsset[];
    hasMore?: boolean;
    loading?: boolean;
    emptyReason?: 'nothing-yet' | 'no-match' | null;
  } = {}
): Promise<{fixture: ComponentFixture<CatalogAssetsTableComponent>; text: () => string}> => {
  TestBed.resetTestingModule();
  await TestBed.configureTestingModule({
    imports: [CatalogAssetsTableComponent],
    providers: [provideRouter([])],
  }).compileComponents();

  const fixture = TestBed.createComponent(CatalogAssetsTableComponent);
  fixture.componentRef.setInput('assets', inputs.assets ?? []);
  fixture.componentRef.setInput('hasMore', inputs.hasMore ?? false);
  fixture.componentRef.setInput('loading', inputs.loading ?? false);
  fixture.componentRef.setInput('emptyReason', inputs.emptyReason ?? null);
  fixture.detectChanges();

  return {fixture, text: () => (fixture.nativeElement as HTMLElement).textContent ?? ''};
};

describe('catalog assets table', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('saying why there is nothing to show', () => {
    it('offers to widen the search when a filter is on', async () => {
      const {text} = await setUp({assets: [], emptyReason: 'no-match'});

      expect(text()).toContain('Nothing matches these filters');
    });

    it('says the catalog itself is empty when no filter is on', async () => {
      const {text} = await setUp({assets: [], emptyReason: 'nothing-yet'});

      expect(text()).toContain('The catalog is empty');
    });

    it('says it is still loading rather than guessing', async () => {
      const {text} = await setUp({assets: [], loading: true});

      expect(text()).toContain('Loading…');
      expect(text()).not.toContain('The catalog is empty');
    });
  });

  describe('saying how much of the catalog is on screen', () => {
    it('says the list was cut short, and how many it is showing', async () => {
      const {text} = await setUp({assets: [asset()], hasMore: true});

      expect(text()).toContain(`showing the first ${CATALOG_PAGE_SIZE}`);
    });

    it('says nothing about a limit when everything fits', async () => {
      const {text} = await setUp({assets: [asset()], hasMore: false});

      expect(text()).not.toContain('showing the first');
    });
  });

  describe('showing the assets', () => {
    it('keeps the three kinds in one list, in the order it was given them', async () => {
      const {fixture} = await setUp({
        assets: [
          asset({kind: 'model', id: 'a', name: 'model-a'}),
          asset({kind: 'dataset', id: 'b', name: 'dataset-b'}),
          asset({kind: 'run', id: 'c', name: 'run-c'}),
        ],
      });

      const names = [
        ...(fixture.nativeElement as HTMLElement).querySelectorAll('tbody td:nth-child(2)'),
      ].map((cell) => (cell.textContent ?? '').trim());

      expect(names).toEqual(['model-a', 'dataset-b', 'run-c']);
    });

    it('links each asset to its own page in the catalog', async () => {
      const {fixture} = await setUp({assets: [asset({kind: 'model', id: 'model-id'})]});

      const link = (fixture.nativeElement as HTMLElement).querySelector('tbody a');

      expect(link?.getAttribute('href')).toBe('/data-catalog/model/model-id');
    });

    it('shows the time in UTC, and says which zone that is', async () => {
      // ローカル時刻へ寄せると、ClearML側の画面と突き合わせたときに読み違える。
      const {text} = await setUp({assets: [asset()]});

      expect(text()).toContain('2026-09-12 04:30 GMT');
    });

    it('shows a dash rather than a blank when there is no time', async () => {
      const {fixture} = await setUp({assets: [asset({updatedAt: null})]});

      const cell = (fixture.nativeElement as HTMLElement).querySelector('tbody td:last-child');

      expect((cell?.textContent ?? '').trim()).toBe('—');
    });
  });
});

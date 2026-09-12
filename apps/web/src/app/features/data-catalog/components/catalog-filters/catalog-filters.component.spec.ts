import {ComponentFixture, TestBed} from '@angular/core/testing';
import {CatalogFilter, emptyCatalogFilter} from '~/features/data-catalog/data-catalog.model';
import {CatalogFiltersComponent} from './catalog-filters.component';

/**
 * 絞り込みの入力欄が、条件をどう受け取りどう返すかを確かめる。
 *
 * 判断は2つある。外から来た条件を入力欄へ書き戻すことと、押されたときにだけ
 * 返すことである。前者が壊れると、条件つきURLを開いた人は「絞られているのに
 * 何で絞られているか分からない」画面を見ることになる。
 */

const setUp = async (
  filter: CatalogFilter = emptyCatalogFilter
): Promise<{
  fixture: ComponentFixture<CatalogFiltersComponent>;
  emitted: CatalogFilter[];
  element: HTMLElement;
}> => {
  TestBed.resetTestingModule();
  await TestBed.configureTestingModule({imports: [CatalogFiltersComponent]}).compileComponents();

  const fixture = TestBed.createComponent(CatalogFiltersComponent);
  const emitted: CatalogFilter[] = [];
  fixture.componentRef.setInput('filter', filter);
  fixture.componentRef.setInput('projects', ['Pipeline']);
  fixture.componentRef.setInput('availableTags', ['seed']);
  fixture.componentInstance.filterChange.subscribe((value) => emitted.push(value));
  fixture.detectChanges();

  return {fixture, emitted, element: fixture.nativeElement as HTMLElement};
};

const inputValue = (element: HTMLElement, id: string): string =>
  (element.querySelector(`#${id}`) as HTMLInputElement).value;

const setInputValue = (element: HTMLElement, id: string, value: string): void => {
  const field = element.querySelector(`#${id}`) as HTMLInputElement;
  field.value = value;
  field.dispatchEvent(new Event('input'));
};

describe('catalog filters', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('showing the conditions that are already in effect', () => {
    it('fills the fields from a filter that came in from the URL', async () => {
      const {element} = await setUp({
        ...emptyCatalogFilter,
        text: 'wafer',
        project: 'Pipeline',
        tags: ['seed', 'stage:production'],
        kinds: ['model'],
        updatedFrom: '2026-01-01',
      });

      expect(inputValue(element, 'catalog-text')).toBe('wafer');
      expect(inputValue(element, 'catalog-project')).toBe('Pipeline');
      expect(inputValue(element, 'catalog-tags')).toBe('seed,stage:production');
      expect(inputValue(element, 'catalog-from')).toBe('2026-01-01');
      expect((element.querySelector('#catalog-kind-model') as HTMLInputElement).checked).toBe(true);
      expect((element.querySelector('#catalog-kind-run') as HTMLInputElement).checked).toBe(false);
    });

    it('does not report a change just because it was told the current filter', async () => {
      // 書き戻しが変更として跳ね返ると、URLの書き換えが止まらなくなる。
      const {emitted} = await setUp({...emptyCatalogFilter, text: 'wafer'});

      expect(emitted).toEqual([]);
    });
  });

  describe('reporting a change', () => {
    it('waits for the form to be submitted', async () => {
      // 1文字ごとに返すと、その都度URLが書き換わり問い合わせも同じ回数飛ぶ。
      const {element, emitted} = await setUp();
      setInputValue(element, 'catalog-text', 'wafer');

      expect(emitted).toEqual([]);
    });

    it('reports every condition together when applied', async () => {
      const {fixture, element, emitted} = await setUp();
      setInputValue(element, 'catalog-text', ' wafer ');
      setInputValue(element, 'catalog-tags', 'seed, stage:production');
      (element.querySelector('#catalog-kind-dataset') as HTMLInputElement).click();
      fixture.detectChanges();

      (element.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));

      expect(emitted).toEqual([
        {
          ...emptyCatalogFilter,
          text: 'wafer',
          kinds: ['dataset'],
          tags: ['seed', 'stage:production'],
        },
      ]);
    });

    it('drops an empty tag rather than searching for one', async () => {
      // 空のタグを送ると、結果が黙って0件になる。
      const {element, emitted} = await setUp();
      setInputValue(element, 'catalog-tags', 'seed,,');

      (element.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));

      expect(emitted[0].tags).toEqual(['seed']);
    });

    it('reports that everything was cleared, not just empties the fields', async () => {
      const {element, emitted} = await setUp({...emptyCatalogFilter, text: 'wafer'});

      (element.querySelector('[data-id="catalogClear"]') as HTMLButtonElement).click();

      expect(emitted).toEqual([emptyCatalogFilter]);
    });
  });
});

import {
  selectCanSave,
  selectEmptyReason,
  selectLineageIsPartial,
  selectLineageNodes,
} from '~/features/data-catalog/state/data-catalog.selectors';
import {
  CatalogAsset,
  CatalogLineage,
  DataCatalogState,
  emptyCatalogFilter,
  initialDataCatalogState,
} from '~/features/data-catalog/data-catalog.model';
import {DATA_CATALOG_FEATURE} from '~/features/data-catalog/state/data-catalog.reducer';

/**
 * 導出された問いを確かめる。
 *
 * ここが答えるのは「何が入っているか」ではなく「それが何を意味するか」である。
 * 意味を間違えると、画面は正しい値を出したまま間違ったことを言う。
 */

const asset = (overrides: Partial<CatalogAsset> = {}): CatalogAsset => ({
  kind: 'model',
  id: 'model-id',
  name: 'model',
  project: {id: 'project-id', name: 'Pipeline'},
  updatedAt: null,
  tags: [],
  state: 'completed',
  ...overrides,
});

const rootWith = (overrides: Partial<DataCatalogState>) => ({
  [DATA_CATALOG_FEATURE]: {...initialDataCatalogState, ...overrides},
});

describe('data catalog selectors', () => {
  describe('saying why the list is empty', () => {
    it('says nothing yet when no filter is applied', () => {
      expect(selectEmptyReason(rootWith({assets: [], loading: false}))).toBe('nothing-yet');
    });

    it('says nothing matches when a filter is applied', () => {
      // 同じ文で済ませると、絞り込みを外せば見えるものを、存在しないものとして
      // 読ませることになる。
      const state = rootWith({
        assets: [],
        loading: false,
        filter: {...emptyCatalogFilter, text: 'wafer'},
      });

      expect(selectEmptyReason(state)).toBe('no-match');
    });

    it('says neither while it is still loading', () => {
      expect(selectEmptyReason(rootWith({assets: [], loading: true}))).toBeNull();
    });

    it('says nothing at all when there are results', () => {
      expect(selectEmptyReason(rootWith({assets: [asset()], loading: false}))).toBeNull();
    });
  });

  describe('saying whether metadata can be saved', () => {
    it('refuses while a save is in flight', () => {
      // 送信中も押せると、同じ資産へ更新が2回飛び、あとから届いたほうが勝つ。
      const state = rootWith({
        detail: {asset: asset(), description: '', facts: []},
        saving: true,
      });

      expect(selectCanSave(state)).toBe(false);
    });

    it('refuses when nothing is open', () => {
      expect(selectCanSave(rootWith({detail: null, saving: false}))).toBe(false);
    });
  });

  describe('laying out the chain', () => {
    const lineage = (overrides: Partial<CatalogLineage> = {}): CatalogLineage => ({
      origin: 'model',
      dataset: {kind: 'dataset', id: 'dataset-id', asset: asset({kind: 'dataset'})},
      run: {kind: 'run', id: 'run-id', asset: asset({kind: 'run'})},
      model: {kind: 'model', id: 'model-id', asset: asset()},
      ...overrides,
    });

    it('always reads Dataset → Run → Model, whichever asset was opened', () => {
      // 起点を先頭へ置き換えると、同じ鎖が開いた場所によって逆向きに見える。
      const nodes = selectLineageNodes(rootWith({lineage: lineage({origin: 'model'})}));

      expect(nodes.map((node) => node.kind)).toEqual(['dataset', 'run', 'model']);
    });

    it('leaves out a link that is not there at all', () => {
      const nodes = selectLineageNodes(rootWith({lineage: lineage({dataset: null})}));

      expect(nodes.map((node) => node.kind)).toEqual(['run', 'model']);
    });

    it('says the chain is incomplete when a link is missing', () => {
      expect(selectLineageIsPartial(rootWith({lineage: lineage({run: null})}))).toBe(true);
    });

    it('does not call a chain incomplete before it has been traced', () => {
      expect(selectLineageIsPartial(rootWith({lineage: null}))).toBe(false);
    });
  });
});

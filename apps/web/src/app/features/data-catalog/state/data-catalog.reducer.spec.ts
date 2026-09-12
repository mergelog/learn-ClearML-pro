import {dataCatalogActions} from '~/features/data-catalog/state/data-catalog.actions';
import {dataCatalogFeature} from '~/features/data-catalog/state/data-catalog.reducer';
import {
  CatalogAsset,
  CatalogAssetDetail,
  CatalogLineage,
  DataCatalogState,
  emptyCatalogFilter,
  initialDataCatalogState,
} from '~/features/data-catalog/data-catalog.model';

const reducer = dataCatalogFeature.reducer;

const asset = (overrides: Partial<CatalogAsset> = {}): CatalogAsset => ({
  kind: 'model',
  id: 'model-id',
  name: 'semiconductor-quality-classifier',
  project: {id: 'project-id', name: 'Pipeline'},
  updatedAt: '2026-09-12T00:00:00Z',
  tags: ['stage:production'],
  state: 'completed',
  ...overrides,
});

const detail = (overrides: Partial<CatalogAssetDetail> = {}): CatalogAssetDetail => ({
  asset: asset(),
  description: 'the trial went well',
  facts: [],
  ...overrides,
});

const lineage: CatalogLineage = {
  origin: 'model',
  dataset: null,
  run: null,
  model: {kind: 'model', id: 'model-id', asset: asset()},
};

const stateWith = (overrides: Partial<DataCatalogState> = {}): DataCatalogState => ({
  ...initialDataCatalogState,
  ...overrides,
});

describe('data catalog reducer', () => {
  describe('opening the list', () => {
    it('puts the new filter in place before the results arrive', () => {
      // 結果を待ってから入れると、読み込み中の画面が前の条件を表示し続ける。
      const filter = {...emptyCatalogFilter, text: 'wafer'};

      const state = reducer(initialDataCatalogState, dataCatalogActions.openList({filter}));

      expect(state.filter).toEqual(filter);
      expect(state.loading).toBe(true);
    });

    it('keeps the assets it already had when the list fails to load', () => {
      const previous = stateWith({assets: [asset()], loading: true});

      const state = reducer(previous, dataCatalogActions.listFailed({reason: 'no'}));

      expect(state.assets).toEqual([asset()]);
      expect(state.error).toBe('no');
      expect(state.loading).toBe(false);
    });

    it('clears the failure once the list loads', () => {
      const previous = stateWith({error: 'no'});

      const state = reducer(
        previous,
        dataCatalogActions.listLoaded({page: {assets: [asset()], hasMore: false}})
      );

      expect(state.error).toBeNull();
    });
  });

  describe('opening one asset', () => {
    it('drops the previous asset when a different one is opened', () => {
      const previous = stateWith({detail: detail(), lineage});

      const state = reducer(
        previous,
        dataCatalogActions.openDetail({kind: 'run', id: 'other-id'})
      );

      expect(state.detail).toBeNull();
      expect(state.lineage).toBeNull();
    });

    it('keeps what it has when the same asset is read again', () => {
      // 保存の後の読み直しでは、画面が一度空になってはいけない。
      const previous = stateWith({detail: detail(), lineage});

      const state = reducer(
        previous,
        dataCatalogActions.openDetail({kind: 'model', id: 'model-id'})
      );

      expect(state.detail).toEqual(detail());
      expect(state.lineage).toEqual(lineage);
      expect(state.detailLoading).toBe(true);
    });

    it('keeps the list while one asset is being read', () => {
      const previous = stateWith({assets: [asset()]});

      const state = reducer(
        previous,
        dataCatalogActions.openDetail({kind: 'model', id: 'model-id'})
      );

      expect(state.assets).toEqual([asset()]);
      expect(state.loading).toBe(false);
    });
  });

  describe('saving metadata', () => {
    it('does not change what is shown until the save comes back', () => {
      // 押した直後に表示が変わると、受け付けられなかったときに台帳が嘘をつく。
      const previous = stateWith({detail: detail()});

      const state = reducer(
        previous,
        dataCatalogActions.saveMetadata({
          kind: 'model',
          id: 'model-id',
          edit: {tags: ['new'], description: 'changed'},
        })
      );

      expect(state.detail).toEqual(detail());
      expect(state.saving).toBe(true);
    });

    it('applies the saved value to both the detail and the row in the list', () => {
      const previous = stateWith({detail: detail(), assets: [asset()], saving: true});

      const state = reducer(
        previous,
        dataCatalogActions.metadataSaved({edit: {tags: ['new'], description: 'changed'}})
      );

      expect(state.detail?.description).toBe('changed');
      expect(state.detail?.asset.tags).toEqual(['new']);
      expect(state.assets[0].tags).toEqual(['new']);
      expect(state.saving).toBe(false);
    });

    it('leaves other rows in the list alone', () => {
      const other = asset({kind: 'run', id: 'run-id', tags: ['seed']});
      const previous = stateWith({detail: detail(), assets: [asset(), other]});

      const state = reducer(
        previous,
        dataCatalogActions.metadataSaved({edit: {tags: ['new'], description: ''}})
      );

      expect(state.assets[1].tags).toEqual(['seed']);
    });

    it('stops saving and says why when the save fails', () => {
      const previous = stateWith({detail: detail(), saving: true});

      const state = reducer(previous, dataCatalogActions.saveFailed({reason: 'conflict'}));

      expect(state.saving).toBe(false);
      expect(state.error).toBe('conflict');
      expect(state.detail).toEqual(detail());
    });
  });

  describe('leaving', () => {
    it('keeps the list when only the detail is closed', () => {
      const previous = stateWith({assets: [asset()], detail: detail(), lineage});

      const state = reducer(previous, dataCatalogActions.leaveDetail());

      expect(state.assets).toEqual([asset()]);
      expect(state.detail).toBeNull();
      expect(state.lineage).toBeNull();
    });

    it('throws everything away when the page is left', () => {
      const previous = stateWith({assets: [asset()], detail: detail(), error: 'no'});

      expect(reducer(previous, dataCatalogActions.leavePage())).toEqual(initialDataCatalogState);
    });
  });
});

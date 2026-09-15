import {TestBed} from '@angular/core/testing';
import {HttpErrorResponse} from '@angular/common/http';
import {Router} from '@angular/router';
import {provideMockActions} from '@ngrx/effects/testing';
import {provideMockStore} from '@ngrx/store/testing';
import {Action} from '@ngrx/store';
import {Observable, of, throwError} from 'rxjs';
import {take, toArray} from 'rxjs/operators';
import {dataCatalogActions} from '@features/data-catalog/state/data-catalog.actions';
import {DataCatalogEffects} from '@features/data-catalog/state/data-catalog.effects';
import {DataCatalogApiService} from '@features/data-catalog/data-access/data-catalog-api.service';
import {
  DATA_CATALOG_FEATURE,
} from '@features/data-catalog/state/data-catalog.reducer';
import {
  CatalogAsset,
  CatalogAssetDetail,
  CatalogLineage,
  CatalogPage,
  DataCatalogState,
  emptyCatalogFilter,
  initialDataCatalogState,
} from '@features/data-catalog/data-catalog.model';
import {CATALOG_ROUTE, QUERY_KEYS} from '@features/data-catalog/data-catalog.consts';

const asset: CatalogAsset = {
  kind: 'model',
  id: 'model-id',
  name: 'model',
  project: {id: 'project-id', name: 'Pipeline'},
  updatedAt: null,
  tags: [],
  state: 'completed',
};

const detail: CatalogAssetDetail = {asset, description: '', facts: []};

const lineage: CatalogLineage = {
  origin: 'model',
  dataset: null,
  run: null,
  model: {kind: 'model', id: 'model-id', asset},
};

/** テスト用のAPI境界。呼ばれた引数を覚える。 */
class StubApi {
  searchResponse: Observable<CatalogPage> = of({assets: [], hasMore: false});
  detailResponse: Observable<CatalogAssetDetail | null> = of(detail);
  lineageResponse: Observable<CatalogLineage> = of(lineage);
  projectsResponse: Observable<string[]> = of(['Pipeline']);
  tagsResponse: Observable<string[]> = of(['seed']);
  updateResponse: Observable<{tags: readonly string[]; description: string}> = of({
    tags: ['seed'],
    description: 'checked',
  });

  readonly updated: unknown[] = [];

  search = () => this.searchResponse;
  getDetail = () => this.detailResponse;
  getLineage = () => this.lineageResponse;
  getProjectNames = () => this.projectsResponse;
  getTags = () => this.tagsResponse;

  updateMetadata = (kind: string, id: string, edit: unknown) => {
    this.updated.push({kind, id, edit});
    return this.updateResponse;
  };
}

class StubRouter {
  readonly navigations: {commands: unknown[]; extras: unknown}[] = [];

  navigate = (commands: unknown[], extras: unknown): Promise<boolean> => {
    this.navigations.push({commands, extras});
    return Promise.resolve(true);
  };
}

const setUp = (
  action: Action,
  state: Partial<DataCatalogState> = {},
  configure: (api: StubApi) => void = () => undefined
): {effects: DataCatalogEffects; api: StubApi; router: StubRouter} => {
  const api = new StubApi();
  configure(api);
  const router = new StubRouter();

  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      DataCatalogEffects,
      provideMockActions(() => of(action)),
      provideMockStore({
        initialState: {[DATA_CATALOG_FEATURE]: {...initialDataCatalogState, ...state}},
      }),
      {provide: DataCatalogApiService, useValue: api},
      {provide: Router, useValue: router},
    ],
  });

  return {effects: TestBed.inject(DataCatalogEffects), api, router};
};

const runEffect = (
  effectOf: (effects: DataCatalogEffects) => Observable<Action>,
  action: Action,
  state: Partial<DataCatalogState> = {},
  configure: (api: StubApi) => void = () => undefined
): Promise<Action[]> => {
  const {effects} = setUp(action, state, configure);

  return new Promise((resolve) => {
    effectOf(effects).pipe(take(1), toArray()).subscribe(resolve);
  });
};

describe('data catalog effects', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('loading the list', () => {
    it('turns a failure into an action instead of throwing', async () => {
      // 例外を投げると、そのeffectは以後何も受け取らなくなる。
      const actions = await runEffect(
        (effects) => effects.loadList,
        dataCatalogActions.openList({filter: emptyCatalogFilter}),
        {},
        (api) => {
          api.searchResponse = throwError(
            () =>
              new HttpErrorResponse({
                status: 500,
                error: {meta: {result_msg: 'the index is unavailable'}},
              })
          );
        }
      );

      expect(actions).toEqual([
        dataCatalogActions.listFailed({reason: 'the index is unavailable'}),
      ]);
    });

    it('explains a request that never reached the server', async () => {
      const actions = await runEffect(
        (effects) => effects.loadList,
        dataCatalogActions.openList({filter: emptyCatalogFilter}),
        {},
        (api) => {
          api.searchResponse = throwError(
            () => new HttpErrorResponse({status: 0, error: null, statusText: 'Unknown Error'})
          );
        }
      );

      const [failure] = actions as unknown as [{reason: string}];
      // 状態コード0を数字のまま出しても何も言っていない。
      expect(failure.reason).not.toBe('0 Unknown Error');
    });
  });

  describe('putting the filter in the URL', () => {
    it('writes the conditions to the URL and does not search here', async () => {
      // ここでも引くと、同じ条件で2回引くことになる。
      const {effects, router, api} = setUp(
        dataCatalogActions.filterChanged({
          filter: {...emptyCatalogFilter, text: 'wafer'},
        })
      );
      const searched: unknown[] = [];
      api.search = () => {
        searched.push('search');
        return of({assets: [], hasMore: false});
      };

      await new Promise<void>((resolve) => {
        effects.syncUrl.pipe(take(1)).subscribe(() => resolve());
      });

      expect(router.navigations[0].commands).toEqual([CATALOG_ROUTE]);
      expect(
        (router.navigations[0].extras as {queryParams: Record<string, unknown>}).queryParams[
          QUERY_KEYS.text
        ]
      ).toBe('wafer');
      expect(searched).toEqual([]);
    });

    it('replaces the current URL so filtering does not fill the history', async () => {
      const {effects, router} = setUp(
        dataCatalogActions.filterChanged({filter: emptyCatalogFilter})
      );

      await new Promise<void>((resolve) => {
        effects.syncUrl.pipe(take(1)).subscribe(() => resolve());
      });

      expect((router.navigations[0].extras as {replaceUrl: boolean}).replaceUrl).toBe(true);
    });
  });

  describe('reading one asset', () => {
    it('traces where it came from once the asset itself is read', async () => {
      const actions = await runEffect(
        (effects) => effects.loadLineage,
        dataCatalogActions.detailLoaded({detail})
      );

      expect(actions).toEqual([dataCatalogActions.lineageLoaded({lineage})]);
    });

    it('says nothing when the asset is gone, rather than tracing nothing', async () => {
      const {effects} = setUp(dataCatalogActions.detailLoaded({detail: null}));
      const seen: Action[] = [];

      await new Promise<void>((resolve) => {
        effects.loadLineage.subscribe({next: (action) => seen.push(action), complete: resolve});
      });

      expect(seen).toEqual([]);
    });

    it('keeps the asset on screen when the trace fails', async () => {
      // 出所が辿れないことは、資産が読めないことではない。
      const {effects} = setUp(
        dataCatalogActions.detailLoaded({detail}),
        {},
        (api) => {
          api.lineageResponse = throwError(() => new Error('no'));
        }
      );
      const seen: Action[] = [];

      await new Promise<void>((resolve) => {
        effects.loadLineage.subscribe({next: (action) => seen.push(action), complete: resolve});
      });

      expect(seen).toEqual([]);
    });
  });

  describe('saving metadata', () => {
    it('reports the value the server accepted', async () => {
      const actions = await runEffect(
        (effects) => effects.saveMetadata,
        dataCatalogActions.saveMetadata({
          kind: 'model',
          id: 'model-id',
          edit: {tags: ['seed'], description: 'checked'},
        })
      );

      expect(actions).toEqual([
        dataCatalogActions.metadataSaved({edit: {tags: ['seed'], description: 'checked'}}),
      ]);
    });

    it('turns a refused save into a failure the screen can show', async () => {
      const actions = await runEffect(
        (effects) => effects.saveMetadata,
        dataCatalogActions.saveMetadata({
          kind: 'model',
          id: 'model-id',
          edit: {tags: [], description: ''},
        }),
        {},
        (api) => {
          api.updateResponse = throwError(() => new Error('ClearML did not apply the change'));
        }
      );

      expect(actions).toEqual([
        dataCatalogActions.saveFailed({reason: 'ClearML did not apply the change'}),
      ]);
    });

    it('reads the asset again afterwards, in case someone else changed it too', async () => {
      const actions = await runEffect(
        (effects) => effects.reloadAfterSave,
        dataCatalogActions.metadataSaved({edit: {tags: [], description: ''}}),
        {detail}
      );

      expect(actions).toEqual([
        dataCatalogActions.openDetail({kind: 'model', id: 'model-id'}),
      ]);
    });
  });

  describe('loading the filter options', () => {
    it('does not fail the screen when the options cannot be read', async () => {
      // 選択肢が出ないだけで、絞り込みは自由入力からでも成立する。
      const {effects} = setUp(dataCatalogActions.loadOptions(), {}, (api) => {
        api.projectsResponse = throwError(() => new Error('no'));
      });
      const seen: Action[] = [];

      await new Promise<void>((resolve) => {
        effects.loadOptions.subscribe({next: (action) => seen.push(action), complete: resolve});
      });

      expect(seen).toEqual([]);
    });
  });
});

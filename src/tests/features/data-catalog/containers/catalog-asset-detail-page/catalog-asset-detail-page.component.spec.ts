import {ComponentFixture, TestBed} from '@angular/core/testing';
import {ActivatedRoute, convertToParamMap, ParamMap, provideRouter} from '@angular/router';
import {Action} from '@ngrx/store';
import {MockStore, provideMockStore} from '@ngrx/store/testing';
import {BehaviorSubject} from 'rxjs';
import {dataCatalogActions} from '@features/data-catalog/state/data-catalog.actions';
import {DATA_CATALOG_FEATURE} from '@features/data-catalog/state/data-catalog.reducer';
import {
  CatalogAssetDetail,
  DataCatalogState,
  initialDataCatalogState,
} from '@features/data-catalog/data-catalog.model';
import {CatalogAssetDetailPageComponent} from '@features/data-catalog/containers/catalog-asset-detail-page/catalog-asset-detail-page.component';

/**
 * 詳細画面の結線を確かめる。
 *
 * **URLだけで開けることが仕様である。** 一覧を経由しなくても読める。
 * 一覧の state に依存させると、渡されたURLが「一覧を開いてから来た人」に
 * しか働かなくなる。
 */

const detail: CatalogAssetDetail = {
  asset: {
    kind: 'model',
    id: 'model-id',
    name: 'semiconductor-quality-classifier',
    project: {id: 'project-id', name: 'Pipeline'},
    updatedAt: null,
    tags: [],
    state: 'completed',
  },
  description: '',
  facts: [],
};

const setUp = async (
  routeParams: Record<string, string>,
  state: Partial<DataCatalogState> = {}
): Promise<{
  fixture: ComponentFixture<CatalogAssetDetailPageComponent>;
  dispatched: Action[];
  store: MockStore;
  element: HTMLElement;
}> => {
  const params = new BehaviorSubject<ParamMap>(convertToParamMap(routeParams));

  TestBed.resetTestingModule();
  await TestBed.configureTestingModule({
    imports: [CatalogAssetDetailPageComponent],
    providers: [
      provideRouter([]),
      provideMockStore({
        initialState: {[DATA_CATALOG_FEATURE]: {...initialDataCatalogState, ...state}},
      }),
      {provide: ActivatedRoute, useValue: {paramMap: params.asObservable()}},
    ],
  }).compileComponents();

  const store = TestBed.inject(MockStore);
  const dispatched: Action[] = [];
  store.scannedActions$.subscribe((action) => dispatched.push(action));

  const fixture = TestBed.createComponent(CatalogAssetDetailPageComponent);
  fixture.detectChanges();

  return {fixture, dispatched, store, element: fixture.nativeElement as HTMLElement};
};

describe('catalog asset detail page', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('deciding what to open', () => {
    it('opens the asset the URL names', async () => {
      const {dispatched} = await setUp({kind: 'model', id: 'model-id'});

      expect(dispatched).toContainEqual(
        dataCatalogActions.openDetail({kind: 'model', id: 'model-id'})
      );
    });

    it('asks ClearML nothing when the URL names a kind it does not know', async () => {
      // 読めない種別で問い合わせても、返ってくるのは理由の言えない空である。
      const {dispatched, element} = await setUp({kind: 'banana', id: 'model-id'});

      expect(
        dispatched.filter((action) => action.type === dataCatalogActions.openDetail.type)
      ).toEqual([]);
      expect(element.textContent ?? '').toContain('does not name a dataset, model or run');
    });
  });

  describe('saving', () => {
    it('sends the kind and id from the URL along with the edit', async () => {
      const {element, dispatched} = await setUp({kind: 'model', id: 'model-id'}, {detail});

      const tags = element.querySelector('#catalog-edit-tags') as HTMLInputElement;
      tags.value = 'checked';
      tags.dispatchEvent(new Event('input'));
      (element.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));

      expect(dispatched.at(-1)).toEqual(
        dataCatalogActions.saveMetadata({
          kind: 'model',
          id: 'model-id',
          edit: {tags: ['checked'], description: ''},
        })
      );
    });

    it('offers no edit form for an asset that is gone', async () => {
      const {element} = await setUp({kind: 'model', id: 'model-id'}, {detail: null});

      expect(element.querySelector('[data-id="catalogSave"]')).toBeNull();
    });
  });

  describe('showing what the state says', () => {
    it('puts a failure where a screen reader will reach it', async () => {
      const {element} = await setUp({kind: 'model', id: 'model-id'}, {error: 'conflict'});

      expect(element.querySelector('[role="alert"]')?.textContent).toContain('conflict');
    });
  });

  it('closes only the detail when it is left, keeping the list', async () => {
    const {fixture, dispatched} = await setUp({kind: 'model', id: 'model-id'});

    fixture.destroy();

    expect(dispatched.at(-1)).toEqual(dataCatalogActions.leaveDetail());
  });
});

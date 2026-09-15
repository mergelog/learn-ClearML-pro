import {ComponentFixture, TestBed} from '@angular/core/testing';
import {ActivatedRoute, Params, provideRouter} from '@angular/router';
import {Action} from '@ngrx/store';
import {MockStore, provideMockStore} from '@ngrx/store/testing';
import {BehaviorSubject} from 'rxjs';
import {dataCatalogActions} from '@features/data-catalog/state/data-catalog.actions';
import {DATA_CATALOG_FEATURE} from '@features/data-catalog/state/data-catalog.reducer';
import {
  CatalogAsset,
  DataCatalogState,
  emptyCatalogFilter,
  initialDataCatalogState,
} from '@features/data-catalog/data-catalog.model';
import {QUERY_KEYS} from '@features/data-catalog/data-catalog.consts';
import {CatalogDownloadService} from '@features/data-catalog/data-catalog.download';
import {CatalogExportDocument} from '@features/data-catalog/data-catalog.export';
import {DataCatalogPageComponent} from '@features/data-catalog/containers/data-catalog-page/data-catalog-page.component';

/**
 * 一覧画面の結線を確かめる。
 *
 * **この画面の要は「条件は必ずURLから来る」ことである**（プランの §4.2）。
 * 絞り込みの操作はURLの書き換えになり、書き換わったURLを読んで一覧を引く。
 * 経路を2本にすると、片方だけ直って「自分で絞ると出るのに、URLを渡すと
 * 出ない」という壊れ方をする。
 */

const asset: CatalogAsset = {
  kind: 'model',
  id: 'model-id',
  name: 'model',
  project: {id: 'project-id', name: 'Pipeline'},
  updatedAt: null,
  tags: [],
  state: 'completed',
};

interface SavedFile {
  filename: string;
  mediaType: string;
  text: string;
}

/**
 * ブラウザへ渡す側を差し替える。
 *
 * 本物は `Blob` を作ってダウンロードを起こす。ここで見たいのは
 * 「何を、どの名前で渡したか」だけなので、渡されたものを覚えるだけにする。
 */
class RecordingDownloadService {
  readonly saved: SavedFile[] = [];

  save(filename: string, mediaType: string, text: string): void {
    this.saved.push({filename, mediaType, text});
  }
}

const setUp = async (
  queryParams: Params = {},
  state: Partial<DataCatalogState> = {}
): Promise<{
  fixture: ComponentFixture<DataCatalogPageComponent>;
  dispatched: Action[];
  params: BehaviorSubject<Params>;
  store: MockStore;
  text: () => string;
  downloads: RecordingDownloadService;
}> => {
  const downloads = new RecordingDownloadService();
  const params = new BehaviorSubject<Params>(queryParams);

  TestBed.resetTestingModule();
  await TestBed.configureTestingModule({
    imports: [DataCatalogPageComponent],
    providers: [
      provideRouter([]),
      provideMockStore({
        initialState: {[DATA_CATALOG_FEATURE]: {...initialDataCatalogState, ...state}},
        selectors: [],
      }),
      {provide: ActivatedRoute, useValue: {queryParams: params.asObservable()}},
      {provide: CatalogDownloadService, useValue: downloads},
    ],
  }).compileComponents();

  const store = TestBed.inject(MockStore);
  const dispatched: Action[] = [];
  store.scannedActions$.subscribe((action) => dispatched.push(action));

  const fixture = TestBed.createComponent(DataCatalogPageComponent);
  fixture.detectChanges();

  return {
    fixture,
    dispatched,
    params,
    store,
    text: () => (fixture.nativeElement as HTMLElement).textContent ?? '',
    downloads,
  };
};

const openListActions = (dispatched: Action[]) =>
  dispatched.filter((action) => action.type === dataCatalogActions.openList.type);

describe('data catalog page', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('deciding what to load', () => {
    it('reads the conditions out of the URL', async () => {
      const {dispatched} = await setUp({[QUERY_KEYS.text]: 'wafer'});

      expect(openListActions(dispatched)).toEqual([
        dataCatalogActions.openList({filter: {...emptyCatalogFilter, text: 'wafer'}}),
      ]);
    });

    it('does not load the same conditions twice when the URL is revisited', async () => {
      // URLは同じ条件でも別のオブジェクトとして流れてくる。
      const {dispatched, params, fixture} = await setUp({[QUERY_KEYS.text]: 'wafer'});

      params.next({[QUERY_KEYS.text]: 'wafer'});
      fixture.detectChanges();

      expect(openListActions(dispatched)).toHaveLength(1);
    });

    it('loads again when the URL really changed', async () => {
      const {dispatched, params, fixture} = await setUp({[QUERY_KEYS.text]: 'wafer'});

      params.next({[QUERY_KEYS.text]: 'lot'});
      fixture.detectChanges();

      expect(openListActions(dispatched)).toHaveLength(2);
    });

    it('asks for the filter options once, separately from the list', async () => {
      const {dispatched} = await setUp();

      expect(dispatched.filter((action) => action.type === dataCatalogActions.loadOptions.type))
        .toHaveLength(1);
    });
  });

  describe('changing the filter', () => {
    it('reports the change instead of loading directly', async () => {
      const {fixture, dispatched} = await setUp();
      const before = openListActions(dispatched).length;

      (fixture.nativeElement as HTMLElement)
        .querySelector<HTMLButtonElement>('[data-id="catalogClear"]')
        ?.click();

      expect(dispatched.at(-1)).toEqual(
        dataCatalogActions.filterChanged({filter: emptyCatalogFilter})
      );
      expect(openListActions(dispatched)).toHaveLength(before);
    });
  });

  describe('showing what the state says', () => {
    it('passes the assets down to the table', async () => {
      const {text} = await setUp({}, {assets: [asset]});

      expect(text()).toContain('model');
    });

    it('puts a failure where a screen reader will reach it', async () => {
      const {fixture} = await setUp({}, {error: 'the index is unavailable'});

      const alert = (fixture.nativeElement as HTMLElement).querySelector('[role="alert"]');

      expect(alert?.textContent).toContain('the index is unavailable');
    });
  });

  describe('handing the list to someone outside', () => {
    const exportButton = (fixture: ComponentFixture<DataCatalogPageComponent>) =>
      (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
        '[data-id="catalogExport"]'
      );

    it('writes out what is on the screen, without asking ClearML again', async () => {
      // 条件は state のものを書く。**画面に見えている一覧が、どの条件で
      // 引かれたものか**を文書に残したいのであって、アドレス欄にいま何が
      // 打たれているかではない。
      const {fixture, downloads, dispatched} = await setUp(
        {[QUERY_KEYS.kinds]: 'model'},
        {assets: [asset], filter: {...emptyCatalogFilter, kinds: ['model']}}
      );
      const before = openListActions(dispatched).length;

      exportButton(fixture)?.click();

      expect(downloads.saved).toHaveLength(1);
      const document = JSON.parse(downloads.saved[0].text) as CatalogExportDocument;
      expect(document.assets).toHaveLength(1);
      expect(document.filter.kinds).toEqual(['model']);
      expect(document.reference).toBe('/data-catalog?kind=model');
      // 書き出しは写しである。引き直すと、渡した相手と画面を見ている人が
      // 違うものを見て話すことになる。
      expect(openListActions(dispatched)).toHaveLength(before);
    });

    it('lets the file say it was capped', async () => {
      const {fixture, downloads} = await setUp({}, {assets: [asset], hasMore: true});

      exportButton(fixture)?.click();

      expect((JSON.parse(downloads.saved[0].text) as CatalogExportDocument).truncated).toBe(true);
    });

    it('says on the screen too that the file will be a capped one', async () => {
      const {text} = await setUp({}, {assets: [asset], hasMore: true});

      expect(text()).toContain('the exported file says so as well');
    });

    it('cannot be pressed when there is nothing to hand over', async () => {
      const {fixture} = await setUp();

      expect(exportButton(fixture)?.disabled).toBe(true);
    });

    it('names the file and its type, so it opens as JSON', async () => {
      const {fixture, downloads} = await setUp({}, {assets: [asset]});

      exportButton(fixture)?.click();

      expect(downloads.saved[0].filename).toMatch(/^data-catalog-\d{8}T\d{6}Z\.json$/);
      expect(downloads.saved[0].mediaType).toBe('application/json');
    });
  });

  it('stops tracking the page when it is left', async () => {
    const {fixture, dispatched} = await setUp();

    fixture.destroy();

    expect(dispatched.at(-1)).toEqual(dataCatalogActions.leavePage());
  });
});

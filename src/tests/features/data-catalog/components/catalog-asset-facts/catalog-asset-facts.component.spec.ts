import {ComponentFixture, TestBed} from '@angular/core/testing';
import {provideRouter} from '@angular/router';
import {CatalogAsset, CatalogAssetDetail} from '@features/data-catalog/data-catalog.model';
import {CatalogAssetFactsComponent} from '@features/data-catalog/components/catalog-asset-facts/catalog-asset-facts.component';

/**
 * 詳細の表示を確かめる。
 *
 * 台帳は横断の入口であって、詳細の置き換えではない。既存のClearML画面へ
 * 渡せるかどうかがここの仕様で、渡し先が作れないときに黙ってリンクを消すと、
 * 「この資産にはClearML側の画面が無い」と読めてしまう。
 */

const asset = (overrides: Partial<CatalogAsset> = {}): CatalogAsset => ({
  kind: 'model',
  id: 'model-id',
  name: 'semiconductor-quality-classifier',
  project: {id: 'project-id', name: 'Pipeline'},
  updatedAt: '2026-09-12T04:30:00Z',
  tags: ['stage:production'],
  state: 'completed',
  ...overrides,
});

const detail = (overrides: Partial<CatalogAssetDetail> = {}): CatalogAssetDetail => ({
  asset: asset(),
  description: 'the trial went well',
  facts: [{label: 'Model version', value: '1.0.0'}],
  ...overrides,
});

const setUp = async (
  value: CatalogAssetDetail | null
): Promise<{fixture: ComponentFixture<CatalogAssetFactsComponent>; text: () => string}> => {
  TestBed.resetTestingModule();
  await TestBed.configureTestingModule({
    imports: [CatalogAssetFactsComponent],
    providers: [provideRouter([])],
  }).compileComponents();

  const fixture = TestBed.createComponent(CatalogAssetFactsComponent);
  fixture.componentRef.setInput('detail', value);
  fixture.detectChanges();

  return {fixture, text: () => (fixture.nativeElement as HTMLElement).textContent ?? ''};
};

describe('catalog asset facts', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('shows the facts that are specific to this kind', async () => {
    const {text} = await setUp(detail());

    expect(text()).toContain('Model version');
    expect(text()).toContain('1.0.0');
  });

  it('keeps the description row even when there is no description', async () => {
    // 欄が消えると「この種別には説明という概念が無い」ように読める。
    const {text} = await setUp(detail({description: ''}));

    expect(text()).toContain('Description');
  });

  it('shows the time in UTC, and says which zone that is', async () => {
    const {text} = await setUp(detail());

    expect(text()).toContain('2026-09-12 04:30 GMT');
  });

  it('links to the ClearML page that owns the deep detail', async () => {
    const {fixture} = await setUp(detail());

    const link = (fixture.nativeElement as HTMLElement).querySelector(
      '[data-id="catalogVendorLink"]'
    );

    expect(link?.getAttribute('href')).toBe('/projects/project-id/models/model-id');
  });

  it('says why there is no ClearML page instead of dropping the link', async () => {
    // 押しても404になるリンクは、リンクが無いことより悪い。黙って消すのも悪い。
    const {text} = await setUp(detail({asset: asset({project: {id: '', name: ''}})}));

    expect(text()).toContain('not attached to a project');
  });

  it('says the asset is gone rather than showing an empty page', async () => {
    const {text} = await setUp(null);

    expect(text()).toContain('no longer in ClearML');
  });
});

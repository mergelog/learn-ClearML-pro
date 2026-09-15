import {ComponentFixture, TestBed} from '@angular/core/testing';
import {provideRouter} from '@angular/router';
import {CatalogAsset, CatalogLineageNode} from '@features/data-catalog/data-catalog.model';
import {CatalogLineageComponent} from '@features/data-catalog/components/catalog-lineage/catalog-lineage.component';

/**
 * 鎖の表示を確かめる。
 *
 * ここが黙ると、出所が分からない資産が「出所を辿る必要が無い資産」に見える。
 * それはこの feature が存在する理由そのものを裏切る。
 */

const asset = (id: string, kind: CatalogAsset['kind']): CatalogAsset => ({
  kind,
  id,
  name: `${kind}-${id}`,
  project: {id: 'project-id', name: 'Pipeline'},
  updatedAt: null,
  tags: [],
  state: 'completed',
});

const node = (kind: CatalogAsset['kind'], id: string, found = true): CatalogLineageNode => ({
  kind,
  id,
  asset: found ? asset(id, kind) : null,
});

const setUp = async (
  inputs: {nodes?: readonly CatalogLineageNode[]; partial?: boolean; loading?: boolean} = {}
): Promise<{fixture: ComponentFixture<CatalogLineageComponent>; text: () => string}> => {
  TestBed.resetTestingModule();
  await TestBed.configureTestingModule({
    imports: [CatalogLineageComponent],
    providers: [provideRouter([])],
  }).compileComponents();

  const fixture = TestBed.createComponent(CatalogLineageComponent);
  fixture.componentRef.setInput('nodes', inputs.nodes ?? []);
  fixture.componentRef.setInput('partial', inputs.partial ?? false);
  fixture.componentRef.setInput('loading', inputs.loading ?? false);
  fixture.detectChanges();

  return {fixture, text: () => (fixture.nativeElement as HTMLElement).textContent ?? ''};
};

describe('catalog lineage', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('shows the chain in the order it was given', async () => {
    const {fixture} = await setUp({
      nodes: [node('dataset', 'd1'), node('run', 'r1'), node('model', 'm1')],
    });

    const kinds = [
      ...(fixture.nativeElement as HTMLElement).querySelectorAll('.catalog-lineage__kind'),
    ].map((element) => (element.textContent ?? '').trim());

    expect(kinds).toEqual(['Dataset', 'Run', 'Model']);
  });

  it('links each link in the chain back into the catalog', async () => {
    const {fixture} = await setUp({nodes: [node('run', 'r1')]});

    const link = (fixture.nativeElement as HTMLElement).querySelector('a');

    expect(link?.getAttribute('href')).toBe('/data-catalog/run/r1');
  });

  it('says a link points at something that is gone', async () => {
    // 節ごと落とすと、切れている鎖が繋がっているように見える。
    const {text} = await setUp({nodes: [node('dataset', '9.9.9', false)]});

    expect(text()).toContain('9.9.9');
    expect(text()).toContain('no longer in ClearML');
  });

  it('says the chain is incomplete when part of it could not be traced', async () => {
    const {text} = await setUp({nodes: [node('model', 'm1')], partial: true});

    expect(text()).toContain('This chain is incomplete');
  });

  it('separates "still tracing" from "nothing links this"', async () => {
    const tracing = await setUp({nodes: [], loading: true});
    expect(tracing.text()).toContain('Tracing…');

    const traced = await setUp({nodes: [], loading: false});
    expect(traced.text()).toContain('Nothing links this asset');
  });
});

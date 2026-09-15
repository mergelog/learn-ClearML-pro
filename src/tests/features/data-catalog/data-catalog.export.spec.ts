import {
  CATALOG_EXPORT_KIND,
  CATALOG_EXPORT_VERSION,
  catalogExportDocument,
  catalogExportFilename,
  catalogExportText,
} from '@features/data-catalog/data-catalog.export';
import {CatalogAsset, CatalogFilter, emptyCatalogFilter} from '@features/data-catalog/data-catalog.model';
import {fromQueryParams} from '@features/data-catalog/data-catalog.query';

/**
 * 書き出す文書を確かめる。
 *
 * **このファイルは画面を離れる。** 離れた先には注記も画面も付いてこないので、
 * 文書が自分で「どの条件で引いたか」「打ち切られたか」を名乗らなければ、
 * 抜粋が台帳として読まれる（ADR 010）。ここで見ているのはその名乗りである。
 */

const asset = (overrides: Partial<CatalogAsset> = {}): CatalogAsset => ({
  kind: 'model',
  id: 'model-id',
  name: 'wafer-classifier',
  project: {id: 'project-id', name: 'Semiconductor Quality Prediction'},
  updatedAt: '2026-09-12T00:00:00Z',
  tags: ['stage:production'],
  state: 'published',
  ...overrides,
});

const filter = (overrides: Partial<CatalogFilter> = {}): CatalogFilter => ({
  ...emptyCatalogFilter,
  ...overrides,
});

const exportedAt = new Date('2026-09-12T08:30:15.500Z');

describe('catalog export document', () => {
  it('names itself, so the file is not mistaken for another JSON', () => {
    const document = catalogExportDocument({
      filter: emptyCatalogFilter,
      assets: [],
      hasMore: false,
      exportedAt,
    });

    expect(document.catalog).toBe(CATALOG_EXPORT_KIND);
    expect(document.version).toBe(CATALOG_EXPORT_VERSION);
  });

  it('says it was capped, because the note on the screen does not travel with the file', () => {
    const document = catalogExportDocument({
      filter: emptyCatalogFilter,
      assets: [asset()],
      hasMore: true,
      exportedAt,
    });

    expect(document.truncated).toBe(true);
    expect(document.count).toBe(1);
  });

  it('carries the conditions that were in force', () => {
    const applied = filter({text: 'wafer', kinds: ['model'], tags: ['seed', 'stage:production']});

    const document = catalogExportDocument({
      filter: applied,
      assets: [],
      hasMore: false,
      exportedAt,
    });

    expect(document.filter).toEqual(applied);
  });

  it('carries a link back to the screen that produced it', () => {
    const applied = filter({text: 'wafer', kinds: ['dataset', 'model'], updatedFrom: '2026-01-01'});

    const {reference} = catalogExportDocument({
      filter: applied,
      assets: [],
      hasMore: false,
      exportedAt,
    });

    expect(reference).toBe('/data-catalog?q=wafer&kind=dataset,model&from=2026-01-01');

    // 戻れることまで見る。URLの形が合っていても、読み直して同じ条件に
    // ならなければ「元の画面へ戻れる」とは言えない。
    const [, query] = reference.split('?');
    expect(fromQueryParams(Object.fromEntries(new URLSearchParams(query)))).toEqual(applied);
  });

  it('links to the plain list when nothing is filtered', () => {
    const {reference} = catalogExportDocument({
      filter: emptyCatalogFilter,
      assets: [],
      hasMore: false,
      exportedAt,
    });

    expect(reference).toBe('/data-catalog');
  });

  it('exports the asset as the ledger holds it, not as ClearML answered', () => {
    const {assets} = catalogExportDocument({
      filter: emptyCatalogFilter,
      assets: [asset()],
      hasMore: false,
      exportedAt,
    });

    expect(assets[0]).toEqual({
      kind: 'model',
      id: 'model-id',
      name: 'wafer-classifier',
      project: {id: 'project-id', name: 'Semiconductor Quality Prediction'},
      updatedAt: '2026-09-12T00:00:00Z',
      tags: ['stage:production'],
      state: 'published',
    });
  });

  it('keeps "never updated" distinguishable from "updated at the epoch"', () => {
    const {assets} = catalogExportDocument({
      filter: emptyCatalogFilter,
      assets: [asset({updatedAt: null})],
      hasMore: false,
      exportedAt,
    });

    expect(assets[0].updatedAt).toBeNull();
  });
});

describe('catalog export file', () => {
  it('is indented, because a person opens it before a program does', () => {
    const text = catalogExportText(
      catalogExportDocument({
        filter: emptyCatalogFilter,
        assets: [asset()],
        hasMore: false,
        exportedAt,
      })
    );

    expect(text.startsWith('{\n  "catalog"')).toBe(true);
    expect(text.endsWith('}\n')).toBe(true);
    expect(JSON.parse(text).count).toBe(1);
  });

  it('names the file down to the second, so a second export does not replace the first', () => {
    expect(catalogExportFilename(exportedAt)).toBe('data-catalog-20260912T083015Z.json');
  });

  it('keeps the name free of characters a file system refuses', () => {
    expect(catalogExportFilename(exportedAt)).not.toMatch(/[:*?"<>|]/);
  });
});

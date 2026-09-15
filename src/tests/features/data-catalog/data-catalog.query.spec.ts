import {
  fromQueryParams,
  isDefaultFilter,
  sameFilter,
  toQueryParams,
  toReferenceUrl,
} from '@features/data-catalog/data-catalog.query';
import {CatalogFilter, emptyCatalogFilter} from '@features/data-catalog/data-catalog.model';
import {QUERY_KEYS} from '@features/data-catalog/data-catalog.consts';

/**
 * URLと条件の変換を確かめる。
 *
 * ここが壊れると、渡されたURLが黙って別の条件になる。**URLは外向きの約束**で
 * （プランの §4.2）、画面の中だけで閉じた話ではない。型では何も守れない。
 */

const filter = (overrides: Partial<CatalogFilter> = {}): CatalogFilter => ({
  ...emptyCatalogFilter,
  ...overrides,
});

describe('catalog query params', () => {
  describe('reading a URL', () => {
    it('reads every condition it knows', () => {
      const result = fromQueryParams({
        [QUERY_KEYS.text]: 'wafer',
        [QUERY_KEYS.kinds]: 'dataset,model',
        [QUERY_KEYS.project]: 'Semiconductor Quality Prediction',
        [QUERY_KEYS.tags]: 'stage:production,seed',
        [QUERY_KEYS.updatedFrom]: '2026-01-01',
        [QUERY_KEYS.updatedTo]: '2026-09-12',
      });

      expect(result).toEqual(
        filter({
          text: 'wafer',
          kinds: ['dataset', 'model'],
          project: 'Semiconductor Quality Prediction',
          tags: ['stage:production', 'seed'],
          updatedFrom: '2026-01-01',
          updatedTo: '2026-09-12',
        })
      );
    });

    it('drops a kind it does not know rather than filtering by it', () => {
      // 知らない種別で絞ると、理由の言えない空の一覧になる。
      const result = fromQueryParams({[QUERY_KEYS.kinds]: 'dataset,banana'});

      expect(result.kinds).toEqual(['dataset']);
    });

    it('drops a date it cannot read rather than sending it to ClearML', () => {
      const result = fromQueryParams({[QUERY_KEYS.updatedFrom]: 'last tuesday'});

      expect(result.updatedFrom).toBe('');
    });

    it('takes the first value when a key appears more than once', () => {
      // 連結すると、誰も入力していない検索語ができる。
      const result = fromQueryParams({[QUERY_KEYS.text]: ['wafer', 'lot']});

      expect(result.text).toBe('wafer');
    });

    it('reads repeated keys as separate tags', () => {
      const result = fromQueryParams({[QUERY_KEYS.tags]: ['seed', 'stage:production']});

      expect(result.tags).toEqual(['seed', 'stage:production']);
    });

    it('treats an empty query as no filter at all', () => {
      expect(isDefaultFilter(fromQueryParams({}))).toBe(true);
    });
  });

  describe('writing a URL', () => {
    it('leaves out the conditions that are not set', () => {
      const params = toQueryParams(filter({text: 'wafer'}));

      expect(params[QUERY_KEYS.text]).toBe('wafer');
      // 鍵を省くのではなく null を置く。省くと前のURLの条件が消えずに残る。
      expect(params[QUERY_KEYS.project]).toBeNull();
      expect(params[QUERY_KEYS.kinds]).toBeNull();
    });

    it('comes back the same after a round trip', () => {
      const original = filter({
        text: 'wafer',
        kinds: ['model', 'run'],
        project: 'Pipeline',
        tags: ['seed'],
        updatedFrom: '2026-01-01',
        updatedTo: '2026-09-12',
      });

      expect(fromQueryParams(toQueryParams(original) as Record<string, string>)).toEqual(original);
    });
  });

  describe('handing the URL to someone', () => {
    it('writes one URL that carries every condition', () => {
      const url = toReferenceUrl(
        filter({text: 'wafer', kinds: ['dataset', 'model'], tags: ['seed'], updatedTo: '2026-09-12'})
      );

      expect(url).toBe('/data-catalog?q=wafer&kind=dataset,model&tag=seed&to=2026-09-12');
    });

    it('keeps the separator readable instead of escaping it', () => {
      // アドレス欄に出ているURLと、渡すURLを違えない。%2C はコンマである。
      expect(toReferenceUrl(filter({kinds: ['dataset', 'run']}))).toContain('kind=dataset,run');
    });

    it('escapes what has to be escaped', () => {
      expect(toReferenceUrl(filter({project: 'Semiconductor Quality'}))).toBe(
        '/data-catalog?project=Semiconductor%20Quality'
      );
    });

    it('is just the list when nothing is filtered', () => {
      expect(toReferenceUrl(emptyCatalogFilter)).toBe('/data-catalog');
    });

    it('reads back as the same conditions', () => {
      const original = filter({text: 'wafer', kinds: ['model'], tags: ['seed', 'stage:production']});
      const [, query] = toReferenceUrl(original).split('?');

      expect(fromQueryParams(Object.fromEntries(new URLSearchParams(query)))).toEqual(original);
    });
  });

  describe('comparing two filters', () => {
    it('says two filters built from the same URL are the same', () => {
      // 参照の比較では足りない。URLから読み直すたびに別のオブジェクトになる。
      const params = {[QUERY_KEYS.tags]: 'seed,stage:production'};

      expect(sameFilter(fromQueryParams(params), fromQueryParams(params))).toBe(true);
    });

    it('notices a tag that only one of them has', () => {
      expect(sameFilter(filter({tags: ['seed']}), filter({tags: ['seed', 'other']}))).toBe(false);
    });
  });
});

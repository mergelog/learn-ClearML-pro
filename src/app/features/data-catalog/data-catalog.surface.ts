import {
  CATALOG_ASSET_KINDS,
  CatalogAsset,
  CatalogAssetState,
  emptyCatalogFilter,
} from '@features/data-catalog/data-catalog.model';
import {
  CATALOG_ROUTE,
  QUERY_KEYS,
  QUERY_VALUE_SEPARATOR,
} from '@features/data-catalog/data-catalog.consts';
import {
  CATALOG_EXPORT_KIND,
  CATALOG_EXPORT_MEDIA_TYPE,
  CATALOG_EXPORT_VERSION,
  CatalogExportDocument,
} from '@features/data-catalog/data-catalog.export';

/**
 * 台帳が外へ約束している面。
 *
 * 台帳には出口が2つある（ADR 010）。どちらも**この画面の外に持ち出される**。
 *
 * - 参照URL（E-b）: 絞り込んだ一覧のURLは人に渡され、あとで開かれる
 * - 書き出し（E-a）: JSON はファイルとして手元を離れる
 *
 * 渡された側は、渡された時点の形を前提に読む。だから守らなければならないのは
 * 形そのものではなく、**形が黙って変わらないこと**である（ADR 006 と同じ問題）。
 *
 * ここは面を**組み立てるだけ**である。組み立てた面が
 * `data-catalog.surface.published.json`（コミットしてある、公開中の面）と
 * 一致するかは `data-catalog.surface.spec.ts` が見る。
 *
 * **註釈は検査ではない。** `QUERY_KEYS` には以前から「外向きの名前である」と
 * 書いてあった。書いてあることと守られていることの差を埋めるのがこの文書である。
 */

export interface CatalogSurface {
  reference: {
    list: string;
    detail: string;
    queryKeys: Readonly<Record<string, string>>;
    multiValueSeparator: string;
    dateFormat: string;
  };
  export: {
    kind: string;
    version: number;
    mediaType: string;
    envelope: readonly string[];
    assetFields: readonly string[];
    projectFields: readonly string[];
    filterFields: readonly string[];
  };
  vocabulary: {
    kind: readonly string[];
    state: readonly string[];
  };
}

/**
 * 種別と状態の語。
 *
 * `kind` は URL の `kind=` とファイルの両方に現れる。`state` はファイルにだけ
 * 現れる。**どちらも `CatalogAssetState` から機械的に導けない**（型は実行時に
 * 残らない）ので、ここに並べる。並びが型からずれたら、下の `satisfies` が
 * 型検査で落とす。
 */
const STATE_VOCABULARY = [
  'draft',
  'running',
  'completed',
  'failed',
  'stopped',
  'published',
  'unknown',
] as const satisfies readonly CatalogAssetState[];

/**
 * 封筒・資産・条件の鍵。
 *
 * 型の鍵をそのまま書き写すのではなく、**`satisfies` で型に縛る**。書き写すだけだと、
 * `CatalogAsset` に項目が増えたときにここが古いまま緑になる。縛っておけば、
 * 型を変えた側が必ずここへ来る。
 */
const ENVELOPE_FIELDS = [
  'catalog',
  'version',
  'exportedAt',
  'reference',
  'filter',
  'truncated',
  'count',
  'assets',
] as const satisfies readonly (keyof CatalogExportDocument)[];

const ASSET_FIELDS = [
  'kind',
  'id',
  'name',
  'project',
  'updatedAt',
  'tags',
  'state',
] as const satisfies readonly (keyof CatalogAsset)[];

const PROJECT_FIELDS = ['id', 'name'] as const;

/** 詳細の経路。`data-catalog.routes.ts` の `:kind/:id` と同じものを指す。 */
const DETAIL_PATH = `${CATALOG_ROUTE}/:kind/:id`;

/** 期間の書式。`data-catalog.query.ts` の `DATE_PATTERN` が受ける形と同じ。 */
const DATE_FORMAT = 'YYYY-MM-DD';

/** いまコードが公開している面。 */
export const catalogSurface = (): CatalogSurface => ({
  reference: {
    list: CATALOG_ROUTE,
    detail: DETAIL_PATH,
    queryKeys: {...QUERY_KEYS},
    multiValueSeparator: QUERY_VALUE_SEPARATOR,
    dateFormat: DATE_FORMAT,
  },
  export: {
    kind: CATALOG_EXPORT_KIND,
    version: CATALOG_EXPORT_VERSION,
    mediaType: CATALOG_EXPORT_MEDIA_TYPE,
    envelope: [...ENVELOPE_FIELDS],
    assetFields: [...ASSET_FIELDS],
    projectFields: [...PROJECT_FIELDS],
    // 条件の鍵は、URLの鍵とは別に出る（ファイルの中では `q` ではなく `text`）。
    // 実体から取る。書き写すと、条件が1つ増えたときに気付けない。
    filterFields: Object.keys(emptyCatalogFilter),
  },
  vocabulary: {
    kind: [...CATALOG_ASSET_KINDS],
    state: [...STATE_VOCABULARY],
  },
});

/**
 * 公開している面と、いまの面のずれ。
 *
 * **検知は完全一致、分類は説明**（ADR 006 §1 と同じ）。差分があれば、それが
 * どんな差分でも失敗する。分類を検知に使うと、分類できない種類の変更が
 * 黙って緑になる。
 *
 * 向きは**読み手の側**から見る（ADR 006 §2 の「応答」列）。渡したURLと
 * 渡したファイルを読むのは常に外の誰かで、こちらは送る側ではない。
 */
export interface SurfaceChange {
  path: string;
  breaking: boolean;
  description: string;
}

/** ずれの説明。一致していれば `null`。 */
export const surfaceDrift = (published: unknown, current: CatalogSurface): string | null => {
  if (deepEqual(published, current)) {
    return null;
  }

  const changes = compare(published, current, '');
  const breaking = changes.filter((change) => change.breaking);
  const compatible = changes.filter((change) => !change.breaking);

  return [
    '外へ公開している面が data-catalog.surface.published.json と違う。',
    '',
    ...section('渡した先が壊れる変更', breaking),
    ...section('互換の変更', compatible),
    ...unclassified(changes),
    '意図した変更であれば、公開中の面を下の内容へ直し、差分をレビューに載せる',
    '（ADR 010）。',
    '',
    `${JSON.stringify(current, null, 2)}\n`,
  ].join('\n');
};

const section = (heading: string, changes: readonly SurfaceChange[]): string[] =>
  changes.length === 0
    ? []
    : [heading, ...changes.map((change) => `  - ${change.path}: ${change.description}`), ''];

/**
 * 形は変わっていないのに一致しない場合。
 *
 * 註釈や並べ方など、比較が名前を付けられないところが動いている。
 * **名前を付けられないことを「何も無い」として出さない**（ADR 006 の
 * `_unclassified` と同じ）。
 */
const unclassified = (changes: readonly SurfaceChange[]): string[] =>
  changes.length > 0
    ? []
    : ['鍵・値・並びは変わっていない。比較が読まないどこかが動いている。差分を読むこと。', ''];

const compare = (published: unknown, current: unknown, path: string): SurfaceChange[] => {
  if (deepEqual(published, current)) {
    return [];
  }

  if (Array.isArray(published) && Array.isArray(current)) {
    return compareArrays(published, current, path);
  }

  if (isRecord(published) && isRecord(current)) {
    return compareRecords(published, current, path);
  }

  return [
    {
      path: path || '(全体)',
      breaking: true,
      description: `${show(published)} が ${show(current)} になった`,
    },
  ];
};

/**
 * 並びの比較。
 *
 * 末尾に足すだけなら互換である。**途中に入れる・順序を変える・減らすのは破壊**で、
 * 語の並びを位置で読んでいる相手（列の順に読むもの）が居るためである。
 */
const compareArrays = (
  published: readonly unknown[],
  current: readonly unknown[],
  path: string
): SurfaceChange[] => {
  const removed = published.filter((item) => !current.some((other) => deepEqual(item, other)));
  if (removed.length > 0) {
    return [
      {
        path,
        breaking: true,
        description: `${removed.map(show).join(' / ')} が無くなった`,
      },
    ];
  }

  const kept = current.slice(0, published.length);
  if (!deepEqual(published, kept)) {
    return [{path, breaking: true, description: '並びが変わった'}];
  }

  const added = current.slice(published.length);
  return [
    {
      path,
      breaking: false,
      description: `${added.map(show).join(' / ')} が末尾に増えた`,
    },
  ];
};

const compareRecords = (
  published: Record<string, unknown>,
  current: Record<string, unknown>,
  path: string
): SurfaceChange[] => {
  const changes: SurfaceChange[] = [];

  for (const key of Object.keys(published)) {
    const at = join(path, key);
    if (!(key in current)) {
      changes.push({path: at, breaking: true, description: '無くなった'});
      continue;
    }
    changes.push(...compare(published[key], current[key], at));
  }

  for (const key of Object.keys(current)) {
    if (!(key in published)) {
      changes.push({path: join(path, key), breaking: false, description: '増えた'});
    }
  }

  return changes;
};

const join = (path: string, key: string): string => (path === '' ? key : `${path}.${key}`);

const show = (value: unknown): string => JSON.stringify(value);

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

/** 面は JSON にできる値だけでできているので、文字列にして比べる。 */
const deepEqual = (left: unknown, right: unknown): boolean =>
  JSON.stringify(left) === JSON.stringify(right);

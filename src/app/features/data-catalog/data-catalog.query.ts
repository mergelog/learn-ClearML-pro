import {Params} from '@angular/router';
import {
  CATALOG_ROUTE,
  QUERY_KEYS,
  QUERY_VALUE_SEPARATOR,
} from '@features/data-catalog/data-catalog.consts';
import {
  CATALOG_ASSET_KINDS,
  CatalogAssetKind,
  CatalogFilter,
  emptyCatalogFilter,
} from '@features/data-catalog/data-catalog.model';

/**
 * 絞り込み条件とURLのクエリの相互変換。
 *
 * **これは外向きの変換である。** 絞り込んだ一覧のURLは人に渡され、あとで
 * 外部提供（Stage E）の入口になりうる（プランの §4.2）。だから変換は
 * container の中に埋めず、独立して確かめられる形で置く。
 *
 * 3つの決めごとがある。
 *
 * 既定値はクエリに出さない。絞っていない条件までURLに並ぶと、何を絞ったのかが
 * URLから読めなくなる。
 *
 * 読めない値は落とす。`kind=banana` を「そういう種別がある」と解釈しても
 * 一致するものは無く、画面は理由の言えない空になる。落として「その条件は
 * 無かった」ことにすれば、少なくとも何が効いているかは一致する。
 *
 * **往復しても同じものになる。** `toQueryParams(fromQueryParams(q))` が
 * 元と食い違うと、URLを開いた瞬間にURLが書き換わる。
 */

/** URLのクエリから条件を読む。読めないものは既定に倒す。 */
export const fromQueryParams = (params: Params): CatalogFilter => ({
  text: readOne(params[QUERY_KEYS.text]),
  kinds: readMany(params[QUERY_KEYS.kinds]).filter(isCatalogAssetKind),
  project: readOne(params[QUERY_KEYS.project]),
  tags: readMany(params[QUERY_KEYS.tags]),
  updatedFrom: readDate(params[QUERY_KEYS.updatedFrom]),
  updatedTo: readDate(params[QUERY_KEYS.updatedTo]),
});

/**
 * 条件をURLのクエリにする。
 *
 * 空の条件には `null` を入れる。Angularの `queryParams` は `null` を
 * 「その鍵を消す」として扱う。鍵ごと省くと、前のURLに残っていた条件が
 * 消えずに残る。
 */
export const toQueryParams = (filter: CatalogFilter): Params => ({
  [QUERY_KEYS.text]: emptyToNull(filter.text),
  [QUERY_KEYS.kinds]: joinOrNull(filter.kinds),
  [QUERY_KEYS.project]: emptyToNull(filter.project),
  [QUERY_KEYS.tags]: joinOrNull(filter.tags),
  [QUERY_KEYS.updatedFrom]: emptyToNull(filter.updatedFrom),
  [QUERY_KEYS.updatedTo]: emptyToNull(filter.updatedTo),
});

/**
 * 条件を、人に渡せる1本のURLにする。
 *
 * `toQueryParams` はAngularのRouterへ渡す形（消す鍵を `null` で表す）なので、
 * そのままでは文字列にならない。ここは**外へ出す側**で、書き出したファイルの
 * `reference` にも入る（ADR 010）。ファイルを受け取った人が、それを作った
 * 画面へ戻れることがこの関数の役目である。
 *
 * 区切りのコンマは戻す。`encodeURIComponent` は `,` を `%2C` にするが、
 * クエリの中のコンマは RFC 3986 でそのまま置ける文字であり、Angular の
 * Router がアドレス欄に出すのもコンマである。**画面に出ているURLと、
 * ファイルに入るURLを違えない。**
 */
export const toReferenceUrl = (filter: CatalogFilter): string => {
  const query = Object.entries(toQueryParams(filter))
    .filter((entry): entry is [string, string] => typeof entry[1] === 'string')
    .map(([key, value]) => `${key}=${encodeValue(value)}`)
    .join('&');

  return query === '' ? CATALOG_ROUTE : `${CATALOG_ROUTE}?${query}`;
};

const encodeValue = (value: string): string =>
  encodeURIComponent(value).replaceAll('%2C', QUERY_VALUE_SEPARATOR);

/** 既定（何も絞っていない）と同じか。URLを書き換える必要があるかの判断に使う。 */
export const isDefaultFilter = (filter: CatalogFilter): boolean =>
  sameFilter(filter, emptyCatalogFilter);

/**
 * 2つの条件が同じものか。
 *
 * URLが変わるたびに一覧を引き直すので、同じ条件で二度引かないための判定が要る。
 * 参照の比較では足りない。URLから読み直すたびに別のオブジェクトになる。
 */
export const sameFilter = (left: CatalogFilter, right: CatalogFilter): boolean =>
  left.text === right.text &&
  left.project === right.project &&
  left.updatedFrom === right.updatedFrom &&
  left.updatedTo === right.updatedTo &&
  sameValues(left.kinds, right.kinds) &&
  sameValues(left.tags, right.tags);

const sameValues = (left: readonly string[], right: readonly string[]): boolean =>
  left.length === right.length && left.every((value, index) => value === right[index]);

const isCatalogAssetKind = (value: string): value is CatalogAssetKind =>
  (CATALOG_ASSET_KINDS as readonly string[]).includes(value);

/**
 * 1つの値。
 *
 * 同じ鍵が複数回現れたら先頭だけを採る。ここで連結すると、
 * `q=a&q=b` が `a,b` という誰も入力していない検索語になる。
 */
const readOne = (value: unknown): string => {
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0].trim() : '';
  }
  return typeof value === 'string' ? value.trim() : '';
};

/** 複数の値。区切り文字でも、同じ鍵の繰り返しでも受ける。 */
const readMany = (value: unknown): string[] => {
  const raw = Array.isArray(value) ? value : [value];
  return raw
    .filter((item): item is string => typeof item === 'string')
    .flatMap((item) => item.split(QUERY_VALUE_SEPARATOR))
    .map((item) => item.trim())
    .filter((item) => item !== '');
};

/**
 * 日付。`YYYY-MM-DD` だけを受ける。
 *
 * 書式を確かめるのは、読めない値をそのままClearMLへ渡さないためである。
 * 渡すと条件として効かないまま結果だけが変わり、なぜ変わったのかが
 * 画面からは分からない。
 */
const readDate = (value: unknown): string => {
  const text = readOne(value);
  return DATE_PATTERN.test(text) ? text : '';
};

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

const emptyToNull = (value: string): string | null => (value === '' ? null : value);

const joinOrNull = (values: readonly string[]): string | null =>
  values.length === 0 ? null : values.join(QUERY_VALUE_SEPARATOR);

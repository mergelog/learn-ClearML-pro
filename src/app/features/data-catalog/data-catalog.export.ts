import {CatalogAsset, CatalogFilter} from '@features/data-catalog/data-catalog.model';
import {toReferenceUrl} from '@features/data-catalog/data-catalog.query';

/**
 * 台帳を1つのファイルにして外へ渡す形。
 *
 * **外へ出すのは `CatalogAsset` であって、ClearML API の応答ではない**
 * （プランの §5）。生の応答を渡すと、ClearML 追従のたびに受け取った側が壊れる。
 *
 * 出すのは資産の並びではなく**封筒**である。封筒が持つのは
 * 「どの条件で引いたか」「その条件で開けるURL」「上限で打ち切られたか」の3つで、
 * これは**画面が黙らないと決めたことを、ファイルになっても黙らないため**にある
 * （ADR 010）。
 *
 * 一覧は上限で打ち切る。画面はそれを注記で言っているが、注記はファイルに
 * 付いてこない。**打ち切られた台帳は、台帳ではなく抜粋である。** 抜粋を台帳と
 * して渡さないために、封筒が自分で `truncated` を名乗る。
 *
 * `reference` があるので、ファイルを受け取った人はそれを作った画面へ戻れる。
 * 書き出し（E-a）と参照URL（E-b）は同じ1つの条件を指す。
 *
 * ここは純粋な変換である。時刻は引数で受け取る。時計をこの中で読むと、
 * 出来上がる文書が呼ぶたびに変わり、確かめられるのは形だけになる。
 */

/** 文書が何であるかの名乗り。受け取った側が、別の JSON と取り違えないために持つ。 */
export const CATALOG_EXPORT_KIND = 'stackup-data-catalog';

/**
 * 文書の版。
 *
 * 上げるのは**受け取った側の読み方が変わるとき**だけである。資産が1件増えても、
 * 条件が変わっても、版は動かない。形が変われば版とは別に
 * `data-catalog.surface.published.json` との差分として失敗する（ADR 010）。
 */
export const CATALOG_EXPORT_VERSION = 1;

/** 書き出しの MIME タイプ。 */
export const CATALOG_EXPORT_MEDIA_TYPE = 'application/json';

export interface CatalogExportDocument {
  catalog: typeof CATALOG_EXPORT_KIND;
  version: typeof CATALOG_EXPORT_VERSION;
  /** 書き出した時刻（UTC・ISO8601）。 */
  exportedAt: string;
  /** この中身をもう一度画面で開くためのURL。 */
  reference: string;
  /** 効いていた絞り込み条件。 */
  filter: CatalogFilter;
  /** 上限で打ち切られたか。**この1つのために封筒がある。** */
  truncated: boolean;
  /** `assets` の件数。打ち切られているときは「全部」ではない。 */
  count: number;
  assets: readonly CatalogAsset[];
}

export interface CatalogExportInput {
  filter: CatalogFilter;
  assets: readonly CatalogAsset[];
  hasMore: boolean;
  exportedAt: Date;
}

/**
 * いま画面に見えているものを、そのまま文書にする。
 *
 * **引き直さない。** 引き直して全件出すと、渡した相手と画面を見ている人が
 * 違うものを見て話すことになる。書き出しは写しであって、別の問い合わせではない
 * （ADR 010）。
 */
export const catalogExportDocument = (input: CatalogExportInput): CatalogExportDocument => ({
  catalog: CATALOG_EXPORT_KIND,
  version: CATALOG_EXPORT_VERSION,
  exportedAt: input.exportedAt.toISOString(),
  reference: toReferenceUrl(input.filter),
  filter: input.filter,
  truncated: input.hasMore,
  count: input.assets.length,
  assets: input.assets,
});

/**
 * 文書を、ファイルに書く文字列にする。
 *
 * 人が読む前提で字下げする。台帳の書き出しは機械へ流し込む前に必ず一度
 * 人が開くもので、1行の JSON は開いた瞬間に読めない。
 */
export const catalogExportText = (document: CatalogExportDocument): string =>
  `${JSON.stringify(document, null, 2)}\n`;

/**
 * ファイル名。
 *
 * 時刻を秒まで入れる。同じ条件で2度書き出したときに、後から取った方が
 * 前のものを黙って置き換えないためである。記号は落とす。`:` を含む名前は
 * Windows で保存できない。
 */
export const catalogExportFilename = (exportedAt: Date): string =>
  `data-catalog-${exportedAt.toISOString().slice(0, 19).replace(/[-:]/g, '')}Z.json`;

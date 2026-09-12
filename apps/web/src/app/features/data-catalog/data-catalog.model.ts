/**
 * 台帳が扱う形。ClearML APIの応答そのものではない。
 *
 * ClearML側の実体は Dataset（`data_processing` のTask）・Model・Run（Task）の
 * 3つに分かれていて、画面もそれぞれ別に割れている。「このモデルはどのデータから
 * 来たのか」を一画面で答えるには、3つを**1つの語彙**へ寄せる必要がある。
 * その語彙がここにある。
 *
 * 共通で持つのは7つだけである。種別・名前・所属プロジェクト・更新日時・タグ・
 * 状態・元の実体へのID。**種別ごとの固有情報をここへ入れない。** 入れると型が
 * 3つの実体の和集合になり、どのフィールドがいつ埋まるのかを誰も言えなくなる。
 * 固有情報は `CatalogAssetDetail` として、種別ごとに取りに行く。
 *
 * ClearMLの語彙（Task、`data_processing`、hyperparams）は `data-access` の
 * 内側に留める。ここから先には現れない。現れていたら、それは adapter の漏れである。
 */

/** 台帳が並べる資産の種別。ClearMLの実体3つに対応する。 */
export type CatalogAssetKind = 'dataset' | 'model' | 'run';

export const CATALOG_ASSET_KINDS: readonly CatalogAssetKind[] = ['dataset', 'model', 'run'];

/**
 * 資産がいまどうなっているか。
 *
 * 3種別で状態の語彙が違う（Taskは実行状態、Modelは公開済みかどうか）。
 * それでも台帳が並べる以上、**同じ列に置ける語**でなければならない。
 * ここに寄せるのは「その資産を当てにしてよいか」を答えられる粒度までである。
 *
 * 知らない値は落とさず `unknown` にする。落とすと「使ってよいのか分からない」
 * ことすら分からなくなる。
 */
export type CatalogAssetState =
  | 'draft'
  | 'running'
  | 'completed'
  | 'failed'
  | 'stopped'
  | 'published'
  | 'unknown';

/** 資産が属するプロジェクト。IDだけだと画面に出せず、名前だけだと絞れない。 */
export interface CatalogProject {
  id: string;
  name: string;
}

/**
 * 台帳の1行。
 *
 * `id` は元の実体のIDである。台帳は自分のIDを振らない。振ると、同じものに
 * 2つの名前が付き、ClearML側と突き合わせるたびに対応表が要る。
 *
 * `updatedAt` は `null` を許す。既定の日付で埋めると「更新されていない」と
 * 「いつ更新されたか分からない」が区別できなくなる。
 */
export interface CatalogAsset {
  kind: CatalogAssetKind;
  id: string;
  name: string;
  project: CatalogProject;
  updatedAt: string | null;
  tags: readonly string[];
  state: CatalogAssetState;
}

/** 一覧の1ページ。 */
export interface CatalogPage {
  assets: readonly CatalogAsset[];
  /**
   * まだ続きがあるか。
   *
   * 総件数は返さない。ClearMLは種別ごとに別の問い合わせで答えるので、
   * 「全部で何件か」を出すにはページングとは別の数え上げが要る。
   * 一覧に必要なのは「見えているものが全部ではない」という一言だけである。
   */
  hasMore: boolean;
}

/**
 * 詳細で出す、種別ごとの固有情報。
 *
 * 型ではなく名前と値の並びにしている。3種別の固有情報は重なりが無く、
 * 共通の型に押し込めると結局すべてが省略可能になる。並びにしておけば、
 * 「何が埋まっているか」は値そのものが答える。
 */
export interface CatalogFact {
  label: string;
  value: string;
}

/**
 * 1つの資産の詳細。
 *
 * `description` を一覧（`CatalogAsset`）へ入れないのは、一覧の判断に要らない
 * からである。要らないものを一覧の問い合わせに載せると、行数ぶんだけ無駄に重くなる。
 */
export interface CatalogAssetDetail {
  asset: CatalogAsset;
  description: string;
  facts: readonly CatalogFact[];
}

/**
 * lineage の1つの節。
 *
 * `asset` が `null` になりうるのは、辿った先が消えている場合である。
 * 消えていることを黙って節ごと落とすと、鎖が繋がっているように見えてしまう。
 * 「ここに何かがあったが、もう無い」と言えるように、IDだけは残す。
 */
export interface CatalogLineageNode {
  kind: CatalogAssetKind;
  id: string;
  asset: CatalogAsset | null;
}

/**
 * Dataset → Run → Model の鎖。
 *
 * どの節から辿り始めても同じ形になる。画面は「いま見ている資産がどこにいるか」
 * を `origin` で知る。
 */
export interface CatalogLineage {
  origin: CatalogAssetKind;
  dataset: CatalogLineageNode | null;
  run: CatalogLineageNode | null;
  model: CatalogLineageNode | null;
}

/**
 * 一覧を絞る条件。
 *
 * すべて省略可能で、省略は「絞らない」を意味する。**空文字と未指定を
 * 区別しない。** 区別すると、URLから復元したときに「空文字で絞る」という
 * 誰も意図しない条件が生まれる。
 */
export interface CatalogFilter {
  /** 名前の部分一致。 */
  text: string;
  /** 種別。空なら全種別。 */
  kinds: readonly CatalogAssetKind[];
  /** プロジェクト名（完全一致）。 */
  project: string;
  /** タグ。複数指定はAND。 */
  tags: readonly string[];
  /** 更新日時の下限（ISO8601の日付）。 */
  updatedFrom: string;
  /** 更新日時の上限（ISO8601の日付）。 */
  updatedTo: string;
}

export const emptyCatalogFilter: CatalogFilter = {
  text: '',
  kinds: [],
  project: '',
  tags: [],
  updatedFrom: '',
  updatedTo: '',
};

/** 何も絞っていないか。「まだ無い」と「条件に合うものが無い」を出し分けるのに使う。 */
export const isEmptyFilter = (filter: CatalogFilter): boolean =>
  filter.text === '' &&
  filter.kinds.length === 0 &&
  filter.project === '' &&
  filter.tags.length === 0 &&
  filter.updatedFrom === '' &&
  filter.updatedTo === '';

/** 編集できるメタデータ。台帳が書き込むのはこの2つだけである。 */
export interface CatalogMetadataEdit {
  tags: readonly string[];
  description: string;
}

/** 画面全体が持つ状態。 */
export interface DataCatalogState {
  /** いま適用されている条件。URLのクエリと同じものを指す。 */
  filter: CatalogFilter;
  assets: readonly CatalogAsset[];
  /** 一覧が上限で打ち切られたか。打ち切ったことを黙っていないために持つ。 */
  hasMore: boolean;
  /** 絞り込みの選択肢。一覧とは別に読む。 */
  projects: readonly string[];
  availableTags: readonly string[];

  /** 詳細で開いている資産。一覧とは別に読む（一覧に無い資産をURLで直接開ける）。 */
  detail: CatalogAssetDetail | null;
  lineage: CatalogLineage | null;

  /** 一覧の読み込み中。 */
  loading: boolean;
  /** 詳細の読み込み中。一覧とは別に持つ。片方の読み込みで他方を隠さない。 */
  detailLoading: boolean;
  /** メタデータの保存中。応答が返るまで二重に送らせないために持つ。 */
  saving: boolean;

  /** 直前の失敗の理由。成功したら消す。 */
  error: string | null;
}

export const initialDataCatalogState: DataCatalogState = {
  filter: emptyCatalogFilter,
  assets: [],
  hasMore: false,
  projects: [],
  availableTags: [],
  detail: null,
  lineage: null,
  loading: false,
  detailLoading: false,
  saving: false,
  error: null,
};

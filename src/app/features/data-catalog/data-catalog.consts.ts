import {CatalogAsset, CatalogAssetKind} from '@features/data-catalog/data-catalog.model';

/**
 * 台帳が置く上限と、外向きの語彙。
 *
 * ここに置くのは「画面の都合で決めた数」と「URLに現れる文字列」である。
 * ClearML上の名前（プロジェクト名・パラメータ名）は `data-access` 側が持つ。
 */

/**
 * 台帳の入口。
 *
 * 条件を変えたときに書き換えるURLの、パスの側である。`app.routes.ts` の
 * `path` と同じ文字列でなければならない。片方だけ変えると、絞り込んだ瞬間に
 * 画面が404へ飛ぶ。
 */
export const CATALOG_ROUTE = '/data-catalog';

/**
 * 一覧が1度に読む件数。
 *
 * 種別ごとに別の問い合わせを出し、それを混ぜて1つの表にする。つまり実際に
 * 運ぶのは最大でこの3倍になる。大きくすると、混ぜた後に捨てる分が増えるだけで
 * 画面に出る件数は変わらない。
 *
 * 上限に達したことは黙らない。件数が合わないことを表の中で言う
 * （`CatalogPage.hasMore`）。黙ると、絞り込みの結果が「これで全部」に見える。
 */
export const CATALOG_PAGE_SIZE = 50;

/** 1種別あたりに読む件数。混ぜてから `CATALOG_PAGE_SIZE` へ切る。 */
export const PER_KIND_PAGE_SIZE = CATALOG_PAGE_SIZE;

/** 絞り込みの選択肢として出すプロジェクトとタグの上限。 */
export const FILTER_OPTION_LIMIT = 200;

/**
 * URLのクエリパラメータ名。
 *
 * **外向きの名前である。** 絞り込んだ一覧のURLは人に渡され、あとで
 * 外部提供（Stage E）の入口になりうる。内部の変数名を変えるのと同じ気軽さで
 * 変えると、渡されたURLが黙って別の意味になる。
 */
export const QUERY_KEYS = {
  text: 'q',
  kinds: 'kind',
  project: 'project',
  tags: 'tag',
  updatedFrom: 'from',
  updatedTo: 'to',
} as const;

/** クエリの中で複数値を並べるときの区切り。 */
export const QUERY_VALUE_SEPARATOR = ',';

/** 種別の表示名。URLに出るのは `CatalogAssetKind` そのものである。 */
export const KIND_LABELS: Readonly<Record<CatalogAssetKind, string>> = {
  dataset: 'Dataset',
  model: 'Model',
  run: 'Run',
};

/**
 * 既存のClearML画面への行き先。
 *
 * 台帳は横断の入口であって、詳細の置き換えではない（プランの §1.2）。
 * 種別ごとの深い情報は、それを持っている既存の画面へ渡す。
 *
 * プロジェクトIDが無い資産へはリンクを作らない。ClearMLのこれらの画面は
 * どれもプロジェクト配下にあり、IDが無いまま組み立てると404へ送ることになる。
 */
export const vendorLinkOf = (asset: CatalogAsset): string[] | null => {
  if (!asset.project.id || !asset.id) {
    return null;
  }

  switch (asset.kind) {
    case 'dataset':
      return ['/datasets', 'simple', asset.project.id, 'tasks', asset.id];
    case 'model':
      return ['/projects', asset.project.id, 'models', asset.id];
    case 'run':
      return ['/projects', asset.project.id, 'tasks', asset.id];
  }
};

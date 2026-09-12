import {createSelector} from '@ngrx/store';
import {
  selectAssets,
  selectDetail,
  selectFilter,
  selectLineage,
  selectLoading,
  selectSaving,
} from '~/features/data-catalog/state/data-catalog.reducer';
import {
  CatalogLineageNode,
  isEmptyFilter,
} from '~/features/data-catalog/data-catalog.model';

/**
 * state から導かれる問い。
 *
 * reducer が答えるのは「いま何が入っているか」までで、「なぜ空なのか」
 * 「保存してよいか」はそこから導かれる別の問いである。導出をここへ集めておくと、
 * 同じ判断が container と template に散らばらない。
 */

/** 何も絞っていないか。 */
export const selectFilterIsEmpty = createSelector(selectFilter, isEmptyFilter);

/**
 * 一覧が空である理由。
 *
 * **「まだ何も無い」と「条件に合うものが無い」は別のことである。** 同じ
 * 「0件です」で済ませると、絞り込みを外せば見えるものを、存在しないものとして
 * 読ませることになる。読み込み中は、まだどちらとも言えないので `null` を返す。
 */
export const selectEmptyReason = createSelector(
  selectAssets,
  selectLoading,
  selectFilterIsEmpty,
  (assets, loading, filterIsEmpty): 'nothing-yet' | 'no-match' | null => {
    if (loading || assets.length > 0) {
      return null;
    }
    return filterIsEmpty ? 'nothing-yet' : 'no-match';
  }
);

/** 詳細で開いている資産そのもの。 */
export const selectDetailAsset = createSelector(selectDetail, (detail) => detail?.asset ?? null);

/**
 * 保存してよいか。
 *
 * 開いている資産があって、いま保存中でないときだけである。送信中も押せると、
 * 同じ資産へ更新が2回飛び、あとから届いたほうが勝つ。どちらが勝つかを
 * 利用者が選べない以上、押させない。
 */
export const selectCanSave = createSelector(
  selectDetail,
  selectSaving,
  (detail, saving) => detail !== null && !saving
);

/**
 * lineage を `Dataset → Run → Model` の並びにする。
 *
 * 起点がどれであっても並び順は変えない。台帳が答えたいのは
 * 「このモデルはどのデータから来たのか」であり、それは**データから
 * モデルへ流れる向き**で読む。起点を先頭に置き換えると、同じ鎖が
 * 開いた場所によって逆向きに見える。
 */
export const selectLineageNodes = createSelector(
  selectLineage,
  (lineage): readonly CatalogLineageNode[] =>
    lineage === null
      ? []
      : [lineage.dataset, lineage.run, lineage.model].filter(
          (node): node is CatalogLineageNode => node !== null
        )
);

/**
 * 鎖が途中で切れているか。
 *
 * 3つ揃っていなければ切れている。切れていることを黙ると、「このモデルの
 * 出所は分からない」ことが「出所を辿る必要が無い」ことのように見える。
 */
export const selectLineageIsPartial = createSelector(
  selectLineage,
  (lineage) =>
    lineage !== null && (lineage.dataset === null || lineage.run === null || lineage.model === null)
);

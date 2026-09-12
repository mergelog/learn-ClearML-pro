import {createActionGroup, emptyProps, props} from '@ngrx/store';
import {
  CatalogAssetDetail,
  CatalogAssetKind,
  CatalogFilter,
  CatalogLineage,
  CatalogMetadataEdit,
  CatalogPage,
} from '~/features/data-catalog/data-catalog.model';

/**
 * 台帳で起こりうることの一覧。
 *
 * 「何が起きたか」を書き、「次に何をするか」は書かない。`filterChanged` は
 * 利用者が条件を変えたという事実であり、`openList` はその条件で一覧を開けと
 * いう事実である。**この2つを分けているのが、この feature の要になる。**
 *
 * 条件を変えたときに直接引きに行かない。条件はまずURLへ載り、URLが変わったことで
 * 一覧を引き直す。そうしておくと、利用者が条件を変えた場合と、条件つきURLを
 * 誰かから渡されて開いた場合が、同じ1本の経路になる（プランの §4.2）。
 * 経路が2本あると、片方だけ直って「自分で絞ると出るのに、URLを渡すと出ない」
 * という壊れ方をする。
 *
 * 失敗は成功と同じ重みで宣言する。一覧の失敗・詳細の失敗・保存の失敗で、
 * 画面の戻し方がそれぞれ違う。
 */
export const dataCatalogActions = createActionGroup({
  source: 'Data Catalog',
  events: {
    /** URLのクエリが決まった。一覧を引く。 */
    'open list': props<{filter: CatalogFilter}>(),
    'list loaded': props<{page: CatalogPage}>(),
    'list failed': props<{reason: string}>(),

    /** 利用者が条件を変えた。URLへ載せるところから始まる。 */
    'filter changed': props<{filter: CatalogFilter}>(),

    /** 絞り込みの選択肢を読む。一覧とは別に読む。 */
    'load options': emptyProps(),
    'options loaded': props<{projects: readonly string[]; tags: readonly string[]}>(),

    /** 1つの資産を開いた。 */
    'open detail': props<{kind: CatalogAssetKind; id: string}>(),
    /**
     * 詳細が読めた。`detail` が `null` なのは「消えている」である。
     * 失敗と分けているのは、戻し方が違うためで、消えたものは再読込しても戻らない。
     */
    'detail loaded': props<{detail: CatalogAssetDetail | null}>(),
    'detail failed': props<{reason: string}>(),
    /** lineage は詳細より遅れて届く。届かなくても詳細は出す。 */
    'lineage loaded': props<{lineage: CatalogLineage}>(),

    /** メタデータを保存する。 */
    'save metadata': props<{kind: CatalogAssetKind; id: string; edit: CatalogMetadataEdit}>(),
    'metadata saved': props<{edit: CatalogMetadataEdit}>(),
    'save failed': props<{reason: string}>(),

    /** 詳細を閉じた。一覧はそのまま残す。 */
    'leave detail': emptyProps(),
    /** 画面を離れた。状態を捨てる。 */
    'leave page': emptyProps(),
  },
});

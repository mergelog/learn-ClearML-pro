import {createFeature, createReducer, on} from '@ngrx/store';
import {dataCatalogActions} from '~/features/data-catalog/state/data-catalog.actions';
import {
  CatalogLineage,
  DataCatalogState,
  initialDataCatalogState,
} from '~/features/data-catalog/data-catalog.model';

export const DATA_CATALOG_FEATURE = 'dataCatalog';

/**
 * その lineage が、どの資産を起点に組まれたものか。
 *
 * 起点の節は `origin` が指す種別の位置にある。別の資産を開いたときに
 * 前の鎖を持ち越さないための判定にだけ使う。
 */
const originIdOf = (lineage: CatalogLineage | null): string | null =>
  lineage === null ? null : (lineage[lineage.origin]?.id ?? null);

/**
 * 台帳の状態遷移。
 *
 * 5つの決めごとがある。
 *
 * 一覧・詳細・保存の進行中を別のフラグで持つ。詳細を読んでいる間に一覧を
 * 隠さないし、保存中に一覧の再読込を止めない。1つのフラグにまとめると、
 * どれかが必ず不自然になる。
 *
 * 条件は一覧の結果と一緒に持たない。`openList` の時点で state に入れる。
 * 結果を待ってから入れると、読み込み中の画面が「前の条件」を表示し続ける。
 *
 * **保存は応答を待ってから state に反映する。** 楽観更新をしない。台帳は
 * 「いま何があるか」を答える場所であり、まだサーバが受け付けていない値を
 * 事実として見せると、台帳が嘘をつくことになる（ADR 008）。
 *
 * 成功したら失敗を消す。失敗しても直前の結果は消さない。消すのは離脱した
 * ときだけである。
 *
 * 派生した問い（絞っているか、結果が空なのはなぜか）はここに書かない。
 * それは `data-catalog.selectors.ts` の仕事である。
 */
export const dataCatalogFeature = createFeature({
  name: DATA_CATALOG_FEATURE,
  reducer: createReducer<DataCatalogState>(
    initialDataCatalogState,

    on(
      dataCatalogActions.openList,
      (state, {filter}): DataCatalogState => ({
        ...state,
        filter,
        loading: true,
        error: null,
      })
    ),
    on(
      dataCatalogActions.listLoaded,
      (state, {page}): DataCatalogState => ({
        ...state,
        assets: page.assets,
        hasMore: page.hasMore,
        loading: false,
        error: null,
      })
    ),
    on(
      dataCatalogActions.listFailed,
      (state, {reason}): DataCatalogState => ({
        ...state,
        loading: false,
        error: reason,
      })
    ),

    on(
      dataCatalogActions.optionsLoaded,
      (state, {projects, tags}): DataCatalogState => ({
        ...state,
        projects,
        availableTags: tags,
      })
    ),

    on(
      dataCatalogActions.openDetail,
      (state, {id}): DataCatalogState => ({
        ...state,
        // 別の資産を開いたなら、前の資産の詳細とlineageは持ち越さない。
        // 同じ資産の読み直し（保存の後など）では消さない。消すと画面が一度空になる。
        detail: state.detail?.asset.id === id ? state.detail : null,
        lineage: originIdOf(state.lineage) === id ? state.lineage : null,
        detailLoading: true,
        error: null,
      })
    ),
    on(
      dataCatalogActions.detailLoaded,
      (state, {detail}): DataCatalogState => ({
        ...state,
        detail,
        detailLoading: false,
        error: null,
      })
    ),
    on(
      dataCatalogActions.detailFailed,
      (state, {reason}): DataCatalogState => ({
        ...state,
        detailLoading: false,
        error: reason,
      })
    ),
    on(
      dataCatalogActions.lineageLoaded,
      (state, {lineage}): DataCatalogState => ({
        ...state,
        lineage,
      })
    ),

    on(
      dataCatalogActions.saveMetadata,
      (state): DataCatalogState => ({
        ...state,
        saving: true,
        error: null,
      })
    ),
    on(
      dataCatalogActions.metadataSaved,
      (state, {edit}): DataCatalogState => ({
        ...state,
        saving: false,
        // サーバが受け付けた値だけを反映する。開いている詳細が無いなら、
        // 反映先も無い（保存中に別の資産へ移った場合）。
        detail:
          state.detail === null
            ? null
            : {
                ...state.detail,
                description: edit.description,
                asset: {...state.detail.asset, tags: edit.tags},
              },
        // 一覧にも同じ資産が並んでいる。片方だけ直すと、一覧と詳細で
        // 違うタグが出る。
        assets: state.assets.map((asset) =>
          asset.id === state.detail?.asset.id ? {...asset, tags: edit.tags} : asset
        ),
        error: null,
      })
    ),
    on(
      dataCatalogActions.saveFailed,
      (state, {reason}): DataCatalogState => ({
        ...state,
        saving: false,
        error: reason,
      })
    ),

    on(
      dataCatalogActions.leaveDetail,
      (state): DataCatalogState => ({
        ...state,
        detail: null,
        lineage: null,
        detailLoading: false,
        saving: false,
        error: null,
      })
    ),

    on(dataCatalogActions.leavePage, (): DataCatalogState => initialDataCatalogState)
  ),
});

export const {
  selectDataCatalogState,
  selectFilter,
  selectAssets,
  selectHasMore,
  selectProjects,
  selectAvailableTags,
  selectDetail,
  selectLineage,
  selectLoading,
  selectDetailLoading,
  selectSaving,
  selectError,
} = dataCatalogFeature;

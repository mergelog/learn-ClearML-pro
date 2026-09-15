import {inject, Injectable} from '@angular/core';
import {Router} from '@angular/router';
import {Actions, createEffect, ofType} from '@ngrx/effects';
import {concatLatestFrom} from '@ngrx/operators';
import {Store} from '@ngrx/store';
import {EMPTY, of} from 'rxjs';
import {catchError, concatMap, exhaustMap, map, mergeMap, switchMap} from 'rxjs/operators';
import {dataCatalogActions} from '@features/data-catalog/state/data-catalog.actions';
import {DataCatalogApiService} from '@features/data-catalog/data-access/data-catalog-api.service';
import {selectDetail} from '@features/data-catalog/state/data-catalog.reducer';
import {toQueryParams} from '@features/data-catalog/data-catalog.query';
import {CATALOG_ROUTE} from '@features/data-catalog/data-catalog.consts';
import {CatalogAsset} from '@features/data-catalog/data-catalog.model';
import {describeClearmlFailure} from '~/shared/clearml/clearml-failure';

/**
 * 台帳が外の世界に触れる唯一の場所。
 *
 * Effectsは、更新する state と同じ feature の下に置いてある。どの state が
 * どこから書き換わるのかを、ディレクトリを見れば追えるようにするためである
 * （ADR 007）。
 *
 * 決めごとが5つある。
 *
 * 失敗はactionとして流す。例外をそのまま投げると、そのeffectは以後
 * 何も受け取らなくなる。画面が「押しても無反応」になるのはこれが原因になりやすい。
 *
 * **条件の変更はURLの書き換えで終わる。** ここで一覧を引かない。引くのは
 * URLが変わったことを見た container が `openList` を流したときである。
 * 両方でやると同じ条件で2回引く。
 *
 * 読み取りは新しい要求で置き換えてよい（`switchMap`）。条件を素早く変えた
 * ときに、古い条件の結果が後から届いて上書きするのを防ぐ。
 *
 * **書き込みは打ち切らない。** 保存は `exhaustMap` で、送信中の要求を
 * 後から来た要求で置き換えない。打ち切ると、ClearML側が受け付けたのか
 * どうか分からないまま画面だけが次へ進む。
 *
 * lineage の失敗は画面全体の失敗にしない。出所が辿れないことは、資産が
 * 読めないことではない。詳細は出したまま、鎖だけ空にしておく。
 */
@Injectable()
export class DataCatalogEffects {
  private readonly actions = inject(Actions);
  private readonly store = inject(Store);
  private readonly router = inject(Router);
  private readonly api = inject(DataCatalogApiService);

  /** URLのクエリが決まったら、その条件で引く。 */
  readonly loadList = createEffect(() =>
    this.actions.pipe(
      ofType(dataCatalogActions.openList),
      switchMap(({filter}) =>
        this.api.search(filter).pipe(
          map((page) => dataCatalogActions.listLoaded({page})),
          catchError((error: unknown) =>
            of(dataCatalogActions.listFailed({reason: describeClearmlFailure(error)}))
          )
        )
      )
    )
  );

  /**
   * 条件が変わったらURLへ載せる。ここで一覧は引かない。
   *
   * `replaceUrl` にしているのは、絞り込みの1文字ごとに履歴が積まれると、
   * 戻るボタンで画面を出られなくなるためである。条件つきURLを渡す目的には
   * 現在のURLがあれば足りる。
   */
  readonly syncUrl = createEffect(
    () =>
      this.actions.pipe(
        ofType(dataCatalogActions.filterChanged),
        concatMap(({filter}) =>
          this.router.navigate([CATALOG_ROUTE], {
            queryParams: toQueryParams(filter),
            replaceUrl: true,
          })
        )
      ),
    {dispatch: false}
  );

  /**
   * 絞り込みの選択肢を読む。
   *
   * 失敗しても action を流さない。選択肢が出ないだけで、絞り込みは
   * 自由入力からでも成立する。ここで画面全体を失敗にすると、一覧は
   * 読めているのに赤い文字が出る。
   */
  readonly loadOptions = createEffect(() =>
    this.actions.pipe(
      ofType(dataCatalogActions.loadOptions),
      switchMap(() =>
        this.api.getProjectNames().pipe(
          mergeMap((projects) =>
            this.api
              .getTags()
              .pipe(map((tags) => dataCatalogActions.optionsLoaded({projects, tags})))
          ),
          catchError(() => EMPTY)
        )
      )
    )
  );

  /** 1つの資産の詳細を読む。 */
  readonly loadDetail = createEffect(() =>
    this.actions.pipe(
      ofType(dataCatalogActions.openDetail),
      switchMap(({kind, id}) =>
        this.api.getDetail(kind, id).pipe(
          map((detail) => dataCatalogActions.detailLoaded({detail})),
          catchError((error: unknown) =>
            of(dataCatalogActions.detailFailed({reason: describeClearmlFailure(error)}))
          )
        )
      )
    )
  );

  /**
   * 詳細が読めたら、その資産の出所を辿る。
   *
   * 詳細と同時に投げない。lineage は詳細の中身（どのDataset版数で走ったか）を
   * 起点にするため、詳細が読めるまで辿る相手が決まらない。
   */
  readonly loadLineage = createEffect(() =>
    this.actions.pipe(
      ofType(dataCatalogActions.detailLoaded),
      map(({detail}) => detail?.asset ?? null),
      switchMap((asset: CatalogAsset | null) =>
        asset === null
          ? EMPTY
          : this.api.getLineage(asset).pipe(
              map((lineage) => dataCatalogActions.lineageLoaded({lineage})),
              // 出所が辿れないことは、資産が読めないことではない。
              catchError(() => EMPTY)
            )
      )
    )
  );

  /**
   * メタデータを保存する。
   *
   * 応答が「1件変えた」と言ったときだけ成功にする。判定は
   * `DataCatalogApiService.updateMetadata` の中にあり、変えられなかったときは
   * 例外として上がってくる。ここではそれを失敗のactionへ移すだけである。
   */
  readonly saveMetadata = createEffect(() =>
    this.actions.pipe(
      ofType(dataCatalogActions.saveMetadata),
      exhaustMap(({kind, id, edit}) =>
        this.api.updateMetadata(kind, id, edit).pipe(
          map((saved) => dataCatalogActions.metadataSaved({edit: saved})),
          catchError((error: unknown) =>
            of(dataCatalogActions.saveFailed({reason: describeClearmlFailure(error)}))
          )
        )
      )
    )
  );

  /**
   * 保存した後は、開いている資産を読み直す。
   *
   * サーバが受け付けた値は反映済みだが、**同じ資産を別の場所（既存の
   * Dataset / Model 画面）から編集されている**可能性がある。読み直すことで、
   * 自分の変更が他の変更を上書きしていた場合に、その結果が画面に出る
   * （ADR 008）。
   */
  readonly reloadAfterSave = createEffect(() =>
    this.actions.pipe(
      ofType(dataCatalogActions.metadataSaved),
      concatLatestFrom(() => this.store.select(selectDetail)),
      mergeMap(([, detail]) =>
        detail === null
          ? EMPTY
          : of(
              dataCatalogActions.openDetail({kind: detail.asset.kind, id: detail.asset.id})
            )
      )
    )
  );
}

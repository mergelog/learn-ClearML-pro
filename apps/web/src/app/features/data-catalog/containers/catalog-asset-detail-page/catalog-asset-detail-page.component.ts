import {ChangeDetectionStrategy, Component, computed, effect, inject, OnDestroy} from '@angular/core';
import {toSignal} from '@angular/core/rxjs-interop';
import {ActivatedRoute, ParamMap, RouterLink} from '@angular/router';
import {Store} from '@ngrx/store';
import {dataCatalogActions} from '~/features/data-catalog/state/data-catalog.actions';
import {
  selectDetail,
  selectDetailLoading,
  selectError,
  selectSaving,
} from '~/features/data-catalog/state/data-catalog.reducer';
import {
  selectCanSave,
  selectLineageIsPartial,
  selectLineageNodes,
} from '~/features/data-catalog/state/data-catalog.selectors';
import {CATALOG_ROUTE, KIND_LABELS} from '~/features/data-catalog/data-catalog.consts';
import {
  CATALOG_ASSET_KINDS,
  CatalogAssetKind,
  CatalogMetadataEdit,
} from '~/features/data-catalog/data-catalog.model';
import {CatalogAssetFactsComponent} from '~/features/data-catalog/components/catalog-asset-facts/catalog-asset-facts.component';
import {CatalogLineageComponent} from '~/features/data-catalog/components/catalog-lineage/catalog-lineage.component';
import {CatalogMetadataFormComponent} from '~/features/data-catalog/components/catalog-metadata-form/catalog-metadata-form.component';

/**
 * 1つの資産の詳細。
 *
 * **URLだけで開ける。** 一覧を経由しなくても、`/data-catalog/model/<id>` を
 * 直接開けば読める。台帳から渡されるのは結局この形のURLなので、一覧の state に
 * 依存させると、渡されたURLが「一覧を開いてから来た人」にしか働かなくなる。
 *
 * 種別が読めないURLでは何も引かない。`kind` はURLの一部であって利用者の
 * 入力ではないが、URLは手で書き換えられる。読めない種別でClearMLへ
 * 問い合わせても、返ってくるのは理由の言えない空である。
 */
@Component({
  selector: 'sm-catalog-asset-detail-page',
  templateUrl: './catalog-asset-detail-page.component.html',
  styleUrls: ['./catalog-asset-detail-page.component.scss'],
  imports: [
    RouterLink,
    CatalogAssetFactsComponent,
    CatalogLineageComponent,
    CatalogMetadataFormComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CatalogAssetDetailPageComponent implements OnDestroy {
  private readonly store = inject(Store);
  private readonly route = inject(ActivatedRoute);

  protected readonly catalogRoute = CATALOG_ROUTE;
  protected readonly kindLabels = KIND_LABELS;

  protected readonly detail = this.store.selectSignal(selectDetail);
  protected readonly detailLoading = this.store.selectSignal(selectDetailLoading);
  protected readonly saving = this.store.selectSignal(selectSaving);
  protected readonly canSave = this.store.selectSignal(selectCanSave);
  protected readonly error = this.store.selectSignal(selectError);
  protected readonly lineageNodes = this.store.selectSignal(selectLineageNodes);
  protected readonly lineageIsPartial = this.store.selectSignal(selectLineageIsPartial);

  // 初期値を置かない。`toSignal` の初期値は本来の型でなければならず、
  // `ParamMap` の「まだ無い」を表す値は存在しない。購読前を `undefined` の
  // まま扱い、読めないURLと同じ扱いにする。
  private readonly params = toSignal(this.route.paramMap);

  /** URLが指している資産。読めないURLでは `null`。 */
  protected readonly target = computed(() => readTarget(this.params()));

  constructor() {
    effect(() => {
      const target = this.target();
      if (target === null) {
        return;
      }
      this.store.dispatch(dataCatalogActions.openDetail(target));
    });
  }

  ngOnDestroy(): void {
    // 一覧はそのまま残す。詳細から戻ったときに一覧を引き直さないためである。
    this.store.dispatch(dataCatalogActions.leaveDetail());
  }

  protected save(edit: CatalogMetadataEdit): void {
    const target = this.target();
    if (target === null) {
      return;
    }
    this.store.dispatch(dataCatalogActions.saveMetadata({...target, edit}));
  }
}

/** URLから種別とIDを読む。どちらかが読めなければ開かない。 */
const readTarget = (
  params: ParamMap | undefined
): {kind: CatalogAssetKind; id: string} | null => {
  const kind = params?.get('kind') ?? '';
  const id = params?.get('id') ?? '';

  if (id === '' || !isCatalogAssetKind(kind)) {
    return null;
  }
  return {kind, id};
};

const isCatalogAssetKind = (value: string): value is CatalogAssetKind =>
  (CATALOG_ASSET_KINDS as readonly string[]).includes(value);

import {ChangeDetectionStrategy, Component, effect, inject, OnDestroy, OnInit} from '@angular/core';
import {toSignal} from '@angular/core/rxjs-interop';
import {ActivatedRoute, Params} from '@angular/router';
import {Store} from '@ngrx/store';
import {dataCatalogActions} from '@features/data-catalog/state/data-catalog.actions';
import {
  selectAssets,
  selectAvailableTags,
  selectError,
  selectFilter,
  selectHasMore,
  selectLoading,
  selectProjects,
} from '@features/data-catalog/state/data-catalog.reducer';
import {selectEmptyReason} from '@features/data-catalog/state/data-catalog.selectors';
import {fromQueryParams, sameFilter} from '@features/data-catalog/data-catalog.query';
import {CatalogFilter} from '@features/data-catalog/data-catalog.model';
import {CatalogFiltersComponent} from '@features/data-catalog/components/catalog-filters/catalog-filters.component';
import {CatalogAssetsTableComponent} from '@features/data-catalog/components/catalog-assets-table/catalog-assets-table.component';
import {
  CATALOG_EXPORT_MEDIA_TYPE,
  catalogExportDocument,
  catalogExportFilename,
  catalogExportText,
} from '@features/data-catalog/data-catalog.export';
import {CatalogDownloadService} from '@features/data-catalog/data-catalog.download';

/**
 * 資産を1つの語彙で横断して引く画面。
 *
 * この feature で store に触れる container は2つあり（もう1つは詳細）、
 * どちらも state を読んで子へ渡し、子から返ってきた操作を action にするだけである。
 * 子は store を知らないので、単体で組み立てて確かめられる。
 *
 * **一覧を引く条件は、常にURLから読む。** 絞り込みの操作は
 * `filterChanged` としてURLの書き換えになり、書き換わったURLをここが読んで
 * `openList` になる。条件つきURLを渡されて開いた場合とまったく同じ経路を通る
 * （プランの §4.2）。経路を2本にすると、片方だけ直って「自分で絞ると出るのに、
 * URLを渡すと出ない」という壊れ方をする。
 *
 * ClearMLの語彙はここまで届かない。届いていたら、それはadapterかEffectsの
 * 漏れである。
 */
@Component({
  selector: 'sm-data-catalog-page',
  templateUrl: './data-catalog-page.component.html',
  styleUrls: ['./data-catalog-page.component.scss'],
  imports: [CatalogFiltersComponent, CatalogAssetsTableComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DataCatalogPageComponent implements OnInit, OnDestroy {
  private readonly store = inject(Store);
  private readonly route = inject(ActivatedRoute);
  private readonly downloads = inject(CatalogDownloadService);

  protected readonly filter = this.store.selectSignal(selectFilter);
  protected readonly assets = this.store.selectSignal(selectAssets);
  protected readonly hasMore = this.store.selectSignal(selectHasMore);
  protected readonly projects = this.store.selectSignal(selectProjects);
  protected readonly availableTags = this.store.selectSignal(selectAvailableTags);
  protected readonly loading = this.store.selectSignal(selectLoading);
  protected readonly error = this.store.selectSignal(selectError);
  protected readonly emptyReason = this.store.selectSignal(selectEmptyReason);

  private readonly queryParams = toSignal(this.route.queryParams, {
    initialValue: {} as Params,
  });

  /**
   * 直前に引いた条件。
   *
   * URLは同じ条件でも別のオブジェクトとして流れてくる（戻る・進む・
   * 自分で書き換えた直後）。参照だけで見ると同じ条件で何度も引くことになる。
   */
  private requested: CatalogFilter | null = null;

  constructor() {
    effect(() => {
      const filter = fromQueryParams(this.queryParams());
      if (this.requested !== null && sameFilter(this.requested, filter)) {
        return;
      }
      this.requested = filter;
      this.store.dispatch(dataCatalogActions.openList({filter}));
    });
  }

  ngOnInit(): void {
    // 選択肢は条件に依らないので、一覧とは別に1度だけ読む。
    this.store.dispatch(dataCatalogActions.loadOptions());
  }

  ngOnDestroy(): void {
    this.store.dispatch(dataCatalogActions.leavePage());
  }

  protected applyFilter(filter: CatalogFilter): void {
    this.store.dispatch(dataCatalogActions.filterChanged({filter}));
  }

  /**
   * いま見えているものを1つのファイルにして渡す（ADR 010）。
   *
   * store へ action を出さない。state は何も変わらないためである。
   * 引き直しもしない。**書き出しは、いま画面にあるものの写しである。**
   * 上限で打ち切られているなら、そのことは文書の `truncated` が名乗る。
   *
   * 時刻は1度だけ読む。ファイル名と中身で別々に読むと、秒をまたいだときに
   * 名前と `exportedAt` が食い違う。
   */
  protected exportAssets(): void {
    const exportedAt = new Date();
    const document = catalogExportDocument({
      filter: this.filter(),
      assets: this.assets(),
      hasMore: this.hasMore(),
      exportedAt,
    });

    this.downloads.save(
      catalogExportFilename(exportedAt),
      CATALOG_EXPORT_MEDIA_TYPE,
      catalogExportText(document)
    );
  }
}

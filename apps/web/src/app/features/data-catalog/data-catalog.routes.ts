import {Routes} from '@angular/router';
import {provideState} from '@ngrx/store';
import {provideEffects} from '@ngrx/effects';
import {CrumbTypeEnum} from '@common/layout/breadcrumbs/breadcrumbs.component';
import {dataCatalogFeature} from '~/features/data-catalog/state/data-catalog.reducer';
import {DataCatalogEffects} from '~/features/data-catalog/state/data-catalog.effects';
import {DataCatalogApiService} from '~/features/data-catalog/data-access/data-catalog-api.service';
import {CatalogDownloadService} from '~/features/data-catalog/data-catalog.download';

const staticBreadcrumb = [
  [
    {
      name: 'DATA CATALOG',
      type: CrumbTypeEnum.Feature,
    },
  ],
];

/**
 * state・Effects・API境界を、この経路に入ったときだけ用意する。
 *
 * アプリ全体へ登録しないのは、この画面を開かない利用者にとっては存在しない
 * ほうが正しいからで、どの state がどこで生まれるかもここを見れば分かる
 * （ADR 007）。`quality-pipeline.routes.ts` と同じ形である。
 *
 * **provider は親の経路に置く。** 一覧と詳細は同じ state を共有する。
 * それぞれの経路に置くと、詳細へ移った瞬間に state が作り直され、
 * 戻ったときに一覧を引き直すことになる。
 */
export const routes: Routes = [
  {
    path: '',
    providers: [
      provideState(dataCatalogFeature),
      provideEffects([DataCatalogEffects]),
      DataCatalogApiService,
      // 外向きの境界はもう1つある。ClearML ではなくブラウザが相手で、
      // 書き出したファイルを利用者へ渡す（ADR 010）。
      CatalogDownloadService,
    ],
    children: [
      {
        path: '',
        // breadcrumb は子ごとに置く。Angular の既定
        // （`paramsInheritanceStrategy: 'emptyOnly'`）では、パラメータを持つ
        // 子は親の `data` を受け継がない。親にだけ置くと詳細で消える。
        data: {staticBreadcrumb},
        loadComponent: () =>
          import(
            '~/features/data-catalog/containers/data-catalog-page/data-catalog-page.component'
          ).then((c) => c.DataCatalogPageComponent),
      },
      {
        // 種別を経路に入れるのは、IDだけではどのAPIへ問い合わせるか決まらない
        // ためである。ClearMLのTaskとModelはIDの空間が別で、片方のIDを
        // もう片方へ問い合わせると、失敗ではなく「見つからない」が返る。
        path: ':kind/:id',
        data: {staticBreadcrumb},
        loadComponent: () =>
          import(
            '~/features/data-catalog/containers/catalog-asset-detail-page/catalog-asset-detail-page.component'
          ).then((c) => c.CatalogAssetDetailPageComponent),
      },
    ],
  },
];

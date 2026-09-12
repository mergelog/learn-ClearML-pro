import {Routes} from '@angular/router';
import {provideState} from '@ngrx/store';
import {provideEffects} from '@ngrx/effects';
import {CrumbTypeEnum} from '@common/layout/breadcrumbs/breadcrumbs.component';
import {qualityPipelineFeature} from '~/features/quality-pipeline/state/quality-pipeline.reducer';
import {QualityPipelineEffects} from '~/features/quality-pipeline/state/quality-pipeline.effects';
import {QualityPipelineApiService} from '~/features/quality-pipeline/data-access/quality-pipeline-api.service';

const staticBreadcrumb = [
  [
    {
      name: 'QUALITY PIPELINE',
      type: CrumbTypeEnum.Feature,
    },
  ],
];

/**
 * state・Effects・API境界を、この経路に入ったときだけ用意する。
 *
 * アプリ全体へ登録しないのは、この画面を開かない利用者にとっては存在しない
 * ほうが正しいからで、どの state がどこで生まれるかもここを見れば分かる。
 */
export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import(
        '~/features/quality-pipeline/containers/quality-pipeline-page/quality-pipeline-page.component'
      ).then((c) => c.QualityPipelinePageComponent),
    data: {staticBreadcrumb},
    providers: [
      provideState(qualityPipelineFeature),
      provideEffects([QualityPipelineEffects]),
      QualityPipelineApiService,
    ],
  },
];

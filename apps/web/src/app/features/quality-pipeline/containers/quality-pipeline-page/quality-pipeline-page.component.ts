import {ChangeDetectionStrategy, Component, inject, OnDestroy, OnInit} from '@angular/core';
import {Store} from '@ngrx/store';
import {qualityPipelineActions} from '~/features/quality-pipeline/state/quality-pipeline.actions';
import {
  selectCancelling,
  selectError,
  selectLoading,
  selectProductionModel,
  selectRun,
  selectScores,
  selectStarting,
  selectSteps,
  selectStepsTruncated,
  selectTemplate,
} from '~/features/quality-pipeline/state/quality-pipeline.reducer';
import {
  selectCanCancel,
  selectCanStart,
  selectRunIsTemplate,
} from '~/features/quality-pipeline/state/quality-pipeline.selectors';
import {StartRunFormComponent} from '~/features/quality-pipeline/components/start-run-form/start-run-form.component';
import {RunSummaryComponent} from '~/features/quality-pipeline/components/run-summary/run-summary.component';
import {PipelineStepsTableComponent} from '~/features/quality-pipeline/components/pipeline-steps-table/pipeline-steps-table.component';
import {EvaluationScoresTableComponent} from '~/features/quality-pipeline/components/evaluation-scores-table/evaluation-scores-table.component';
import {ProductionModelCardComponent} from '~/features/quality-pipeline/components/production-model-card/production-model-card.component';

/**
 * 学習Pipelineを起動し、結果までを追う画面。
 *
 * この feature で store に触れる唯一のcomponentである。ここが state を読んで
 * 子へ渡し、子から返ってきた操作を action にする。子は store を知らないので、
 * 単体で組み立てて確かめられる。
 *
 * この画面が持っているのは「利用者の操作」だけで、判断も取得も持たない。
 * ClearMLの語彙はここまで届かない。届いていたら、それはadapterかEffectsの
 * 漏れである。
 */
@Component({
  selector: 'sm-quality-pipeline-page',
  templateUrl: './quality-pipeline-page.component.html',
  styleUrls: ['./quality-pipeline-page.component.scss'],
  imports: [
    StartRunFormComponent,
    RunSummaryComponent,
    PipelineStepsTableComponent,
    EvaluationScoresTableComponent,
    ProductionModelCardComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class QualityPipelinePageComponent implements OnInit, OnDestroy {
  private readonly store = inject(Store);

  protected readonly template = this.store.selectSignal(selectTemplate);
  protected readonly run = this.store.selectSignal(selectRun);
  protected readonly steps = this.store.selectSignal(selectSteps);
  protected readonly stepsTruncated = this.store.selectSignal(selectStepsTruncated);
  protected readonly scores = this.store.selectSignal(selectScores);
  protected readonly productionModel = this.store.selectSignal(selectProductionModel);
  protected readonly loading = this.store.selectSignal(selectLoading);
  protected readonly starting = this.store.selectSignal(selectStarting);
  protected readonly cancelling = this.store.selectSignal(selectCancelling);
  protected readonly error = this.store.selectSignal(selectError);
  protected readonly canStart = this.store.selectSignal(selectCanStart);
  protected readonly canCancel = this.store.selectSignal(selectCanCancel);
  protected readonly runIsTemplate = this.store.selectSignal(selectRunIsTemplate);

  ngOnInit(): void {
    this.store.dispatch(qualityPipelineActions.openPage());
  }

  ngOnDestroy(): void {
    // 追跡を止め、次に開いたときに前の実行が残らないようにする。
    this.store.dispatch(qualityPipelineActions.leavePage());
  }

  protected start(datasetVersion: string): void {
    this.store.dispatch(qualityPipelineActions.startRun({datasetVersion}));
  }

  protected refresh(): void {
    this.store.dispatch(qualityPipelineActions.refreshRun());
  }

  protected reload(): void {
    this.store.dispatch(qualityPipelineActions.openPage());
  }

  protected cancel(): void {
    this.store.dispatch(qualityPipelineActions.cancelRun());
  }
}

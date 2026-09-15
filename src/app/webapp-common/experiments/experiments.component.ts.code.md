````ts
import {                                                                                                  // 使用する依存要素の名前付きimportを開始
  ChangeDetectionStrategy,                                                                                // ChangeDetectionStrategyを名前付きimportの対象に追加
  Component,                                                                                              // Componentを名前付きimportの対象に追加
  computed,                                                                                               // computedを名前付きimportの対象に追加
  effect,                                                                                                 // effectを名前付きimportの対象に追加
  OnDestroy,                                                                                              // OnDestroyを名前付きimportの対象に追加
  signal,                                                                                                 // signalを名前付きimportの対象に追加
  viewChild                                                                                               // viewChildを名前付きimportの対象に追加
} from '@angular/core';                                                                                   // 名前付きimportの読み込み元を指定
import {                                                                                                  // 使用する依存要素の名前付きimportを開始
  selectActiveParentsFilter,                                                                              // selectActiveParentsFilterを名前付きimportの対象に追加
  selectCompareSelectedMetrics,                                                                           // selectCompareSelectedMetricsを名前付きimportの対象に追加
  selectCustomColumns,                                                                                    // selectCustomColumnsを名前付きimportの対象に追加
  selectExperimentsList,                                                                                  // selectExperimentsListを名前付きimportの対象に追加
  selectExperimentsParents,                                                                               // selectExperimentsParentsを名前付きimportの対象に追加
  selectExperimentsTableColsOrder,                                                                        // selectExperimentsTableColsOrderを名前付きimportの対象に追加
  selectExperimentsTags,                                                                                  // selectExperimentsTagsを名前付きimportの対象に追加
  selectExperimentsTypes,                                                                                 // selectExperimentsTypesを名前付きimportの対象に追加
  selectFilteredTableCols,                                                                                // selectFilteredTableColsを名前付きimportの対象に追加
  selectHyperParamsOptions,                                                                               // selectHyperParamsOptionsを名前付きimportの対象に追加
  selectHyperParamsVariants,                                                                              // selectHyperParamsVariantsを名前付きimportの対象に追加
  selectIsExperimentInEditMode,                                                                           // selectIsExperimentInEditModeを名前付きimportの対象に追加
  selectMetricVariantForView,                                                                             // selectMetricVariantForViewを名前付きimportの対象に追加
  selectMetricVariants,                                                                                   // selectMetricVariantsを名前付きimportの対象に追加
  selectNoMoreExperiments,                                                                                // selectNoMoreExperimentsを名前付きimportの対象に追加
  selectSelectedExperiments,                                                                              // selectSelectedExperimentsを名前付きimportの対象に追加
  selectSelectedExperimentsDisableAvailable,                                                              // selectSelectedExperimentsDisableAvailableを名前付きimportの対象に追加
  selectSelectedTableExperiment,                                                                          // selectSelectedTableExperimentを名前付きimportの対象に追加
  selectShowAllSelectedIsActive,                                                                          // selectShowAllSelectedIsActiveを名前付きimportの対象に追加
  selectShowCompareScalarSettings,                                                                        // selectShowCompareScalarSettingsを名前付きimportの対象に追加
  selectSplitSize,                                                                                        // selectSplitSizeを名前付きimportの対象に追加
  selectTableCompareView,                                                                                 // selectTableCompareViewを名前付きimportの対象に追加
  selectTableFilters,                                                                                     // selectTableFiltersを名前付きimportの対象に追加
  selectTableMode,                                                                                        // selectTableModeを名前付きimportの対象に追加
  selectTableRefreshSessionList,                                                                          // selectTableRefreshSessionListを名前付きimportの対象に追加
  selectTableSortFields                                                                                   // selectTableSortFieldsを名前付きimportの対象に追加
} from './reducers';                                                                                      // 名前付きimportの読み込み元を指定
import {                                                                                                  // 使用する依存要素の名前付きimportを開始
  selectCompanyTags,                                                                                      // selectCompanyTagsを名前付きimportの対象に追加
  selectRouterProjectId,                                                                                  // selectRouterProjectIdを名前付きimportの対象に追加
  selectSelectedProjectId,                                                                                // selectSelectedProjectIdを名前付きimportの対象に追加
  selectTagsFilterByProject                                                                               // selectTagsFilterByProjectを名前付きimportの対象に追加
} from '../core/reducers/projects.reducer';                                                               // 名前付きimportの読み込み元を指定
import {ColHeaderTypeEnum, ISmCol, TableSortOrderEnum} from '../shared/ui-components/data/table/table.consts'; // 使用する依存要素の名前付きimportを開始
import {isEqual} from 'lodash-es';                                                                        // 使用する依存要素の名前付きimportを開始
import {selectRouterParams} from '../core/reducers/router-reducer';                                       // 使用する依存要素の名前付きimportを開始
import {debounceTime, distinctUntilChanged, filter, map, skip, switchMap, tap} from 'rxjs/operators';     // 使用する依存要素の名前付きimportを開始
import {combineLatest, Observable} from 'rxjs';                                                           // 使用する依存要素の名前付きimportを開始
import {selectBackdropActive} from '../core/reducers/view.reducer';                                       // 使用する依存要素の名前付きimportを開始
import {initSearch, resetSearch} from '../common-search/common-search.actions';                           // 使用する依存要素の名前付きimportを開始
import {selectSearchQuery} from '../common-search/common-search.reducer';                                 // 使用する依存要素の名前付きimportを開始
import {ITableExperiment} from './shared/common-experiment-model.model';                                  // 使用する依存要素の名前付きimportを開始
import * as experimentsActions from './actions/common-experiments-view.actions';                          // 実験画面のAction群を名前空間付きで読み込む
import {resetAceCaretsPositions, setAutoRefresh} from '../core/actions/layout.actions';                   // 使用する依存要素の名前付きimportを開始
import {                                                                                                  // 使用する依存要素の名前付きimportを開始
  getProjectUsers,                                                                                        // getProjectUsersを名前付きimportの対象に追加
  setArchive as setProjectArchive,                                                                        // プロジェクトのarchive Actionを衝突しない別名で読み込む
  setBreadcrumbsOptions,                                                                                  // setBreadcrumbsOptionsを名前付きimportの対象に追加
  setDeep                                                                                                 // setDeepを名前付きimportの対象に追加
} from '../core/actions/projects.actions';                                                                // 名前付きimportの読み込み元を指定
import {                                                                                                  // 使用する依存要素の名前付きimportを開始
  createCompareMetricColumn,                                                                              // createCompareMetricColumnを名前付きimportの対象に追加
  createMetricColumn,                                                                                     // createMetricColumnを名前付きimportの対象に追加
  decodeColumns,                                                                                          // decodeColumnsを名前付きimportの対象に追加
  decodeFilter,                                                                                           // decodeFilterを名前付きimportの対象に追加
  decodeOrder,                                                                                            // decodeOrderを名前付きimportの対象に追加
  decodeURIComponentSafe                                                                                  // decodeURIComponentSafeを名前付きimportの対象に追加
} from '../shared/utils/tableParamEncode';                                                                // 名前付きimportの読み込み元を指定
import {BaseEntityPageComponent} from '../shared/entity-page/base-entity-page';                           // 使用する依存要素の名前付きimportを開始
import {groupHyperParams} from '../shared/utils/shared-utils';                                            // 使用する依存要素の名前付きimportを開始
import {                                                                                                  // 使用する依存要素の名前付きimportを開始
  ProjectsGetTaskParentsResponseParents                                                                   // ProjectsGetTaskParentsResponseParentsを名前付きimportの対象に追加
} from '~/business-logic/model/projects/projectsGetTaskParentsResponseParents';                           // 名前付きimportの読み込み元を指定
import {FilterMetadata, SortMeta} from 'primeng/api';                                                     // 使用する依存要素の名前付きimportを開始
import {EntityTypeEnum} from '~/shared/constants/non-common-consts';                                      // 使用する依存要素の名前付きimportを開始
import {ShowItemsFooterSelected} from '../shared/entity-page/footer-items/show-items-footer-selected';    // 使用する依存要素の名前付きimportを開始
import {CompareFooterItem} from '../shared/entity-page/footer-items/compare-footer-item';                 // 使用する依存要素の名前付きimportを開始
import {DividerFooterItem} from '../shared/entity-page/footer-items/divider-footer-item';                 // 使用する依存要素の名前付きimportを開始
import {ArchiveFooterItem} from '../shared/entity-page/footer-items/archive-footer-item';                 // 使用する依存要素の名前付きimportを開始
import {SelectedTagsFooterItem} from '../shared/entity-page/footer-items/selected-tags-footer-item';      // 使用する依存要素の名前付きimportを開始
import {DeleteFooterItem} from '../shared/entity-page/footer-items/delete-footer-item';                   // 使用する依存要素の名前付きimportを開始
import {ResetFooterItem} from '../shared/entity-page/footer-items/reset-footer-item';                     // 使用する依存要素の名前付きimportを開始
import {PublishFooterItem} from '../shared/entity-page/footer-items/publish-footer-item';                 // 使用する依存要素の名前付きimportを開始
import {MoveToFooterItem} from '../shared/entity-page/footer-items/move-to-footer-item';                  // 使用する依存要素の名前付きimportを開始
import {EnqueueFooterItem} from '../shared/entity-page/footer-items/enqueue-footer-item';                 // 使用する依存要素の名前付きimportを開始
import {AbortFooterItem} from '../shared/entity-page/footer-items/abort-footer-item';                     // 使用する依存要素の名前付きimportを開始
import {addTag} from './actions/common-experiments-menu.actions';                                         // 使用する依存要素の名前付きimportを開始
import {                                                                                                  // 使用する依存要素の名前付きimportを開始
  CountAvailableAndIsDisableSelectedFiltered,                                                             // CountAvailableAndIsDisableSelectedFilteredを名前付きimportの対象に追加
  MenuItems,                                                                                              // MenuItemsを名前付きimportの対象に追加
  selectionDisabledAbort,                                                                                 // selectionDisabledAbortを名前付きimportの対象に追加
  selectionDisabledAbortAllChildren,                                                                      // selectionDisabledAbortAllChildrenを名前付きimportの対象に追加
  selectionDisabledArchive,                                                                               // selectionDisabledArchiveを名前付きimportの対象に追加
  selectionDisabledDelete,                                                                                // selectionDisabledDeleteを名前付きimportの対象に追加
  selectionDisabledDequeue,                                                                               // selectionDisabledDequeueを名前付きimportの対象に追加
  selectionDisabledEnqueue,                                                                               // selectionDisabledEnqueueを名前付きimportの対象に追加
  selectionDisabledMoveTo,                                                                                // selectionDisabledMoveToを名前付きimportの対象に追加
  selectionDisabledPipelineRun,                                                                           // selectionDisabledPipelineRunを名前付きimportの対象に追加
  selectionDisabledPublishExperiments,                                                                    // selectionDisabledPublishExperimentsを名前付きimportの対象に追加
  selectionDisabledQueue,                                                                                 // selectionDisabledQueueを名前付きimportの対象に追加
  selectionDisabledReset,                                                                                 // selectionDisabledResetを名前付きimportの対象に追加
  selectionDisabledRetry,                                                                                 // selectionDisabledRetryを名前付きimportの対象に追加
  selectionDisabledViewWorker                                                                             // selectionDisabledViewWorkerを名前付きimportの対象に追加
} from '../shared/entity-page/items.utils';                                                               // 名前付きimportの読み込み元を指定
import {ExperimentsTableComponent} from './dumb/experiments-table/experiments-table.component';           // 使用する依存要素の名前付きimportを開始
import {DequeueFooterItem} from '../shared/entity-page/footer-items/dequeue-footer-item';                 // 使用する依存要素の名前付きimportを開始
import {HasReadOnlyFooterItem} from '../shared/entity-page/footer-items/has-read-only-footer-item';       // 使用する依存要素の名前付きimportを開始
import {encodeHyperParameter, filterArchivedExperiments} from './shared/common-experiments.utils';        // 使用する依存要素の名前付きimportを開始
import {AbortAllChildrenFooterItem} from '../shared/entity-page/footer-items/abort-all-footer-item';      // 使用する依存要素の名前付きimportを開始
import {                                                                                                  // 使用する依存要素の名前付きimportを開始
  ExperimentMenuExtendedComponent                                                                         // ExperimentMenuExtendedComponentを名前付きimportの対象に追加
} from '@features/experiments/containers/experiment-menu-extended/experiment-menu-extended.component';    // 名前付きimportの読み込み元を指定
import {INITIAL_EXPERIMENT_TABLE_COLS} from './experiment.consts';                                        // 使用する依存要素の名前付きimportを開始
import {selectIsPipelines} from '@common/experiments-compare/reducers';                                   // 使用する依存要素の名前付きimportを開始
import {isReadOnly} from '@common/shared/utils/is-read-only';                                             // 使用する依存要素の名前付きimportを開始
import {rootProjectsPageSize} from '@common/constants';                                                   // 使用する依存要素の名前付きimportを開始
import {                                                                                                  // 使用する依存要素の名前付きimportを開始
  SelectionEvent                                                                                          // SelectionEventを名前付きimportの対象に追加
} from '@common/experiments/dumb/select-metric-for-custom-col/select-metric-for-custom-col.component';    // 名前付きimportの読み込み元を指定
import {                                                                                                  // 使用する依存要素の名前付きimportを開始
  CreateExperimentDialogComponent                                                                         // CreateExperimentDialogComponentを名前付きimportの対象に追加
} from '@common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component';      // 名前付きimportの読み込み元を指定
import {RetryFooterItem} from '@common/shared/entity-page/footer-items/retry-footer-item';                // 使用する依存要素の名前付きimportを開始
import {computedPrevious} from 'ngxtension/computed-previous';                                            // 使用する依存要素の名前付きimportを開始
import {takeUntilDestroyed, toSignal} from '@angular/core/rxjs-interop';                                  // 使用する依存要素の名前付きimportを開始
import {setExperiment} from '@common/experiments/actions/common-experiments-info.actions';                // 使用する依存要素の名前付きimportを開始
import {selectMetricsLoading, selectSelectedExperiment} from '@features/experiments/reducers';            // 使用する依存要素の名前付きimportを開始
import {ProjectsGetUserNamesRequest} from '~/business-logic/model/projects/projectsGetUserNamesRequest';  // 使用する依存要素の名前付きimportを開始
import {distinctParamsUntilChanged$} from '@common/projects/common-projects.utils';                       // 使用する依存要素の名前付きimportを開始
import {SplitAreaComponent, SplitComponent} from 'angular-split';                                         // 使用する依存要素の名前付きimportを開始
import {RouterOutlet} from '@angular/router';                                                             // 使用する依存要素の名前付きimportを開始
import {OverlayComponent} from '@common/shared/ui-components/overlay/overlay/overlay.component';          // 使用する依存要素の名前付きimportを開始
import {ExperimentHeaderComponent} from '@common/experiments/dumb/experiment-header/experiment-header.component'; // 使用する依存要素の名前付きimportを開始
import {EntityFooterComponent} from '@common/shared/entity-page/entity-footer/entity-footer.component';   // 使用する依存要素の名前付きimportを開始
import {PushPipe} from '@ngrx/component';                                                                 // 使用する依存要素の名前付きimportを開始
import {TooltipDirective} from '@common/shared/ui-components/indicators/tooltip/tooltip.directive';       // 使用する依存要素の名前付きimportを開始
import {MatButton} from '@angular/material/button';                                                       // 使用する依存要素の名前付きimportを開始
import {MatIconModule} from '@angular/material/icon';                                                     // 使用する依存要素の名前付きimportを開始
import {concatLatestFrom} from '@ngrx/operators';                                                         // 使用する依存要素の名前付きimportを開始


@Component({                                                                                              // Angularコンポーネントのメタデータを定義
  selector: 'sm-common-experiments',                                                                      // テンプレートから使う要素名を指定
  templateUrl: './experiments.component.html',                                                            // 画面構造を外部HTMLへ分離
  styleUrls: ['./experiments.component.scss'],                                                            // この画面専用のスタイルを読み込む
  changeDetection: ChangeDetectionStrategy.OnPush,                                                        // 参照変更を中心に再描画し、不要な変更検知を抑える
  imports: [                                                                                              // テンプレートで利用するスタンドアロン依存を列挙
    SplitComponent,                                                                                       // SplitComponentを名前付きimportの対象に追加
    SplitAreaComponent,                                                                                   // SplitAreaComponentを名前付きimportの対象に追加
    RouterOutlet,                                                                                         // RouterOutletを名前付きimportの対象に追加
    ExperimentsTableComponent,                                                                            // ExperimentsTableComponentをテンプレート依存へ登録
    ExperimentMenuExtendedComponent,                                                                      // ExperimentMenuExtendedComponentをテンプレート依存へ登録
    OverlayComponent,                                                                                     // OverlayComponentをテンプレート依存へ登録
    ExperimentHeaderComponent,                                                                            // ExperimentHeaderComponentをテンプレート依存へ登録
    EntityFooterComponent,                                                                                // EntityFooterComponentをテンプレート依存へ登録
    MatIconModule,                                                                                        // MatIconModuleをテンプレート依存へ登録
    PushPipe,                                                                                             // PushPipeをテンプレート依存へ登録
    TooltipDirective,                                                                                     // TooltipDirectiveをテンプレート依存へ登録
    MatButton                                                                                             // MatButtonをテンプレート依存へ登録
  ]                                                                                                       // 現在の構造または呼び出しを終了
})                                                                                                        // コールバックまたは設定オブジェクトを閉じる
export class ExperimentsComponent extends BaseEntityPageComponent implements OnDestroy {                  // 共通エンティティ画面を継承し、破棄処理も実装
  protected get tableCols() {                                                                             // tableColsを画面の状態または設定として定義
    return INITIAL_EXPERIMENT_TABLE_COLS;                                                                 // 実験一覧の標準列定義を返す
  }                                                                                                       // 現在の構造または呼び出しを終了

  public entityTypeEnum = EntityTypeEnum;                                                                 // entityTypeEnumを画面の状態または設定として定義
  public tableSortOrder$: Observable<TableSortOrderEnum>;                                                 // tableSortOrder$のObservable型を宣言
  public readOnlySelection: boolean;                                                                      // readOnlySelectionの真偽状態を保持
  public contextMenuActive: boolean;                                                                      // contextMenuActiveの真偽状態を保持
  public singleRowContext: boolean;                                                                       // singleRowContextの真偽状態を保持
  public firstExperiment: ITableExperiment;                                                               // firstExperimentを画面の状態または設定として定義
  public menuBackdrop: boolean;                                                                           // menuBackdropの真偽状態を保持
  protected setTableModeAction = experimentsActions.setTableMode;                                         // setTableModeActionを画面の状態または設定として定義
  private sortFields: SortMeta[];                                                                         // sortFieldsを画面の状態または設定として定義

  protected override splitSize = this.store.selectSignal(selectSplitSize);                                // splitSizeをStoreと同期するSignalとして保持
  protected override showAllSelectedIsActive$ = this.store.select(selectShowAllSelectedIsActive);         // showAllSelectedIsActive$をStoreから購読するObservableとして保持

  protected isPipeline$ = this.store.select(selectIsPipelines);                                           // isPipeline$をStoreから購読するObservableとして保持
  protected tableSortFields$ = this.store.select(selectTableSortFields).pipe(tap(field => this.sortFields = field)); // tableSortFields$をStoreから購読するObservableとして保持
  protected backdropActive$ = this.store.select(selectBackdropActive);                                    // backdropActive$をStoreから購読するObservableとして保持
  protected noMoreExperiments$ = this.store.select(selectNoMoreExperiments);                              // noMoreExperiments$をStoreから購読するObservableとして保持
  protected tableFilters$ = this.store.select(selectTableFilters);                                        // tableFilters$をStoreから購読するObservableとして保持
  protected selectedExperimentsDisableAvailable$ = this.store.select(selectSelectedExperimentsDisableAvailable); // selectedExperimentsDisableAvailable$をStoreから購読するObservableとして保持
  protected selectedExperimentsHasUpdate$ = this.store.select(selectTableRefreshSessionList);             // selectedExperimentsHasUpdate$をStoreから購読するObservableとして保持
  protected checkedExperiments$ = this.store.select(selectSelectedExperiments)                            // checkedExperiments$をStoreから購読するObservableとして保持
    .pipe(tap((selectedExperiments: ITableExperiment[]) => {                                              // Observableへ変換・制御処理を連結
      this.checkedExperiments = selectedExperiments;                                                      // コンポーネントの状態または処理参照を設定
      this.readOnlySelection = this.checkedExperiments.some(exp => isReadOnly(exp));                      // コンポーネントの状態または処理参照を設定
    }));                                                                                                  // Actionまたはコールバックを閉じて呼び出しを完了
  protected searchQuery$ = this.store.select(selectSearchQuery);                                          // searchQuery$をStoreから購読するObservableとして保持
  protected parents$ = this.store.select(selectExperimentsParents).pipe(tap(parents => this.parents = parents)); // parents$をStoreから購読するObservableとして保持
  protected activeParentsFilter$ = this.store.select(selectActiveParentsFilter);                          // activeParentsFilter$をStoreから購読するObservableとして保持
  protected types$ = this.store.select(selectExperimentsTypes);                                           // types$をStoreから購読するObservableとして保持
  protected tags$ = this.store.select(selectExperimentsTags);                                             // tags$をStoreから購読するObservableとして保持
  protected tagsFilterByProject$ = this.store.select(selectTagsFilterByProject);                          // tagsFilterByProject$をStoreから購読するObservableとして保持
  protected companyTags$ = this.store.select(selectCompanyTags);                                          // companyTags$をStoreから購読するObservableとして保持
  protected tableColsOrder$ = this.store.select(selectExperimentsTableColsOrder);                         // tableColsOrder$をStoreから購読するObservableとして保持
  protected metricVariants$ = this.store.select(selectMetricVariants);                                    // metricVariants$をStoreから購読するObservableとして保持
  protected metricLoading$ = this.store.select(selectMetricsLoading);                                     // metricLoading$をStoreから購読するObservableとして保持
  protected hyperParamsOptions$ = this.store.select(selectHyperParamsOptions);                            // hyperParamsOptions$をStoreから購読するObservableとして保持
  protected hyperParams$ = this.store.select(selectHyperParamsVariants).pipe(                             // hyperParams$をStoreから購読するObservableとして保持
    map(hyperParams => groupHyperParams(hyperParams.filter(hp => hp.section !== 'properties' || hp.name !== 'version'))) // ストリーム値を画面で必要な形へ変換
  );                                                                                                      // 現在の構造または呼び出しを終了

  protected experiments$ = combineLatest([                                                                // experiments$を画面の状態または設定として定義
    this.store.select(selectExperimentsList)                                                              // コンポーネントが保持する機能を実行
  ])                                                                                                      // 現在の構造または呼び出しを終了
    .pipe(                                                                                                // Observableへ変換・制御処理を連結
      filter(([experiments, ]) => experiments !== null),                                                  // 条件を満たすストリーム値だけを通す
      // lil hack for hiding archived task after they have been archived from task info or footer...
      map(([experiments, ]) => filterArchivedExperiments(experiments, this.inArchivedMode()))             // ストリーム値を画面で必要な形へ変換
    );                                                                                                    // 現在の構造または呼び出しを終了

  protected filteredTableCols$ = this.store.select(selectFilteredTableCols);                              // filteredTableCols$をStoreから購読するObservableとして保持


  protected tableCols$ = this.filteredTableCols$.pipe(                                                    // tableCols$を画面の状態または設定として定義
    distinctUntilChanged((a, b) => isEqual(a, b)),                                                        // 同じ値の連続通知を抑制
    map(cols => cols.filter(col => !col.hidden))                                                          // ストリーム値を画面で必要な形へ変換
  );                                                                                                      // 現在の構造または呼び出しを終了
  override tableMode = this.store.selectSignal(selectTableMode);                                          // tableModeをStoreと同期するSignalとして保持
  // .pipe(tap(tableMode => this.tableMode = tableMode));
  protected showCompareScalarSettings$ = this.store.select(selectShowCompareScalarSettings);              // showCompareScalarSettings$をStoreから購読するObservableとして保持
  protected compareSelectedMetricsScalars$ = this.store.select(selectCompareSelectedMetrics('scalars'));  // compareSelectedMetricsScalars$をStoreから購読するObservableとして保持
  protected compareSelectedMetricsPlots$ = this.store.select(selectCompareSelectedMetrics('plots'));      // compareSelectedMetricsPlots$をStoreから購読するObservableとして保持
  protected selectedExperiment$ = this.store.select(selectSelectedExperiment);                            // selectedExperiment$をStoreから購読するObservableとして保持
  protected selectedTableExperiment = toSignal(this.store.select(selectSelectedTableExperiment)           // selectedTableExperimentをStoreから購読するObservableとして保持
    .pipe(distinctUntilChanged((a, b) => a?.id === b?.id)));                                              // Observableへ変換・制御処理を連結
  private previousTableExperiment = computedPrevious(this.selectedTableExperiment);                       // previousTableExperimentを画面の状態または設定として定義
  protected selectionState = computed(() => ({                                                            // selectionStateを依存Signalから自動再計算
    prevExperiment: this.previousTableExperiment(),                                                       // prevExperimentプロパティへ必要な値を設定
    highlited: signal(this.selectedTableExperiment() ?? this.previousTableExperiment())                   // highlitedプロパティへ必要な値を設定
  }));                                                                                                    // Actionまたはコールバックを閉じて呼び出しを完了
  protected highlited = computed(() => this.tableMode() === 'compare' ? null : this.selectionState().highlited()); // highlitedを依存Signalから自動再計算


  table = viewChild(ExperimentsTableComponent);                                                           // tableとして子コンポーネント参照を取得
  contextMenuExtended = viewChild.required(ExperimentMenuExtendedComponent);                              // contextMenuExtendedとして必須の子コンポーネント参照を取得
  public contextMenu = computed(() => this.contextMenuExtended().contextMenu());                          // contextMenuを依存Signalから自動再計算

  // public tableMode: 'table' | 'info' | 'compare';
  private previousSelectedIds: string;                                                                    // previousSelectedIdsの文字列状態を保持
  public metricsVariants$ = this.store.selectSignal(selectMetricVariantForView);                          // metricsVariants$をStoreと同期するSignalとして保持
  public tableCompareView = this.store.selectSignal(selectTableCompareView);                              // tableCompareViewをStoreと同期するSignalとして保持

  protected showColorsInCards = computed(() => {                                                          // showColorsInCardsを依存Signalから自動再計算
    return this.tableMode() === 'compare';                                                                // 比較モードかどうかからカード配色の要否を返す
  });                                                                                                     // 現在の構造または呼び出しを終了


  override get selectEditMode() {                                                                         // selectEditModeを画面の状態または設定として定義
    return selectIsExperimentInEditMode;                                                                  // 計算結果または処理結果を呼び出し元へ返す
  }                                                                                                       // 現在の構造または呼び出しを終了

  protected override get entityType() {                                                                   // entityTypeを画面の状態または設定として定義
    return EntityTypeEnum.experiment;                                                                     // この画面の対象を実験エンティティとして指定
  }                                                                                                       // 現在の構造または呼び出しを終了

  constructor() {                                                                                         // 画面初期化とStore・URL同期を組み立てる
    super();                                                                                              // 基底クラスの依存関係と初期化処理を実行
    this.setSplitSizeAction = experimentsActions.setSplitSize;                                            // コンポーネントの状態または処理参照を設定
    this.addTag = addTag;                                                                                 // コンポーネントの状態または処理参照を設定
    this.syncAppSearch();                                                                                 // 共通検索欄と一覧フィルターの同期を開始

    this.store.dispatch(getProjectUsers({                                                                 // 画面状態を変更するActionをStoreへdispatch
      projectId: this.selectedProjectId,                                                                  // projectIdプロパティへ必要な値を設定
      entity: ProjectsGetUserNamesRequest.EntityEnum.Task                                                 // entityプロパティへ必要な値を設定
    }));                                                                                                  // Actionまたはコールバックを閉じて呼び出しを完了
    this.store.dispatch(experimentsActions.setTableCols({cols: this.tableCols}));                         // 画面状態を変更するActionをStoreへdispatch

    // effect(() => {
    //   this.shouldOpenDetails = this.tableMode() !== 'table';
    // });

    this.store.select(selectRouterParams)                                                                 // コンポーネントが保持する機能を実行
      .pipe(                                                                                              // Observableへ変換・制御処理を連結
        takeUntilDestroyed(),                                                                             // コンポーネント破棄時に購読を自動解除
        map(params => this.getParamId(params)))                                                           // ストリーム値を画面で必要な形へ変換
      .subscribe(() =>                                                                                    // Observableを購読して画面処理を実行
        this.store.dispatch(resetAceCaretsPositions()));                                                  // 画面状態を変更するActionをStoreへdispatch

    distinctParamsUntilChanged$(combineLatest([                                                           // URL関連値が実質的に変化した時だけ処理
      this.store.select(selectRouterProjectId),                                                           // コンポーネントが保持する機能を実行
      this.route.queryParams,                                                                             // コンポーネントが保持する機能を実行
      this.store.select(selectCustomColumns)                                                              // コンポーネントが保持する機能を実行
    ]))                                                                                                   // combineLatestへ渡すストリーム配列を閉じる
      .subscribe(([prevProjectId, projectId, params]) => {                                                // Observableを購読して画面処理を実行
        if (projectId !== prevProjectId && Object.keys(params || {}).length === 0) {                      // 条件を満たす場合だけ後続処理を実行
          this.emptyUrlInit();                                                                            // コンポーネントが保持する機能を実行
        } else {                                                                                          // 前の条件に該当しない場合を処理
          if ((projectId === prevProjectId || prevProjectId === null) && this.entityType === this.entityTypeEnum.experiment) { // 条件を満たす場合だけ後続処理を実行
            this.setupHeaderTabs('tasks', params.archive === 'true');                                     // コンポーネントの状態または処理参照を設定
          }                                                                                               // 現在の構造または呼び出しを終了
          if (params.columns) {                                                                           // 条件を満たす場合だけ後続処理を実行
            const [cols, metrics, hyperParams, , allIds] = decodeColumns(params.columns, this.tableCols); // 後続処理で使う変更不可のローカル値を作成
            this.store.dispatch(experimentsActions.setVisibleColumnsForProject({                          // 画面状態を変更するActionをStoreへdispatch
              visibleColumns: cols,                                                                       // visibleColumnsプロパティへ必要な値を設定
              projectId: this.projectId()                                                                 // projectIdプロパティへ必要な値を設定
            }));                                                                                          // Actionまたはコールバックを閉じて呼び出しを完了
            this.store.dispatch(experimentsActions.setExtraColumns({                                      // 画面状態を変更するActionをStoreへdispatch
              projectId: this.selectedProjectId,                                                          // projectIdプロパティへ必要な値を設定
              columns: metrics.map(metricCol => createMetricColumn(metricCol, projectId))                 // columnsプロパティへ必要な値を設定
                .concat(hyperParams.map(param => this.createParamColumn(decodeURIComponentSafe(param), projectId))) // 追加列を既存の列配列へ連結
            }));                                                                                          // Actionまたはコールバックを閉じて呼び出しを完了
            this.columnsReordered(allIds, false);                                                         // コンポーネントが保持する機能を実行
          }                                                                                               // 現在の構造または呼び出しを終了
          if (params.order) {                                                                             // 条件を満たす場合だけ後続処理を実行
            const orders = decodeOrder(params.order);                                                     // 後続処理で使う変更不可のローカル値を作成
            this.store.dispatch(experimentsActions.setTableSort({orders, projectId}));                    // 画面状態を変更するActionをStoreへdispatch
          }                                                                                               // 現在の構造または呼び出しを終了
          if (params.filter != null) {                                                                    // 条件を満たす場合だけ後続処理を実行
            const filters = decodeFilter(params.filter);                                                  // 後続処理で使う変更不可のローカル値を作成
            this.store.dispatch(experimentsActions.setTableFilters({filters, projectId: this.selectedProjectId})); // 画面状態を変更するActionをStoreへdispatch
          } else {                                                                                        // 前の条件に該当しない場合を処理
            if (params.order) {                                                                           // 条件を満たす場合だけ後続処理を実行
              this.store.dispatch(experimentsActions.setTableFilters({filters: [], projectId}));          // 画面状態を変更するActionをStoreへdispatch
            }                                                                                             // 現在の構造または呼び出しを終了
          }                                                                                               // 現在の構造または呼び出しを終了
          if (params.deep) {                                                                              // 条件を満たす場合だけ後続処理を実行
            this.store.dispatch(setDeep({deep: true}));                                                   // 画面状態を変更するActionをStoreへdispatch
          }                                                                                               // 現在の構造または呼び出しを終了
          this.store.dispatch(setProjectArchive({archive: params.archive === 'true'}));                   // 画面状態を変更するActionをStoreへdispatch
          this.store.dispatch(experimentsActions.getExperiments());                                       // 画面状態を変更するActionをStoreへdispatch
        }                                                                                                 // 現在の構造または呼び出しを終了
      });                                                                                                 // 現在の構造または呼び出しを終了

    this.createFooterItemsRunner();                                                                       // 選択行に対するフッターメニューを初期化


    this.selectExperimentFromUrl();                                                                       // URLと選択実験・表示モードを同期
    this.store.dispatch(experimentsActions.getParents({searchValue: null}));                              // 画面状態を変更するActionをStoreへdispatch
    effect(() => {                                                                                        // effect処理を定義
      if (this.projectId()) {                                                                             // 条件を満たす場合だけ後続処理を実行
        this.store.dispatch(experimentsActions.getTags({}));                                              // 利用可能なタグ一覧を再取得
        this.store.dispatch(experimentsActions.getProjectTypes({}));                                      // プロジェクト内の実験種別を再取得
      }                                                                                                   // 現在の構造または呼び出しを終了
    });                                                                                                   // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  createFooterItemsRunner = () => this.createFooterItems({                                                // 共通設定を渡してフッター項目を再構築
    entitiesType: this.entityType,                                                                        // entitiesTypeプロパティへ必要な値を設定
    showAllSelectedIsActive$: this.showAllSelectedIsActive$,                                              // 全選択表示の状態ストリームを渡す
    selected$: this.checkedExperiments$,                                                                  // チェック済み実験のストリームを渡す
    tags$: this.tags$,                                                                                    // プロジェクトタグのストリームを渡す
    data$: this.selectedExperimentsDisableAvailable$,                                                     // 操作ごとの利用可否情報を渡す
    companyTags$: this.companyTags$,                                                                      // 会社全体のタグ候補を渡す
    projectTags$: this.store.select(selectSelectedProjectId).pipe(switchMap(id =>                         // 選択プロジェクトに応じてタグ取得元を切り替える
      id === '*' ? this.companyTags$ : this.tags$                                                         // 全プロジェクト時は会社タグ、それ以外はプロジェクトタグを使う
    )),                                                                                                   // 現在の構造または呼び出しを終了
    tagsFilterByProject$: this.tagsFilterByProject$                                                       // タグをプロジェクト単位で絞る設定を渡す
  });                                                                                                     // 現在の構造または呼び出しを終了

  protected emptyUrlInit() {                                                                              // emptyUrlInitを画面の状態または設定として定義
    this.store.dispatch(experimentsActions.updateUrlParams());                                            // 現在の表設定をURLクエリへ反映
    this.shouldOpenDetails = true;                                                                        // コンポーネントの状態または処理参照を設定
  }                                                                                                       // 現在の構造または呼び出しを終了

  getSelectedEntities() {                                                                                 // getSelectedEntities処理を定義
    return this.checkedExperiments;                                                                       // 現在チェックされている実験を返す
  }                                                                                                       // 現在の構造または呼び出しを終了

  override createFooterItems(config: {                                                                    // createFooterItemsを画面の状態または設定として定義
    entitiesType: EntityTypeEnum;                                                                         // entitiesTypeプロパティへ必要な値を設定
    selected$: Observable<ITableExperiment[]>;                                                            // 選択された実験配列のストリーム
    showAllSelectedIsActive$: Observable<boolean>;                                                        // 選択項目だけを表示中か示すストリーム
    tags$: Observable<string[]>;                                                                          // 利用可能なタグ候補のストリーム
    data$?: Observable<Record<string, CountAvailableAndIsDisableSelectedFiltered>>;                       // 各操作の件数と無効理由を持つ省略可能なストリーム
    companyTags$: Observable<string[]>;                                                                   // 会社全体のタグ候補ストリーム
    projectTags$: Observable<string[]>;                                                                   // 現在のプロジェクト用タグ候補ストリーム
    tagsFilterByProject$: Observable<boolean>;                                                            // プロジェクト単位のタグ絞り込み設定
  }) {                                                                                                    // 複数行で宣言した引数型を閉じ、メソッド本体を開始
    super.createFooterItems(config);                                                                      // 基底クラスへフッターの共通設定を渡す
    this.footerItems = [                                                                                  // コンポーネントの状態または処理参照を設定
      new ShowItemsFooterSelected(config.entitiesType),                                                   // 選択件数・全選択切替を表示する項目を追加
      new CompareFooterItem(config.entitiesType),                                                         // 選択項目に対するフッター操作を追加
      new DividerFooterItem(),                                                                            // 選択項目に対するフッター操作を追加
      new ArchiveFooterItem(config.entitiesType),                                                         // 選択項目に対するフッター操作を追加
      new DeleteFooterItem(),                                                                             // 選択項目に対するフッター操作を追加
      new DividerFooterItem(),                                                                            // 選択項目に対するフッター操作を追加
      new EnqueueFooterItem(),                                                                            // 選択項目に対するフッター操作を追加
      new RetryFooterItem(),                                                                              // 選択項目に対するフッター操作を追加
      new DequeueFooterItem(),                                                                            // 選択項目に対するフッター操作を追加
      new ResetFooterItem(config.entitiesType),                                                           // 選択項目に対するフッター操作を追加
      new AbortFooterItem(config.entitiesType),                                                           // 選択項目に対するフッター操作を追加
      new AbortAllChildrenFooterItem(),                                                                   // 選択項目に対するフッター操作を追加
      new PublishFooterItem(this.entityType),                                                             // 選択項目に対するフッター操作を追加
      new DividerFooterItem(),                                                                            // 選択項目に対するフッター操作を追加

      new SelectedTagsFooterItem(this.entityType),                                                        // 選択項目に対するフッター操作を追加
      new DividerFooterItem(),                                                                            // 選択項目に対するフッター操作を追加

      new MoveToFooterItem(),                                                                             // 選択項目に対するフッター操作を追加
      new HasReadOnlyFooterItem()                                                                         // 選択項目に対するフッター操作を追加
    ];                                                                                                    // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  onFooterHandler({emitValue, item}) {                                                                    // onFooterHandler処理を定義
    this.singleRowContext = false;                                                                        // フッター操作では複数選択コンテキストとして扱う
    window.setTimeout(() => {                                                                             // 現在の同期処理後に実行するよう遅延予約
      switch (item.id) {                                                                                  // 選択されたメニューIDごとに処理を分岐
        case MenuItems.showAllItems:                                                                      // showAllItems操作の場合
          this.showAllSelected(!emitValue);                                                               // コンポーネントが保持する機能を実行
          break;                                                                                          // このcaseの処理を終えてswitchを抜ける
        case MenuItems.compare:                                                                           // compare操作の場合
          this.compareExperiments();                                                                      // コンポーネントが保持する機能を実行
          break;                                                                                          // このcaseの処理を終えてswitchを抜ける
        case MenuItems.archive:                                                                           // archive操作の場合
          this.contextMenu().restoreArchive(item.entitiesType);                                           // コンポーネントが保持する機能を実行
          break;                                                                                          // このcaseの処理を終えてswitchを抜ける
        case MenuItems.reset:                                                                             // reset操作の場合
          this.contextMenu().resetPopup();                                                                // コンポーネントが保持する機能を実行
          break;                                                                                          // このcaseの処理を終えてswitchを抜ける
        case MenuItems.publish:                                                                           // publish操作の場合
          this.contextMenu().publishPopup();                                                              // コンポーネントが保持する機能を実行
          break;                                                                                          // このcaseの処理を終えてswitchを抜ける
        case MenuItems.retry:                                                                             // retry操作の場合
          this.contextMenu().retryPopup();                                                                // コンポーネントが保持する機能を実行
          break;                                                                                          // このcaseの処理を終えてswitchを抜ける
        case MenuItems.enqueue:                                                                           // enqueue操作の場合
          this.contextMenu().enqueuePopup();                                                              // コンポーネントが保持する機能を実行
          break;                                                                                          // このcaseの処理を終えてswitchを抜ける
        case MenuItems.dequeue:                                                                           // dequeue操作の場合
          this.contextMenu().dequeuePopup();                                                              // コンポーネントが保持する機能を実行
          break;                                                                                          // このcaseの処理を終えてswitchを抜ける
        case MenuItems.delete:                                                                            // delete操作の場合
          this.contextMenu().deleteExperimentPopup();                                                     // コンポーネントが保持する機能を実行
          break;                                                                                          // このcaseの処理を終えてswitchを抜ける
        case MenuItems.abort:                                                                             // abort操作の場合
          this.contextMenu().stopPopup();                                                                 // コンポーネントが保持する機能を実行
          break;                                                                                          // このcaseの処理を終えてswitchを抜ける
        case MenuItems.abortAllChildren:                                                                  // abortAllChildren操作の場合
          this.contextMenu().stopAllChildrenPopup();                                                      // コンポーネントが保持する機能を実行
          break;                                                                                          // このcaseの処理を終えてswitchを抜ける
        case MenuItems.moveTo:                                                                            // moveTo操作の場合
          this.contextMenu().moveToProjectPopup();                                                        // コンポーネントが保持する機能を実行
          break;                                                                                          // このcaseの処理を終えてswitchを抜ける
      }                                                                                                   // 現在の構造または呼び出しを終了
    });                                                                                                   // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  onAddTag(tag: string, contextExperiment: ITableExperiment) {                                            // onAddTag処理を定義
    this.store.dispatch(addTag({                                                                          // 画面状態を変更するActionをStoreへdispatch
      tag,                                                                                                // 追加するタグ文字列をActionへ渡す
      experiments: this.singleRowContext ? [contextExperiment] : this.checkedExperiments.filter(_selected => !isReadOnly(_selected)) // experimentsプロパティへ必要な値を設定
    }));                                                                                                  // Actionまたはコールバックを閉じて呼び出しを完了
    this.store.dispatch(experimentsActions.addProjectsTag({tag}));                                        // 画面状態を変更するActionをStoreへdispatch
  }                                                                                                       // 現在の構造または呼び出しを終了

  setContextMenuStatus(menuStatus: boolean) {                                                             // setContextMenuStatus処理を定義
    this.contextMenuActive = menuStatus;                                                                  // コンテキストメニューの表示状態を保持
  }                                                                                                       // 現在の構造または呼び出しを終了

  override ngOnDestroy(): void {                                                                          // ngOnDestroyを画面の状態または設定として定義
    super.ngOnDestroy();                                                                                  // 基底クラス側の購読解除などを実行
    this.store.dispatch(experimentsActions.resetExperiments({}));                                         // 画面状態を変更するActionをStoreへdispatch
    this.store.dispatch(setExperiment({experiment: null}));                                               // 画面状態を変更するActionをStoreへdispatch
    this.stopSyncSearch();                                                                                // コンポーネントが保持する機能を実行
  }                                                                                                       // 現在の構造または呼び出しを終了

  stopSyncSearch() {                                                                                      // stopSyncSearch処理を定義
    this.store.dispatch(resetSearch());                                                                   // 共通検索状態を初期化
    this.store.dispatch(experimentsActions.resetGlobalFilter());                                          // 実験一覧の全文検索条件を初期化
  }                                                                                                       // 現在の構造または呼び出しを終了

  syncAppSearch() {                                                                                       // syncAppSearch処理を定義
    this.store.dispatch(initSearch({payload: 'Search for tasks'}));                                       // 共通検索欄へタスク検索用の案内を設定

    this.searchQuery$                                                                                     // コンポーネントが保持する機能を実行
      .pipe(                                                                                              // Observableへ変換・制御処理を連結
        takeUntilDestroyed(),                                                                             // コンポーネント破棄時に購読を自動解除
        skip(1),                                                                                          // 指定回数分の初期通知を無視
        filter(query => query !== null)                                                                   // 条件を満たすストリーム値だけを通す
      )                                                                                                   // 現在の構造または呼び出しを終了
      .subscribe(query => this.store.dispatch(experimentsActions.globalFilterChanged(query)));            // Observableを購読して画面処理を実行
  }                                                                                                       // 現在の構造または呼び出しを終了

  selectExperimentFromUrl() {                                                                             // selectExperimentFromUrl処理を定義
    combineLatest([                                                                                       // 複数Observableの最新値を組み合わせる
      this.store.select(selectRouterParams).pipe(map(params => this.getParamId(params))),                 // コンポーネントの状態または処理参照を設定
      this.experiments$                                                                                   // コンポーネントが保持する機能を実行
    ])                                                                                                    // 現在の構造または呼び出しを終了
      .pipe(                                                                                              // Observableへ変換・制御処理を連結
        takeUntilDestroyed(),                                                                             // コンポーネント破棄時に購読を自動解除
        debounceTime(0),                                                                                  // 同一イベントループ内の連続通知をまとめる
        concatLatestFrom(() => this.store.select(selectTableMode)),                                       // 通知時点でStoreの最新値を追加取得
        map(([[experimentId, experiments], mode]) => {                                                    // map処理を定義
          this.firstExperiment = experiments?.[0];                                                        // コンポーネントの状態または処理参照を設定
          this.entities = experiments;                                                                    // コンポーネントの状態または処理参照を設定
          const experimentsIds = (this.route.snapshot.firstChild?.firstChild ?? this.route.snapshot.firstChild)?.params?.ids?.split(',').filter(id => !!id); // 後続処理で使う変更不可のローカル値を作成
          if (this.getTableModeFromURL() === 'compare' && experimentsIds?.length > 0 && this.checkedExperiments?.length === 0 && !this.previousSelectedIds) { // 条件を満たす場合だけ後続処理を実行
            this.store.dispatch(experimentsActions.getSelectedExperiments({ids: experimentsIds}));        // 画面状態を変更するActionをStoreへdispatch
          }                                                                                               // 現在の構造または呼び出しを終了
          this.previousSelectedIds = experimentsIds;                                                      // コンポーネントの状態または処理参照を設定
          if (!experimentId && this.shouldOpenDetails && this.firstExperiment && mode === 'info') {       // 条件を満たす場合だけ後続処理を実行
            this.shouldOpenDetails = false;                                                               // コンポーネントの状態または処理参照を設定
            this.store.dispatch(experimentsActions.experimentSelectionChanged({                           // 画面状態を変更するActionをStoreへdispatch
              experiment: this.firstExperiment,                                                           // experimentプロパティへ必要な値を設定
              project: this.selectedProjectId                                                             // projectプロパティへ必要な値を設定
            }));                                                                                          // Actionまたはコールバックを閉じて呼び出しを完了
          } else if (mode !== 'compare' || ![EntityTypeEnum.experiment, EntityTypeEnum.controller].includes(this.entityType)) { // 前条件に該当せず追加条件を満たす場合を処理
            this.store.dispatch(experimentsActions.setTableMode({mode: this.getTableModeFromURL()}));     // 画面状態を変更するActionをStoreへdispatch
          } else if (this.shouldOpenDetails) {                                                            // 前条件に該当せず追加条件を満たす場合を処理
            this.modeChanged(mode);                                                                       // コンポーネントが保持する機能を実行
            this.shouldOpenDetails = false;                                                               // コンポーネントの状態または処理参照を設定
          } else if (this.getTableModeFromURL() !== mode) {                                               // 前条件に該当せず追加条件を満たす場合を処理
            this.modeChanged(this.getTableModeFromURL());                                                 // コンポーネントが保持する機能を実行
          }                                                                                               // 現在の構造または呼び出しを終了
          this.shouldOpenDetails = false;                                                                 // コンポーネントの状態または処理参照を設定
          return experiments.find(experiment => experiment.id === experimentId);                          // 計算結果または処理結果を呼び出し元へ返す
        }),                                                                                               // 現在の構造または呼び出しを終了
        distinctUntilChanged()                                                                            // 同じ値の連続通知を抑制
      )                                                                                                   // 現在の構造または呼び出しを終了
      .subscribe((selectedExperiment) => {                                                                // Observableを購読して画面処理を実行
          // this.tableMode = this.getTableModeFromURL();
          this.store.dispatch(experimentsActions.setTableMode({mode: this.tableMode()}));                 // 画面状態を変更するActionをStoreへdispatch
          this.store.dispatch(experimentsActions.setSelectedExperiment({experiment: selectedExperiment})); // 画面状態を変更するActionをStoreへdispatch
        }                                                                                                 // 現在の構造または呼び出しを終了
      );                                                                                                  // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  public getTableModeFromURL() {                                                                          // getTableModeFromURLを画面の状態または設定として定義
    if (!this.route.snapshot.firstChild) {                                                                // 条件を満たす場合だけ後続処理を実行
      return 'table';                                                                                     // 子ルートがなければ一覧表示と判断
    }                                                                                                     // 現在の構造または呼び出しを終了
    return this.route.snapshot.firstChild?.url[0].path === 'compare' ? 'compare' :                        // 現在の子ルート構造から表示モードを判定
      this.route.snapshot.firstChild?.routeConfig.path === undefined ? 'table' : 'info';                  // コンポーネントの状態または処理参照を設定
  }                                                                                                       // 現在の構造または呼び出しを終了

  getNextExperiments() {                                                                                  // getNextExperiments処理を定義
    this.store.dispatch(experimentsActions.getNextExperiments());                                         // 次ページの実験一覧取得を要求
  }                                                                                                       // 現在の構造または呼び出しを終了

  experimentsSelectionChanged(experiments: ITableExperiment[]) {                                          // experimentsSelectionChanged処理を定義
    this.store.dispatch(experimentsActions.setSelectedExperiments({experiments}));                        // 画面状態を変更するActionをStoreへdispatch
    if (this.getTableModeFromURL() === 'compare') {                                                       // 条件を満たす場合だけ後続処理を実行
      this.router.navigate(['compare'], {relativeTo: this.route, queryParamsHandling: 'preserve'});       // Angular Routerで対象ビューへ遷移
    }                                                                                                     // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  experimentSelectionChanged({experiment, openInfo, origin}: {                                            // experimentSelectionChanged処理を定義
    experiment: ITableExperiment;                                                                         // experimentプロパティへ必要な値を設定
    openInfo?: boolean;                                                                                   // 強制的に詳細を開くかを任意指定
    origin: 'table' | 'row'                                                                               // originプロパティへ必要な値を設定
  }) {                                                                                                    // 分割代入するイベント型を閉じ、選択変更処理を開始
    if (experiment) {                                                                                     // 条件を満たす場合だけ後続処理を実行
      if (this.minimizedView() || openInfo) {                                                             // 条件を満たす場合だけ後続処理を実行
        this.store.dispatch(experimentsActions.experimentSelectionChanged({                               // 画面状態を変更するActionをStoreへdispatch
          experiment: experiment,                                                                         // experimentプロパティへ必要な値を設定
          project: this.selectedProjectId                                                                 // projectプロパティへ必要な値を設定
        }));                                                                                              // Actionまたはコールバックを閉じて呼び出しを完了
      } else if (origin === 'row') {                                                                      // 前条件に該当せず追加条件を満たす場合を処理
        this.selectionState().highlited.update(current => current?.id === experiment.id ? null : experiment); // コンポーネントの状態または処理参照を設定
      }                                                                                                   // 現在の構造または呼び出しを終了
    }                                                                                                     // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  sortedChanged(event: { isShift: boolean; colId: ISmCol['id'] }) {                                       // sortedChanged処理を定義
    this.store.dispatch(experimentsActions.tableSortChanged(event));                                      // 新しいソート条件をStoreへ通知
  }                                                                                                       // 現在の構造または呼び出しを終了

  filterChanged({col, value, andFilter}: { col: ISmCol; value: any; andFilter?: boolean }) {              // filterChanged処理を定義
    this.store.dispatch(experimentsActions.tableFilterChanged({                                           // 画面状態を変更するActionをStoreへdispatch
      filters: [{                                                                                         // filtersプロパティへ必要な値を設定
        col: col.id,                                                                                      // colプロパティへ必要な値を設定
        value,                                                                                            // 入力されたフィルター値を渡す
        filterMatchMode: col.filterMatchMode || andFilter ? 'AND' : undefined                             // filterMatchModeプロパティへ必要な値を設定
      }], projectId: this.projectId()                                                                     // フィルター配列と対象プロジェクトIDをまとめる
    }));                                                                                                  // Actionまたはコールバックを閉じて呼び出しを完了
  }                                                                                                       // 現在の構造または呼び出しを終了

  compareExperiments() {                                                                                  // compareExperiments処理を定義
    this.router.navigate(                                                                                 // Angular Routerで対象ビューへ遷移
      [                                                                                                   // ルーターへ渡すコマンド配列を開始
        `compare-tasks`,                                                                                  // 比較画面のルート名を指定
        {ids: this.checkedExperiments.map(experiment => experiment.id).join(',')}                         // 選択中の実験IDをカンマ区切りの行列パラメータへ変換
      ],                                                                                                  // 現在の構造または呼び出しを終了
      {relativeTo: this.route.parent.parent});                                                            // プロジェクトルートを基準に遷移
  }                                                                                                       // 現在の構造または呼び出しを終了

  afterArchiveChanged() {                                                                                 // afterArchiveChanged処理を定義
    this.store.dispatch(experimentsActions.showOnlySelected({active: false, projectId: this.projectId()})); // 画面状態を変更するActionをStoreへdispatch
  }                                                                                                       // 現在の構造または呼び出しを終了

  showAllSelected(active: boolean) {                                                                      // showAllSelected処理を定義
    this.store.dispatch(experimentsActions.showOnlySelected({active, projectId: this.projectId()}));      // 画面状態を変更するActionをStoreへdispatch
  }                                                                                                       // 現在の構造または呼び出しを終了

  selectedTableColsChanged(col: ISmCol) {                                                                 // selectedTableColsChanged処理を定義
    this.store.dispatch(experimentsActions.toggleColHidden({columnId: col.id, projectId: this.projectId()})); // 画面状態を変更するActionをStoreへdispatch
  }                                                                                                       // 現在の構造または呼び出しを終了

  toggleSelectedMetricHidden(col: ISmCol) {                                                               // toggleSelectedMetricHidden処理を定義
    this.store.dispatch(experimentsActions.toggleSelectedMetricCompare({                                  // 画面状態を変更するActionをStoreへdispatch
      columnId: col.id,                                                                                   // columnIdプロパティへ必要な値を設定
      projectId: this.projectId()                                                                         // projectIdプロパティへ必要な値を設定
    }));                                                                                                  // Actionまたはコールバックを閉じて呼び出しを完了
  }                                                                                                       // 現在の構造または呼び出しを終了

  getMetricsToDisplay() {                                                                                 // getMetricsToDisplay処理を定義
    if (this.getTableModeFromURL() !== 'compare') {                                                       // 条件を満たす場合だけ後続処理を実行
      this.store.dispatch(experimentsActions.getCustomMetrics({hideLoader: true}));                       // ローダーを出さずカスタム指標候補を取得
      this.store.dispatch(experimentsActions.getCustomHyperParams());                                     // カスタム列用のハイパーパラメータ候補を取得
    }                                                                                                     // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  selectedMetricToShow(event: SelectionEvent) {                                                           // selectedMetricToShow処理を定義
    if (!event.valueType) {                                                                               // 条件を満たす場合だけ後続処理を実行
      return;                                                                                             // この条件では後続処理を行わず終了
    }                                                                                                     // 現在の構造または呼び出しを終了
    const variantCol = createMetricColumn({                                                               // 後続処理で使う変更不可のローカル値を作成
      metricHash: event.variant.metric_hash,                                                              // metricHashプロパティへ必要な値を設定
      variantHash: event.variant.variant_hash,                                                            // variantHashプロパティへ必要な値を設定
      valueType: event.valueType,                                                                         // valueTypeプロパティへ必要な値を設定
      metric: event.variant.metric,                                                                       // metricプロパティへ必要な値を設定
      variant: event.variant.variant                                                                      // variantプロパティへ必要な値を設定
    }, this.projectId());                                                                                 // 指標情報とプロジェクトIDから列定義を完成
    if (event.addCol) {                                                                                   // 条件を満たす場合だけ後続処理を実行
      this.store.dispatch(experimentsActions.addColumn({col: variantCol}));                               // 画面状態を変更するActionをStoreへdispatch
    } else {                                                                                              // 前の条件に該当しない場合を処理
      this.store.dispatch(experimentsActions.removeCol({id: variantCol.id, projectId: variantCol.projectId})); // 画面状態を変更するActionをStoreへdispatch
    }                                                                                                     // 現在の構造または呼び出しを終了
    this.store.dispatch(experimentsActions.updateUrlParams());                                            // 現在の表設定をURLクエリへ反映
  }                                                                                                       // 現在の構造または呼び出しを終了

  compareSelectedMetricToShow(event: SelectionEvent) {                                                    // compareSelectedMetricToShow処理を定義
    const variantCol = createCompareMetricColumn(event.variant);                                          // 後続処理で使う変更不可のローカル値を作成
    if (event.addCol) {                                                                                   // 条件を満たす場合だけ後続処理を実行
      this.store.dispatch(experimentsActions.addSelectedMetric({col: variantCol, projectId: this.projectId()})); // 画面状態を変更するActionをStoreへdispatch
    } else {                                                                                              // 前の条件に該当しない場合を処理
      this.store.dispatch(experimentsActions.removeSelectedMetric({id: variantCol.id, projectId: this.projectId()})); // 画面状態を変更するActionをStoreへdispatch
    }                                                                                                     // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  createParamColumn(param: string, projectId?: string): ISmCol {                                          // createParamColumn処理を定義
    return {                                                                                              // 必要な設定値をオブジェクトとして返す
      id: param,                                                                                          // idプロパティへ必要な値を設定
      getter: encodeHyperParameter(param),                                                                // getterプロパティへ必要な値を設定
      headerType: ColHeaderTypeEnum.sortFilter,                                                           // headerTypeプロパティへ必要な値を設定
      sortable: true,                                                                                     // sortableプロパティへ必要な値を設定
      filterable: true,                                                                                   // filterableプロパティへ必要な値を設定
      header: decodeURIComponentSafe(param.replace('hyperparams.', '')),                                  // headerプロパティへ必要な値を設定
      hidden: false,                                                                                      // hiddenプロパティへ必要な値を設定
      projectId: projectId || this.projectId(),                                                           // projectIdプロパティへ必要な値を設定
      isParam: true,                                                                                      // isParamプロパティへ必要な値を設定
      style: {width: '200px'},                                                                            // styleプロパティへ必要な値を設定
      searchableFilter: true,                                                                             // searchableFilterプロパティへ必要な値を設定
      asyncFilter: true,                                                                                  // asyncFilterプロパティへ必要な値を設定
      paginatedFilterPageSize: rootProjectsPageSize                                                       // paginatedFilterPageSizeプロパティへ必要な値を設定
    };                                                                                                    // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  selectedHyperParamToShow(event: { param: string; addCol: boolean }) {                                   // selectedHyperParamToShow処理を定義
    const variantCol = this.createParamColumn(event.param);                                               // 後続処理で使う変更不可のローカル値を作成
    if (event.addCol) {                                                                                   // 条件を満たす場合だけ後続処理を実行
      this.store.dispatch(experimentsActions.addColumn({col: variantCol}));                               // 画面状態を変更するActionをStoreへdispatch
    } else {                                                                                              // 前の条件に該当しない場合を処理
      this.store.dispatch(experimentsActions.removeCol({id: variantCol.id, projectId: variantCol.projectId})); // 画面状態を変更するActionをStoreへdispatch
    }                                                                                                     // 現在の構造または呼び出しを終了
    this.store.dispatch(experimentsActions.updateUrlParams());                                            // 現在の表設定をURLクエリへ反映
  }                                                                                                       // 現在の構造または呼び出しを終了

  removeColFromList(colId: string) {                                                                      // removeColFromList処理を定義
    const sortIndex = this.sortFields.findIndex(field => field.field === colId);                          // 後続処理で使う変更不可のローカル値を作成
    if (sortIndex > -1) {                                                                                 // 条件を満たす場合だけ後続処理を実行
      this.store.dispatch(experimentsActions.resetSortOrder({sortIndex, projectId: this.projectId()}));   // 画面状態を変更するActionをStoreへdispatch
    }                                                                                                     // 現在の構造または呼び出しを終了
    this.store.dispatch(experimentsActions.removeCol({id: colId, projectId: this.projectId()}));          // 画面状態を変更するActionをStoreへdispatch
    this.store.dispatch(experimentsActions.updateUrlParams());                                            // 現在の表設定をURLクエリへ反映
  }                                                                                                       // 現在の構造または呼び出しを終了

  compareRemoveColFromList(colId: string) {                                                               // compareRemoveColFromList処理を定義
    this.store.dispatch(experimentsActions.removeSelectedMetric({id: colId, projectId: this.projectId()})); // 画面状態を変更するActionをStoreへdispatch
  }                                                                                                       // 現在の構造または呼び出しを終了

  columnResized(event: { columnId: string; widthPx: number }) {                                           // columnResized処理を定義
    this.store.dispatch(experimentsActions.setColumnWidth({                                               // 画面状態を変更するActionをStoreへdispatch
      ...event,                                                                                           // 条件成立時だけ追加プロパティを展開
      projectId: this.projectId()                                                                         // projectIdプロパティへ必要な値を設定
    }));                                                                                                  // Actionまたはコールバックを閉じて呼び出しを完了
  }                                                                                                       // 現在の構造または呼び出しを終了

  refreshList(isAutoRefresh: boolean) {                                                                   // refreshList処理を定義
    this.store.dispatch(experimentsActions.refreshExperiments({                                           // 画面状態を変更するActionをStoreへdispatch
      hideLoader: isAutoRefresh,                                                                          // hideLoaderプロパティへ必要な値を設定
      autoRefresh: isAutoRefresh                                                                          // autoRefreshプロパティへ必要な値を設定
    }));                                                                                                  // Actionまたはコールバックを閉じて呼び出しを完了
  }                                                                                                       // 現在の構造または呼び出しを終了

  setAutoRefresh($event: boolean) {                                                                       // setAutoRefresh処理を定義
    this.store.dispatch(setAutoRefresh({autoRefresh: $event}));                                           // 画面状態を変更するActionをStoreへdispatch
  }                                                                                                       // 現在の構造または呼び出しを終了

  clearSelection() {                                                                                      // clearSelection処理を定義
    this.store.dispatch(experimentsActions.clearHyperParamsCols({projectId: this.projectId()}));          // 画面状態を変更するActionをStoreへdispatch
  }                                                                                                       // 現在の構造または呼び出しを終了

  columnsReordered(cols: string[], updateUrl = true) {                                                    // columnsReordered処理を定義
    this.store.dispatch(experimentsActions.setColsOrderForProject({                                       // 画面状態を変更するActionをStoreへdispatch
      cols: Array.from(new Set([...cols, 'project.name'])),                                               // colsプロパティへ必要な値を設定
      projectId: this.projectId()                                                                         // projectIdプロパティへ必要な値を設定
    }));                                                                                                  // Actionまたはコールバックを閉じて呼び出しを完了
    if (updateUrl) {                                                                                      // 条件を満たす場合だけ後続処理を実行
      this.store.dispatch(experimentsActions.updateUrlParams());                                          // 現在の表設定をURLクエリへ反映
    }                                                                                                     // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  refreshTagsList() {                                                                                     // refreshTagsList処理を定義
    this.store.dispatch(experimentsActions.getTags({}));                                                  // 利用可能なタグ一覧を再取得
  }                                                                                                       // 現在の構造または呼び出しを終了

  refreshTypesList() {                                                                                    // refreshTypesList処理を定義
    this.store.dispatch(experimentsActions.getProjectTypes({}));                                          // プロジェクト内の実験種別を再取得
  }                                                                                                       // 現在の構造または呼び出しを終了

  protected getParamId(params) {                                                                          // getParamIdを画面の状態または設定として定義
    return params?.experimentId;                                                                          // ルートパラメータから実験IDを安全に取得
  }                                                                                                       // 現在の構造または呼び出しを終了

  clearTableFiltersHandler(tableFilters: Record<string, FilterMetadata>, others?: Record<string, string>) { // clearTableFiltersHandler処理を定義
    const filters = Object.keys(tableFilters).map(col => ({col, value: []}));                             // 後続処理で使う変更不可のローカル値を作成
    this.store.dispatch(experimentsActions.setTableFilters({filters: [], projectId: this.selectedProjectId})); // 画面状態を変更するActionをStoreへdispatch
    this.store.dispatch(experimentsActions.tableFilterChanged({filters, projectId: this.selectedProjectId, // 画面状態を変更するActionをStoreへdispatch
      others: others || {}                                                                                // othersプロパティへ必要な値を設定
    }));                                                                                                  // Actionまたはコールバックを閉じて呼び出しを完了
  }                                                                                                       // 現在の構造または呼び出しを終了

  clearTableFiltersAndSearchHandler(tableFilters: Record<string, FilterMetadata>) {                       // clearTableFiltersAndSearchHandler処理を定義
    this.clearTableFiltersHandler(tableFilters, {                                                         // コンポーネントが保持する機能を実行
      q: null,                                                                                            // qプロパティへ必要な値を設定
    });                                                                                                   // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  onContextMenuOpen({x, y, single, backdrop}: { x: number; y: number; single?: boolean; backdrop?: boolean }) { // onContextMenuOpen処理を定義
    this.singleRowContext = single;                                                                       // コンポーネントの状態または処理参照を設定
    this.menuBackdrop = !!backdrop;                                                                       // 任意値を真偽値へ正規化して背景表示へ反映
    this.contextMenu().openMenu({x, y});                                                                  // 指定座標でコンテキストメニューを開く
  }                                                                                                       // 現在の構造または呼び出しを終了

  getSingleSelectedDisableAvailable(experiment): Record<string, CountAvailableAndIsDisableSelectedFiltered> { // getSingleSelectedDisableAvailable処理を定義
    return {                                                                                              // 必要な設定値をオブジェクトとして返す
      [MenuItems.abort]: selectionDisabledAbort([experiment]),                                            // メニュー項目ごとの活性・非活性判定を設定
      [MenuItems.abortAllChildren]: selectionDisabledAbortAllChildren([experiment]),                      // メニュー項目ごとの活性・非活性判定を設定
      [MenuItems.publish]: selectionDisabledPublishExperiments([experiment]),                             // メニュー項目ごとの活性・非活性判定を設定
      [MenuItems.reset]: selectionDisabledReset([experiment]),                                            // メニュー項目ごとの活性・非活性判定を設定
      [MenuItems.delete]: selectionDisabledDelete([experiment]),                                          // メニュー項目ごとの活性・非活性判定を設定
      [MenuItems.moveTo]: selectionDisabledMoveTo([experiment]),                                          // メニュー項目ごとの活性・非活性判定を設定
      [MenuItems.enqueue]: selectionDisabledEnqueue([experiment]),                                        // メニュー項目ごとの活性・非活性判定を設定
      [MenuItems.retry]: selectionDisabledRetry([experiment]),                                            // メニュー項目ごとの活性・非活性判定を設定
      [MenuItems.dequeue]: selectionDisabledDequeue([experiment]),                                        // メニュー項目ごとの活性・非活性判定を設定
      [MenuItems.queue]: selectionDisabledQueue([experiment]),                                            // メニュー項目ごとの活性・非活性判定を設定
      [MenuItems.viewWorker]: selectionDisabledViewWorker([experiment]),                                  // メニュー項目ごとの活性・非活性判定を設定
      [MenuItems.archive]: selectionDisabledArchive([experiment]),                                        // メニュー項目ごとの活性・非活性判定を設定
      [MenuItems.run]: selectionDisabledPipelineRun([experiment])                                         // メニュー項目ごとの活性・非活性判定を設定
    };                                                                                                    // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  modeChanged(mode: 'info' | 'table' | 'compare') {                                                       // modeChanged処理を定義
    if (this.tableMode() !== mode) {                                                                      // 条件を満たす場合だけ後続処理を実行
      this.store.dispatch(experimentsActions.setTableMode({mode}));                                       // 画面状態を変更するActionをStoreへdispatch
    }                                                                                                     // 現在の構造または呼び出しを終了
    setTimeout(() => this.createFooterItemsRunner(), 100);                                                // 現在の同期処理後に実行するよう遅延予約
    if (mode === 'info') {                                                                                // 条件を満たす場合だけ後続処理を実行
      this.store.dispatch(experimentsActions.experimentSelectionChanged({                                 // 画面状態を変更するActionをStoreへdispatch
        experiment: this.selectionState().highlited() || this.checkedExperiments?.[0] || this.firstExperiment, // experimentプロパティへ必要な値を設定
        project: this.selectedProjectId                                                                   // projectプロパティへ必要な値を設定
      }));                                                                                                // Actionまたはコールバックを閉じて呼び出しを完了
      return Promise.resolve();                                                                           // 情報表示への切替完了を即時Promiseで返す
    } else if (mode === 'compare') {                                                                      // 前条件に該当せず追加条件を満たす場合を処理
      setTimeout(() => {                                                                                  // setTimeout処理を定義
        const experimentsIds = (this.route.snapshot.firstChild?.firstChild ?? this.route.snapshot.firstChild)?.params?.ids?.split(',').filter(id => !!id); // 後続処理で使う変更不可のローカル値を作成
        this.store.dispatch(experimentsActions.getSelectedExperiments({ids: experimentsIds}));            // 画面状態を変更するActionをStoreへdispatch
      })                                                                                                  // コールバックまたは設定オブジェクトを閉じる
      return this.compareView();                                                                          // 比較ビューを開く共通処理へ委譲
    } else {                                                                                              // 前の条件に該当しない場合を処理
      return this.closePanel();                                                                           // 一覧モードでは詳細パネルを閉じる
    }                                                                                                     // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  newExperiment() {                                                                                       // newExperiment処理を定義
    this.dialog.open(CreateExperimentDialogComponent, {                                                   // 新規実験作成ダイアログを開く
      width: '800px',                                                                                     // widthプロパティへ必要な値を設定
      disableClose: true                                                                                  // disableCloseプロパティへ必要な値を設定
    }).afterClosed()                                                                                      // ダイアログを開き、閉じた後の結果へ処理を連結
      .pipe(filter(res => !!res))                                                                         // Observableへ変換・制御処理を連結
      .subscribe(data => this.store.dispatch(experimentsActions.createExperiment({data})));               // Observableを購読して画面処理を実行
  }                                                                                                       // 現在の構造または呼び出しを終了

  downloadTableAsCSV() {                                                                                  // downloadTableAsCSV処理を定義
    this.table().table().downloadTableAsCSV(`ClearML ${this.selectedProject().id === '*' ? 'All' : this.selectedProject()?.basename?.substring(0, 60)} Experiments`); // コンポーネントの状態または処理参照を設定
  }                                                                                                       // 現在の構造または呼び出しを終了

  downloadFullTableAsCSV() {                                                                              // downloadFullTableAsCSV処理を定義
    this.store.dispatch(experimentsActions.prepareTableForDownload({entityType: 'task'}));                // 画面状態を変更するActionをStoreへdispatch
  }                                                                                                       // 現在の構造または呼び出しを終了

  override setupBreadcrumbsOptions() {                                                                    // setupBreadcrumbsOptionsを画面の状態または設定として定義
    effect(() => {                                                                                        // effect処理を定義
      const selectedProject = this.selectedProject();                                                     // 後続処理で使う変更不可のローカル値を作成
      if (selectedProject) {                                                                              // 条件を満たす場合だけ後続処理を実行
        this.store.dispatch(setBreadcrumbsOptions({                                                       // 画面状態を変更するActionをStoreへdispatch
          breadcrumbOptions: {                                                                            // breadcrumbOptionsプロパティへ必要な値を設定
            showProjects: !!selectedProject,                                                              // showProjectsプロパティへ必要な値を設定
            featureBreadcrumb: {                                                                          // featureBreadcrumbプロパティへ必要な値を設定
              name: 'PROJECTS',                                                                           // nameプロパティへ必要な値を設定
              url: 'projects'                                                                             // urlプロパティへ必要な値を設定
            },                                                                                            // 現在の構造または呼び出しを終了
            ...(this.projectDeepMode() && selectedProject?.id !== '*' && {                                // 条件成立時だけ追加プロパティを展開
              subFeatureBreadcrumb: {                                                                     // subFeatureBreadcrumbプロパティへ必要な値を設定
                name: 'All Tasks'                                                                         // nameプロパティへ必要な値を設定
              }                                                                                           // 現在の構造または呼び出しを終了
            }),                                                                                           // 現在の構造または呼び出しを終了
            projectsOptions: {                                                                            // projectsOptionsプロパティへ必要な値を設定
              basePath: 'projects',                                                                       // basePathプロパティへ必要な値を設定
              filterBaseNameWith: null,                                                                   // filterBaseNameWithプロパティへ必要な値を設定
              compareModule: null,                                                                        // compareModuleプロパティへ必要な値を設定
              showSelectedProject: selectedProject?.id !== '*',                                           // showSelectedProjectプロパティへ必要な値を設定
              ...(selectedProject && {                                                                    // 条件成立時だけ追加プロパティを展開
                selectedProjectBreadcrumb: {                                                              // selectedProjectBreadcrumbプロパティへ必要な値を設定
                  name: selectedProject?.id === '*' ? 'All Tasks' : selectedProject?.basename,            // nameプロパティへ必要な値を設定
                  url: `projects/${selectedProject?.id}/projects`                                         // urlプロパティへ必要な値を設定
                }                                                                                         // 現在の構造または呼び出しを終了
              })                                                                                          // コールバックまたは設定オブジェクトを閉じる
            }                                                                                             // 現在の構造または呼び出しを終了
          }                                                                                               // 現在の構造または呼び出しを終了
        }));                                                                                              // Actionまたはコールバックを閉じて呼び出しを完了
      }                                                                                                   // 現在の構造または呼び出しを終了
    });                                                                                                   // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了

  showCompareSettingsChanged() {                                                                          // showCompareSettingsChanged処理を定義
    this.store.dispatch(experimentsActions.toggleCompareScalarSettings());                                // スカラー比較設定パネルの開閉状態を反転
  }                                                                                                       // 現在の構造または呼び出しを終了

  compareViewChanged(compareView: 'scalars' | 'plots') {                                                  // compareViewChanged処理を定義
    this.store.dispatch(experimentsActions.setCompareView({mode: compareView}));                          // 画面状態を変更するActionをStoreへdispatch
    return this.router.navigate(['compare'], {relativeTo: this.route, queryParamsHandling: 'preserve'});  // 計算結果または処理結果を呼び出し元へ返す
  }                                                                                                       // 現在の構造または呼び出しを終了

  override filterSearchChanged({colId, value}: { colId: string; value: { value: string; loadMore?: boolean } }) { // filterSearchChangedの真偽状態を保持
    super.filterSearchChanged({colId, value});                                                            // まず基底クラスの候補検索処理を実行
    if (colId === 'parent.name') {                                                                        // 条件を満たす場合だけ後続処理を実行
      // No pagination in BE - setting same list will set noMoreOptions to true
      if (value.loadMore) {                                                                               // 条件を満たす場合だけ後続処理を実行
        this.store.dispatch(experimentsActions.setParents({parents: [...this.parents]}));                 // 画面状態を変更するActionをStoreへdispatch
      } else {                                                                                            // 前の条件に該当しない場合を処理
        this.store.dispatch(experimentsActions.resetTablesFilterParentsOptions());                        // 画面状態を変更するActionをStoreへdispatch
        this.store.dispatch(experimentsActions.getParents({searchValue: value.value}));                   // 画面状態を変更するActionをStoreへdispatch
      }                                                                                                   // 現在の構造または呼び出しを終了
    } else if (colId.startsWith('hyperparams.')) {                                                        // 前条件に該当せず追加条件を満たす場合を処理
      if (!value.loadMore) {                                                                              // 条件を満たす場合だけ後続処理を実行
        this.store.dispatch(experimentsActions.hyperParamSelectedInfoExperiments({                        // 画面状態を変更するActionをStoreへdispatch
          col: {id: colId},                                                                               // colプロパティへ必要な値を設定
          loadMore: false,                                                                                // loadMoreプロパティへ必要な値を設定
          values: null                                                                                    // valuesプロパティへ必要な値を設定
        }));                                                                                              // Actionまたはコールバックを閉じて呼び出しを完了
        this.store.dispatch(experimentsActions.setHyperParamsFiltersPage({page: 0}));                     // 画面状態を変更するActionをStoreへdispatch
      }                                                                                                   // 現在の構造または呼び出しを終了
      this.store.dispatch(experimentsActions.hyperParamSelectedExperiments({                              // 画面状態を変更するActionをStoreへdispatch
        col: {id: colId, getter: `${colId}.value`},                                                       // colプロパティへ必要な値を設定
        searchValue: value.value                                                                          // searchValueプロパティへ必要な値を設定
      }));                                                                                                // Actionまたはコールバックを閉じて呼び出しを完了
    }                                                                                                     // 現在の構造または呼び出しを終了
  }                                                                                                       // 現在の構造または呼び出しを終了
}                                                                                                         // 現在の構造または呼び出しを終了
````

# ExperimentsComponent 解説

## このコンポーネントの役割

ExperimentsComponent は、ClearML の実験（Task）一覧画面を統括するコンテナコンポーネントです。表の描画は子コンポーネントへ任せ、このクラスでは NgRx Store、URL、選択状態、詳細・比較ビュー、検索、列設定、フッターメニューを相互に同期します。

## [■観点:Storeを画面状態の基準にする]

store.select は継続的な値を扱う Observable、store.selectSignal はテンプレートや computed から同期的に読む Signal として使い分けています。ユーザー操作では値を直接書き換えず、Action を dispatch し、Reducer・Effect を経由して状態を更新する構造です。

## [■観点:SignalとRxJSの役割分担]

tableMode や selectedTableExperiment のように現在値を基準に表示を計算する状態には Signal を使い、ルーター・検索・一覧データなど時間とともに届くイベント列には RxJS を使っています。takeUntilDestroyed により、破棄後に購読が残ることも防ぎます。

## [■観点:URLを復元可能な画面状態として扱う]

列、並び順、フィルター、アーカイブ表示、選択中の実験、表示モードをURLから復元します。逆に列を追加・削除・並べ替えた際は updateUrlParams を dispatch します。再読み込みやURL共有でも同じ表を再現するための双方向同期です。

## [■観点:一覧・詳細・比較のモード管理]

getTableModeFromURL がルート構造を table・info・compare に変換し、modeChanged がStoreと実画面を切り替えます。比較モードではURL内の複数IDを読み直し、情報モードではハイライト中、チェック中、一覧先頭の順で表示対象を決めます。

## [■観点:選択状態を二種類に分ける]

checkedExperiments は一括操作や比較に使う複数選択です。一方、selectionState().highlited は一覧上で一時的に注目している1行です。複数選択を壊さず、行クリックによる詳細候補を切り替えられます。

## [■観点:フッター操作をオブジェクトへ分離する]

createFooterItems はアーカイブ、削除、キュー投入、停止、タグ付けなどを専用の FooterItem クラスとして構成します。表示・活性判定を各項目へ寄せ、選ばれた操作だけを onFooterHandler からコンテキストメニューへ橋渡しします。

## [■観点:動的なメトリクス・ハイパーパラメータ列]

selectedMetricToShow と selectedHyperParamToShow は、利用者が選んだ値から列定義を生成します。createParamColumn では getter、ソート、フィルター、幅、非同期候補取得など、通常列と同じ機能を動的列にも与えます。

## [■観点:破棄時の後始末]

ngOnDestroy では基底クラスの終了処理に加え、実験一覧、選択実験、共通検索、グローバルフィルターをリセットします。別画面へ移動した後に、この画面固有の状態や検索語を残さないためです。

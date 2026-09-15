````ts
import {                                                                                                         // @angular/core から使うAPIをまとめて取り込む
  ChangeDetectionStrategy,                                                                                       // 変更検知戦略を指定するenum
  Component,                                                                                                     // コンポーネント定義デコレータ
  computed,                                                                                                      // 他のSignalから値を導出する読み取り専用Signal
  effect,                                                                                                        // Signalの変化に反応して副作用を実行する
  EventEmitter,                                                                                                  // 旧API @Output 用の発火器。171行のremoveTagだけが使用
  inject,                                                                                                        // DIコンテナから依存を取得
  input,                                                                                                         // Signalベースの入力プロパティ
  output,                                                                                                        // Signalベースの出力（新API）
  Output,                                                                                                        // 旧デコレータ版の出力。EventEmitterとセットで使う
  signal,                                                                                                        // 書き込み可能なSignal
  TemplateRef                                                                                                    // テンプレート片を入力として受け取るための型
} from '@angular/core';
import {TIME_FORMAT_STRING} from '@common/constants';                                                            // 日時列の表示フォーマット文字列
import {ColHeaderTypeEnum, ISmCol} from '@common/shared/ui-components/data/table/table.consts';                  // 列ヘッダ種別のenumと、列定義の型。この表の列はすべてISmCol
import {get, uniq} from 'lodash-es';                                                                             // lodash。get=ドット区切りパスで深い値を取得、uniq=重複排除
import {FilterMetadata, PrimeTemplate} from 'primeng/api';                                                       // PrimeNG。FilterMetadataは列フィルタ1件分の値とマッチモード
import {ITableExperiment} from '../../shared/common-experiment-model.model';                                     // 一覧の1行として扱う実験データの型
import {EXPERIMENTS_TABLE_COL_FIELDS} from '@features/experiments/shared/experiments.const';                     // 列IDの定数群（'status' 'tags' 'parent.name' など）
import {BaseTableView} from '@common/shared/ui-components/data/table/base-table-view';                           // 一覧表コンポーネント共通の基底クラス（@Directive）
import {getSystemTags, isDevelopment} from '@features/experiments/shared/experiments.utils';                     // システムタグ抽出と開発実行判定。テンプレートから直接呼ぶ
import {User} from '~/business-logic/model/users/user';                                                          // ユーザーフィルタの候補に使うユーザー型
import {sortByArr} from '@common/shared/pipes/show-selected-first.pipe';                                         // 指定配列の並び順を優先して比較するソート用関数
import {NoUnderscorePipe} from '@common/shared/pipes/no-underscore.pipe';                                        // アンダースコアを空白へ変換するPipe。ここではnewして直接使う
import {DatePipe, NgTemplateOutlet, TitleCasePipe} from '@angular/common';                                       // 標準のPipeとNgTemplateOutlet
import {INITIAL_EXPERIMENT_TABLE_COLS} from '../../experiment.consts';                                           // 既定の列定義一覧
import {                                                                                                         // ~/business-logic/model から親タスク候補の型を取り込む
  ProjectsGetTaskParentsResponseParents                                                                          // 親タスク候補1件の型。parents / activeParentsFilter の要素
} from '~/business-logic/model/projects/projectsGetTaskParentsResponseParents';
import {Router} from '@angular/router';                                                                          // 親タスクへ画面遷移するために使う
import {                                                                                                         // オートコンプリート選択肢の型を取り込む
  IOption                                                                                                        // フィルタ候補1件（label / value / tooltip）の型
} from '@common/shared/ui-components/inputs/select-autocomplete-for-template-forms/select-autocomplete-for-template-forms.component';
import {CountAvailableAndIsDisableSelectedFiltered} from '@common/shared/entity-page/items.utils';               // 選択行に対する各操作の可否と件数をまとめた型
import {                                                                                                         // 実験一覧ビューのAction群を取り込む
  hyperParamSelectedExperiments,                                                                                 // ハイパーパラメータ列のフィルタ候補を取得するAction
  hyperParamSelectedInfoExperiments,                                                                             // 取得済み候補の初期化・追記を行うAction
  selectAllExperiments,                                                                                          // 全件（またはフィルタ結果全件）を選択するAction
  setHyperParamsFiltersPage                                                                                      // 候補取得のページング位置をリセットするAction
} from '../../actions/common-experiments-view.actions';
import {createFiltersFromStore, excludedKey, uniqueFilterValueAndExcluded} from '@common/shared/utils/tableParamEncode'; // 除外指定 '__$not' を含むフィルタ値を扱うユーティリティ群
import {getRoundedNumber} from '../../shared/common-experiments.utils';                                          // メトリクス値を既定桁数で丸める
import {EntityTypeEnum} from '~/shared/constants/non-common-consts';                                             // 実験・データセットなど、画面が扱う対象種別
import {MAT_TOOLTIP_DEFAULT_OPTIONS, MatTooltipDefaultOptions} from '@angular/material/tooltip';                 // matTooltipの既定値をDIで差し替えるためのトークンと型
import {IExperimentInfo, ISelectedExperiment} from '@features/experiments/shared/experiment-info.model';         // 詳細表示用と選択中の実験を表す型
import {computedPrevious} from 'ngxtension/computed-previous';                                                   // ngxtension。Signalの「1つ前の値」を返すSignalを作る
import {FILTERED_EXPERIMENTS_STATUS_OPTIONS} from '@features/experiments/experiments.consts';                    // ステータスフィルタの選択肢生成関数。データセットでは文言が変わる
import {TooltipDirective} from '@common/shared/ui-components/indicators/tooltip/tooltip.directive';              // 自前のツールチップディレクティブ
import {TableCardComponent} from '@common/shared/ui-components/data/table-card/table-card.component';            // カード表示（表ではなくカード並び）用のコンポーネント
import {TableComponent} from '@common/shared/ui-components/data/table/table.component';                          // PrimeNGのテーブルをラップした共通表コンポーネント
import {                                                                                                         // 列ヘッダのソート＋フィルタUIを取り込む
  TableFilterSortComponent                                                                                       // 列ヘッダに出すソートとフィルタのUI
} from '@common/shared/ui-components/data/table/table-filter-sort/table-filter-sort.component';
import {                                                                                                         // 省略表示の時だけツールチップを出すディレクティブを取り込む
  ShowTooltipIfEllipsisDirective                                                                                 // テキストが省略記号になっている時だけツールチップ表示
} from '@common/shared/ui-components/indicators/tooltip/show-tooltip-if-ellipsis.directive';
import {TagListComponent} from '@common/shared/ui-components/tags/tag-list/tag-list.component';                  // ユーザータグの一覧表示
import {StatusIconLabelComponent} from '@common/shared/experiment-status-icon-label/status-icon-label.component'; // 実験ステータスのアイコン＋ラベル
import {                                                                                                         // カード表示用のフィルタテンプレートを取り込む
  TableCardFilterComponent                                                                                       // カード表示時に使うフィルタUI
} from '@common/shared/ui-components/data/table/table-card-filter-template/table-card-filter.component';
import {                                                                                                         // 省スペースなタグ表示を取り込む
  MiniTagsListComponent                                                                                          // 行内に小さくタグを並べる表示
} from '@common/shared/ui-components/tags/user-tag/mini-tags-list/mini-tags-list.component';
import {                                                                                                         // 実験種別の表示部品を取り込む
  ExperimentTypeIconLabelComponent                                                                               // 実験タイプのアイコン＋ラベル
} from '@common/shared/experiment-type-icon-label/experiment-type-icon-label.component';
import {MatCheckbox} from '@angular/material/checkbox';                                                          // 行とヘッダの選択チェックボックス
import {MatMenu, MatMenuItem, MatMenuTrigger} from '@angular/material/menu';                                     // 列ヘッダなどで開くメニュー
import {                                                                                                         // 動的列のセル部品を取り込む
  HyperParamMetricColumnComponent                                                                                // hyperparams. / last_metrics. といった動的列のセル表示
} from '@common/experiments/shared/components/hyper-param-metric-column/hyper-param-metric-column.component';
import {ClickStopPropagationDirective} from '@common/shared/ui-components/directives/click-stop-propagation.directive'; // 子要素のクリックを行クリックへ伝播させない
import {ReactiveFormsModule} from '@angular/forms';                                                              // 基底の selectionChecked（FormControl）をテンプレートで使うため
import {IsRowSelectedPipe} from '@common/shared/ui-components/data/table/is-rwo-selected.pipe';                  // 行が選択済みかを判定するPipe
import {ReplaceViaMapPipe} from '@common/shared/pipes/replaceViaMap';                                            // 値をマップで置換するPipe（ステータス表記の変換など）
import {DurationPipe} from '@common/shared/pipes/duration.pipe';                                                 // 実行時間の整形
import {TimeAgoPipe} from '@common/shared/pipes/timeAgo';                                                        // 「〜前」表記への整形
import {FilterPipe} from '@common/shared/pipes/filter.pipe';                                                     // 候補一覧をlabelで絞り込む（テンプレート91行で使用）

@Component({                                                                                                     // コンポーネントのメタデータ定義
  selector: 'sm-experiments-table',                                                                              // テンプレート上での要素名
  templateUrl: './experiments-table.component.html',                                                             // テンプレートは別ファイル。インライン化しない方針
  styleUrls: ['./experiments-table.component.scss'],                                                             // スタイルも別ファイル
  changeDetection: ChangeDetectionStrategy.OnPush,                                                               // 入力Signalやイベントが変わった時だけ再描画。行数の多い表では必須
  providers: [{                                                                                                  // このコンポーネント配下だけDIを差し替える
    provide: MAT_TOOLTIP_DEFAULT_OPTIONS,                                                                        // 差し替え対象はmatTooltipの既定オプション
    useValue: {showDelay: 500, position: 'above'} as MatTooltipDefaultOptions,                                   // 表示遅延500ms・上寄せに統一。表のセルが密なので即時表示を避ける
  }],
  imports: [                                                                                                     // standaloneコンポーネントがテンプレートで使う部品の宣言
    TooltipDirective,                                                                                            // smTooltip
    NgTemplateOutlet,                                                                                            // contextMenuTemplate / noDataTemplate の差し込み
    TableCardComponent,                                                                                          // カード表示
    TableComponent,                                                                                              // 表本体
    TableFilterSortComponent,                                                                                    // 列ヘッダのソートとフィルタ
    ShowTooltipIfEllipsisDirective,                                                                              // 省略時のみツールチップ
    PrimeTemplate,                                                                                               // pTemplate属性でテンプレート名を指定するため
    TagListComponent,                                                                                            // タグ列
    StatusIconLabelComponent,                                                                                    // ステータス列
    MiniTagsListComponent,                                                                                       // カード内の小さいタグ
    ExperimentTypeIconLabelComponent,                                                                            // タイプ列
    MatCheckbox,                                                                                                 // 選択列のチェックボックス
    MatMenuItem,                                                                                                 // メニュー項目
    HyperParamMetricColumnComponent,                                                                             // 動的列のセル
    TableCardFilterComponent,                                                                                    // カード表示のフィルタ
    ClickStopPropagationDirective,                                                                               // 行クリックへの伝播停止
    ReactiveFormsModule,                                                                                         // [formControl] を使うため
    MatMenuTrigger,                                                                                              // メニューを開くトリガ
    MatMenu,                                                                                                     // メニュー本体
    DatePipe,                                                                                                    // 日付整形
    IsRowSelectedPipe,                                                                                           // 選択判定
    ReplaceViaMapPipe,                                                                                           // 表記置換
    DurationPipe,                                                                                                // 実行時間
    TimeAgoPipe,                                                                                                 // 相対時刻
    FilterPipe                                                                                                   // 候補の絞り込み
  ]
})
export class ExperimentsTableComponent extends BaseTableView {                                                   // BaseTableViewを継承。範囲選択やソート、フィルタ開閉の共通処理は基底側にある
  override entitiesKey = 'experiments';                                                                          // 基底が this['experiments']() で一覧を読むためのキー名
  override selectedEntitiesKey = 'checkedExperiments';                                                           // 同じく選択済み一覧のキー名。文字列でプロパティを引くため型チェックは効かない
  readonly getSystemTags = getSystemTags;                                                                        // テンプレートから呼べるよう、関数をプロパティとして公開
  initialColumns = input(INITIAL_EXPERIMENT_TABLE_COLS);                                                         // 既定の列定義。親から差し替え可能
  contextMenuTemplate = input<TemplateRef<{                                                                      // 右クリックメニューの中身を親からTemplateRefで受け取る
    $implicit: IExperimentInfo;                                                                                  // テンプレートへ渡す暗黙引数の型（対象の実験）
  }>>(null);
  tableCols = input<ISmCol[]>();                                                                                 // 表示する列定義の配列
  experiments = input<ITableExperiment[]>();                                                                     // 表示する実験一覧
  selectedExperimentsDisableAvailable = input<Record<string, CountAvailableAndIsDisableSelectedFiltered>>();     // 選択行に対する操作可否。フッターやメニューの活性制御に使う
  users = input<User[]>();                                                                                       // ユーザーフィルタの候補
  hyperParamsOptions = input<Record<ISmCol['id'], string[]>>();                                                  // ハイパーパラメータ列ごとのフィルタ候補。nullは未取得
  activeParentsFilter = input<ProjectsGetTaskParentsResponseParents[]>();                                        // 現在フィルタに入っている親。候補一覧から欠けないよう別途受け取る
  parents = input<ProjectsGetTaskParentsResponseParents[]>();                                                    // 親タスクの候補一覧
  checkedExperiments = input<ITableExperiment[]>();                                                              // チェックボックスで選択中の実験
  selectedExperiment = input<IExperimentInfo>();                                                                 // 詳細表示中（ハイライト中）の実験
  noMoreExperiments = input<boolean>();                                                                          // これ以上読み込む実験が無いか
  tags = input<string[]>();                                                                                      // タグフィルタの候補
  experimentTypes = input<string[]>();                                                                           // タイプフィルタの候補
  projects = input<ProjectsGetTaskParentsResponseParents[]>();                                                   // プロジェクトフィルタの候補
  cardHeight = input(90);                                                                                        // カード表示時の1枚の高さ(px)
  showColors = input(false);                                                                                     // 実験ごとの色分け表示を行うか
  reorderableColumns = input(true);                                                                              // 列のドラッグ並べ替えを許すか
  resizableColumns = input(true);                                                                                // 列幅の変更を許すか
  selectionReachedLimit = input<boolean>();                                                                      // 選択件数が上限に達しているか
  tableFilters = input<Record<string, FilterMetadata>>({});                                                      // 列フィルタの現在値。URL由来のStore状態がそのまま渡る
  searchQuery = input<string>();                                                                                 // 検索ボックスの入力値
  enableMultiSelect = input(true);                                                                               // 複数選択の可否。falseなら先頭のチェック列を隠す（296行）

  experimentSelectionChanged = output<{                                                                          // 1件が選択された時の通知
    experiment: ITableExperiment;                                                                                // 対象の実験
    openInfo?: boolean;                                                                                          // 詳細パネルまで開くか
    origin: 'table' | 'row';                                                                                     // 発生源。'table'=表側の操作、'row'=行クリック
  }>();
  experimentsSelectionChanged = output<ITableExperiment[]>();                                                    // 複数選択が変わった時の通知
  loadMoreExperiments = output();                                                                                // 追加読み込みの要求
  sortedChanged = output<{                                                                                       // 並び替えの要求
    isShift: boolean;                                                                                            // Shift併用なら多段ソート
    colId: ISmCol['id'];                                                                                         // 対象の列ID
  }>();
  tagsMenuOpened = output();                                                                                     // タグ候補が未取得の時に親へ取得を依頼
  typesMenuOpened = output();                                                                                    // タイプ候補の取得依頼
  columnResized = output<{                                                                                       // 列幅が確定した時の通知
    columnId: string;                                                                                            // 対象の列ID
    widthPx: number;                                                                                             // 確定した幅(px)
  }>();
  contextMenu = output<{                                                                                         // コンテキストメニューの表示要求
    x: number;                                                                                                   // 表示位置X（clientX）
    y: number;                                                                                                   // 表示位置Y（clientY）
    single?: boolean;                                                                                            // 単一行専用のメニューか
    backdrop?: boolean;                                                                                          // 背景クリックで閉じる形で開くか
  }>();
  @Output() removeTag = new EventEmitter<{                                                                       // タグ削除。ここだけ旧API。新しいoutput()へ統一する余地がある
    experiment: ITableExperiment;                                                                                // 対象の実験
    tag: string;                                                                                                 // 外すタグ名
  }>();
  clearTableFilters = output<Record<string, FilterMetadata>>();                                                  // フィルタだけをまとめて消す
  clearTableFiltersAndSearch = output<Record<string, FilterMetadata>>();                                         // フィルタと検索語を同時に消す（0件表示のリンクから）
  protected readonly experimentsTableColFields = EXPERIMENTS_TABLE_COL_FIELDS;                                   // 列ID定数をテンプレートから参照できるよう公開
  protected readonly timeFormatString = TIME_FORMAT_STRING;                                                      // 日付列のフォーマットをテンプレートへ公開
  protected isDevelopment = isDevelopment;                                                                       // 開発実行かの判定関数をテンプレートへ公開
  protected readonly colHeaderTypeEnum = ColHeaderTypeEnum;                                                      // ヘッダ種別enumをテンプレートへ公開
  protected hasActiveFilters = computed(() =>                                                                    // フィルタか検索が効いているか
    Object.keys(this.tableFilters() ?? {}).length > 0 || (this.searchQuery() && this.searchQuery().trim().length > 0) // フィルタが1件以上、または検索語が空白以外なら true
  );
  protected experimentsUpdated = false;                                                                          // 一度でも実験一覧が流れてきたか。初回ロード中に「No data」を出さないためのフラグ
  protected roundedMetricValues = computed<Record<string, Record<string, boolean>>>(() => {                      // メトリクス列ごと・実験ごとに「丸め表示になっているか」を先に計算
    const roundedMetricValues = {};                                                                              // 結果を貯める入れ物
    this.tableCols()                                                                                             // 現在の列定義から
      ?.filter(tableCol => tableCol.id.startsWith('last_metrics'))                                               // メトリクス列（last_metrics.〜）だけを対象にする
      .forEach(col => this.experiments()?.forEach(exp => {                                                       // 列×行の総当たりで走査
          const value = get(exp, col.id);                                                                        // 'last_metrics.<hash>.<hash>.value' のような深いパスを取り出す
          roundedMetricValues[col.id] = roundedMetricValues[col.id] || {};                                       // 列単位のマップを初めて触る時だけ用意
          roundedMetricValues[col.id][exp.id] = value && getRoundedNumber(value) !== value;                      // 丸めると値が変わる＝表示は近似値。元の値をツールチップで出すかの判定に使う
        })
      );
    return roundedMetricValues;                                                                                  // 列ID→実験ID→真偽 の二段マップを返す
  });
  protected contextExperiment = signal<IExperimentInfo | ISelectedExperiment>(null);                             // 右クリックの対象。contextMenuTemplateへcontextとして渡す
  protected filtersValues = computed<Record<string, string[]>>(() => {                                           // Storeのフィルタ状態を、列ID→値 の形へ整形してテンプレートへ渡す
    const filters = this.tableFilters();                                                                         // 元になる列フィルタ
    const filtersValues = {                                                                                      // 固定列ぶんを先に組み立てる
      [EXPERIMENTS_TABLE_COL_FIELDS.STATUS]: filters?.[EXPERIMENTS_TABLE_COL_FIELDS.STATUS]?.value ?? [],        // ステータス
      [EXPERIMENTS_TABLE_COL_FIELDS.TYPE]: filters?.[EXPERIMENTS_TABLE_COL_FIELDS.TYPE]?.value ?? [],            // タイプ
      [EXPERIMENTS_TABLE_COL_FIELDS.USER]: filters?.[EXPERIMENTS_TABLE_COL_FIELDS.USER]?.value ?? [],            // ユーザー
      [EXPERIMENTS_TABLE_COL_FIELDS.TAGS]: filters?.[EXPERIMENTS_TABLE_COL_FIELDS.TAGS]?.value ?? [],            // タグ
      [EXPERIMENTS_TABLE_COL_FIELDS.PARENT]: filters?.parent?.['name']?.value ?? [],                             // ネストしたキーなので filters.parent.name から取り出す
      [EXPERIMENTS_TABLE_COL_FIELDS.PROJECT]: filters?.project?.['name']?.value ?? [],                           // 同じく filters.project.name から取り出す
      [EXPERIMENTS_TABLE_COL_FIELDS.VERSION]: filters?.hyperparams?.['properties']?.version?.value ?? null,      // hyperparams.properties.version。未設定はnull（空配列と区別する）
      [EXPERIMENTS_TABLE_COL_FIELDS.LAST_UPDATE]: filters?.[EXPERIMENTS_TABLE_COL_FIELDS.LAST_UPDATE]?.value ?? [], // 更新日時
      [EXPERIMENTS_TABLE_COL_FIELDS.STARTED]: filters?.[EXPERIMENTS_TABLE_COL_FIELDS.STARTED]?.value ?? []       // 開始日時
    };
    // handle dynamic filters;
    const storeValues = createFiltersFromStore(filters || {}, false);                                            // 動的列（メトリクス・ハイパラ）は列IDが固定でないのでStoreの内容をそのまま展開。第2引数falseで空値も残す
    return {...filtersValues, ...storeValues};                                                                   // 固定列の値を動的列の値で上書きして1つのマップにする
  });
  protected sortByFilterValues = signal<Record<string, string[]>>(this.filtersValues());                         // 「フィルタを開いた時点の選択値」。候補の並びを固定するために別管理する
  protected filtersSubValues = computed(() => ({                                                                 // タグ列の副次的な値
    [EXPERIMENTS_TABLE_COL_FIELDS.TAGS]: this.tableFilters()?.system_tags?.value ?? [],                          // system_tagsの選択もタグ欄のサブ値として見せる
  }));
  protected filtersMatch = computed(() => ({                                                                     // 各列のマッチモード（AND / OR）
    [EXPERIMENTS_TABLE_COL_FIELDS.TAGS]: this.tableFilters()?.[EXPERIMENTS_TABLE_COL_FIELDS.TAGS]?.matchMode ?? '' // タグ列のマッチモード。未設定は空文字
  }), {equal: () => Object.keys(this.tableFilters() ?? {}).length === 0}); //Don't reset match mode when remove all filters
  private router = inject(Router);                                                                               // 親タスクへの遷移に使う
  private readonly titleCasePipe = new TitleCasePipe();                                                          // PipeをDIせずクラスとして直接使う。純粋な文字列変換なのでこれで足りる
  protected filtersOptions = computed(() => ({                                                                   // 各列のフィルタ候補一覧
    [EXPERIMENTS_TABLE_COL_FIELDS.STATUS]: FILTERED_EXPERIMENTS_STATUS_OPTIONS(this.entityType() === EntityTypeEnum.dataset), // データセット画面では選択肢の文言が変わる
    [EXPERIMENTS_TABLE_COL_FIELDS.TYPE]: uniq((this.experimentTypes() ?? []).concat(this.filtersValues[EXPERIMENTS_TABLE_COL_FIELDS.TYPE])) // 重複排除して候補化。※ filtersValues はSignalなので () が要る。現状は常にundefinedが混ざり、227行で捨てられている
      .filter(type => !!type)                                                                                    // 空の値を除去
      .map((type: string) => ({                                                                                  // 選択肢の形へ変換
        label: (type?.length < 4 ? type.toUpperCase() : this.titleCasePipe.transform((new NoUnderscorePipe()).transform(type))), // 4文字未満は大文字（rl→RL）、それ以外はアンダースコアを外して先頭大文字
        value: type                                                                                              // 値はタイプ名そのもの
      })),
    [EXPERIMENTS_TABLE_COL_FIELDS.USER]: this.sortOptionsList(this.users()?.map(user => ({                       // ユーザー候補を作って並べ替える
      label: user.name ? user.name : 'Unknown User',                                                             // 名前が無ければ 'Unknown User'
      value: user.id,                                                                                            // 値はユーザーID
      tooltip: ''                                                                                                // ツールチップは使わないが、候補の型を揃えるため空文字を入れる
    })) ?? [], [...this.sortByFilterValues()[EXPERIMENTS_TABLE_COL_FIELDS.USER], this.currentUserId()]),         // 選択中ユーザーと自分自身を先頭へ寄せる
    [EXPERIMENTS_TABLE_COL_FIELDS.TAGS]: this.calcOptionalTagsList(),                                            // タグ候補だけは除外指定の扱いが特殊なので専用メソッドで生成
    [EXPERIMENTS_TABLE_COL_FIELDS.PARENT]: !this.parents() ? null :                                              // 親候補は未取得(null)ならnullのまま渡し、ローディング表示にする
      this.sortOptionsList(                                                                                      // 並べ替えつきで候補化
        Array.from(new Set(this.parents().concat(this.activeParentsFilter() || [])))                             // フィルタ中の親が候補から消えないよう合流させる
          .map(parent => ({                                                                                      // 選択肢の形へ変換
            label: parent.name ? parent.name : 'Unknown Experiment',                                             // 名前が無ければ 'Unknown Experiment'
            value: parent.id,                                                                                    // 値は親タスクのID
            tooltip: `${parent.project?.name} / ${parent.name}`                                                  // どのプロジェクトの実験かをツールチップで補う
          })),
        this.sortByFilterValues()[EXPERIMENTS_TABLE_COL_FIELDS.PARENT]                                           // 選択中の親を先頭へ
      ),
    [EXPERIMENTS_TABLE_COL_FIELDS.PROJECT]: !this.projects() ? null :                                            // プロジェクト候補も未取得ならnullのまま
      this.sortOptionsList(                                                                                      // 並べ替えつきで候補化
        this.projects().map(project => ({                                                                        // 選択肢の形へ変換
          label: project.name,                                                                                   // 表示名
          value: project.id,                                                                                     // プロジェクトID
        })),
        this.sortByFilterValues()[EXPERIMENTS_TABLE_COL_FIELDS.PROJECT]                                          // 選択中のプロジェクトを先頭へ
      ),
    [EXPERIMENTS_TABLE_COL_FIELDS.VERSION]: [],                                                                  // バージョンは候補を出さず自由入力
    ...Object.entries(this.hyperParamsOptions() ?? []).reduce((acc, [id, values]) => {                           // 動的なハイパーパラメータ列の候補をここへ展開する
      acc[id] = values === null ?                                                                                // 未取得かどうかで分岐
        null :                                                                                                   // nullはそのまま渡してローディング表示
        this.sortOptionsList([{label: '(No Value)', value: null}].concat(values.map(value => ({                  // 先頭に「値なし」を足してから候補化
          label: value,                                                                                          // 表示はそのままの値
          value                                                                                                  // 値も同じ
        }))), this.sortByFilterValues()[id]);                                                                    // この列で選択中の値を先頭へ
      return acc;                                                                                                // 列ID→候補配列 を積み上げる
    }, {})
  }));
  private prevExperiment = computedPrevious(this.selectedExperiment);                                            // 1つ前に選択されていた実験。変化検知に使う

  constructor() {                                                                                                // コンストラクタでeffectを登録する（注入コンテキストが必要なため）
    super();                                                                                                     // 基底のeffect登録とDestroyRef購読を先に実行

    effect(() => {                                                                                               // 実験一覧が届いたことを記録するeffect
      this.experiments();                                                                                        // 値は使わず依存登録だけ。Signalを読むことで再実行の条件になる
      this.experimentsUpdated = true;                                                                            // 以後はデータ0件なら「No data」を出してよい
    });

    effect(() => {                                                                                               // フィルタ状態が変わったら未取得扱いへ戻すeffect
      this.hasActiveFilters();                                                                                   // フィルタの有無を依存に取る
      this.experimentsUpdated = false;                                                                           // 再取得が走るので、結果が届くまで「No data」を出さない
    });

    effect(() => {                                                                                               // 全選択チェックボックスの活性を制御するeffect
      if (this.experiments()?.length > 0) {                                                                      // 表示できる実験があるか
        this.selectionChecked.enable();                                                                          // あれば操作可能
      } else {                                                                                                   // 無い場合
        this.selectionChecked.disable();                                                                         // 押せないようにする
      }
    });

    effect(() => {                                                                                               // 選択実験が変わったらその行へフォーカスを移すeffect
      if (this.prevExperiment()?.id !== this.selectedExperiment()?.id) {                                         // 前回と今回のIDを比べて、本当に変わった時だけ動かす
        window.setTimeout(() => !this.contextMenuActive() && this.table()?.focusSelected());                     // DOM更新後に実行。コンテキストメニュー表示中はフォーカスを奪わない
      }
    });

    effect(() => {                                                                                               // 単一選択の画面では先頭のチェック列を隠すeffect
      if (!this.enableMultiSelect()) {                                                                           // 複数選択が無効なら
        this.tableCols()[0].hidden = true;                                                                       // 入力で受け取った配列の要素を直接書き換えている。親側の参照を汚す書き方
      }
    })
  }

  calcOptionalTagsList() {                                                                                       // タグフィルタの候補を組み立てる
    const tags = uniqueFilterValueAndExcluded(this.tags() || [], this.filtersValues()[EXPERIMENTS_TABLE_COL_FIELDS.TAGS]) // 候補と選択値を合流。'__$not' 付きの除外指定は接頭辞を外して同一視する
      .map(tag => ({                                                                                             // 選択肢の形へ変換
        label: tag === null ? '(No tags)' : tag,                                                                 // nullは「タグなし」として表示
        value: tag                                                                                               // 値はタグ名（nullを含む）
      }) as IOption);
    const selectedTags = (this.sortByFilterValues()[EXPERIMENTS_TABLE_COL_FIELDS.TAGS] || [])                    // 選択中タグからも除外接頭辞を外す
      .map(tag => typeof tag === 'string' ? tag.replace(excludedKey, '') : tag);                                 // 文字列以外（null）はそのまま通す
    const tagsWithNull = [null].concat(selectedTags);                                                            // 「タグなし」と選択中タグを先頭グループにする
    tags.sort((a, b) => sortByArr(a.value, b.value, tagsWithNull));                                              // 先頭グループの順序を優先して並べ替え
    return tags;                                                                                                 // 並べ替え済みの候補を返す
  }

  onLoadMoreClicked() {                                                                                          // 「さらに読み込む」ボタン
    this.loadMoreExperiments.emit();                                                                             // 取得は親（コンテナ）の責務なので通知だけ
  }

  onSortChanged(isShift: boolean, colId: ISmCol['id']) {                                                         // 列ヘッダのソート操作
    this.sortedChanged.emit({isShift, colId});                                                                   // 並び替えを親へ依頼
    this.scrollTableToTop();                                                                                     // 並びが変わるので表示位置を先頭へ戻す
  }

  rowSelectedChanged(change: { value: boolean; event: Event }, experiment: ITableExperiment) {                   // 行チェックボックスの変更
    if (change.value) {                                                                                          // チェックを入れた場合
      const addList = this.getSelectionRange<ITableExperiment>(change, experiment);                              // Shift併用なら前回選択からの範囲をまとめて取得（基底の処理）
      this.experimentsSelectionChanged.emit([...this.checkedExperiments(), ...addList]);                         // 既存の選択に追加分を足して通知
    } else {                                                                                                     // チェックを外した場合
      const removeList = this.getDeselectionRange(change, experiment);                                           // 解除側も同様に範囲を求める
      this.experimentsSelectionChanged.emit(this.checkedExperiments().filter((selectedExperiment) =>             // 解除対象を除いた配列を通知
        !removeList.includes(selectedExperiment.id)));                                                           // IDで突き合わせて除外
    }
  }

  tableRowClicked({e, data}: { e: MouseEvent; data: ITableExperiment }) {                                        // 行クリック
    if (this.selectionMode() === 'single') {                                                                     // 単一選択モードでは詳細表示の対象を切り替える
      this.experimentSelectionChanged.emit({experiment: data, origin: 'row'});                                   // 発生源を'row'として通知
    }
    if (this.checkedExperiments()?.some(exp => exp.id === data.id)) {                                            // すでに選択済みの行をクリックした場合
      this.openContextMenu({e, rowData: data, backdrop: true});                                                  // 背景付きのコンテキストメニューを開く
    }
  }

  emitSelection(selection: ISelectedExperiment[]) {                                                              // 基底の抽象メソッドの実装。選択結果の通知口を1つにまとめる
    this.experimentsSelectionChanged.emit(selection);                                                            // 親へそのまま流す
  }

  openContextMenu(data: { e: Event; rowData; single?: boolean; backdrop?: boolean }) {                           // 基底の抽象メソッドの実装。右クリックやカードクリックから呼ばれる
    if (!data?.single) {                                                                                         // 表の行から開いた場合
      this.contextExperiment.set(this.experiments().find(experiment => experiment.id === data.rowData.id));      // 一覧側の実体を対象にする（渡された行データより型が揃っている）
      if (!this.checkedExperiments().map(exp => exp.id).includes(this.contextExperiment().id)) {                 // その行が未選択なら
        this.prevSelected = this.contextExperiment().id;                                                         // Shift範囲選択の基点も更新しておく（基底のフィールド）
        this.emitSelection([this.contextExperiment() as ISelectedExperiment]);                                   // その1件だけを選択した状態に切り替える
      }
    } else {                                                                                                     // 単一行指定で開いた場合
      this.contextExperiment.set(data.rowData);                                                                  // 渡された行データをそのまま対象にする
    }
    const event = data.e as MouseEvent;                                                                          // 座標を読むためMouseEventとして扱う
    event.preventDefault();                                                                                      // ブラウザ既定の右クリックメニューを止める
    this.contextMenu.emit({x: event.clientX, y: event.clientY, single: data?.single, backdrop: data?.backdrop}); // 表示位置と種別を親へ渡す
  }


  navigateToParent(event: MouseEvent, experiment: ITableExperiment) {                                            // 親タスクへの遷移
    event.stopPropagation();                                                                                     // 行クリック側の処理を走らせない
    return this.router.navigate(['projects', experiment.parent.project?.id || '*', 'tasks', experiment.parent.id], // プロジェクトが無い実験は '*'（全プロジェクト）配下として開く
      {queryParams: {filter: []}});                                                                              // 遷移先のフィルタは空にする
  }

  columnsWidthChanged({columnId, width}) {                                                                       // 動的列の展開など、列幅変更の反映
    const colIndex = this.tableCols().findIndex(col => col.id === columnId);                                     // 対象列の位置を求める
    const delta = width - parseInt(this.tableCols()[colIndex].style.width, 10);                                  // 現在幅との差分。'260px' のような文字列からpx値を取り出す
    this.table()?.updateColumnsWidth(columnId, width, delta);                                                    // 実際の幅調整は表コンポーネントに任せる
  }

  columnFilterOpened(col: ISmCol) {                                                                              // 列フィルタを開いた瞬間の候補取得
    this.sortByFilterValues.set(this.filtersValues());                                                           // 開いた時点の選択値を固定し、操作中に候補の並びが動かないようにする
    if (col.id === EXPERIMENTS_TABLE_COL_FIELDS.TAGS) {                                                          // タグ列の場合
      if (!this.filtersOptions()[EXPERIMENTS_TABLE_COL_FIELDS.TAGS]?.length) {                                   // 候補が空＝未取得なら
        this.tagsMenuOpened.emit();                                                                              // 親へ取得を依頼
      }
    } else if (col.id.includes('hyperparams')) {                                                                 // ハイパーパラメータ列の場合
      this.store.dispatch(hyperParamSelectedInfoExperiments({col: {id: col.id}, loadMore: false, values: []}));  // 取得済み候補をクリア
      this.store.dispatch(setHyperParamsFiltersPage({page: 0}));                                                 // ページング位置を先頭へ戻す
      this.store.dispatch(hyperParamSelectedExperiments({col, searchValue: ''}));                                // 空文字検索で候補を取り直す
    } else if (col.id === EXPERIMENTS_TABLE_COL_FIELDS.PROJECT) {                                                // プロジェクト列の場合
      if (!this.filtersOptions()[EXPERIMENTS_TABLE_COL_FIELDS.PROJECT]?.length) {                                // 候補が空なら
        this.filterSearchChanged.emit({colId: col.id, value: {value: ''}});                                      // 基底のoutput経由で初期候補を要求
      }
    }
  }

  selectAll(filtered?: boolean) {                                                                                // 「全選択」。filtered=true ならフィルタ結果の全件
    this.store.dispatch(selectAllExperiments({filtered}));                                                       // 件数が多く画面外も含むため、選択自体をStore側で行う
  }
}
````

# ExperimentsTableComponent 解説

## このコンポーネントの役割

ExperimentsTableComponent は、実験（Task）一覧の表とカードを描画する表示専用コンポーネントです。`dumb/` 配下にある通り、データ取得も状態更新も持たず、親の ExperimentsComponent から入力を受け取り、ユーザー操作を output で返すのが基本設計です。列定義、フィルタ候補、選択状態、コンテキストメニュー位置といった「見せ方」の計算だけをここに閉じ込めています。

同じ表は実験一覧だけでなく、比較対象の選択、モデルの実験一覧、データセットバージョン、パイプラインコントローラからも使われます。入力の数が多いのは、それら全部の差異を props で吸収しているためです。

## [■観点:BaseTableView への共通化]

範囲選択（Shift クリック）、全選択チェックボックス、ソート、フィルタの開閉、表のスクロールといった「一覧表なら必ず要る処理」は BaseTableView 側にあります。このクラスは差分だけを書きます。

注目すべきは 119〜120 行です。

```ts
override entitiesKey = 'experiments';
override selectedEntitiesKey = 'checkedExperiments';
```

基底クラスは `this[this.entitiesKey]()` のように文字列でプロパティを引きます。継承先が持つ input 名を基底が知らなくても共通処理を書けますが、型チェックは効きません。綴りを間違えても実行時まで気づけない、という代償の上に成り立っている仕組みです。

## [■観点:input() / output() というSignalベースのAPI]

入力は全て `input()`、出力はほぼ `output()` で書かれています。`@Input()` と違い、input は読み取り専用の Signal なので `this.experiments()` と関数呼び出しで読みます。これにより computed や effect の依存として自動追跡されます。

ただし 171 行だけは旧 API のままです。

```ts
@Output() removeTag = new EventEmitter<{...}>();
```

同じクラスに新旧が混在している状態で、移行途中であることが読み取れます。新規で書くなら `output()` に揃えます。

## [■観点:computed でフィルタ値と候補を組み立てる]

この画面の中心は `filtersValues`（現在のフィルタ値）と `filtersOptions`（各列の候補一覧）という2つの computed です。

`filtersValues` は Store 由来の `tableFilters` を、テンプレートが使いやすい「列ID → 値」の形へ変換します。厄介なのは parent や project のようにネストしたキーで、`filters.parent.name.value` のように階層が1つ深いため手で取り出しています（205〜207行）。さらに、メトリクスやハイパーパラメータの列は列IDが実行時に決まるため、固定列を列挙するだけでは足りません。そこで `createFiltersFromStore` で Store の中身を丸ごと展開し、固定列にスプレッドで重ねています（212〜213行）。

`filtersOptions` は候補側です。「未取得は null、取得済みは配列、空配列は候補ゼロ」という3状態を使い分けている点が要所で、`!this.parents() ? null : ...` の分岐（238行）はローディング表示のための区別です。

## [■観点:computed の equal オプションで再計算を止める]

219〜221 行は珍しい書き方です。

```ts
protected filtersMatch = computed(() => ({
  [EXPERIMENTS_TABLE_COL_FIELDS.TAGS]: this.tableFilters()?.[...]?.matchMode ?? ''
}), {equal: () => Object.keys(this.tableFilters() ?? {}).length === 0});
```

`equal` は「前の値と新しい値が等しいか」を判定する関数で、true を返すと Signal は値を更新せず、依存する再描画も起きません。ここでは中身を比べず「フィルタが1件も無いなら true」と答えています。つまり、利用者がフィルタを全部消した瞬間だけ再計算を止め、直前の AND/OR 設定を保持します。フィルタを消したら AND 指定まで OR に戻ってしまう、という挙動を防ぐための細工です。

## [■観点:sortByFilterValues で候補の並びを固定する]

`filtersValues` は選択が変わるたびに変化します。これをそのまま並べ替えの基準にすると、チェックを付けた項目が即座に先頭へ飛び、次にクリックしたい行が動いてしまいます。

そこで `sortByFilterValues` という別の signal を用意し、`columnFilterOpened`（378行）で「フィルタを開いた瞬間の値」を焼き付けます。候補の並び順はこの焼き付けた値だけを見るので、メニューを開いている間は順序が動きません。選択中の値を先頭に寄せつつ操作性も保つ、という2つの要求を両立させる定石です。

## [■観点:effect の使い方と、その良し悪し]

コンストラクタに5つの effect が並びます。effect は注入コンテキストが必要なので、フィールド初期化子ではなくコンストラクタに置くのが基本です。

272〜280 行の2つは、`experimentsUpdated` という素の boolean を書き換えます。

```ts
effect(() => {
  this.experiments();      // 値は捨てて依存登録だけ
  this.experimentsUpdated = true;
});
```

「一覧が一度でも届いたか」を記録し、初回ロード中に「No data to show」を出さないためのフラグです。読み捨ての `this.experiments();` は依存を張るためだけの行で、Signal を読む＝購読する、という性質を利用しています。意図は分かりますが、Signal から素のフィールドへ書き戻す形なので、OnPush の再描画タイミングとずれる可能性があります。本来は computed で導出したい部分です。

290〜294 行は前回値との比較です。`computedPrevious` で1つ前の選択実験を保持し、ID が変わった時だけフォーカスを移します。`setTimeout` を挟むのは、DOM 更新が終わってからでないと対象行が存在しないためです。

## [■観点:入力を直接書き換えている箇所]

296〜300 行は注意して読む価値があります。

```ts
effect(() => {
  if (!this.enableMultiSelect()) {
    this.tableCols()[0].hidden = true;
  }
})
```

`tableCols` は input です。その配列の要素を直接書き換えているので、親が渡した配列そのものが変化します。OnPush では参照が変わらないと再描画されないため書き換えが効かない場面があり、同じ列定義を別の場所で使っていれば影響が波及します。本来は「enableMultiSelect が false なら先頭列を除いた配列」を computed で作るのが素直です。既存コードの意図（親を書き換えてでも最短で隠したい）は分かりますが、ベストプラクティスとしては避ける形です。

## [■観点:Signal の呼び出し漏れ]

226 行は Signal を関数として呼んでいません。

```ts
uniq((this.experimentTypes() ?? []).concat(this.filtersValues[EXPERIMENTS_TABLE_COL_FIELDS.TYPE]))
```

`this.filtersValues` は computed、つまり関数オブジェクトです。そこへ添字を付けると必ず `undefined` になります。結果として「選択中のタイプを候補に残す」意図が働かず、227 行の `filter(type => !!type)` で静かに捨てられています。エラーにならないため気づきにくい種類の不具合です。

同じ型の書き漏れがテンプレート側にもあります。`experiments-table.component.html` の 193 行で `roundedMetricValues[col.id]` と書かれており、185 行で丁寧に組み立てた丸め判定マップが子コンポーネントに渡っていません。models-table、serving-table にも同じ記述があるので、この書き方が横展開されたものと見られます。Signal を導入したコードを読む時は、`()` の有無を機械的に確認する習慣が要ります。

## [■観点:dumb コンポーネントに残るStore依存]

このクラスは表示専用のはずですが、384〜386 行と 395 行で `store.dispatch` を直接呼びます。

- ハイパーパラメータ列のフィルタを開いた時の候補取得
- 「全選択」の実行

前者は列IDが動的で親が事前に知り得ないため、後者は画面外の行まで含めるため Store 側でしか処理できません。理由のある逸脱ではありますが、他の列は `tagsMenuOpened` や `filterSearchChanged` という output で親へ委ねているので、同じ役割の処理が2通りの経路で書かれている状態です。読む側としては「なぜここだけ直接 dispatch なのか」を意識しておくと迷いません。

## [■観点:コンテキストメニューを開く時の選択状態]

`openContextMenu`（349行）は、右クリックした行が未選択だった場合にその1件だけの選択へ切り替えます。表計算ソフトと同じ挙動で、「選択中の3件を右クリック」なら3件が対象、「選択外の行を右クリック」ならその行だけが対象になります。この時 `prevSelected` も更新しておくことで、続けて Shift クリックした際の範囲選択の基点がずれません。

また `contextExperiment` には、渡された行データではなく一覧から `find` した実体を入れます（351行）。カード側とテーブル側で渡ってくるオブジェクトの素性が違うため、一覧の実体に揃えて型を安定させています。

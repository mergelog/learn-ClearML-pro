````ts
import {                                                                                           // Angular コアAPIの名前付きimport
  AfterContentInit,                                                                                // ng-content 投影が終わった直後に呼ばれるフックの型
  ChangeDetectionStrategy,                                                                         // 変更検知戦略（OnPush指定）に使う列挙
  ChangeDetectorRef,                                                                               // 手動で変更検知を走らせるための参照
  Component,                                                                                       // コンポーネント定義デコレーター
  ElementRef,                                                                                      // 自分のホストDOM要素へ直接アクセスするため
  HostListener,                                                                                    // ホスト要素のイベントをメソッドへ紐付ける
  OnDestroy,                                                                                       // 破棄時フックの型。購読解除に使う
  signal,                                                                                          // 書き換え可能なSignalを作る関数
  TemplateRef,                                                                                     // ng-template の参照を保持する型
  input, computed, model, effect, viewChild, inject, contentChildren, output, Output, EventEmitter // Signalベースの入出力API群。末尾のOutput/EventEmitterだけ旧来方式
} from '@angular/core';
import {get} from 'lodash-es';                                                  // ネストしたプロパティを 'a.b.c' 形式で安全に取り出す
import {MenuItem, PrimeTemplate, ScrollerOptions, SortMeta} from 'primeng/api'; // PrimeNGの共通型。PrimeTemplateは <ng-template pTemplate> の実体
import {FilterMetadata} from 'primeng/api';                                     // PrimeNGのフィルター条件型（列ID→条件）
import {ContextMenu, ContextMenuModule} from 'primeng/contextmenu';             // 右クリックメニュー本体とそのモジュール
import {                                                                        // PrimeNG テーブル本体と関連イベント型
  Table,                                                                        // p-table のコンポーネントクラス。内部APIを直接叩くために型が必要
  TableColumnReorderEvent,                                                      // 列のドラッグ並べ替えイベント型
  TableContextMenuSelectEvent, TableModule,                                     // コンテキストメニュー選択イベント型と、テーブルのモジュール
  TableRowCollapseEvent,                                                        // 行を閉じたときのイベント型
  TableRowExpandEvent                                                           // 行を展開したときのイベント型
} from 'primeng/table';
import {                // RxJS の生成系
  BehaviorSubject,      // 最新値を保持するSubject。リサイズ要求の入れ物
  combineLatest,        // 複数ストリームの最新値を組み合わせる
  distinctUntilChanged, // 同じ値が続いたら流さない
  interval,             // debounce の待ち時間を作るために使用
  Subject,              // 追加読み込み要求を流すストリーム
  Subscription          // 購読解除に使う型
} from 'rxjs';
import {debounce, filter, map, take, throttleTime} from 'rxjs/operators';                               // 変換・間引き系オペレーター
import {custumFilterFunc, custumSortSingle} from './overrideFilterFunc';                                // PrimeNG内部のfilter/sortを差し替えるための自前実装
import {ColHeaderTypeEnum, ISmCol, TableSortOrderEnum} from './table.consts';                           // このテーブル独自の列定義（ISmCol）と列ヘッダ種別
import {Store} from '@ngrx/store';                                                                      // NgRx Store。ここでは表示倍率を取るためだけに使う
import {selectScaleFactor} from '@common/core/reducers/view.reducer';                                   // ブラウザ表示倍率のセレクター。列幅計算の補正に使う
import {sortCol} from '@common/shared/utils/sortCol';                                                   // columnsOrder の順番に従って列を比較する関数
import {mkConfig, download, generateCsv, asString} from 'export-to-csv';                                // CSV出力ライブラリ。設定生成・ダウンロード・文字列化
import {prepareColsForDownload, sanitizeCSVCell} from '@common/shared/utils/download';                  // ダウンロード用の列整形と、CSVインジェクション対策のセル無害化
import {NgTemplateOutlet} from '@angular/common';                                                       // テンプレート参照を動的に描画するディレクティブ
import {ResizableColumnDirective} from '@common/shared/ui-components/data/table/resizable-column.directive'; // 列幅のドラッグ変更を担当する自前ディレクティブ
import {MenuComponent} from '@common/shared/ui-components/panel/menu/menu.component';                   // ソート・フィルターを出すメニューUI
import {MenuItemComponent} from '@common/shared/ui-components/panel/menu-item/menu-item.component';     // 上記メニューの各項目
import {DotsLoadMoreComponent} from '@common/shared/ui-components/indicators/dots-load-more/dots-load-more.component'; // 追加読み込み中を示すドットのインジケーター
import {MatButton} from '@angular/material/button';                                                     // Material のボタン
import {MatIcon} from '@angular/material/icon';                                                         // Material のアイコン
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';                                          // コンポーネント破棄時に購読を自動解除する
import {MultiLineTooltipComponent} from '@common/shared/components/multi-line-tooltip/multi-line-tooltip.component'; // 複数行に折り返せるツールチップ
import {injectResize} from 'ngxtension/resize';                                                         // ngxtension製。ホスト要素のサイズ変化をObservableで受け取る

export interface TableContextMenuSelectEventExt extends Omit<TableContextMenuSelectEvent, 'index'> { // PrimeNGのイベント型から index を外して作り直した拡張型
  single?: boolean;                                                                                  // 右クリック対象が単一行かどうか
  index?: number;                                                                                    // 元の型では必須の index を任意にする
}

@Component({                                         // コンポーネントのメタデータ
    selector: 'sm-table',                            // テンプレート上では <sm-table> として使う
    templateUrl: './table.component.html',           // 描画テンプレート
    styleUrls: ['./table.component.scss'],           // スタイル定義
    changeDetection: ChangeDetectionStrategy.OnPush, // OnPush。Signalや入力が変わったときだけ再描画する
  imports: [                                         // standalone コンポーネントとして使う依存の列挙
    TableModule,                                     // p-table 本体
    ResizableColumnDirective,                        // 列幅ドラッグ
    MenuComponent,                                   // ソート/フィルターのメニュー
    MenuItemComponent,                               // メニュー項目
    ContextMenuModule,                               // 右クリックメニュー
    NgTemplateOutlet,                                // 親から投影されたテンプレートの描画
    DotsLoadMoreComponent,                           // 読み込み中表示
    MatIcon,                                         // アイコン
    MatButton,                                       // ボタン
    MultiLineTooltipComponent                        // 複数行ツールチップ
  ]
})
export class TableComponent<D extends { id: string }> implements AfterContentInit, OnDestroy { // 行データは id を持つ型に限定。選択判定を id で行うため
  private element = inject(ElementRef);                                                        // キーボード操作時にDOMから選択行を探すため
  private cdr = inject(ChangeDetectorRef);                                                     // 描画後に計算した値を反映するとき、OnPushを手動で回すため
  private store = inject(Store);                                                               // 表示倍率の取得用
  private resizeComponent$ = injectResize({emitInitialResult: true, debounce: 5})              // ホスト要素の幅変化を購読。初回も発火させ、5msデバウンスする
    .pipe(
      map(res => res.width), // 必要なのは幅だけなので取り出す
      distinctUntilChanged() // 幅が変わらない通知は捨てる
    );

  public active = false;                                                                                // Tableを掴んだ後にtrue。フィルター変更で先頭に戻すかの判定に使う
  public bodyTemplate: TemplateRef<{ $implicit: ISmCol; rowData: D; rowIndex: number; expanded: boolean }>; // 各セルの描画テンプレート。親から pTemplate="body" で受け取る
  public cardTemplate: TemplateRef<{ rowData: D; rowNumber: number; selected: boolean }>;               // カード表示モードでの1件分のテンプレート
  public footerTemplate: TemplateRef<{ $implicit: ISmCol }>;                                            // フッター行のテンプレート
  public rowExpansionTemplate: TemplateRef<{ $implicit: D; lastFrame: boolean }>;                       // 行を展開したときに差し込むテンプレート
  public cardHeaderTemplate: TemplateRef<null>;                                                         // カード表示のヘッダ（フィルター）テンプレート
  public checkboxTemplate: TemplateRef<{ $implicit: ISmCol }>;                                          // チェックボックス列ヘッダのテンプレート
  public sortFilterTemplate: TemplateRef<{ $implicit: ISmCol }>;                                        // ソート＋フィルター付きヘッダのテンプレート
  private loadMoreSubscription: Subscription;                                                           // 追加読み込みストリームの購読。破棄時に解除する
  private loadMoreDebouncer: Subject<null>;                                                             // 追加読み込み要求を間引くためのSubject
  public menuItems = [] as MenuItem[];                                                                  // コンテキストメニューの項目。中身は親が差し込む
  private readonly isChrome = navigator.userAgent.indexOf('Chrome') > -1;                               // Chromeだけスクロールバー幅の補正値が違うので分岐用に持つ
  public lastRowExpanded: boolean;                                                                      // 最終行が展開中か。下端の余白調整に使う
  public noDataTop: number;                                                                             // 「データなし」表示の縦位置(px)
  protected rightClicked: boolean;                                                                      // 右クリック由来の選択中フラグ。テンプレートの見た目制御用


  readonly colHeaderTypeEnum = ColHeaderTypeEnum;      // テンプレートから列挙を参照できるように公開
  table = viewChild(Table);                            // PrimeNGのTableインスタンス。内部APIを直接操作するために掴む
  menu = viewChild(ContextMenu);                       // 右クリックメニューを閉じるために保持
  templates = contentChildren(PrimeTemplate);          // 親が投影した <ng-template pTemplate> を全部受け取る
  private scaleFactor: number;                         // 表示倍率(%)。列幅計算の補正に使う
  private waiting: boolean;                            // スクロール連打を抑制するためのフラグ
  public scrollContainer: HTMLDivElement;              // PrimeNGが生成するスクロール領域のDOM
  private resize$ = new BehaviorSubject<number>(null); // リサイズ要求。流す値はデバウンスの待ち時間(ms)
  private waitForClick: number;                        // シングルクリック確定待ちのタイマーID
  search: string;                                      // テーブル内検索の入力値

  scrollHeight = input('flex');                                  // p-tableのscrollHeight。'flex'は親の高さに追従
  autoLoadMore = input(false);                                   // trueなら間引かずに即座へ追加読み込みする
  columnResizeMode = input('expand' as 'fit' | 'expand');        // 'fit'は他列と幅を分け合う、'expand'は表全体が広がる
  expandableRows = input(false);                                 // 行の展開を許可するか
  expandRowOnClick = input(true);                                // 行クリックで展開するか
  initialColumns = input<ISmCol[]>();                            // 動的列を含まない初期列。ソートメニューの候補に使う
  tableData = input<D[]>();                                      // 表示する行データ
  columnsOrder = input<string[]>();                              // 列IDの並び順。ユーザーが並べ替えた結果
  columns = input<ISmCol[]>();                                   // 実際に描画する列定義（hidden なものも含む）
  reorderableColumns = input(false);                             // 列のドラッグ並べ替えを許可するか
  resizableColumns = input(false);                               // 列幅のドラッグ変更を許可するか
  scrollable = input(false);                                     // スクロール領域を作るか
  sortOrder = input<TableSortOrderEnum>();                       // 昇順(1)/降順(-1)
  sortFields = input<SortMeta[]>();                              // 複数ソート条件（列と向きの組）
  selection = input<D | D[]>();                                  // 選択中の行。単一選択と複数選択の両方を受ける
  activeContextRow = input<D>();                                 // 右クリック中の行
  contextMenuOpen = input(false);                                // コンテキストメニューが開いているか
  first = input(0);                                              // 表示開始インデックス（ページング位置）
  rowsNumber = model(10);                                        // model なので親と双方向。1ページあたりの行数
  selectionMode = input<'multiple' | 'single' | null>('single'); // 単一選択か複数選択か
  rowHeight = input(48);                                         // 1行の高さ(px)。仮想スクロールの計算にも使う
  cardHeight = input(130);                                       // カード表示の1枚の高さ(px)
  lazyLoading = input(false);                                    // データ取得を親に任せる（PrimeNGのlazy）
  keyboardControl = input(false);                                // 上下キーで行を移動できるようにするか
  noMoreData = input<boolean>();                                 // これ以上取得できるデータが無いか
  rowHover = input<boolean>();                                   // 行ホバーの見た目を出すか
  noHeader = input(false);                                       // ヘッダ行を出さない
  simple = input(false);                                         // 装飾を省いた簡易表示
  expandedRowKeys = input<Record<string, boolean>>({});          // 展開中の行IDの集合
  rowExpandMode = input<'multiple' | 'single'>('multiple');      // 同時に複数行を展開できるか
  cardsCollapsed = input(false);                                 // カード表示を畳んでいるか
  minimizedView = input(false);                                  // 左側に縮小表示するモード。フィルターの挙動も差し替わる
  filters = input<Record<string, FilterMetadata>>();             // 列IDごとのフィルター条件
  noDataTemplate = input<TemplateRef<null>>();                   // データが無いときに描画するテンプレート
  checkedItems = input([]);                                      // チェックボックスで選択された行
  virtualScroll = input<boolean>();                              // 仮想スクロールを使うか
  virtualScrollOptions = input<ScrollerOptions>({});             // 仮想スクロールの詳細設定
  globalFilterFields = input<string[]>();                        // テーブル内検索の対象フィールド
  enableTableSearch = input(false);                              // テーブル内検索を出すか
  minimizedTableHeader = input<string>();                        // 縮小表示時のヘッダ文言
  hasExperimentUpdate = input<boolean>();                        // 一覧に更新があることを示すバッジ制御

  sortChanged = output<{     // ヘッダ操作によるソート要求
        field: ISmCol['id']; // 対象の列ID
        isShift: boolean;    // Shift押下なら既存条件に追加（複数ソート）
    }>();
  rowClicked = output<{ // シングルクリックが確定したときに発火
        e: MouseEvent;  // 元のマウスイベント
        data: D;        // 対象行のデータ
    }>();
  rowDoubleClicked = output<{ // ダブルクリックが確定したときに発火
        e: MouseEvent;        // 元のマウスイベント
        data: D;              // 対象行のデータ
    }>();
  rowSelectionChanged = output<{ // 選択行が変わった。解除時は data:null を送る
        data: D;                 // 新しい選択行
        originalEvent?: Event;   // きっかけになったイベント
    }>();
  rowExpanded = output<TableRowExpandEvent>();                                                // 行を展開した
  rowCollapsed = output<TableRowCollapseEvent>();                                             // 行を閉じた
  firstChanged = output<number>();                                                            // 表示開始位置の変更を親へ通知
  loadMoreClicked = output();                                                                 // 追加読み込みの要求
  @Output() rowRightClick = new EventEmitter<{ e: MouseEvent; rowData; single?: boolean }>(); // observed で購読有無を見たいので、あえて旧来のEventEmitterのまま
  colReordered = output<string[]>();                                                          // 並べ替え後の列ID配列
  columnResized = output<{                                                                    // 幅が変わった列の通知
        columnId: string;                                                                     // 対象の列ID
        widthPx: number;                                                                      // 新しい幅(px)
    }>();
  cardsCollapsedToggle = output(); // カード表示の折り畳み切り替え

  protected visibleColumns = computed(() => (this.columns() ?? []).filter(col => !col.hidden));  // hiddenでない列だけ。columns が変われば自動で再計算される
  protected currRowsNumber = computed(() => this.tableData()?.length ?? this.rowsNumber() ?? 0); // 実データ件数。無ければ行数入力へフォールバック
  protected tableSate = computed(() => ({                                                        // データと読み込み中フラグをまとめた状態（綴りは原文ママ）
    table: this.tableData(),                                                                     // 元データ
    loading: signal(!this.tableData())                                                           // computed内でsignalを作るので、tableDataが変わると器ごと作り直される
  }))

  constructor() {                       // DIはinject()で済ませ、constructorはeffectと購読の設定に使う
    this.tableSate().loading.set(true); // 初期状態は読み込み中

    effect(() => {               // 列順が届いたら並べ替える
      if (this.columnsOrder()) { // columnsOrder を読むことでこのeffectの依存になる
        this.orderColumns();     // visibleColumns を columnsOrder の順に並べ替える
      }
    });

    effect(() => {                      // 列定義が届いたら並べ替えて幅を測り直す
      if (this.columns()?.length > 0) { // 列が1つ以上あることが前提
        this.orderColumns();            // 新しい列順を反映
        this.resize();                  // 列が変わると幅も変わるので再計算
      }
    });

    effect(() => {                                                    // 縮小表示以外ならフィルター関数の差し替え状態を確認し、常に幅を再計算
      if (!this.minimizedView()) {                                    // 縮小表示のときは何もしない
        window.setTimeout(() => this.table() && this.updateFilter()); // Tableの生成を待つため、次のマクロタスクへ回してから実行
      }
      this.calcResize(); // どちらにせよ幅は測り直す
    });

    effect(() => {                                      // フィルターとソート条件をPrimeNGの内部プロパティへ直接書き込む
      if (!this.minimizedView() && this.table()) {      // Tableが生成済みで、縮小表示でないこと
        this.table().filters = this.filters();          // 列フィルターを流し込む
        this.table().multiSortMeta = this.sortFields(); // 複数ソート条件を流し込む
        if (this.active) {                              // 初期設定ではなくユーザー操作による変更なら
          this.table().first.set(0);                    // 条件が変わったので表示位置を先頭へ戻す
          this.firstChanged.emit(0);                    // 戻したことを親へも伝える
        }
      }
    });


    effect(() => {        // Tableのインスタンスが取れた時点で一度だけ初期化する
      if (this.table()) { // viewChildがまだ未解決の間はundefined
        // In order to know if we should reset first to 0 on filter input.
        this.active = true; // 以降のフィルター変更は「ユーザー操作」とみなす
        this.gotTable();    // スクロール要素の取得とフィルター関数の差し替え
      }
    });

    this.loadMoreDebouncer = new Subject();            // 追加読み込み要求の入り口
    this.loadMoreSubscription = this.loadMoreDebouncer // 要求を受けて
      .pipe(throttleTime(1500))                        // 1.5秒に1回だけ通す（連打・スクロール連続での多重取得を防ぐ）
      .subscribe(                                      // 購読開始
        () => this.loadMoreClicked.emit()              // 間引いたうえで親へ通知
      );

    this.store.select(selectScaleFactor)             // 表示倍率をStoreから取得
      .pipe(filter(s => !!s), take(1))               // 値が入った最初の1回だけでよい
      .subscribe(scale => this.scaleFactor = scale); // 以後は列幅計算で使う

    combineLatest([         // 明示的なリサイズ要求と、要素サイズの変化を合流させる
      this.resize$,         // resize(delay) で発火する要求
      this.resizeComponent$ // ResizeObserver由来の幅変化
    ])
      .pipe(
        takeUntilDestroyed(),                                                  // 破棄時に自動で購読解除
        debounce(([delay]) => interval(typeof delay === 'number' ? delay : 0)) // resize(delay) で渡された待ち時間だけ遅らせる（未指定なら0）
      )
      .subscribe(() => this.calcResize()); // 実際の幅計算へ
  }

  gotTable = () => {                                                                                    // アロー関数プロパティ。thisを固定したまま参照を渡せる
      this.scrollContainer = this.table().el.nativeElement.getElementsByClassName('p-datatable-table-container')[0] as HTMLDivElement; // PrimeNGが描くスクロール要素を、クラス名を頼りに掘り出す
      if (this.scrollContainer) {                                                                       // 取れなかった場合は何もしない
        this.scrollContainer.onscroll = () => {                                                         // スクロール中フラグを立てる
          if (!this.waiting) {                                                                          // すでに待機中なら何もしない
            this.waiting = true;                                                                        // フラグを立てて
            window.setTimeout(() => {                                                                   // 60ms後に
              this.waiting = false;                                                                     // 倒す（この間の処理を抑制する）
            }, 60);
          }
        };
      this.updateFilter(); // 縮小表示ならPrimeNG内部関数を差し替える
    }
  };

  resize(delay: number = null) { // 外部からの再計算要求。delayはデバウンスの待ち時間(ms)
    this.resize$.next(delay);    // combineLatest側へ流す
  }

  private calcResize() {                                                 // 列幅と表全体の幅を実測し、PrimeNGの幅復元機構へ流し込む
    if (this.table() && this.resizableColumns()) {                       // 幅可変が有効なときだけ処理する
      const element = (this.table().el.nativeElement as HTMLDivElement); // テーブルのルート要素
      let width = element.getBoundingClientRect().width;                 // 実際の描画幅
      if (this.scaleFactor) {                                            // 表示倍率が設定されていれば
        width *= this.scaleFactor / 100;                                 // 論理サイズへ補正する
      }
      let totalWidth = 0;                                                            // 全列の合計幅
      this.table().destroyStyleElement();                                            // 前回の列幅スタイルを一旦破棄
      if (this.minimizedView()) {                                                    // 縮小表示は実質1列扱い
        totalWidth = Math.max(width, 300);                                           // 狭すぎないよう最低300pxは確保
        this.table().columnWidthsState = `${totalWidth - (this.isChrome ? 13 : 4)}`; // スクロールバー幅の差（Chromeだけ広い）を引く
      } else {
        this.table().createStyleElement();                                           // 通常表示は列ごとに幅を作り直す
        this.table().columnWidthsState = this.visibleColumns().map((col, index) => { // 表示中の列の幅を順に求める
          let colWidth: number;
          if (col.style?.width?.endsWith('px')) {                  // px指定があれば
            colWidth = parseInt(col.style.width.slice(0, -2), 10); // その定義値を優先する
            totalWidth += colWidth;                                // 合計へ加算
          } else {
            colWidth = element.getElementsByTagName('th')[index]?.getBoundingClientRect().width || 0; // 指定が無ければ対応する th の実測値を使う
            totalWidth += this.scaleFactor ? colWidth * this.scaleFactor / 100 : colWidth;            // 実測値は表示倍率の影響を受けるので補正して加算
          }
          return colWidth;                        // この列の幅を返す
        }).join(',');                             // PrimeNGは幅をカンマ区切りの文字列で保持する
        totalWidth = Math.max(totalWidth, width); // 合計が枠より狭ければ枠幅まで広げる
      }

      this.table().tableWidthState = `${totalWidth}`; // 表全体の幅も文字列で渡す
      this.table().restoreColumnWidths();             // 作った値を実際のスタイルへ反映させる
    }
    this.noDataTop = this.table()?.wrapperViewChild()?.nativeElement.getBoundingClientRect().height / 2 - this.rowHeight() / 2 - 1; // データなし表示を表示領域の中央へ置くための縦位置
    if (this.noDataTop) {                                                                               // 値が求まったときだけ
      this.cdr.detectChanges();                                                                         // 描画後に計算した値なので、OnPushを手動で回して反映する
    }
  }

  @HostListener('keydown', ['$event'])                                                       // ホスト要素上のキー入力を拾う
  keyDownHandler(event: KeyboardEvent) {                                                     // 上下キーで選択行を動かす
    if (this.keyboardControl() === false || !['ArrowDown', 'ArrowUp'].includes(event.key)) { // キーボード操作が無効、または上下キー以外なら
      return;                                                                                // 何もしない
    }
    event.preventDefault();              // ページ全体のスクロールを止める
    if (event.key == 'ArrowDown') {      // 下キーなら
      this.incrementIndex(1);            // 1つ次の行へ
    } else if (event.key == 'ArrowUp') { // 上キーなら
      this.incrementIndex((-1));         // 1つ前の行へ
    }
    setTimeout(() => {                                                                                  // 選択が描画へ反映された後のDOMを見るため一拍置く
      let selected = this.element.nativeElement.querySelectorAll('.table-card.selected');               // カード表示の選択要素を探す
      if (selected.length < 1) {                                                                        // 見つからなければ
        selected = this.element.nativeElement.querySelectorAll('tr.ui-state-highlight'); // support obsolote scrolling in table // 旧来のテーブル表示のハイライト行を探す
      }
      if (selected && selected.length === 1) {                             // 選択が1つに定まっていれば
        selected[0].scrollIntoView({block: 'nearest', inline: 'nearest'}); // はみ出した分だけ最小限スクロールする
      }
      selected = null; // 参照を落として解放しやすくする
    }, 0);

  }

  ngAfterContentInit(): void {           // 親から投影されたテンプレートを種類ごとに仕分ける
    this.templates().forEach((item) => { // contentChildrenで集めたテンプレートを走査
      switch (item.getType()) {          // pTemplate に渡された名前で分岐
        case 'body':                     // セル本体
          this.bodyTemplate = item.template;
          break;
        case 'card': // カード表示
          this.cardTemplate = item.template;
          break;
        case 'sort-filter': // ソート＋フィルター付きヘッダ
          this.sortFilterTemplate = item.template;
          break;
        case 'checkbox': // チェックボックス列ヘッダ
          this.checkboxTemplate = item.template;
          break;
        case 'cardFilter': // カード表示のヘッダ（フィルター）
          this.cardHeaderTemplate = item.template;
          break;
        case 'footer': // フッター
          this.footerTemplate = item.template;
          break;
        case 'rowexpansion': // 行の展開部分
          this.rowExpansionTemplate = item.template;
          break;
        default: // 名前が無い・未知のものはセル本体として扱う
          this.bodyTemplate = item.template;
          break;
      }
    });
  }

  ngOnDestroy(): void {                      // 自前で作ったSubjectと購読の後始末
    this.loadMoreSubscription.unsubscribe(); // throttle購読を解除
    this.loadMoreDebouncer.complete();       // Subjectを完了させ
    this.loadMoreDebouncer.unsubscribe();    // 購読も解除する
    this.scrollContainer = null;             // DOM参照を残さない
  }

  onSortChanged(event) {          // ヘッダのソート操作をそのまま親へ中継
    this.sortChanged.emit(event); // 親側でソート条件を更新する
  }

  onRowSelected(event) {                                                                                // 行が選択されたとき
    if (this.selection() && !Array.isArray(this.selection()) && event.data.id === (this.selection() as D).id) { // 単一選択で、いま選ばれている行と同じなら
      this.rowSelectionChanged.emit({data: null, originalEvent: event.originalEvent});                  // 再クリックは選択解除として扱う
    } else {
      this.rowSelectionChanged.emit(event); // それ以外はそのまま通知
    }
  }

  onRowDeselected(event) {                                                             // 行の選択が外れたとき
    if (this.minimizedView()) {                                                        // 縮小表示では
      this.rowSelectionChanged.emit({data: null, originalEvent: event.originalEvent}); // 素直に「選択なし」を通知
    } else {
      this.rowSelectionChanged.emit({data: this.table()?.selection(), originalEvent: event.originalEvent}); // 通常表示ではPrimeNG側に残っている選択を通知する
    }
  }

  public scrollToIndex(rowIndex) {                                              // 指定行までスクロールする
    if (rowIndex > -1 && this.table()) {                                        // 行が存在し、Tableが生成済みであること
      if (this.virtualScroll()) {                                               // 仮想スクロール時は
        const {height} = this.table().el.nativeElement.getBoundingClientRect(); // 表示領域の高さを取り
        const rowsInPage = height / this.rowHeight();                           // 画面に入る行数を求め
        const maxScroll = Math.ceil(this.currRowsNumber() - rowsInPage);        // 最終行が下端に来る位置を上限にする
        this.table().scrollToVirtualIndex(Math.min(maxScroll, rowIndex));       // 上限を超えない位置までスクロール
      } else {
        const row = this.table().el.nativeElement.getElementsByTagName('tr')[rowIndex] as HTMLTableRowElement; // 通常スクロール時は実際の tr を探す
        if (row) {                                                                                      // 見つかったら
          let location = row.offsetTop;                                                                 // その行の上端位置へ
          if (rowIndex + 1 === this.tableData().length) {                                               // 最終行なら
            location += row.getBoundingClientRect().height;                                             // 行の高さぶん余分に送って全体を見せる
          }
          this.table().scrollTo({top: location, behavior: 'smooth'}); // 滑らかにスクロール
        }
      }
    }
  }

  public scrollToElement(data) {                                            // 行データからスクロール先を決める
    const rowIndex = this.tableData().findIndex(row => row.id === data.id); // idで行の位置を特定
    this.scrollToIndex(rowIndex);                                           // あとはindex指定と同じ
  }

  onFirstChanged(event) {          // ページ位置の変更を親へ中継
    this.firstChanged.emit(event); // 親がURLやStoreへ反映する
  }

  openContext({originalEvent, data, single}: TableContextMenuSelectEventExt) {          // 右クリックメニューの入り口
    if (this.rowRightClick.observed) {                                                  // 親が購読しているときだけ処理する（observedが使えるのがEventEmitterの利点）
      this.rowRightClick.emit({e: originalEvent as MouseEvent, rowData: data, single}); // どの行を右クリックしたかを親へ渡す
      if (this.table()) {                                                               // Tableが生成済みなら
        this.rightClicked = !single;                                                    // 単一行指定でなければ「右クリック選択中」とみなす
        this.table().contextMenuSelection = null;                                       // PrimeNG側の選択ハイライトは使わず、自前で制御する
      }
      window.setTimeout(() => this.menu().hide()); // PrimeNGが開いた直後に閉じる。実際のメニュー表示は親に任せる
    }
  }

  trackByFunction(index: number, item) { // 行の同一性判定。id→name→indexの順で使えるものを返す
    return item?.id || item?.name || index;
  }

  // public locateInTable() {
  //   const selectedTask = this.selection;
  //   const tableData = this.table.filteredValue ? this.table.filteredValue : this.table.value;
  //   const rowIndex = tableData.findIndex((task) => task.id === selectedTask.id);
  //   const first = rowIndex > 0 ? (rowIndex - rowIndex % 10) : 0;
  //   this.first = first;
  //   this.firstChanged.emit(first);
  // }

  getBodyData(rowData, col) {    // col.id を 'a.b' 形式のパスとして値を取り出す
    return get(rowData, col.id); // lodashのgetでネストも安全に辿る
  }

  incrementIndex(change: number) {               // 上下キーによる選択移動
    const currentIndex = this.getCurrentIndex(); // 現在の選択位置
    if (currentIndex == -1) {                    // 選択が見つからなければ
      return;                                    // 何もしない
    }
    if (this.tableData().length && this.tableData().length - currentIndex < 3 && !this.noMoreData()) { // 下端まで残り3件を切り、まだ続きがあるなら
      this.loadMore();                                                                                 // 先に次ページを取りにいく
    }
    const nextSelected = (this.selection()) ? this.tableData()[currentIndex + change] : this.tableData()[0]; // 未選択のときは先頭行を選ぶ
    if (nextSelected) {                                                                                 // 移動先があれば
      this.rowSelectionChanged.emit({data: nextSelected});                                              // 選択変更として親へ通知
    }
  }

  getCurrentIndex() {                                                                    // 現在の選択位置を返す
    if (this.selection() && !Array.isArray(this.selection())) {                          // 単一選択のときだけ
      return this.tableData().findIndex((row) => row.id === (this.selection() as D).id); // idで実インデックスを求める
    } else {
      return 0; // 複数選択・未選択時は先頭扱い
    }
  }

  loadMore() {                          // 追加読み込みの実行
    this.tableSate().loading.set(true); // 先に読み込み中にする
    if (this.autoLoadMore()) {          // 自動読み込みモードなら
      this.loadMoreClicked.emit();      // そのまま親へ要求
    } else {
      this.loadMoreDebouncer.next(null); // 通常は1.5秒のthrottleを通す
    }
  }

  onColReorder($event: TableColumnReorderEvent) {                // 列をドラッグで並べ替えたとき
    const columnsList = $event.columns.map(column => column.id); // 新しい並び順を列IDの配列にする
    this.colReordered.emit(columnsList);                         // 親（Store/URL）へ保存させる
    this.resize();                                               // 並びが変われば幅も測り直す
  }

  orderColumns() {                                                                  // columnsOrder の順に列を並べ替える
    if (this.visibleColumns() && this.columnsOrder()) {                             // どちらも揃っているときだけ
      this.visibleColumns().sort((a, b) => sortCol(a.id, b.id, this.columnsOrder()) // visibleColumns() が返す配列をその場で並べ替える
      );
    }
  }

  isRowSelected(entity: { id: string }) { // チェックボックスで選択済みの行かどうか
    if (!entity) {                        // 行が無ければ
      return false;                       // 選択されていない
    }

    return this.checkedItems()?.length > 0 &&                                                           // チェック済みが1件以上あり
      (this.checkedItems().some((selectedEntity: { id: string }) => selectedEntity?.id === entity.id)); // その中に同じidが含まれていれば選択中
  }

  private updateFilter() {      // 縮小表示のときだけPrimeNG内部の関数を差し替える
    if (this.minimizedView()) { // 通常表示では何もしない
      // Overriding prime ng filter and sort functions so that it wont reset first after data change.
      this.table()._filter = custumFilterFunc.bind(this.table());    // データ更新のたびに先頭へ戻される挙動を避けるための差し替え
      this.table().sortSingle = custumSortSingle.bind(this.table()); // 単一ソートも同じ理由で差し替える

      this.table().filters = this.filters(); // 差し替え後にフィルター条件を入れ直す
    }
  }

  focusSelected() {                                                                 // 選択中の要素へフォーカスを移す。キーボード操作の起点になる
    this.table()?.el?.nativeElement.getElementsByClassName('selected')[0]?.focus(); // 最初に見つかった選択要素へ
  }

  colResize({delta, element}: { delta: number; element: HTMLElement }) { // 列幅をドラッグしたときの通知
    if (delta) {                                                         // 移動量がゼロなら何もしない
      const columnId = element.attributes['data-col-id']?.value;         // DOM属性から対象の列を特定する
      const col = this.columns().find(col => col.id === columnId);       // 列定義を引く
      let colWidth: number;
      if (col.style?.width?.endsWith('px')) {                  // px指定があれば
        colWidth = parseInt(col.style.width.slice(0, -2), 10); // その値を基準にする
      } else {
        colWidth = element.getBoundingClientRect().width || 0; // 無ければ実測値を基準にする
      }
      this.columnResized.emit({columnId, widthPx: colWidth + delta}); // 移動量を足した幅を親へ通知
    }
  }

  updateColumnsWidth(columnId, width: number, delta: number) {        // 隣の列と幅を融通し合う調整
    const columns = this.visibleColumns();                            // 表示中の列だけを対象にする
    if (columnId) {                                                   // 対象列が指定されているとき
      const colIndex = columns.findIndex(col => col.id === columnId); // 対象の位置
      delta = width - parseInt(columns[colIndex].style?.width, 10);   // 引数のdeltaは使わず、実際の差分で上書きする
      if (width < 30) {                                               // 最小幅を下回るなら
        width = 30;                                                   // 30pxで止める
      }
      columns[colIndex].style = {...columns[colIndex].style, width: `${width}px`};                     // 列定義のstyleを直接書き換えている点に注意
      if (columns[colIndex + 1]) {                                                                     // 右隣の列があれば
        const newWidth = parseInt(columns[colIndex + 1]?.style.width, 10) - delta;                     // 広げた分だけ隣を縮める
        if (newWidth < 30) {                                                                           // 隣が最小幅を割り込むなら
          columns[colIndex + 1].style = {...columns[colIndex + 1].style, width: '30px'};               // 隣は30pxで止め
          columns[colIndex].style = {...columns[colIndex].style, width: `${width - 30 + newWidth}px`}; // はみ出した分は自分の幅から返す
        } else {
          columns[colIndex + 1].style = {...columns[colIndex + 1].style, width: `${newWidth}px`}; // 割り込まないならそのまま反映
        }
      }
    }
    columns.forEach((col) => {                                                             // 最終的な幅を全列ぶん
      this.columnResized.emit({columnId: col.id, widthPx: parseInt(col.style.width, 10)}); // 親へ通知して保存させる
    });
  }

  get sortableCols(): ISmCol[] {                                                         // ソートメニューに出す候補列
    return (this.initialColumns() || this.visibleColumns()).filter(col => col.sortable); // 動的列を含まない初期列があればそちらを優先する
  }

  sortItemClick($event: { event?: MouseEvent; itemValue: string }, colId: string) { // メニューからソートを選んだとき
    this.sortChanged.emit({isShift: $event.event.shiftKey, field: colId});          // Shift併用なら複数ソートへの追加として扱われる
  }

  getOrder(colId: string) {                                                // その列の現在のソート方向。未ソートならundefined
    return this.sortFields()?.find(field => field.field === colId)?.order; // 複数ソート条件の中から該当列を探す
  }

  checkClick(param: { data: D; e: MouseEvent }) {           // シングルクリックとダブルクリックを見分ける
    if (param.e.type === 'dblclick' || this.waitForClick) { // dblclickが来た、または待機中に次が来たら
      window.clearTimeout(this.waitForClick);               // 待機中のシングルクリック発火を取り消し
      this.waitForClick = null;                             // 待機状態を解除して
      this.rowDoubleClicked.emit(param);                    // ダブルクリックとして通知
    } else {
      this.waitForClick = window.setTimeout(() => { // 初回は即座に発火させず
        this.rowClicked.emit(param);                // 250ms後にシングルクリックとして通知
        this.waitForClick = null;                   // 待機状態を解除
      }, 250);
    }
  }

  updateNumberOfRows({event, expanded}: { event: TableRowExpandEvent; expanded: boolean }) {            // 最終行が展開されたかを記録する
    const expandedIndex = Object.values(this.tableData()).findIndex((row: D) => row.id === event.data.id); // 展開された行の位置を求め
    this.lastRowExpanded = expanded && expandedIndex === this.currRowsNumber() - 1;                     // それが最終行かどうかを保持（下端の余白調整に使う）
  }

  preProcessRows(cols: any[]) {                                                                         // CSV用に、行データを「列名をキーにしたオブジェクト」へ変換
    return this.tableData().map(row =>                                                                  // 全行を変換
      cols.reduce((acc, dCol) => {                                                                      // 列ごとに値を集めていく
        const val = get(row, (dCol.field).split('.').map(level=> level.replace('%2E', '.')), '') as unknown; // 列IDの '%2E' はエスケープされたドット。分割後に本来の '.' へ戻す
        acc[dCol.name] = Array.isArray(val) ?                                                           // 配列は
          val.toString() :                                                                              // カンマ区切りの文字列にし
          typeof val === 'string' ?                                                                     // 文字列なら
            sanitizeCSVCell(val.replace(/\r?\n|\r/g, '')) :                                             // 改行を除いたうえで、数式として解釈される先頭文字を無害化する
            val;                                                                                        // それ以外の型はそのまま入れる
        return acc;                                                                                     // 次の列へ
      }, {})
    );
  }

  getTableCopy() {                                                                                    // クリップボード用にCSV文字列を作って返す
    const colsOrder = this.columnsOrder() ?? this.visibleColumns().map(col => col.id);                // 並び順が無ければ表示中の列順を使う
    const sortedAllColumns = colsOrder.map(sortCol => this.columns().find(col => col.id === sortCol)) // 並び順に従って列定義を並べ直す
    const downloadCols = prepareColsForDownload(sortedAllColumns);                                    // ダウンロード用の表示名・キーへ整形
    const rows = this.preProcessRows(downloadCols);                                                   // 行データを変換
    const csvConfig = mkConfig({useKeysAsHeaders: true});                                             // オブジェクトのキーをそのままヘッダにする
    return asString(generateCsv(csvConfig)(rows));                                                    // ファイルにせず文字列として返す
  }


  downloadTableAsCSV(tableName?: string) {                  // CSVファイルとしてダウンロードさせる
    const options = mkConfig({                              // 出力設定
      filename: `${tableName}${tableName ? '-' : ''}table`, // テーブル名があれば接頭辞に付ける
      showColumnHeaders: true,                              // ヘッダ行を出力する
    });

    const colsOrder = this.columnsOrder() ?? this.visibleColumns().map(col => col.id);                  // 並び順が無ければ表示中の列順を使う
    const sortedAllColumns = colsOrder.map(sortCol => this.columns().find(col => col.id === sortCol)).filter(col => !!col); // 存在しない列IDは捨てる
    const rest = this.columns().filter(col => !colsOrder.includes(col.id));                             // 並び順に含まれない列は後ろへ回す
    const downloadCols = prepareColsForDownload([...sortedAllColumns, ...rest]);                        // ダウンロード用の表示名・キーへ整形
    options.columnHeaders = downloadCols.map(dCol => dCol.name);                                        // ヘッダには列定義の表示名を使う
    const rows = this.preProcessRows(downloadCols);                                                     // 行データを変換

    const csv = generateCsv(options)(rows); // CSVを生成し
    download(options)(csv);                 // ブラウザにダウンロードさせる
  }

  isSelected = (rowData: D) =>                                                                          // テンプレートから呼ぶのでアロー関数プロパティで定義
    Array.isArray(this.selection()) ? (this.selection() as D[]).some(s => s.id === rowData.id) : (this.selection() as D)?.id === rowData?.id; // 複数選択なら含まれるか、単一選択ならid一致かで判定
}
````

# TableComponent 解説

## このコンポーネントの役割

PrimeNG の `p-table` を、アプリ共通の作法（`ISmCol` という独自の列定義、Signal ベースの入出力、NgRx との連携、CSV 出力）で包み直したラッパーです。「表をどう描くか」は親から投影されたテンプレートに任せ、このクラスは **列の順番・幅・ソート・フィルター・選択・追加読み込み・スクロール位置** といった表の骨格を受け持ちます。

`D extends { id: string }` という制約が全体の前提です。選択判定・行の同一性判定・スクロール先の特定を、すべて `id` の一致で行っています。

## [■観点:PrimeNGのTableを直接操作する薄いラッパー]

`table = viewChild(Table)` で PrimeNG のコンポーネントインスタンスを掴み、その **内部プロパティを直接書き換えて** います。

- `this.table().filters = this.filters()` / `multiSortMeta`（条件の流し込み）
- `columnWidthsState` / `tableWidthState` / `restoreColumnWidths()`（列幅の復元）
- `this.table()._filter = ...`（アンダースコア付き＝私的APIの差し替え）

入力バインディングだけでは届かない制御を実現するための選択です。代わりに **PrimeNG のバージョン更新に弱い** という代償を負っています。`_filter` のような私的APIを触っている箇所は、ライブラリ更新時に真っ先に壊れる候補として覚えておくとよいです。

## [■観点:contentChildrenとpTemplateでテンプレートを差し込む]

`templates = contentChildren(PrimeTemplate)` は、親が書いた `<ng-template pTemplate="body">` などをすべて集めます。`ngAfterContentInit` で `item.getType()`（= pTemplate に渡した名前）によって仕分け、`bodyTemplate` などのプロパティへ配ります。

```
親: <sm-table><ng-template pTemplate="body" let-col let-row="rowData">…</ng-template></sm-table>
          ↓ contentChildren で収集
子: bodyTemplate に格納 → テンプレート側で NgTemplateOutlet として描画
```

つまり「表の構造」と「セルの見た目」を分離する仕組みです。これがあるので、実験一覧・モデル一覧・データセット一覧が同じ `TableComponent` を共有できます。

## [■観点:Signalベースの入出力と、1つだけEventEmitterが残る理由]

入力はすべて `input()`、出力はほぼ `output()` です。`rowsNumber` だけ `model()` で、親と双方向になっています。

ただし1つだけ例外があります。

```ts
@Output() rowRightClick = new EventEmitter<...>();
```

`openContext()` の中で `this.rowRightClick.observed` を見ているためです。`observed`（購読者がいるか）は `EventEmitter` にはありますが、新しい `output()` にはありません。「親が右クリックを扱わないなら、そもそもメニューを出さない」という判定をしたいので、あえて旧API のまま残してあります。**移行の取り残しではなく、機能上の理由がある例外** です。

## [■観点:effectで宣言的Signalと命令的PrimeNGを橋渡しする]

コンストラクタに4つの `effect` が並びます。Signal は「値が変わったら勝手に追従する」宣言的な仕組み、PrimeNG の内部プロパティは「代入して初めて反映される」命令的な仕組みです。`effect` はその間の変換器として使われています。

| effect | 依存 | やること |
|---|---|---|
| 1 | `columnsOrder()` | 列を並べ替える |
| 2 | `columns()` | 並べ替え＋幅の再計算 |
| 3 | `minimizedView()` | フィルター関数の差し替え確認＋幅の再計算 |
| 4 | `filters()` / `sortFields()` | 条件を PrimeNG へ流し込み、先頭ページへ戻す |
| 5 | `table()` | Table 取得時の初期化 |

effect 4 の `if (this.active)` に注意してください。`active` は effect 5（= Table が取れた瞬間）で `true` になります。つまり **初回の条件セットでは先頭に戻さず、以降のユーザー操作による変更でだけ戻す** という区別をしています。初期化と操作を `active` 1つのフラグで見分ける、素朴ですが効く手です。

## [■観点:リサイズ要求を1本に合流させる]

幅の再計算が走るきっかけは2つあります。

1. コード側からの明示的な要求（`resize(delay)` → `resize$`）
2. ホスト要素のサイズ変化（`injectResize()` → ResizeObserver）

これを `combineLatest` で合流させ、`debounce(([delay]) => interval(delay))` で間引いてから `calcResize()` を1回だけ呼びます。`resize$` に流す値が「イベント」ではなく **待ち時間そのもの** になっているのが工夫どころで、呼び出し側が `resize(200)` のように遅延を指定できます。

## [■観点:calcResizeの列幅計算]

表示倍率（`scaleFactor`）が絡むため、単純な `getBoundingClientRect()` では足りません。

- `col.style.width` に px 指定がある列 → **定義値をそのまま使う**（実測しない）
- 指定が無い列 → `th` を実測し、`× scaleFactor / 100` で論理サイズへ補正

求めた幅をカンマ区切り文字列にして `columnWidthsState` へ入れ、`restoreColumnWidths()` で反映させます。PrimeNG が「幅を文字列で保存・復元する」設計なので、それに合わせた形です。

最後の `noDataTop` は「データなし」表示を縦中央に置くための計算で、**描画後に測った値を使うため** `cdr.detectChanges()` を明示的に呼んでいます。OnPush では自動で反映されないためです。

## [■観点:シングルクリックとダブルクリックの判別]

`checkClick()` は 250ms のタイマーで両者を見分けます。

```
1回目クリック → 250msタイマー開始（まだ何も通知しない）
  ├─ 250ms 経過      → rowClicked（シングル確定）
  └─ 途中で2回目が来た → タイマー取消 → rowDoubleClicked（ダブル確定）
```

代償として、**シングルクリックの反応は必ず 250ms 遅れます**。「行クリックで詳細を開く／ダブルクリックで編集」のように両方を使い分ける画面では、この待ちが避けられません。

## [■観点:追加読み込みのスロットリング]

`loadMore()` は `autoLoadMore` の有無で分岐します。通常は `loadMoreDebouncer`（`throttleTime(1500)`）を通すので、**1.5秒に1回しか要求が出ません**。スクロールやキー連打で同じページを何度も取りに行かないための保険です。

`incrementIndex()` では「残り3件を切ったら先読み」も行っており、上下キーで表の末尾へ向かうと自動で次ページが継ぎ足されます。

## [■観点:縮小表示だけPrimeNGの関数を差し替える]

`updateFilter()` は `minimizedView()` のときだけ `_filter` と `sortSingle` を自前実装に差し替えます。理由は元コードのコメント通り、**データ更新のたびに表示位置が先頭へ戻ってしまう** のを止めるためです。左ペインに一覧を出したまま右で詳細を見る画面では、ポーリング更新のたびにスクロールが跳ねると使い物になりません。

## [■観点:CSV出力とインジェクション対策]

`preProcessRows()` の中の `sanitizeCSVCell()` が要点です。CSV のセルが `=`、`+`、`-`、`@` などで始まると、Excel が **数式として実行** してしまいます（CSV インジェクション）。ユーザー入力が混ざる表をそのまま書き出すのは危険なので、無害化を通しています。改行除去（`replace(/\r?\n|\r/g, '')`）も、行が途中で割れるのを防ぐためです。

`dCol.field` を `split('.')` する前に `'%2E'` を `'.'` へ戻しているのは、**列IDそのものにドットを含めたい**（メトリクス名など）ケースがあるためのエスケープ規約です。

## 気になる点（読むときの注意）

- `tableSate` は `tableState` の綴り誤りですが、テンプレート側も同じ名前を使っているはずなので、直すなら両方まとめてです。
- `orderColumns()` の `this.visibleColumns().sort(...)` は、`computed` が返した配列を **その場で破壊的に並べ替え** ています。`computed` の結果は不変に扱うのが原則なので、本来は `[...].sort()` か、`computed` 側に並べ替えを含めるのが素直です。
- 同様に `updateColumnsWidth()` も `columns[colIndex].style = ...` と列定義オブジェクトを直接書き換えています。Store 由来のオブジェクトなら、NgRx の不変性前提と衝突する可能性があります。
- `updateColumnsWidth()` の引数 `delta` は、直後に `delta = width - parseInt(...)` で必ず上書きされるため、実質使われていません。

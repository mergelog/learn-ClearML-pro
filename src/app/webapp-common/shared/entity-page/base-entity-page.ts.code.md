````ts
import {
  Component, computed,                                       // Component=デコレータ / computed=他Signalから導出する派生Signal
  DestroyRef, effect,                                         // DestroyRef=破棄タイミングの参照 / effect=Signal変化に追従する副作用
  inject,                                                     // コンストラクタ引数を使わないDI取得API
  OnDestroy,                                                  // 破棄時フックのインターフェース
  Signal,                                                     // 読み取り専用リアクティブ値の型
  viewChild                                                   // テンプレート内の子を取得するSignalクエリ
} from '@angular/core';
import {Action, ActionCreator, MemoizedSelector, Store} from '@ngrx/store';   // NgRxのAction/ActionCreator/メモ化セレクタの型とStore本体
import {combineLatest, Observable, of, switchMap} from 'rxjs';                // combineLatest=複数ストリームの最新値合成 / of=即値 / switchMap=ストリーム差し替え
import {debounceTime, filter, map, take, tap} from 'rxjs/operators';          // 間引き・絞り込み・変換・1件で完了・副作用
import {
  selectDefaultNestedModeForFeature,                          // 機能ごとの既定ネスト表示モード
  selectIsArchivedMode, selectIsDeepMode, selectMinimizedView, selectRouterProjectId,  // アーカイブ表示中か / サブプロジェクトまで潜るか / 詳細パネルで一覧が縮小中か / URL上のプロジェクトID
  selectSelectedProject,                                      // 現在選択中のプロジェクト実体
  selectSelectedProjectUsers,                                 // フィルター候補に使うプロジェクト参加ユーザー
  selectTablesFilterProjectsOptions                           // 「プロジェクト」列フィルターの候補一覧
} from '../../core/reducers/projects.reducer';
import {SplitComponent, SplitGutterInteractionEvent} from 'angular-split';    // 一覧/詳細の分割ペインUIと、ガター操作イベント型
import {EntityTypeEnum} from '~/shared/constants/non-common-consts';          // experiment / model / dataset などエンティティ種別
import {IFooterState, ItemFooterModel} from './footer-items/footer-items.models';  // 複数選択時に出る一括操作フッターの状態型と項目モデル
import {
  CountAvailableAndIsDisableSelectedFiltered,                 // 「対象n件・実行可否」を表すフッター項目用の集計型
  selectionAllHasExample,                                     // 選択が全てサンプル(読み取り専用)データか
  selectionAllIsArchive,                                      // 選択が全てアーカイブ済みか
  selectionExamplesCount,                                     // 選択中のサンプルデータ一覧
  selectionHasExample                                         // 選択にサンプルデータが1件でも含まれるか
} from './items.utils';
import {ActivatedRoute, Params, Router} from '@angular/router';               // 現在ルート情報 / クエリパラメータ型 / 画面遷移
import {
  getAllSystemProjects,                                       // 全プロジェクト取得(パンくず・移動先候補用)
  getTablesFilterProjectsOptions,                             // プロジェクト列フィルターの候補をサーバ検索
  resetProjectSelection, resetTablesFilterProjectsOptions,    // プロジェクト側の選択解除 / 候補キャッシュ破棄
  setTablesFilterProjectsOptions                              // 候補を手元の値で直接差し込む
} from '@common/core/actions/projects.actions';
import {MatDialog} from '@angular/material/dialog';                           // 確認ダイアログを開くためのサービス
import {ConfirmDialogComponent} from '@common/shared/ui-components/overlay/confirm-dialog/confirm-dialog.component';  // 汎用Yes/No確認ダイアログ
import {RefreshService} from '@common/core/services/refresh.service';         // 自動/手動リフレッシュの共通トリガー
import {selectTableModeAwareness} from '@common/projects/common-projects.reducer';   // 表示モード切替の案内を出すべきか
import {setTableModeAwareness} from '@common/projects/common-projects.actions';      // その案内を見たとして無効化する
import {neverShowPopupAgain, toggleCardsCollapsed} from '../../core/actions/layout.actions';  // 「今後表示しない」の記録 / カード折りたたみ切替
import {selectNeverShowPopups, selectTableCardsCollapsed} from '../../core/reducers/view.reducer';  // 抑止済みポップアップID / カード折りたたみ状態
import {isReadOnly} from '@common/shared/utils/is-read-only';                 // 対象が編集不可(サンプル等)か判定
import {setCustomMetrics} from '@common/models/actions/models-view.actions';  // 動的メトリクス列の選択状態を設定
import {IExperimentInfo} from '@features/experiments/shared/experiment-info.model';  // 実験詳細の型
import {HeaderMenuService} from '~/shared/services/header-menu.service';      // ヘッダーのタブ・コンテキストメニュー制御
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';                // コンポーネント破棄で購読を自動解除
import {concatLatestFrom} from '@ngrx/operators';                             // 発火時にだけ他ストリームの最新値を取りに行く(遅延評価)
import {resetTablesFilterParentsOptions} from '@common/experiments/actions/common-experiments-view.actions';  // 親タスク列フィルター候補の破棄
import {selectCurrentUser} from '@common/core/reducers/users-reducer';        // ログイン中ユーザー
import {getCompanyTags} from '@common/core/actions/projects.actions';         // 会社全体のタグ一覧取得

@Component({
  selector: 'sm-base-entity-page',                            // 直接は使わないが、DIとSignal APIを使うためComponentとして宣言
  template: '',                                               // 継承専用なのでビューは持たない
})
export abstract class BaseEntityPageComponent implements OnDestroy {   // 実験/モデル/データセット等の一覧画面に共通する土台
  protected store = inject(Store);                            // 画面状態の唯一の基準となるNgRx Store
  protected route = inject(ActivatedRoute);                   // URLパラメータ・相対遷移の基点
  protected router = inject(Router);
  protected dialog = inject(MatDialog);
  protected refresh = inject(RefreshService);
  protected contextMenuService = inject(HeaderMenuService);
  protected readonly destroyRef = inject(DestroyRef);         // takeUntilDestroyedをコンストラクタ外で使うために保持

  protected entities = [];                                    // サブクラスが一覧データを保持する枠
  protected setSplitSizeAction: ActionCreator<string, (props: {splitSize: number}) => ({splitSize: number} & Action)>;  // 分割幅の保存Action。エンティティごとに異なるためサブクラスが注入
  protected addTag: ActionCreator<string, (props: {tag: string}) => ({tag: string} & Action)>;                          // タグ付与Action。同上
  protected abstract setTableModeAction: ActionCreator<string, (props: {mode: string}) => ({mode: string} & Action)>;   // 表示モード変更Actionは必須なのでabstract
  public shouldOpenDetails = false;                           // 詳細パネルを開くべきか(tableMode由来)
  public checkedExperiments: IExperimentInfo[];               // チェックボックスで複数選択中の実験
  public projectId = this.store.selectSignal(selectRouterProjectId);
  protected splitSize?: Signal<number>;                       // 分割幅。保存対象の画面だけがサブクラスで設定
  public infoDisabled: boolean;                               // ドラッグ中などに詳細パネルのポインタ操作を止めるフラグ
  public footerItems = [] as ItemFooterModel[];               // 一括操作フッターに並べるボタン定義
  public footerState$: Observable<IFooterState<{ id: string }>>;   // そのフッターの表示・活性状態
  public tableModeAwareness$: Observable<boolean>;
  private tableModeAwareness: boolean;                        // 同期的に判定したいので最新値をフィールドにも保持
  protected users = this.store.selectSignal(selectSelectedProjectUsers);
  protected currentUser = this.store.selectSignal(selectCurrentUser);
  protected projectsOptions = this.store.selectSignal(selectTablesFilterProjectsOptions);
  protected defaultNestedModeForFeature = this.store.selectSignal(selectDefaultNestedModeForFeature);
  protected projectDeepMode = this.store.selectSignal(selectIsDeepMode);
  protected cardsCollapsed = this.store.selectSignal(selectTableCardsCollapsed(this.entityType));  // entityTypeはgetterなのでサブクラスの上書きが効く
  protected selectedProject = this.store.selectSignal(selectSelectedProject);
  protected allProjects = computed(() => this.selectedProject()?.id === '*');   // '*'は「全プロジェクト横断」表示を意味する
  protected exampleProject = computed(() => isReadOnly(this.selectedProject())); // サンプルプロジェクトなら編集系操作を抑止
  protected tableMode: Signal<'info' | 'table' | 'compare'>;  // 一覧のみ / 詳細付き / 比較。サブクラスがStoreと接続
  protected parents = [];                                     // 親タスクフィルターの候補

  protected split = viewChild(SplitComponent);                // 分割ペイン本体。サイズ再計算などを直接呼ぶため参照を取得
  private currentSelection: { id: string }[];                 // 直前の選択。選択が0件に戻る瞬間もフッターを流すため保持
  protected showAllSelectedIsActive$: Observable<boolean>;    // 「選択中のみ表示」モードか。サブクラスが設定
  protected minimizedView = this.store.selectSignal(selectMinimizedView(this.getParamId));   // getParamIdはURLからID抽出する関数としてセレクタに渡す
  protected inArchivedMode = this.store.selectSignal(selectIsArchivedMode);

  abstract onFooterHandler({emitValue, item}): void;          // フッター操作の実処理はエンティティごとに異なる

  abstract getSelectedEntities();                             // 現在の選択実体を返す

  abstract afterArchiveChanged();                             // Live/Archive切替後の再取得処理

  protected abstract getParamId(params);                      // URLパラメータから対象IDを取り出す規則

  abstract refreshList(auto: boolean);                        // 一覧再取得。autoは自動更新由来かどうか


  get selectedProjectId() {
    return this.route.parent.snapshot.params.projectId;       // 一覧ルートは親ルートにprojectIdを持つ
  }

  get selectEditMode(): MemoizedSelector<unknown, boolean> | undefined {
    return undefined;                                         // 編集中に自動更新を止めたい画面だけが上書きする
  }
  protected get entityType(): EntityTypeEnum {
    return undefined;                                         // サブクラスで必ず上書きされる前提の既定値
  };

  protected constructor() {                                   // abstractなので直接newされない
    this.store.dispatch(getAllSystemProjects({}));            // パンくず・移動先候補のために全プロジェクトを先に取得

    effect(() => {
      if (this.tableMode) {                                   // tableModeはsuper()の後にサブクラスが設定するため存在確認が要る
        this.shouldOpenDetails = this.tableMode() !== 'table'; // table以外(info/compare)なら詳細側を開く
      }
    });

    this.tableModeAwareness$ = this.store.select(selectTableModeAwareness)
      .pipe(
        filter(featuresAwareness => featuresAwareness !== null && featuresAwareness !== undefined),  // 未初期化(null/undefined)は通さない
        tap(aware => this.tableModeAwareness = aware)         // 同期判定用にフィールドへ写す
      );


    this.refresh.tick
      .pipe(
        takeUntilDestroyed(),                                 // コンストラクタ内なのでDestroyRef省略形が使える
        concatLatestFrom(() => [
          ...(this.selectEditMode ? [this.store.select(this.selectEditMode)] : []),   // 編集モードを持つ画面だけ合成対象に加える
          this.showAllSelectedIsActive$]                      // 遅延評価なので、サブクラスの代入後に解決される
        ),
        filter(([tick, edit, showAllSelectedIsActive]) => !tick && !edit && !showAllSelectedIsActive),  // 手動更新中・編集中・選択のみ表示中は自動更新を見送る
        map(([auto]) => auto)                                 // 以降はtick値(自動更新かどうか)だけ使う
      )
      .subscribe(auto => this.refreshList(auto !== false));   // falseのときだけ手動扱い、それ以外は自動更新として再取得
    this.setupBreadcrumbsOptions();
  }


  ngOnDestroy(): void {
    this.footerItems = [];                                    // 次画面にフッター項目を持ち越さない
    this.store.dispatch(setCustomMetrics({metrics: null}));    // 動的メトリクス列の選択もリセット
  }

  closePanel(queryParams?: Params) {                          // 詳細/比較パネルを閉じて一覧のみに戻す
    window.setTimeout(() => this.infoDisabled = false);       // 閉じるアニメーション後に操作を再度許可
    this.store.dispatch(this.setTableModeAction({mode: 'table'}));
    return this.router.navigate(this.minimizedView() ? [{}] : [], {   // 縮小表示中は空マトリクスパラメータで子ルートを外す
      relativeTo: this.route,
      queryParamsHandling: 'merge',                           // 既存のクエリ(フィルター等)は維持
      queryParams
    });
  }

  protected compareView() {
    this.router.navigate(['compare'], {relativeTo: this.route, queryParamsHandling: 'preserve'});  // 比較画面へ。クエリは丸ごと引き継ぐ
  }

  splitSizeChange(event: SplitGutterInteractionEvent) {       // ガターをドラッグし終えたとき
    const size = event.sizes[1] as number;                    // 右側(詳細パネル)の比率を採用
    if (this.setSplitSizeAction) {
      this.store.dispatch(this.setSplitSizeAction({splitSize: size}));   // 保存対象の画面のみ永続化
    }
    this.infoDisabled = false;                                // ドラッグ終了で詳細側の操作を戻す
  }

  disableInfoPanel() {
    this.infoDisabled = true;                                 // ドラッグ開始時、iframe等がマウスを奪わないよう無効化
  }

  clickOnSplit() {
    this.infoDisabled = false;
  }

  tableModeUserAware() {                                      // 表示モードの案内をユーザーが認知した
    if (this.tableModeAwareness === true) {
      this.store.dispatch(setTableModeAwareness({awareness: false}));    // 以後は案内を出さない
    }
  }

  tagSelected({tag, emitValue}, entitiesType) {
    this.store.dispatch(this.addTag({
      tag,
      [entitiesType]: emitValue                               // 'experiments' / 'models' など、対象キー名を動的に決める
    }));
  }

  createFooterItems(config: {                                 // サブクラスから渡された素材でフッター状態を組み立てる
    entitiesType: EntityTypeEnum;
    selected$: Observable<{ id: string }[]>;
    showAllSelectedIsActive$: Observable<boolean>;
    data$?: Observable<Record<string, CountAvailableAndIsDisableSelectedFiltered>>;
    tags$?: Observable<string[]>;
    companyTags$?: Observable<string[]>;
    projectTags$?: Observable<string[]>;
    tagsFilterByProject$?: Observable<boolean>;
  }) {
    this.footerState$ = this.createFooterState(
      config.selected$,
      config.data$,
      config.showAllSelectedIsActive$,
      this.allProjects() ? of(null) : config.companyTags$,     // 全プロジェクト表示では会社タグ枠を使わない
      this.allProjects() ? config.companyTags$ : config.projectTags$,   // 代わりに会社タグをプロジェクトタグ位置へ流す
      this.allProjects() ? of(true) : config.tagsFilterByProject$       // 全プロジェクト時は常にプロジェクト基準で絞る扱い
    );
  }

  createFooterState<T extends { id: string }>(                // 選択内容からフッターの表示情報を作る中核
    selected$: Observable<T[]>,
    data$?: Observable<Record<string, CountAvailableAndIsDisableSelectedFiltered>>,
    showAllSelectedIsActive$?: Observable<boolean>,
    companyTags$?: Observable<string[]>,
    projectTags$?: Observable<string[]>,
    tagsFilterByProject$?: Observable<boolean>
  ): Observable<IFooterState<T>> {
    data$ = data$ || of({});                                  // 未指定の入力は空の即値Observableで埋め、combineLatestが止まらないようにする
    projectTags$ = projectTags$ || of([]);
    companyTags$ = companyTags$ || of([]);
    tagsFilterByProject$ = tagsFilterByProject$ || of(true);
    return combineLatest(
      [
        selected$,
        data$,
        showAllSelectedIsActive$,
        companyTags$,
        projectTags$,
        tagsFilterByProject$
      ]
    ).pipe(
      takeUntilDestroyed(this.destroyRef),                    // コンストラクタ外なのでDestroyRefを明示
      debounceTime(100),                                      // 連続チェック操作をまとめ、フッターのちらつきを防ぐ
      filter(([selected, , showAllSelectedIsActive]) => selected.length > 1 || this.currentSelection?.length > 1 || showAllSelectedIsActive),  // 複数選択時、または直前が複数選択だった(=解除直後)ときだけ流す
      tap(([selected]) => this.currentSelection = selected),   // 次回の「直前の選択」として記録
      map(([selected, data, showAllSelectedIsActive, companyTags, projectTags, tagsFilterByProject]) => {
          const _selectionAllHasExample = selectionAllHasExample(selected);
          const _selectionHasExample = selectionHasExample(selected);
          const _selectionExamplesCount = selectionExamplesCount(selected);
          const isArchive = this.inArchivedMode() ?? selectionAllIsArchive(selected);   // URL上のアーカイブ表示を優先し、無ければ選択内容から判定
          return {
            selectionHasExample: _selectionHasExample,        // 1件でもサンプルを含む→一部操作を警告/抑止
            selectionAllHasExample: _selectionAllHasExample,
            selectionIsOnlyExamples: _selectionExamplesCount.length === selected.length,   // 全件サンプル→編集系は完全に不可
            selected,
            selectionAllIsArchive: isArchive,                 // アーカイブ/復元どちらのボタンを出すかの判断材料
            data,
            showAllSelectedIsActive,
            companyTags,
            projectTags,
            tagsFilterByProject
          };
        }
      ),
      filter(({selected, data}) => !!selected && !!data)       // 未解決の値が混じった状態は描画させない
    );
  }

  archivedChanged(archived: boolean) {                        // Live↔Archive の切替。選択が失われるため確認を挟む
    const navigate = () => this.closePanel({archive: archived || null}).then(() => {   // falseはURLから消すためnull化
      this.afterArchiveChanged();
      this.store.dispatch(resetProjectSelection());
    });
    this.store.select(selectNeverShowPopups)
      .pipe(
        take(1),                                              // その時点の設定を1回読むだけ
        switchMap(neverShow => {
          if (this.getSelectedEntities().length > 0 && !neverShow?.includes('go-to-archive')) {   // 選択があり、かつ抑止されていないときだけ確認
            return this.dialog.open(ConfirmDialogComponent, {
              data: {
                title: 'Are you sure?',
                body: `Navigating between "Live" and "Archive" will deselect your selected ${this.entityType}s.`,
                yes: 'Proceed',
                no: 'Back',
                iconClass: 'al-ico-alert',
                conColor: 'var(--color-warning)',
                showNeverShowAgain: true                      // 「今後表示しない」チェックを出す
              }
            }).afterClosed();                                 // 閉じた結果をそのまま下流へ流す
          } else {
            navigate();                                       // 確認不要なら即遷移
            return of(false);                                 // 下流のsubscribeでは何もさせない
          }
        })
      )
      .subscribe((confirmed) => {
        if (confirmed) {
          navigate();
          if (confirmed.neverShowAgain) {                     // 戻り値はboolean兼オブジェクト。チェック時のみ抑止を記録
            this.store.dispatch(neverShowPopupAgain({popupId: 'go-to-archive'}));
          }
        }
      });
  }

  filterSearchChanged({colId, value}: { colId: string; value: { value: string; loadMore?: boolean } }) {   // 列フィルター内の検索欄の入力
    if (colId === 'project.name') {                           // プロジェクト列だけが候補をサーバから引く
      if ((this.projectId() || this.selectedProjectId) === '*') {
        this.store.dispatch(getTablesFilterProjectsOptions({
          searchString: value.value || '',
          loadMore: value.loadMore                            // スクロール追加読み込みかどうか
        }));
      } else {
        this.store.dispatch(setTablesFilterProjectsOptions({
          projects: this.selectedProject() ? [this.selectedProject(),
            ...(this.selectedProject()?.sub_projects ?? [])] : [], scrollId: null   // 単一プロジェクト配下なら自分+サブのみで十分
        }));
      }
    }
  }

  setupBreadcrumbsOptions() {}                                // 既定は何もしない。パンくずを出す画面が上書きする

  public setupHeaderTabs(entitiesType: string, archive: boolean) {
    this.contextMenuService.setupProjectHeaderTabs(entitiesType, this.selectedProjectId, archive);   // ヘッダーのタブ構成をサービスへ委譲
  }

  cardsCollapsedToggle() {
    this.store.dispatch(toggleCardsCollapsed({entityType: this.entityType}));
  }
  resetTablesFilterOptions() {
    this.store.dispatch(resetTablesFilterProjectsOptions());   // 画面離脱時などに候補キャッシュを掃除
    this.store.dispatch(resetTablesFilterParentsOptions());
  }

  protected getCompanyTags() {
    this.store.dispatch(getCompanyTags());                    // タグ付けUIの候補として会社全体のタグを取得
  }
}
````

# BaseEntityPageComponent 解説

## このクラスの役割

実験・モデル・データセットなど「一覧 + 詳細/比較パネル」という同じ形をした画面群の共通土台です。各画面固有のセレクタやActionは持たず、**どの画面でも同じになる手順**だけを引き受けます。具体的には、自動更新の抑制条件、分割ペインの幅保存、複数選択フッターの状態生成、Live/Archive切替の確認ダイアログ、プロジェクト列フィルターの候補取得です。

`@Component({template: ''})` を付けた `abstract class` という形は、Angular で **DI と Signal API を使える抽象基底クラス**を作る定石です。セレクタは登録されていても実際にテンプレートで使われることはありません。

## [■観点:テンプレートメソッドパターン]

`refreshList` / `getSelectedEntities` / `afterArchiveChanged` / `getParamId` / `onFooterHandler` は `abstract`、`entityType` / `selectEditMode` / `setupBreadcrumbsOptions` は「既定値を返すだけの上書き可能メンバ」です。

- **abstract** = サブクラスに実装を強制する穴
- **既定値付き** = 必要な画面だけ上書きする任意フック

この二段構えにより、基底側は「アーカイブ切替のときは確認 → 閉じる → `afterArchiveChanged()`」という*流れ*だけを書き、中身は各画面へ委ねられます。

## [■観点:フィールド初期化と継承の順序]

TypeScript のフィールド初期化子は `super()` 実行直後、サブクラスのフィールド初期化より**前**に走ります。ここが本クラスを読む上での要点です。

```ts
protected cardsCollapsed = this.store.selectSignal(selectTableCardsCollapsed(this.entityType));
```

`entityType` は**フィールドではなく getter**（プロトタイプ上にある）なので、この時点でもサブクラスの上書き実装が呼ばれます。もしサブクラスが `entityType = EntityTypeEnum.experiment` とフィールドで書いていたら、基底の初期化時点ではまだ `undefined` で、狙った値になりません。getter にしてあるのは偶然ではなくこの制約への対処です。

逆に `tableMode` や `showAllSelectedIsActive$` は**サブクラスのフィールド**なので、基底のコンストラクタ実行中はまだ `undefined` です。だからこそ次の2つの書き方が必要になります。

```ts
effect(() => {
  if (this.tableMode) { ... }   // 存在確認が必須
});
```

```ts
concatLatestFrom(() => [ ..., this.showAllSelectedIsActive$])   // 関数なので評価が遅延される
```

`concatLatestFrom` は `withLatestFrom` と違い、**元のストリームが発火して初めて**ファクトリ関数を評価します。購読を組み立てる時点では `showAllSelectedIsActive$` に触らないため、サブクラスの代入が間に合います。

## [■観点:自動更新を「止めるべきとき」だけ止める]

```ts
this.refresh.tick.pipe(
  takeUntilDestroyed(),
  concatLatestFrom(...),
  filter(([tick, edit, showAllSelectedIsActive]) => !tick && !edit && !showAllSelectedIsActive),
  map(([auto]) => auto)
).subscribe(auto => this.refreshList(auto !== false));
```

一覧の定期更新は、**編集中**（入力が巻き戻る）と**「選択中のみ表示」中**（表から行が消える）には走らせてはいけません。その判断をここに一箇所だけ置いています。

注意点として、`selectEditMode` を持たない画面では合成される配列が2要素になり、分割代入の `edit` には実際には `showAllSelectedIsActive` の値が入り、第3要素は `undefined` になります。条件式の結果は偶然同じになりますが、位置依存の分割代入と可変長配列の組み合わせは読み手に優しくない形です。

`takeUntilDestroyed()` を引数なしで呼べるのは**コンストラクタ内＝インジェクションコンテキスト内**だからで、`createFooterState` のようにコンテキスト外で使う箇所では `takeUntilDestroyed(this.destroyRef)` と明示しています。

## [■観点:Signal と RxJS の使い分け]

このクラスは両方を併用していますが、役割は分かれています。

- **Signal**（`store.selectSignal`）… `allProjects()` や `inArchivedMode()` のように、**その瞬間の値を同期的に読みたい**もの。`computed` で派生も作れる
- **RxJS**（`store.select`）… `refresh.tick` や `footerState$` のように、**時間とともに届くイベント列**を合成・間引きしたいもの

`tableModeAwareness$` はその橋渡しの例です。Observable として公開しつつ、`tap` で `tableModeAwareness` フィールドにも最新値を写し、`tableModeUserAware()` から同期的に判定できるようにしています。

## [■観点:フッター状態の生成]

`createFooterState` は「選択の中身」から「フッターに出すべき情報」への変換器です。

`filter` の条件が読みどころです。

```ts
selected.length > 1 || this.currentSelection?.length > 1 || showAllSelectedIsActive
```

第2項の `currentSelection` は**直前の選択**です。これが無いと、複数選択を解除した瞬間の「0件になった」という状態が下流に流れず、フッターが消えないまま残ります。**状態の変化を伝えるために一つ前を覚えておく**、という典型的な手当てです。

`debounceTime(100)` はチェックボックス連打時の再計算とちらつきの抑制、末尾の `filter(({selected, data}) => !!selected && !!data)` は未解決値が混ざった中途半端な状態を描画させないためのガードです。

## [■観点:全プロジェクト表示(`'*'`)という特殊モード]

`selectedProject()?.id === '*'` は「プロジェクト横断表示」を表す規約値です。このモードでは、

- タグの意味が変わる（プロジェクト固有タグではなく会社タグを見る）ため、`createFooterItems` で `companyTags$` を**プロジェクトタグの位置へ流し込む**
- フィルター候補をローカルで作れないため、`filterSearchChanged` ではサーバ検索 (`getTablesFilterProjectsOptions`) に切り替える

というように、同じUIのまま供給源だけを差し替えています。

## [■観点:破壊的操作の前に確認を挟む]

`archivedChanged` は「選択が失われる操作は、失われるものがあるときだけ確認する」を実装しています。

```ts
if (this.getSelectedEntities().length > 0 && !neverShow?.includes('go-to-archive'))
```

選択が空なら確認せず即遷移、ユーザーが「今後表示しない」を選んでいれば以後は聞かない。`take(1)` で設定値を一度だけ読み、`switchMap` でダイアログの結果ストリームへ差し替える流れです。`confirmed` は `false` か `{neverShowAgain}` を持つオブジェクトのどちらかで、真偽値とオブジェクトを同じ変数で受ける点は型としては緩い書き方です。

## [■観点:画面離脱時の後始末]

`ngOnDestroy` での `footerItems = []` と `setCustomMetrics({metrics: null})`、`resetTablesFilterOptions()` での候補キャッシュ破棄は、いずれも**Store がアプリ全体で生き続ける**ことへの対処です。コンポーネントは消えても状態は残るため、次に開いた画面へ前の画面の選択・候補・動的列が漏れないよう明示的に消しています。

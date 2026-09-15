````ts
import {
  ChangeDetectionStrategy,                    // 変更検知をOnPushにするための列挙
  Component,                                  // コンポーネント宣言デコレータ
  computed,                                   // 他のSignalから導出する派生Signal
  effect,                                     // Signalの変化に追従して副作用を走らせる
  input,                                      // 親から受け取る値をSignalとして宣言
  model,                                      // 双方向バインド可能な書き込み可Signal
  output,                                     // 親へイベントを出すEventEmitterのSignal版
  signal,                                     // 書き込み可能な内部状態
  viewChild,                                  // テンプレート内の子コンポーネントを取得するクエリ
} from '@angular/core';
import {ColHeaderFilterTypeEnum, ISmCol, TABLE_SORT_ORDER, TableSortOrderEnum} from '../table.consts';  // フィルター種別enum / 列定義の型 / 昇降順の定数と型
import {addOrRemoveFromArray} from '../../../../utils/shared-utils';   // 配列に無ければ追加・有れば除去するトグル用ユーティリティ
import {
  CheckboxThreeStateListComponent                                     // ON/OFF/除外の3状態チェックボックス一覧。選択肢UIの本体
} from '@common/shared/ui-components/panel/checkbox-three-state-list/checkbox-three-state-list.component';
import {
  TableFilterDurationNumericComponent                                 // 数値範囲でのフィルターUI
} from '@common/shared/ui-components/data/table/table-duration-sort-template/table-filter-duration-numeric/table-filter-duration-numeric.component';
import {
  TableFilterDurationComponent                                        // 日-時-分の経過時間でのフィルターUI
} from '@common/shared/ui-components/data/table/table-duration-sort-template/table-filter-duration/table-filter-duration.component';
import {MenuComponent} from '@common/shared/ui-components/panel/menu/menu.component';                   // 検索欄付きドロップダウンの器。開閉と検索語をイベントで通知
import {TooltipDirective} from '@common/shared/ui-components/indicators/tooltip/tooltip.directive';     // ヘッダー文字が省略されたときの全文表示
import {MenuItemComponent} from '@common/shared/ui-components/panel/menu-item/menu-item.component';     // subOptions(固定項目)を描くための1行
import {ClickStopPropagationDirective} from '@common/shared/ui-components/directives/click-stop-propagation.directive';  // メニュー内クリックで親のソート処理や閉動作が走らないよう伝播を止める
import {
  TableFilterDurationDateTimeComponent                                // 日時(DD-MM-YYYY hh:mm)でのフィルターUI
} from '@common/shared/ui-components/data/table/table-duration-sort-template/table-filter-duration-date-time/table-filter-duration-date-time.component';
import {DotsLoadMoreComponent} from '@common/shared/ui-components/indicators/dots-load-more/dots-load-more.component';   // 「…」の追加読込トリガー。表示されること自体がloadMoreの合図になる
import {MatIcon} from '@angular/material/icon';                        // ソート矢印などのアイコン
import {MatButton} from '@angular/material/button';                    // Any/Allの切替ボタン

@Component({
  selector: 'sm-table-filter-sort',                     // テーブルの各列ヘッダーに1個ずつ置かれる
  templateUrl: './table-filter-sort.component.html',
  styleUrls: ['./table-filter-sort.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,      // 列数×行数ぶん存在しうるので、入力が変わった時だけ再描画する
  imports: [                                            // standaloneコンポーネントなのでNgModuleを介さず依存を直接列挙
    CheckboxThreeStateListComponent,
    TableFilterDurationNumericComponent,
    TableFilterDurationComponent,
    MenuComponent,
    TooltipDirective,
    MenuItemComponent,
    ClickStopPropagationDirective,
    TableFilterDurationDateTimeComponent,
    DotsLoadMoreComponent,
    MatIcon,
    MatButton,
  ],
})
export class TableFilterSortComponent {                 // 列ヘッダーの「ソート矢印＋フィルターメニュー」を担当する表示専用部品
  // Constants
  public readonly TABLE_SORT_ORDER = TABLE_SORT_ORDER;  // テンプレートからは定数importが見えないので、フィールドとして公開し直す
  public readonly FILTER_TYPE = ColHeaderFilterTypeEnum;  // 同上。@switch (column().filterType) の分岐で使う

  // Inputs
  public sortOrder = input<{ index: number; field: string; order: TableSortOrderEnum }>();  // この列の現在のソート状態。index=複数列ソート時の優先順位
  public fixedOptionsSubheader = input<string>();        // subOptions群の上に出す見出し文字(subOptionsが無いときは表示しない)
  public value = input<string[]>([]);                    // 現在この列に掛かっているフィルター値。選択状態の唯一の基準は親側にある
  public subValue = input<string[]>([]);                 // 固定項目側の選択値。valueとは別系統で管理される
  public andFilter = model<boolean>(null);               // Any(OR)かAll(AND)か。親と双方向で共有するのでinputではなくmodel
  public column = input.required<ISmCol>();              // 列定義。sortable/filterable/asyncFilter等の振る舞いがここで決まる
  public searchValue = input<string>('');                // メニュー内検索欄の現在値(状態は親が保持)
  public options = input<{ label: string; value: string; tooltip?: string }[]>();  // 選択肢一覧。undefined=未取得、null=読込中の合図として使い分けられる
  public afterPinned = input<string[]>([]);              // 先頭固定群の直後に置きたい値(例: 自分自身や特別扱いの項目)
  public subOptions = input<{ label: string; value: string }[]>();  // 検索対象外で常に出す固定項目
  public tooltip = input(false);                         // ヘッダー文字にツールチップを付けるか
  smMenu = viewChild(MenuComponent);                     // メニュー本体への参照。現状このクラス内では使われていない


  // Outputs
  public filterChanged = output<{ value: string[]; andFilter?: boolean }>();  // 選択肢の確定値を親へ。自分ではvalueを書き換えない
  public subFilterChanged = output<{ value: string[] }>();                    // 固定項目側の確定値
  public menuClosed = output<void>();                    // 親が候補キャッシュの破棄などに使う
  public menuOpened = output<void>();                    // 親が候補取得を始める合図
  public sortOrderChanged = output<boolean>();           // trueならShift押し=複数列ソートへの追加
  public searchValueChanged = output<{ value: string; loadMore?: boolean }>();  // 検索語の変更。loadMore=trueは「同じ語で続きを取れ」の意味

  // Internal State Signals
  protected pinnedValues = signal<string[]>([]);         // メニューを開いた瞬間の選択値。開いている間だけ先頭固定に使う
  protected pageNumber = signal(1);                      // 何ページ分を表示しているか。ローカル切り出しとサーバ要求の両方で使う
  private lengthBeforeLoad = signal<number | null>(null);  // 追加読込の直前の件数。null=まだ一度も追加読込していない
  protected loading = signal(false); // For "load more" spinner
  protected searching = signal(false); // For initial search spinner


  // Computed Signals
  protected sortedOptions = computed(() => {             // 選択肢を「固定群→afterPinned群→残り」の順に並べ替える
    const options = this.options();
    const pinned = this.pinnedValues();
    const after = this.afterPinned();

    if (!options?.length || (!pinned?.length && !after?.length)) {   // 並べ替える理由が無いときは元配列をそのまま返し、参照を変えない
      return options;
    }

    const afterSet = new Set(after ?? []);               // includesのO(n)検索を避けるため集合化
    const pinnedSet = new Set([null, ...(pinned ?? [])]);  // nullを混ぜているのは、value===nullの特殊項目(「未設定」等)を常に先頭に出すため
    const pinnedTop = options.filter(opt => !afterSet.has(opt.value) && pinnedSet.has(opt.value));  // 選択済み。afterPinned指定があればそちらを優先
    const afterMid = options.filter(opt => afterSet.has(opt.value));
    const rest = options.filter(opt => !afterSet.has(opt.value) && !pinnedSet.has(opt.value));

    return [...pinnedTop, ...afterMid, ...rest];         // 3回走査するが、元の相対順序は各群の中で保たれる
  });

  protected paginatedOptions = computed(() => {          // 実際に子へ渡す選択肢。テンプレートはこれだけを見る
    // When a new search is happening, return null to trigger the spinner in the child component.
    if (this.searching() && !this.noMoreOptions()) {     // nullは子側で「スピナーを出せ」と解釈される契約になっている
      return null;
    }

    const col = this.column();
    const options = this.sortedOptions();
    if (!col.paginatedFilterPageSize || this.noMoreOptions()) {  // ページングしない列、または全件出し終えた後は丸ごと渡す
      return options;
    }
    return options?.slice(0, col.paginatedFilterPageSize * this.pageNumber());  // 手元にある配列から今表示すべき分だけ切り出す
  });

  protected noMoreOptions = computed(() => {             // 「…」を出すか消すかの判定。追加読込の終端検出そのもの
    const col = this.column();
    const options = this.sortedOptions();

    // Logic for non-async filters (Cycle is removed here)
    if (!col.asyncFilter) {                              // ローカル完結の列。全件が手元にあるので件数比較だけで済む
      if (!options?.length || !col.paginatedFilterPageSize) {
        return true; // No options or no pagination means there are no more to load.
      }
      // Calculate if the number of items that should be displayed exceeds the total available.
      const displayedCount = col.paginatedFilterPageSize * this.pageNumber();
      return displayedCount >= options.length;          // 表示予定数が総数に達したら終端
      }

    // Logic for async filters (remains the same)
    if (this.loading()) {                                // 取得中は終端が確定しないので、まだ有る扱いにして「…」を残す
      return false;
    }

    const prevLength = this.lengthBeforeLoad();

    if (prevLength === null && options && options.length < col.paginatedFilterPageSize) {  // 初回応答が1ページ未満=それで全部
      return true;
    }

    return prevLength !== null && options && options.length === prevLength;  // 追加読込しても件数が増えなかった=サーバ側も打ち止め
  });

  public isFiltered = computed(() => (this.value()?.length ?? 0) > 0 || (this.subValue()?.length ?? 0) > 0);  // フィルターON表示(アイコン・色)の判定

  constructor() {
    // Effect to automatically turn off loading indicators when new options arrive.
    effect(() => {
      if (this.options()) {                              // 新しい選択肢が届いたらスピナーを消す。「応答が来た」ことをoptionsの変化で代理検知している
        this.loading.set(false);
        this.searching.set(false);
      }
    });

    // The problematic effect that reset pageNumber has been removed.
  }

  public switchSortOrder($event: MouseEvent): void {
    this.sortOrderChanged.emit($event.shiftKey);         // 昇順/降順の決定は親に任せ、ここはShift有無だけ伝える
  }

  public onSubFilterChanged(val: { itemValue: string }): void {
    if (val) {
      const newValues = addOrRemoveFromArray(this.subValue(), val.itemValue);  // 押された項目をトグルした新配列を作る(元配列は壊さない)
      this.subFilterChanged.emit({ value: newValues });
    }
  }

  public toggleCombination(): void {                     // Any/Allの切替。どちらのボタンを押しても反転する作り
    this.andFilter.update(filter => !filter);            // 初期値nullからは必ずtrue(=All)になる
    this.emitFilterChanged();                            // 組み合わせ方が変わったら、値は同じでも再検索が必要
  }

  public emitFilterChanged(value?: string[]): void {
    this.filterChanged.emit({
      value: value || this.value(),                      // 引数省略時は現在値を再送。空配列[]はtruthyなので「全解除」も正しく通る
      andFilter: this.andFilter(),
    });
  }

  public loadMore(): void {
    // Don't do anything if we are already loading or know there are no more options.
    if (this.loading() || this.noMoreOptions()) {        // 「…」が見えている間に何度も呼ばれうるので、入口で弾く
      return;
    }

    const col = this.column();

    // For non-async filters, just increment the page number to show more local items
    if (!col.asyncFilter) {
      this.pageNumber.update(num => num + 1);            // 手元の配列を多めに切り出すだけ。通信は発生しない
      return;
    }

    // For async filters, fetch more data from the server
    this.lengthBeforeLoad.set(this.options()?.length ?? 0);  // 応答後に件数が増えたかを比べるため、要求前の件数を控える
    this.pageNumber.update(num => num + 1);
    this.loading.set(true);                              // 解除はconstructorのeffect側が担う
    this.searchValueChanged.emit({ value: this.searchValue() || '', loadMore: true });  // 検索語は据え置き、続きだけを要求
  }

  public searchChanged(value: string): void {
    // A new search is starting.
    this.pageNumber.set(1); // Reset page number on new search.
    this.lengthBeforeLoad.set(null); // Reset for a new search.
    this.searching.set(true); // Show initial spinner.
    this.searchValueChanged.emit({ value });             // loadMoreを付けない=先頭からの取り直し
  }

  public onMenuClose(): void {
    // Need to wait until menu actually close, otherwise loadMore because 3dots is visible
    setTimeout(() => this.pageNumber.set(1), 500);       // 閉じるアニメーション中に「…」が見えたままだとloadMoreが誘発されるため待つ
    this.menuClosed.emit();
  }

  public onMenuOpen(): void {
    this.pinnedValues.set(this.value());                 // 開いた時点の選択を焼き付ける。以後チェックを外しても位置は動かない
    this.menuOpened.emit();
    // If the menu is opened and there are no options, trigger an initial search.
    if (!this.options()?.length) {
      this.searchChanged(this.searchValue());            // 候補が空のまま開かれたら、自分から初回取得を促す
    }
  }
}
````

---

## このコンポーネントの役割

テーブルの列ヘッダー1個ぶんのUI、つまり **ソート矢印** と **フィルターメニュー** を描く部品です。押さえておきたいのは、**自分では何も決めない**という設計です。

- 現在のソート状態 (`sortOrder`)、フィルター値 (`value`)、選択肢 (`options`) はすべて `input` で受け取る
- ユーザー操作は `output` で親へ投げるだけで、`value` を自分で書き換えない
- 例外は `andFilter` の `model` と、後述する表示都合の内部状態 (`pinnedValues` / `pageNumber` / `loading` / `searching`)

一覧画面の状態はNgRx Storeが持っており、この部品はその**投影と入力受付**に徹します。だから `OnPush` で十分に成立します。

## [■観点:input / model / output]

`input()` は読み取り専用、`model()` は親と双方向、`output()` は親への通知です。`andFilter` だけ `model` なのは、Any/All の切替が「押したら即座にこの部品の中で反転し、同時に親にも反映したい」値だからです。

```ts
public column = input.required<ISmCol>();
```

`required` を付けると、親が渡し忘れた場合にコンパイル時に落ちます。この部品は `column()` が無いと何も描けないので妥当です。

`smMenu = viewChild(MenuComponent)` は取得しているだけで、このクラスからは一度も使われていません。テンプレート側の `#smMenu` も同様に参照されていないので、実質的に不要なコードです。

## [■観点:options の undefined / null / 配列という3値]

このコンポーネントの分かりにくさは、ほぼここに集約されています。`options` は3つの状態を持ちます。

| 値 | 意味 |
|---|---|
| `undefined` | まだ取得していない（`onMenuOpen` で初回取得を促す） |
| `null` | 親が「取得中」を表明している |
| 配列 | 取得済み（空配列なら該当なし） |

テンプレートの `@if (options() !== null && !noMoreOptions())` は、**取得中は「…」を出さない**ためのガードです。そして `paginatedOptions` は自分でも `null` を返し、子の `CheckboxThreeStateListComponent` 側の `@if (options() === null)` がスピナーを描きます。

つまり「`null` はスピナー」という**暗黙の取り決めが親・自分・子の3者にまたがって**います。型は `T[] | null | undefined` でしかないので、読む側はコードを追わないと意味が分かりません。状態を `'idle' | 'loading' | 'loaded'` のような明示的な形で持てば、この取り決めは型の上に現れます。

## [■観点:pinnedValues ― 開いた瞬間の選択を固定する]

```ts
public onMenuOpen(): void {
  this.pinnedValues.set(this.value());
```

選択済みの項目は一覧の先頭に出したい。しかし `value()` をそのまま並べ替えの基準にすると、**チェックを外した瞬間にその行が下へ飛んでいく**ため、連続してチェックを外せません。

そこで「開いた時点の選択」をコピーして固定し、メニューを開いている間はその順序を維持します。`value()` の変化に追従しない**意図的なスナップショット**です。Signalは基本的に追従させる道具ですが、ここでは追従しないことが正しい挙動になります。

## [■観点:sortedOptions ― 3群に分けて並べ直す]

`filter` を3回かけて `pinnedTop` / `afterMid` / `rest` を作り、連結しています。ソート関数を書くより、**群ごとの優先順位**をそのまま表せるのが利点です。各群の中では元配列の順序が保たれます。

2点、読みどころがあります。

```ts
const pinnedSet = new Set([null, ...(pinned ?? [])]);
```

`null` を無条件に混ぜているので、`value === null` の選択肢（「未設定」のような特殊項目）は選択の有無に関わらず常に先頭群へ入ります。

```ts
if (!options?.length || (!pinned?.length && !after?.length)) {
  return options;
}
```

並べ替える必要が無いときは**新しい配列を作らずに元の参照を返す**。`computed` の結果は参照比較で下流に伝わるため、無駄な再描画を防ぐ効果があります。

## [■観点:noMoreOptions ― 終端検出が2系統に分かれる]

「もう読むものが無い」の判定方法が、列の性質で全く違います。

**ローカル完結 (`asyncFilter` が偽)**: 全件が手元にあるので、`ページサイズ × ページ番号 >= 総件数` で確定します。

**サーバ取得 (`asyncFilter` が真)**: サーバが「これで最後」と教えてくれないため、**件数の変化から推測**しています。

- 初回応答が1ページ未満 → それで全部（`prevLength === null` の分岐）
- 追加読込したのに件数が変わらない → サーバ側も打ち止め（`options.length === prevLength`）

`lengthBeforeLoad` はそのための控えで、`null` は「まだ追加読込していない」を表します。`searchChanged` で `null` に戻すのは、検索語が変われば前回件数との比較が無意味になるからです。

この推測方式の弱点は、**追加読込の結果が偶然ちょうど0件だった場合と、本当に終端に達した場合を区別できない**ことです。サーバが総件数や `has_more` を返せば推測は不要になります。

## [■観点:loading の解除をeffectに任せる]

```ts
effect(() => {
  if (this.options()) {
    this.loading.set(false);
    this.searching.set(false);
  }
});
```

`loading` を立てるのは `loadMore`、`searching` を立てるのは `searchChanged`。**下ろすのはこのeffect1箇所**、という分担です。要求と応答が `output` と `input` に分かれている（自分では待てない）ため、「`options` が変化した＝応答が来た」と見なして解除しています。

ただし条件が `if (this.options())` である点に注意が必要です。

- 応答が**空配列**だった場合、`[]` はtruthyなので解除される（これは意図通り）
- 一方で、**自分の要求とは無関係に親が `options` を差し替えた**場合にも解除される

要求と応答が対応付けられていないので、後者を避けられません。本来は要求ごとのIDやRxJSの `switchMap` で紐付ける領域を、Signalの変化検知で簡略化した形です。

## [■観点:setTimeout(500) が要る理由]

```ts
setTimeout(() => this.pageNumber.set(1), 500);
```

コメントにある通り、**閉じるアニメーションの最中に「…」が見えているとloadMoreが発火してしまう**ための待ちです。`pageNumber` を1に戻すと表示件数が減り、`noMoreOptions` が偽に転じて「…」が復活する。それがまだ画面に残っているメニュー内で見えると、`DotsLoadMoreComponent` が読込を要求する、という連鎖です。

500msはアニメーション時間に合わせた数字で、**UIの都合がロジックに漏れている**箇所です。アニメーション時間が変われば壊れますし、閉じた直後に開き直すと初期化が後から走って表示が乱れる可能性もあります。本来はメニューの閉じ切りイベントで初期化するか、そもそも閉じている間は「…」を描かない（可視性で制御する）のが素直です。

## [■観点:コードの残骸]

```ts
// The problematic effect that reset pageNumber has been removed.
```

```ts
// Logic for non-async filters (Cycle is removed here)
```

```ts
// Logic for async filters (remains the same)
```

いずれも**「以前どうだったか」を語るコメント**です。現在のコードが何をしているかは説明しておらず、履歴はGitが持っているので、読む側には情報になりません。とくに1つ目は「問題があったeffect」が何だったのかを知らない読み手には手掛かりにならず、下手にeffectを足し戻す判断を誘発します。消すか、「`pageNumber` は検索とメニュー閉時にのみリセットする」という**現在の規則**として書き直すのが適切です。

なお `noMoreOptions` の非async分岐の閉じ括弧（`return displayedCount >= options.length;` の次行）はインデントが1段ずれています。動作には影響しませんが、フォーマッタを通せば直ります。

````ts
import {                        // Angular コアAPIの名前付きimport
  ChangeDetectionStrategy,      // 変更検知戦略（OnPush指定）に使う列挙
  Component, computed, input,   // コンポーネント定義／派生Signal／入力Signal
  signal, output, model, effect // 内部状態のsignal、出力のoutput、双方向のmodel、副作用のeffect
} from '@angular/core';
import {ISmCol} from '../table.consts';                              // このアプリ独自の列定義型。列がフィルター対象かどうかもここに入る
import {addOrRemoveFromArray} from '../../../../utils/shared-utils'; // 配列に無ければ足し、あれば取り除くトグル用ユーティリティ
import {MatMenuModule} from '@angular/material/menu';                // Material のメニュー。フィルターはメニューの入れ子で作る
import {MatInputModule} from '@angular/material/input';              // 検索入力欄
import {                                                             // 三状態（含む／除外／未選択）チェックボックス一覧
  CheckboxThreeStateListComponent
} from '@common/shared/ui-components/panel/checkbox-three-state-list/checkbox-three-state-list.component';
import {MatListModule} from '@angular/material/list';                                                   // メニュー内リスト
import {MenuItemComponent} from '@common/shared/ui-components/panel/menu-item/menu-item.component';     // チェック付きメニュー項目。固定オプションの表示に使う
import {FilterPipe} from '@common/shared/pipes/filter.pipe';                                            // 配列をキーワードで絞り込むパイプ。検索欄の絞り込みに使う
import {ClickStopPropagationDirective} from '@common/shared/ui-components/directives/click-stop-propagation.directive'; // クリックをメニューへ伝播させないディレクティブ（メニューが閉じるのを防ぐ）
import {DotsLoadMoreComponent} from '@common/shared/ui-components/indicators/dots-load-more/dots-load-more.component'; // 「もっと読み込む」のドットインジケーター
import {IOption} from '@common/constants';                                                              // {label, value} 形式の選択肢型
import {FormsModule} from '@angular/forms';                                                             // [(ngModel)] を使うため
import {MatButton, MatIconButton} from '@angular/material/button';                                      // Material のボタン
import {MatIcon} from '@angular/material/icon';                                                         // Material のアイコン

@Component({                                           // コンポーネントのメタデータ
    selector: 'sm-table-card-filter',                  // テンプレート上では <sm-table-card-filter> として使う
    templateUrl: './table-card-filter.component.html', // 描画テンプレート
    styleUrls: ['./table-card-filter.component.scss'], // スタイル定義
    changeDetection: ChangeDetectionStrategy.OnPush,   // OnPush。Signalや入力が変わったときだけ再描画する
    imports: [                                         // standalone コンポーネントとして使う依存の列挙
        MatMenuModule,                                 // メニュー本体
        MatInputModule,                                // 検索入力欄
        CheckboxThreeStateListComponent,               // 三状態チェックボックス一覧
        MatListModule,                                 // メニュー内リスト
        MenuItemComponent,                             // チェック付きメニュー項目
        FilterPipe,                                    // 検索語での絞り込み
        ClickStopPropagationDirective,                 // クリックの伝播停止
        DotsLoadMoreComponent,                         // 追加読み込み表示
        FormsModule,                                   // ngModel
        MatIconButton,                                 // アイコンボタン
        MatIcon,                                       // アイコン
    MatButton,                                         // ボタン
  ]
})
export class TableCardFilterComponent { // カード表示（詳細ビュー）用のフィルターメニュー

  protected searchTerms = {};                 // 列IDごとの検索語。signalではなく素のオブジェクトで、テンプレートの[(ngModel)]が直接書き換える
  protected pageNumber = signal(1);           // ページ送りの現在位置。paginatedFilterPageSize と掛けて表示件数を決める
  protected loading = signal<boolean>(false); // 読み込み中フラグ。非同期候補の取得中は一覧を空にして出す


  value = input<Record<string, string[]>>({});                                            // 列IDごとの選択済み値
  fixedOptionsSubheader = input<string>();                                                // 固定オプション欄の見出し文言
  subValue = input<string[]>( []);                                                        // 固定オプション側で選択されている値（system_tags用）
  subOptions = input<IOption[]>([]);                                                      // 固定オプションの選択肢
  columns = input.required<ISmCol[]>();                                                   // 列定義。required なので親は必ず渡す
  andFilter = model<boolean>(null);                                                       // 複数選択の結合方法。false=Any(OR) / true=All(AND)。modelなので親と双方向
  options = input.required<Record<string, IOption[]>>();                                  // 列IDごとの選択肢一覧
  filterMatch = input<Record<string, string>>();                                          // 列IDごとのマッチ方法
  protected isFiltering = computed(() =>                                                  // いずれかにフィルターがかかっているか。アイコンの表示とClear allの活性に使う
    (this.value() && Object.values(this.value()).some(options => options?.length > 0)) || // どれかの列に選択値が1つでもあるか
    this.subValue()?.length > 0                                                           // 固定オプション側に選択があるか
  );
  protected optionsFiltered = computed(() => {                                   // メニューに並べる「列ID→選択肢」の組
    if (this.options() && this.columns()) {                                      // 選択肢と列定義が揃っているときだけ
      return this.columns()                                                      // 列定義を起点に
        .filter(column => column.showInCardFilters && this.options()[column.id]) // カードフィルターに出す指定があり、選択肢が用意されている列だけに絞る
        .map(column => ({key: column.id, value: this.options()[column.id]}));    // テンプレートで扱いやすい {key, value} の形へ変換
    }
    return []; // 条件が揃わなければ空配列（テンプレート側で分岐を書かずに済む）
  });

  subFilterChanged = output<{col: ISmCol; value}>(); // 固定オプション側の変更通知
  filterChanged = output<{                           // 通常のフィルター変更通知
        col: string;                                 // 対象の列ID
        value: unknown;                              // 選択された値
        andFilter?: boolean;                         // AND/OR の別
    }>();
  searchValueChanged =  output<{ value: string; loadMore?: boolean; colId: string; async: boolean }>(); // 検索語の変更。非同期候補の取得要求にもなる
  menuClosed = output<ISmCol>();                                                                        // サブメニューが閉じた
  menuOpened = output<ISmCol>();                                                                        // サブメニューが開いた（親はここで候補の取得を始める）
  clearAll = output();                                                                                  // 全フィルターの解除要求

  constructor() {                  // コンストラクタはeffectの設定だけ
    effect(() => {                 // 選択肢が届いたら読み込み中を解除する
      if(this.optionsFiltered()) { // optionsFiltered() を読むことで、選択肢の変化がこのeffectの依存になる
        this.loading.set(false);   // 非同期取得の結果が反映されたとみなして表示を戻す
      }
    });
  }

  emitFilterChangedCheckBox(colId: string, values: string[]) {                         // チェックボックス一覧の変更を親へ通知
    this.filterChanged.emit({col: colId, value: values, andFilter: this.andFilter()}); // 現在のAND/OR設定も一緒に送る
  }

  onSubFilterChanged(col: ISmCol, val) {                                      // 固定オプション（system_tags）側の変更
    if (val) {                                                                // 値があるときだけ処理する
      const newValues = addOrRemoveFromArray(this.subValue(), val.itemValue); // すでに選ばれていれば外し、無ければ足すトグル
      this.subFilterChanged.emit({col, value: newValues});                    // トグル後の配列を親へ渡す
    }
  }

  setSearchTerm($event, col: ISmCol) {                                                                  // 検索欄に入力されたとき
    this.searchTerms[col.id] = $event.target.value;                                                     // 列IDごとに検索語を保持
    if (col.asyncFilter) {                                                                              // 候補をサーバーから取りにいく列なら
      this.searchValueChanged.emit({value: this.searchTerms[col.id], loadMore: false, colId: col.id, async: col.asyncFilter}); // 検索語を親へ送って再取得させる
      setTimeout(() => this.loading.set(true));                                                         // 次のマクロタスクで読み込み中にする（emitによる同期的な解除と順序が競合しないように）
    } else {
      this.startLoadingIndication(); // ローカル絞り込みなら、見た目だけのローディングを短く出す
    }
    this.pageNumber.set(1); // 検索語が変われば1ページ目から表示し直す
  }

  closeMenu(col: ISmCol) {     // サブメニューが閉じたとき
    this.searchTerms = {};     // 検索語をすべて破棄する
    this.pageNumber.set(1);    // ページ送りも初期化
    this.menuClosed.emit(col); // 親へ通知（候補のリセット等に使われる）
  }

  clearSearch(col: ISmCol) {                        // 検索欄のクリアボタン
    this.searchTerms[col.id] = '';                  // その列の検索語を空にする
    this.startLoadingIndication();                  // ローディング表示を短く出し
    this.pageNumber.set(1);                         // ページ送りを初期化して
    this.setSearchTerm({target: {value: ''}}, col); // 空文字で入力されたときと同じ処理を通す（非同期列なら再取得も走る）
  }

  toggleCombination(colId: string) {                                                                // Any/All の切り替え
    this.andFilter.update(filter => !filter);                                                       // AND/OR を反転。modelなので親側の値も同時に変わる
    this.filterChanged.emit({col: colId, value: this.value()[colId], andFilter: this.andFilter()}); // 結合方法が変わると絞り込み結果も変わるので、現在の選択値のまま再通知する
  }

  getColumnByOption(option: {key: string}) {                  // {key, value} の組から元の列定義を引き直す
    return this.columns().find(col => col.id === option.key); // keyは列IDなので、それで探す
  }

  loadMore(col: ISmCol) {                                                                               // 「もっと読み込む」が押されたとき
    if (col.asyncFilter) {                                                                              // 候補をサーバーから取りにいく列なら
      this.searchValueChanged.emit({value: this.searchTerms[col.id], loadMore: true, colId: col.id, async: col.asyncFilter}); // loadMore:true を付けて次ページの取得を要求
    }
    window.setTimeout(() => this.pageNumber.update(num => num + 1), 300); // 取得を待つ時間を見込んで、300ms後に表示件数を1ページ分増やす
  }

  startLoadingIndication() {                              // 短いローディング表示。処理の実体ではなく、体感のための演出
    this.loading.set(true);                               // すぐ点灯し
    window.setTimeout(() => this.loading.set(false), 300) // 300ms後に消灯する
  }
}
````

# TableCardFilterComponent 解説

## このコンポーネントの役割

カード表示（詳細ビュー）のヘッダに出る **フィルターアイコンとそのメニュー** です。表のヘッダに列が並んでいないカード表示では列ごとのフィルターUIを置けないので、代わりに1つのアイコンへ全列のフィルターを畳み込んでいます。

```
[フィルターアイコン]
  └ Status  ▸ ┌ 検索欄 ────────────┐
  └ Tags    ▸ │ Any / All          │
  └ User    ▸ │ ☑ Completed        │
  └ …        │ ☐ Failed           │
  Clear all   │ ⋯ もっと読み込む   │
              └────────────────────┘
```

状態そのものは持たず、**値は親から `input` で受け取り、変更は `output` で返す** のが基本方針です。自前で持つのは検索語・ページ位置・ローディングという、閉じたら捨ててよいUI都合の状態だけです。

## [■観点:optionsFilteredが二つの入力を突き合わせる]

メニューに並ぶ項目は `columns()`（列定義）と `options()`（選択肢）の両方が揃った列だけです。

```ts
.filter(column => column.showInCardFilters && this.options()[column.id])
.map(column => ({key: column.id, value: this.options()[column.id]}))
```

`showInCardFilters` は `ISmCol` 側のフラグで、「この列はカード表示のフィルターにも出す」という宣言です。つまり **どの列をフィルターに出すかは列定義が決め、このコンポーネントは従うだけ** になっています。

`return []` で終わっているのも意図的で、`null` を返さないぶんテンプレート側に `@if` を増やさずに済みます。

## [■観点:searchTermsだけsignalでない理由]

内部状態のうち `pageNumber` と `loading` は `signal` ですが、`searchTerms` は素のオブジェクトです。

```ts
protected searchTerms = {};
```
```html
[(ngModel)]="searchTerms[option.key]"
```

テンプレートの `[(ngModel)]` がプロパティを直接書き換えるためで、`signal` にすると `searchTerms()[key] = …` という書き方ができません。**動くけれども一貫していない** 箇所で、揃えるなら `model` か、`signal<Record<string,string>>` ＋ `update()` で書き換える形になります。

なお `closeMenu()` で `this.searchTerms = {}` とオブジェクトごと差し替えているため、メニューを閉じれば検索語は全列ぶんリセットされます。

## [■観点:同期フィルターと非同期フィルターの二本立て]

同じUIですが、`col.asyncFilter` の有無で中身がまったく違います。

| | `asyncFilter` なし | `asyncFilter` あり |
|---|---|---|
| 絞り込み | テンプレートの `filter` パイプがクライアント側で実行 | `searchValueChanged` を親へ出し、サーバーが絞り込む |
| `loading` の意味 | 見た目だけの演出（`startLoadingIndication`、300msで消える） | 実際の取得待ち。取得中は候補一覧に `null` を渡して空にする |
| 「もっと読み込む」 | `pageNumber` を増やして `slice` の範囲を広げるだけ | `loadMore:true` を親へ出して次ページを取得 |

テンプレート側の該当部分がその分岐です。

```html
[options]="(loading() && col.asyncFilter) ? null : …"
```

`loading()` だけでなく `col.asyncFilter` も条件に入っているので、**同期列では演出中も候補が消えない** ようになっています。

## [■観点:effectでローディングを解除する]

```ts
effect(() => {
  if (this.optionsFiltered()) {
    this.loading.set(false);
  }
});
```

非同期取得の完了を知る手段が「`options` 入力が更新されたこと」しかないため、それを `effect` で拾って消灯しています。`optionsFiltered()` は必ず配列を返すので `if` は実質いつも真で、**判定ではなく依存登録が目的** です（Signal を読まないと effect が再実行されないため）。意図を明示するなら、`if` を外して依存を明示的に読むほうが誤解が少ない書き方です。

## [■観点:setTimeoutが3か所に出てくる理由]

```ts
setTimeout(() => this.loading.set(true));                            // setSearchTerm
window.setTimeout(() => this.pageNumber.update(num => num + 1), 300); // loadMore
window.setTimeout(() => this.loading.set(false), 300);                // startLoadingIndication
```

それぞれ意味が違います。

1. **遅延0** — 直前の `emit()` が同期的に親へ届き、その結果 `options` が更新されて先ほどの effect が `loading` を `false` にしてしまう可能性があります。点灯を次のマクロタスクへ回して順序を確保しています。
2. **300ms** — 取得が返ってくるであろう時間を見込んだ待ち。取得完了を待っているわけではないので、遅い回線では **候補が届く前に表示件数だけ増える** ことがあります。
3. **300ms** — 純粋な演出。一瞬で終わる処理でも「反応した」と見せるための点灯時間です。

1 はタイミングの辻褄合わせ、2 は当て推量、3 は意図的な演出です。同じ `setTimeout` でも信頼度が違うので、読むときに区別しておくとよいです。

## [■観点:clearSearchが自分でsetSearchTermを呼ぶ]

```ts
clearSearch(col: ISmCol) {
  this.searchTerms[col.id] = '';
  this.startLoadingIndication();
  this.pageNumber.set(1);
  this.setSearchTerm({target: {value: ''}}, col);
}
```

最後の行で **イベントオブジェクトを自作して** `setSearchTerm` を呼んでいます。非同期列では「空文字で検索し直す＝候補を全件に戻す」要求を親へ出す必要があるためで、その経路を `setSearchTerm` が一手に握っているからです。

ただし前3行と `setSearchTerm` の中身は重複しており（検索語の設定・ローディング・`pageNumber` のリセット）、実質2回ずつ実行されています。`setSearchTerm` に寄せてしまえば前3行は不要です。

## [■観点:andFilterがmodelである意味]

```ts
andFilter = model<boolean>(null);
```
```ts
this.andFilter.update(filter => !filter);
```

`model` なので `update()` した時点で **親の値も同時に変わります**。そのうえで `filterChanged` も emit しており、親は「AND/OR の値」と「再絞り込みの要求」を別々に受け取る形です。値の反映は双方向バインディングに任せ、副作用（再検索）だけイベントで伝える切り分けになっています。

## 気になる点（読むときの注意）

- `onSubFilterChanged({id: 'system_tags'}, $event)` とテンプレートから呼んでいますが、引数の型は `ISmCol` です。`id` だけのオブジェクトリテラルが通っているのは、`ISmCol` の他プロパティがすべて任意だからで、型としては通っても **実質ダックタイピング** です。
- `filterMatch` 入力は宣言されていますが、このクラスからもテンプレートからも参照されていません。使われていない入力の可能性があります。
- `subFilterChanged` の `value` と `filterChanged` の `value: unknown` は型が付いていません。呼び出し側の実装を見ないと何が飛ぶか分からない箇所です。

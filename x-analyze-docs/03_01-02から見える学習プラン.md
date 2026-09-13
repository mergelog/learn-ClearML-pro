新しい全面調査を見ると、前回の優先順位は少し変えた方がいいです。特に大きい修正は、**「親子通信」だけを勉強対象にするとClearML Webの実際の読みづらさを取りこぼす**ことです。

今回の調査では、`input/output` だけでなく、`viewChild`、テンプレート連携、NgRx、ルーティング、Materialのメニュー・ダイアログ、制御フローがかなり重要だと分かりました。また、`features/data-catalog/` と `features/quality-pipeline/` の扱いも変えます。02 の相違点の表は一度「存在しない」としていましたが、これは 02 側の誤りで、両方とも実在します（`apps/web/src/app/features/` 配下、`.ts` と `.html` で計 75 ファイル）。

しかもこの 2 つは、本プロジェクトで追加された画面なので、使っている仕組みが共通側よりはるかに少ない。container が `store.selectSignal()` で状態を読んで子へ渡し、子の `output()` を action に変換する形で統一されていて、テンプレートの受け渡しも投影も継承も使われていません。

```text
Store
  ↓ selectSignal
container
  ↓ input
dumb
  ↓ output
container
  ↓ dispatch
Store
```

つまり、いま学んでいる `input / output` と、後述する NgRx を、最小構成で一度に読める唯一の場所です。除外するどころか、`webapp-common/` 側の複雑なコードに入る前の踏み台として最初に読むのがよいと思います。

私なら、今後は次の順番にします。

| 順位 | 学習テーマ                                                | 優先度 | ClearML Webでの意味         |
| -: | ---------------------------------------------------- | --- | ----------------------- |
|  1 | `input()` / `output()` / `model()`                   | S   | 全コンポーネント理解の基礎           |
|  2 | standalone `imports` とテンプレート上の親子構築                   | S   | 「このタグの実体は何か」を追う基本       |
|  3 | `#ref` / `viewChild()` / `viewChildren()`            | S   | ClearMLでは非常に多い。99件＋多段連鎖 |
|  4 | `@if` / `@for` / `@defer`                            | S   | 子が「存在するかどうか」自体を決める      |
|  5 | `<ng-content>` / `select`                            | S   | UIコンポーネントの構造理解に必須       |
|  6 | `<ng-template>` / `TemplateRef` / `ngTemplateOutlet` | S   | Tableなど複雑なUIの核心         |
|  7 | 継承＋`override`＋extended系                              | A   | 「実体はどのクラスか」を追うため必要      |
|  8 | `contentChild()` / `contentChildren()` / `pTemplate` | A   | 6を理解した後なら理解しやすい         |
|  9 | NgRx Storeとの接続                                       | A   | 親子を飛び越える最大の通信路          |
| 10 | Material Menu / Dialog                               | A   | ClearMLでは親子通信と同程度に重要    |
| 11 | Router / `router-outlet` / `loadComponent`           | A   | 画面階層を追うために必要            |
| 12 | component `providers` / DI                           | B   | 子孫への依存共有                |
| 13 | `ControlValueAccessor` / Forms                       | B   | 入力部品を触るとき必要             |
| 14 | `exportAs` / Materialのtemplate reference             | B   | 頻繁に見えるが難易度は低い           |
| 15 | Portal / `NgComponentOutlet` / `createComponent`     | C   | 使用範囲が限定的                |
| 16 | iframe / `postMessage` / document events             | C   | 特定機能に遭遇したときでよい          |

一番重要な変更は、**`viewChild` をかなり前に持ってくること**です。

前回はTemplate系を先に勧めましたが、今回の全面調査では `viewChild()` が99件、さらに `viewChildren` や多段連鎖まで存在します。実際に、

```ts
this.table.contextMenuExtended().contextMenu().archiveClicked();
```

のように、

```text
現在のComponent
  ↓
子Component
  ↓
孫Component
  ↓
そのAPI
```

まで辿るコードがあります。

これはClearML Webのコードリーディングではかなり重要です。

したがって今の段階では、

```text
input/output
    ↓
viewChild
    ↓
ng-content
    ↓
TemplateRef
```

くらいがよいです。

さらに今回、`@if` / `@for` を軽視できないことも分かりました。

`@if` が959箇所、`@for` が160箇所あります。

これは単なるHTML記法ではなく、

```html
@if (showDetail()) {
  <sm-detail />
}
```

なら、

```text
親
 ↓
条件がtrue
 ↓
子Componentが初めて生成される
```

という、**コンポーネントツリーそのものを決める仕組み**です。

そして `viewChild()` がSignalなのもここにつながります。

```ts
detail = viewChild(DetailComponent);
```

は最初から必ず子が存在するとは限りません。

```html
@if (selected()) {
  <sm-detail />
}
```

なら、

```text
selected=false
    detail() → undefined

selected=true
    ↓
DetailComponent生成
    ↓
detail() → DetailComponent
```

となります。

今回の資料に `effect()` と `viewChild` を組み合わせたコードが出ているのも、このためです。

なので、これはかなり良い学習セットです。

```text
@if
 ↓
Component生成
 ↓
viewChild Signal更新
 ↓
effectが反応
```

ここはAngular 22らしいコードを読むうえで非常に重要だと思います。

次にTemplate系です。

ここは前回の評価を変えません。

```text
ng-content
    ↓
ng-template
    ↓
TemplateRef
    ↓
ngTemplateOutlet
    ↓
contentChild
    ↓
contentChildren
    ↓
pTemplate
```

この順番が一番自然です。

特に、

```html
<sm-simple-table-2>
  <ng-template let-row="row">
    ...
  </ng-template>
</sm-simple-table-2>
```

という今回新しく見つかったパターンは教材としてかなり良いです。

いきなりPrimeNGの `pTemplate` に行くより、

```text
親が ng-template を渡す
        ↓
子が contentChild(TemplateRef) で取る
        ↓
子が ngTemplateOutlet で描画
```

を理解する方が先です。

その後で、

```text
1個だけ渡す
 ↓
複数渡したくなる
 ↓
名前を付ける必要がある
 ↓
Directive / pTemplate
```

と発展させれば、非常に自然です。

もう一つ大きく優先度を上げたいのがMaterial Menuです。

今回、

* `[matMenuTriggerFor]` 46箇所
* `<mat-menu>` 30箇所
* `MatMenuTrigger` 51件

あります。

しかも、

```html
<button
  #trigger="matMenuTrigger"
  [matMenuTriggerFor]="menuHandle">

<mat-menu #menuHandle="matMenu">
```

という構造は、

```text
テンプレート参照変数
+
exportAs
+
Material Overlay
```

の複合です。

これを理解すると、

```html
#xxx
#xxx="matMenu"
#xxx="matMenuTrigger"
```

の違いもかなり整理できます。

したがって `exportAs` 単独で勉強するより、

**Material Menuを一つ分解して学習する**

方が効率的です。

もう一つ、継承の優先度も上げました。前回はBでしたが、A相当だと思います。

`export class X extends Y` が76件、`override` が154件、抽象基底クラス（`BaseEntityPageComponent`、`BaseTableView` など）が15件あります。

ただ、数の多さより問題なのは、**読むファイルを間違えさせる**ことです。`features/` 側は共通側のコンポーネントを継承して差し替えるのですが、そのとき

```ts
@Component({
  templateUrl: '../../../../webapp-common/models/containers/model-menu/model-menu.component.html',
  styleUrls: ['../../../../webapp-common/models/containers/model-menu/model-menu.component.scss'],
  imports: [TagsMenuComponent, MatIconModule, ...]
})
export class ModelMenuExtendedComponent extends ModelMenuComponent {
```

のように、テンプレートとスタイルを相対パスで共通側のファイルに直接向けています。

```text
features/ のクラス
      ↓ extends
webapp-common/ のクラス（入力・出力・メソッドはこちら）
      ↓ templateUrl は相対パス
webapp-common/ のHTML（テンプレートもこちら）
```

`features/models/containers/model-menu-extended/` を開いても `.html` がない。入力も出力も継承元にしかない。この構造を知らないと、どのファイルを読めばよいかで詰まります。

`imports` だけは継承されないので派生側で並べ直す必要があり、これが順位2の「standalone `imports` とテンプレート上の親子構築」と直結します。さらに継承元の共通側テンプレートには `<ng-content select="[extended]">` という投影口が用意されていて（現状そこへ投影している箇所はない）、順位5のng-contentともつながります。

つまり継承は単独の話題ではなく、2と5を実コードで結ぶ位置にあります。

NgRxについては、今回の数字を見ると「親子関係の後に余裕があれば」ではありません。

```text
dispatch       1013
store.select    903
selectSignal    275
ngrxPush        345
```

です。

つまりClearML Webでは、

```text
親 → input → 子
```

だけ探していると、

「この値どこから来た？」

が分からない場面が大量に出ます。

実際には、

```text
Component A
   ↓ dispatch
Store
   ↓ selectSignal
Component B
```

で、AとBには親子関係がないケースがあります。

ですから頭の中では最初から、

```text
Angularのコンポーネント連携

① 親子
   input
   output
   model

② Template
   ng-content
   TemplateRef
   contentChild

③ 直接参照
   #ref
   viewChild

④ 階層共有
   providers
   DI

⑤ グローバル状態
   NgRx

⑥ Angular外/Overlay
   Dialog
   Menu
   Portal
   iframe
```

という6系統に分けておくとよいです。

そして「今から何をやるか」というレベルまで絞ると、私はこうします。

**直近5テーマだけなら**

1. `viewChild()` / `viewChild.required()` / `viewChildren()`
2. `@if` と `viewChild` の関係
3. `<ng-template>` と `TemplateRef`
4. `ngTemplateOutlet` と `context` / `$implicit`
5. `contentChild()` と `contentChildren()`

です。

現在やっている `input / output / model` はそのまま続けて大丈夫です。文法を一通り触ったら、実物として `features/data-catalog/` を読む。ここは input/output と NgRx しか使っていないので、実コードでありながら最初の題材になります。そのうえで**次は `viewChild` に進む**のが、今回の新情報を踏まえると一番効率がよいと思います。

特に、

```ts
readonly child = viewChild(ChildComponent);
readonly child = viewChild.required(ChildComponent);
```

の違い、

```html
@if (...) {
  <app-child />
}
```

との関係、

```ts
effect(() => {
  this.child()?.doSomething();
});
```

まで一続きで理解すると、今回見つかったClearMLのコードにかなり直接つながります。

そのあとTemplate系へ進み、最後に実際の `table.component.ts` を読む。`data-catalog` から入って `table.component.ts` で終わるこの順序なら、いきなりClearMLの最難関に突っ込まずに済みます。

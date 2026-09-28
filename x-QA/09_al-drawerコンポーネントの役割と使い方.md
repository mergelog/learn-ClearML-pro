# al-drawer（DrawerComponent）の役割と使い方

## 結論

`al-drawer` は Angular Material の `mat-drawer` とは**無関係**な自作コンポーネント。
`al-` は ClearML の前身 allegro.ai 由来の独自プレフィックス（アイコンの `fontSet="al"` / `al-ico-*` と同じ流儀）。
`angular.json` の `prefix` は `sm` なので、このリポジトリには `sm-` と `al-` が混在している。

やっていることは薄い。

- 中身を `<ng-content>` で受け取り、左端に幅 24px の縦長トグルボタンを並べる
- クリックでホスト要素に `collapsed` クラスを付け、幅 24px に潰して中身を `display: none` にする
- 閉じている間は `label` をボタン内に**縦書き**で表示する

つまり「横方向に畳める列」を作るためのラッパー。
**幅・高さ・開閉アニメーションは親コンポーネントの CSS が決める**（後述）。

## ファイル構成

| ファイル | 役割 |
|---|---|
| [drawer.component.ts](../src/app/webapp-common/shared/ui-components/panel/drawer/drawer.component.ts) | `DrawerComponent` 本体。standalone、`OnPush` |
| [drawer.component.html](../src/app/webapp-common/shared/ui-components/panel/drawer/drawer.component.html) | トグルボタン + `<ng-content>` |
| [drawer.component.scss](../src/app/webapp-common/shared/ui-components/panel/drawer/drawer.component.scss) | `:host.collapsed` で幅 24px、縦書きラベル等 |
| [README.md](../src/app/webapp-common/shared/ui-components/panel/drawer/README.md) | 入出力の表は有効だが、`import DrawerModule` の記述は NgModule 時代の残骸 |

## API

| 種別 | 名前 | 型 | 既定値 | 内容 |
|---|---|---|---|---|
| Input | `label` | `string` | `''` | 閉じたときにトグルボタン内へ縦書き表示するテキスト |
| Input | `displayOnHover` | `boolean` | `false` | 開いている間、トグルボタンをホバー時のみ表示する（`opacity` 切替） |
| Output | `toggled` | `EventEmitter<boolean>` | — | 開閉操作の **330ms 後**に「開いているか」を emit |

`closed`（内部状態）と `toggleDrawer()` は public だが、**開閉状態を外から与える Input は無い**。

テスト・自動操作用の目印として `data-id="drawerExpandButton"`（ボタン）と `data-id="drawerCollapseButton"`（開いている間のアイコン）が付いている。

## DOM 構造

```text
al-drawer                          ← :host（display: block、collapsed 時 width: 24px !important）
└─ .drawer-container               ← flex-flow: row-reverse なので「中身 → ボタン」の順で左右が入れ替わる
   ├─ .c-drawer-toggle             ← 描画順は先だが row-reverse で左端に来る
   │  └─ button.drawer-toggle      ← 幅 24px 固定。(click)="toggleDrawer()"
   │     ├─ mat-icon al-ico-previous   ← 開いている間だけ（@if (!closed)）
   │     └─ .label                     ← 閉じている間だけ。writing-mode: tb で縦書き
   └─ .content-container           ← width: calc(100% - 24px)。閉じると display: none
      └─ .fixed-width
         └─ <ng-content>           ← 呼び出し側が入れた中身
```

## 開閉の仕組み

- [drawer.component.ts:36-46](../src/app/webapp-common/shared/ui-components/panel/drawer/drawer.component.ts#L36)

```ts
toggleDrawer() {
  if (!this.closed) {
    // 30px padding for 15px padding for label text
    this.renderer.setStyle(this.closedLabel.nativeElement, 'max-height',
      this.drawerContainer.nativeElement.clientHeight - 30 + 'px');
    this.renderer.addClass(this.ref.nativeElement, 'collapsed');
  } else {
    this.renderer.removeStyle(this.closedLabel.nativeElement, 'max-height');
    this.renderer.removeClass(this.ref.nativeElement, 'collapsed');
  }
  this.closed = !this.closed;
  window.setTimeout(() => this.toggled.emit(!this.closed), 330);
}
```

読みどころは3点。

1. **`collapsed` クラスは `Renderer2` でホスト要素へ直接付ける**。`:host` のスタイルバインディングではなく DOM 操作。
   一方 `.drawer-closed` / `.hidden` はテンプレートの `[class.xxx]` バインディングで、こちらは `closed` の変更を通常の変更検知で反映する（クリックは自コンポーネント由来のイベントなので `OnPush` でも検知される）。
2. **縦書きラベルの `max-height` を閉じる瞬間の実測値で固定する**。`clientHeight - 30` の 30px は上下パディング分。
   縦書きなので高さ制限が無いとラベルが伸び切ってしまうため、`text-overflow: ellipsis` を効かせるために必要。
3. **`toggled` は 330ms 遅延で emit する**。CSS の幅トランジションが終わってから親にサイズ再計算させる意図。

## 使い方

### 最小構成

standalone なので `imports` に `DrawerComponent` を足すだけ。

```ts
import {DrawerComponent} from '@common/shared/ui-components/panel/drawer/drawer.component';

@Component({
  selector: 'sm-foo',
  templateUrl: './foo.component.html',
  imports: [DrawerComponent],
})
```

```html
<al-drawer label="Experiment #1" [displayOnHover]="true" (toggled)="onToggled($event)">
  <div>畳みたい中身</div>
</al-drawer>
```

### 親側の CSS が必須（ここが本題）

`:host` は `display: block` だけで、**幅・高さ・アニメーションを一切持たない**。
親が指定しないと「畳めるが、高さが中身依存でパタンと一瞬で閉じる」状態になる。

実例は [compare-card-list.component.scss:43-52](../src/app/webapp-common/experiments-compare/dumbs/compare-card-list/compare-card-list.component.scss#L43)。

```scss
#experiment-details-container {          // display: flex; flex-direction: row;
  al-drawer {
    height: calc(100% - 16px);
    align-self: flex-start;
    width: 100%;
    margin-right: 4px;
    transition: width 0.4s ease;         // ← 折りたたみアニメーションはここ。部品側には無い
  }

  sm-card2 {
    min-width: 455px;                    // ← 中身の最小幅は呼び出し側で担保する
  }

  ::ng-deep .drawer-container { height: 100%; }   // ← 部品内部の要素は ::ng-deep で触る
  ::ng-deep .fixed-width      { height: 100%; }
}
```

押さえるべき分担。

- **親**: ホストの `width` / `height` / `transition`、および中身の `min-width`
- **部品**: `collapsed` 時の `width: 24px !important`、ボタンの見た目、ラベルの縦書き

部品内部（`.drawer-container`、`.fixed-width`、`.drawer-toggle`）へスタイルを当てるには `::ng-deep` が必要。
角丸の調整例が [experiments-compare.component.scss:63-70](../src/app/webapp-common/experiments-compare/experiments-compare.component.scss#L63) にある。

### `toggled` の使いどころ

幅が変わると、中身にある仮想スクロールや幅計算が古いままになる。そのため実利用側では再計測に使っている。

- [experiment-compare-details.component.html:7](../src/app/webapp-common/experiments-compare/containers/experiment-compare-details/experiment-compare-details.component.html#L7) — `(toggled)="afterResize()"`
- [experiment-compare-base.ts:114-120](../src/app/webapp-common/experiments-compare/containers/experiment-compare-base.ts#L114) — `window:resize` と同じハンドラで幅を再測定し `markForCheck()`

```text
al-drawer (toggled)  ──┐
window:resize        ──┴─▶ afterResize() → nativeWidth 再計算 → markForCheck()
```

## 実際の利用箇所

プロジェクト内の利用は1箇所のみ。

- [compare-card-list.component.html:9-53](../src/app/webapp-common/experiments-compare/dumbs/compare-card-list/compare-card-list.component.html#L9)

実験比較画面で、横並びの各タスク列を `al-drawer` で包んでいる。

```html
<al-drawer
  class="light-theme"
  cdkDrag cdkDragLockAxis="x" cdkDragPreviewContainer="parent"
  [displayOnHover]="i > 0"
  [label]="experiments[i].name"
  (toggled)="toggled.emit($event)"
  (mouseenter)="changeHovered(i, true)"
  (mouseleave)="changeHovered(i, false)">
  <sm-card2 ...>...</sm-card2>
</al-drawer>
```

- `[displayOnHover]="i > 0"` — 先頭列（baseline）はトグルを常時表示、2列目以降はホバー時のみ
- `cdkDrag` と併用して列の並べ替えも兼ねる。ドラッグ中の見た目は部品側の `&.cdk-drag-preview` が引き取る
- `label` に実験名を入れるので、畳むと実験名だけが縦書きの背表紙として残る

## ハマりどころ

1. **開閉状態を外から制御できない。**
   `closed` の Input が無いので、「初期状態は閉じる」「他の操作に連動して閉じる」は素の API では書けない。
   どうしても必要なら `@ViewChild(DrawerComponent)` から `toggleDrawer()` を呼ぶが、`closed` を直接書き換えると `collapsed` クラスと状態がずれるので、必ず `toggleDrawer()` 経由にする。

2. **`toggled` の 330ms は親の `transition: width 0.4s` より短い。**
   現在の利用箇所では 400ms のアニメーション途中（330ms 時点）で `afterResize()` が走る。
   幅の実測値をアニメーション完了後に取りたい場合、この 70ms のずれが誤差になりうる。

3. **縦書きラベルの高さはクリック時点の実測値で固定される。**
   閉じている間に中身の高さが変わっても、ラベルの `max-height` は追従しない（次の開閉で再計算される）。

4. **`content-container` は `width: calc(100% - 24px)` 前提。**
   トグルボタン 24px を差し引いた残りが中身の幅になるので、中身が縮んで困る場合は呼び出し側で `min-width` を与える。

5. **部品側の `transition` は全てコメントアウトされている。**
   `.drawer-toggle` の `background-color` / `color`、`.display-on-hover` の `opacity` いずれも `//transition` になっている。ホバーの明滅を滑らかにしたい場合は親から当てる必要がある。

6. **部品内には `::ng-deep .card-container.bordered { border-color: transparent !important; }` という、`sm-card2` を前提にした記述がある**（`:host.collapsed` 配下）。
   畳んだときにカードの枠線を消すためのもので、`al-drawer` は実質 `sm-card2` と組んで使う想定になっている。

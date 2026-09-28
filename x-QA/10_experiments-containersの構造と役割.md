# `experiments/containers` の構造と役割

## 結論

`src/app/features/experiments/containers/` には、実験一覧や実験詳細の画面に組み込まれる3つのコンポーネントがある。

- `experiment-ouptut/experiment-output.component.*`: 選択した実験の詳細領域を組み立てる画面コンテナ
- `experiment-info-navbar/experiment-info-navbar.component.*`: 詳細画面のタブナビゲーションと、呼び出し側から渡す操作領域を表示
- `experiment-menu-extended/experiment-menu-extended.component.ts`: `webapp-common` の共通実験メニューを機能側の selector として提供

このディレクトリだけでデータ取得や状態管理を完結させる設計ではない。詳細画面の状態と操作は共通基底クラスや NgRx 側にあり、ここには実験機能の画面構成・専用 UI が置かれている。

## ディレクトリ構成

```text
src/app/features/experiments/containers/
├── experiment-info-navbar/
│   ├── experiment-info-navbar.component.ts
│   ├── experiment-info-navbar.component.html
│   └── experiment-info-navbar.component.scss
├── experiment-menu-extended/
│   └── experiment-menu-extended.component.ts
└── experiment-ouptut/
    ├── experiment-output.component.ts
    └── experiment-output.component.html
```

`experiment-ouptut` は `output` の綴り違いだが、ルート設定や import がこのパスを参照している。既存ファイルを移動・改名する場合は、利用箇所もまとめて更新する必要がある。

## 詳細画面の組み立て

```text
experiment-routes.ts
  └─ ExperimentOutputComponent
      ├─ BaseExperimentOutputComponent（共通の状態・操作）
      ├─ ExperimentInfoHeaderComponent（実験名、状態、メニュー等）
      ├─ ExperimentInfoNavbarComponent（タブ、更新操作領域）
      └─ router-outlet（execution / artifacts / scalars / plots / log 等）
```

`experiment-output.component.ts` は `BaseExperimentOutputComponent` を継承し、詳細画面のテンプレートと必要な UI 部品を宣言する薄いコンテナになっている。独自の処理メソッドはなく、共通基底クラスの処理を画面に結び付けている。

基底クラスはルートの実験 ID を読み、NgRx Store から選択中の実験や表示設定を取得する。また、実験詳細の取得・リセット、更新、表示切替などの action dispatch と購読解除も担当する。画面の HTML は、ヘッダーとナビゲーションを表示し、子ルートを `router-outlet` に描画する。

- [ExperimentOutputComponent の定義](../src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.ts#L16)
- [ExperimentOutputComponent のテンプレート](../src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.html#L1)
- [共通基底クラスの Store 接続と初期化](../src/app/webapp-common/experiments/containers/experiment-ouptut/base-experiment-output.component.ts#L55)
- [共通基底クラスの破棄処理と画面操作](../src/app/webapp-common/experiments/containers/experiment-ouptut/base-experiment-output.component.ts#L150)

## ナビゲーション部品

`ExperimentInfoNavbarComponent` は `minimized` と `splitSize` を入力で受け、共通 `RouterTabNavBarComponent` にタブ情報を渡す。タブの URL と表示名は `features/experiments/experiments.consts.ts` の `infoTabLinks` に定義されている。

更新ボタンやグラフ操作をナビバー内に固定せず、`ng-content select="[refresh]"` で呼び出し元から差し込めるようにしている。実際の差し込み内容は `experiment-output.component.html` にあり、選択中のタブや最小化状態に応じて更新ボタンやグラフ設定を表示する。

- [ナビバーの入力とタブ情報](../src/app/features/experiments/containers/experiment-info-navbar/experiment-info-navbar.component.ts#L6)
- [ナビバーのテンプレートと projection slot](../src/app/features/experiments/containers/experiment-info-navbar/experiment-info-navbar.component.html#L1)
- [タブ URL の定義](../src/app/features/experiments/experiments.consts.ts#L19)
- [呼び出し元での操作領域の差し込み](../src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.html#L19)

## 拡張メニュー部品

`ExperimentMenuExtendedComponent` は `ExperimentMenuComponent` を継承する。テンプレートと SCSS は `webapp-common/experiments/shared/components/experiment-menu/` のものを直接参照しているため、メニュー項目や操作ロジックの本体は共通側にある。このクラスは実験機能側の selector `sm-experiment-menu-extended` としてそのメニューを公開する。

主な利用箇所は2つある。

- 実験一覧画面の行コンテキストメニュー: [`experiments.component.html`](../src/app/webapp-common/experiments/experiments.component.html#L140)
- 実験詳細ヘッダーのメニュー: [`experiment-info-header.component.html`](../src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.html#L84)

そのため `experiment-menu-extended` は詳細コンテナ専用ではなく、一覧と詳細ヘッダーの両方から使う共通メニューの機能側エントリである。

- [機能側コンポーネント](../src/app/features/experiments/containers/experiment-menu-extended/experiment-menu-extended.component.ts#L11)
- [共通メニューの実装と入力](../src/app/webapp-common/experiments/shared/components/experiment-menu/experiment-menu.component.ts#L81)

## ルートとの関係

ルート設定では、通常の詳細ペイン `:experimentId` と、全画面表示用の `:experimentId/output` の両方が `ExperimentOutputComponent` を読み込む。詳細画面内の `execution`、`artifacts`、`scalars`、`plots`、`log` などは子ルートであり、テンプレート末尾の `router-outlet` に表示される。

- [`:experimentId` と子タブの定義](../src/app/webapp-common/experiments/experiment-routes.ts#L76)
- [全画面表示ルート](../src/app/webapp-common/experiments/experiment-routes.ts#L180)
- [子画面の `router-outlet`](../src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.html#L74)

## まとめ

```text
containers/
  ├─ ExperimentOutputComponent      詳細画面の構成
  ├─ ExperimentInfoNavbarComponent  タブナビゲーションと操作領域の受け渡し
  └─ ExperimentMenuExtendedComponent 共通メニューの機能側 selector
```

詳細画面の処理基盤は `webapp-common` の `BaseExperimentOutputComponent`、詳細タブの画面はルート先の各コンポーネント、メニュー本体は共通 `ExperimentMenuComponent` に分かれている。`features/experiments/containers` はそれらを実験機能の画面として組み合わせる層と読める。

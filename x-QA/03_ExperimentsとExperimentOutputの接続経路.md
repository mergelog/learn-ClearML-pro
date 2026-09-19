# sm-common-experiments と sm-experiment-output の接続経路

## 結論

`sm-experiment-output` は `sm-common-experiments` のテンプレートに静的に記述されていない。
`sm-common-experiments` 内の `router-outlet` に対し、Angular Router が `:experimentId` 子ルートのコンポーネントとして動的に生成する。

したがって、ブラウザの DOM では親子関係に見える一方、テンプレートをタグ検索しても直接の親子関係は見つからない。

## コンポーネント配置経路

```text
App routing
  projects/:projectId/tasks
    └─ experiment-routes.ts: path ''
         └─ ExperimentsComponent (sm-common-experiments)
              └─ experiments.component.html の router-outlet
                   └─ path ':experimentId'
                        └─ ExperimentOutputComponent (sm-experiment-output)
```

### 親コンポーネントの outlet

`ExperimentsComponent` は右側の `as-split-area` に `router-outlet` を配置する。ここが `ExperimentOutputComponent` の実際の差し込み先となる。

- [`src/app/webapp-common/experiments/experiments.component.html:120-127`](../src/app/webapp-common/experiments/experiments.component.html#L120)

```html
<as-split-area ...>
  <router-outlet></router-outlet>
</as-split-area>
```

### 子ルート

`experiment-routes.ts` では、空パスの親ルートが `ExperimentsComponent` をロードし、その `children` に `:experimentId` を定義する。
この子ルートが `ExperimentOutputComponent` を lazy load するため、URL が実験 ID を含むときだけ outlet に表示される。

- [`src/app/webapp-common/experiments/experiment-routes.ts:44-51`](../src/app/webapp-common/experiments/experiment-routes.ts#L44)
- [`src/app/webapp-common/experiments/experiment-routes.ts:76-80`](../src/app/webapp-common/experiments/experiment-routes.ts#L76)

```ts
{
  path: '',
  loadComponent: () => import('@common/experiments/experiments.component')
    .then(m => m.ExperimentsComponent),
  children: [
    {
      path: ':experimentId',
      loadComponent: () => import('@features/experiments/containers/experiment-ouptut/experiment-output.component')
        .then(m => m.ExperimentOutputComponent)
    }
  ]
}
```

`ExperimentOutputComponent` の selector は `sm-experiment-output`。

- [`src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.ts:16-18`](../src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.ts#L16)

## 行クリックから表示まで

```text
テーブル行クリック
  → ExperimentsTableComponent.experimentSelectionChanged.emit()
  → ExperimentsComponent.experimentSelectionChanged()
  → experimentSelectionChanged action
  → CommonExperimentsViewEffects.experimentSelectionChanged
  → Router.navigate(['projects', projectId, 'tasks', experimentId])
  → ':experimentId' 子ルートに一致
  → 親の router-outlet に sm-experiment-output を生成
```

主な実装箇所:

- テーブルのイベント発火: [`src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts:336-339`](../src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L336)
- 親コンポーネントでの action dispatch: [`src/app/webapp-common/experiments/experiments.component.ts:542-556`](../src/app/webapp-common/experiments/experiments.component.ts#L542)
- 遷移 Effect: [`src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts:388-394`](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L388)
- URL 構築と `Router.navigate`: [`src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts:743-758`](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L743)

### `navigateAfterExperimentSelectionChanged()` による実際の遷移

`experimentSelectionChanged` Effect は `tap` で `navigateAfterExperimentSelectionChanged()` を呼び出す。
このメソッドが、実験を選択した場合に `Router.navigate()` を実行する実体である。Effect 内の `mergeMap` はテーブルモードを `info` に変更するだけで、画面遷移は行わない。

```ts
navigateAfterExperimentSelectionChanged(selectedExperiment, experimentProject, routeConfig, replaceUrl) {
  const module = routeConfig.includes('datasets') ? 'datasets/simple'
    : routeConfig.includes('pipelines') ? 'pipelines' : 'projects';

  if (selectedExperiment) {
    this.router.navigate(
      [module, experimentProject, 'tasks', selectedExperiment.id],
      {queryParamsHandling: 'preserve'}
    );
  }
}
```

実際の実装では、現在開いている子タブ（`scalars` など）を `activeChildUrl` として URL 末尾へ維持する。選択対象がない場合は `tasks` 一覧へ戻る。

- [`navigateAfterExperimentSelectionChanged()` の実装: src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts:743-758](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L743)

## 補足

`ExperimentOutputComponent` 自身にも `router-outlet` があり、`scalars`、`plots`、`log` などはさらにその outlet に子ルートとして表示される。
これは `sm-common-experiments` と `sm-experiment-output` の間ではなく、`sm-experiment-output` の内部にある次の階層のルーティングである。

- [`src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.html:73-75`](../src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.html#L73)
- [`src/app/webapp-common/experiments/experiment-routes.ts:150-174`](../src/app/webapp-common/experiments/experiment-routes.ts#L150)

## AIチャット

コード上で直接タグが入れ子になっていない理由は、`<router-outlet>` によるルート子コンポーネントの動的配置だからです。

接続は次の経路です。

```text
sm-common-experiments
  └─ experiments.component.html の <router-outlet>
       └─ route ':experimentId'
            └─ lazy-load ExperimentOutputComponent
                 └─ sm-experiment-output
```

根拠:

- 親の `sm-common-experiments` は、右ペインに `<router-outlet>` だけを置いています。  
  [experiments.component.html:120](../src/app/webapp-common/experiments/experiments.component.html#120)

- その親ルートの子 `:experimentId` が `ExperimentOutputComponent` を lazy-load しています。  
  [experiment-routes.ts:44](../src/app/webapp-common/experiments/experiment-routes.ts#44)  
  [experiment-routes.ts:76](../src/app/webapp-common/experiments/experiment-routes.ts#76)

- `ExperimentOutputComponent` の selector が `sm-experiment-output` です。  
  [experiment-output.component.ts:16](../src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.ts#16)

クリック起点も追うと、テーブル行クリック → `experimentSelectionChanged` → NgRx Effect が `/projects/{project}/tasks/{experimentId}` へ遷移 → Angular Router が親 outlet に `sm-experiment-output` を生成、です。  
[experiments-table.component.ts:336](../src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#336)  
[experiments.component.ts:542](../src/app/webapp-common/experiments/experiments.component.ts#542)  
[common-experiments-view.effects.ts:388](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#388)  
[common-experiments-view.effects.ts:743](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#743)

つまりブラウザの DOM 上では親子ですが、テンプレートの静的な親子ではなく、Router が runtime で差し込んだ親子関係です。

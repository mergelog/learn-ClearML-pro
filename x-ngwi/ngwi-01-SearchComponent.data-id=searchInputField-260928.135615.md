# data-id="searchInputField" 解析結果

## searchInputField の 遷移

- 14. [▶️:B:V](../src/main.ts#L44) bootstrapApplication(AppRootComponent):44
- 13. [▶️:R:V](../src/app/app.routes.ts#L31) route / → AppComponent:31
- 12. [▶️:O:V](../src/app/app.component.html#L18) &lt;router-outlet class="main-router"&gt;:18
- 11. [▶️:R:V](../src/app/webapp-common/experiments-compare/experiments-compare.routes.ts#L11) route /projects/:projectId/compare-tasks → ExperimentsCompareComponent:11
- 10. [▶️:O:V](../src/app/webapp-common/experiments-compare/experiments-compare.component.html#L53) &lt;router-outlet&gt;:53
- 09. [▶️:R:V](../src/app/webapp-common/experiments-compare/experiments-compare.routes.ts#L49) route /projects/:projectId/compare-tasks/hyper-params/graph → ExperimentCompareHyperParamsGraphComponent:49
- 08. [▶️:h:V](../src/app/webapp-common/experiments-compare/containers/experiment-compare-hyper-params-graph/experiment-compare-hyper-params-graph.component.html#L28) &lt;sm-param-selector&gt;:28
- 07. [▶️:@:C](../src/app/webapp-common/experiments-compare/dumbs/param-selector/param-selector.component.html#L1) @if (!single()):1
- 06. [▶️:h:V](../src/app/webapp-common/experiments-compare/dumbs/param-selector/param-selector.component.html#L4) &lt;sm-menu&gt;:4
- 05. [▶️:h:V](../src/app/webapp-common/shared/ui-components/panel/menu/menu.component.html#L25) &lt;mat-menu&gt;:25
- 04. [▶️:h:V](../src/app/webapp-common/experiments-compare/dumbs/param-selector/param-selector.component.html#L6) &lt;sm-grouped-checked-filter-list&gt;:6
- 03. [▶️:h:V](../src/app/webapp-common/shared/ui-components/data/grouped-checked-filter-list/grouped-checked-filter-list.component.html#L2) &lt;sm-search&gt;:2
- 02. [▶️:h:V](../src/app/webapp-common/shared/ui-components/inputs/search/search.component.html#L14) &lt;input data-id="searchInputField"&gt;:14
- 01. [▶️:h:D](../src/app/webapp-common/shared/ui-components/inputs/search/search.component.html#L19) (focusin)/(focusout)/(dblclick)/(mouseover)/(click) focusInput(true):2,4,6,8,12,19,20
- 通信: この探索範囲では未検出

## 凡例

1個目（種別）

- `:B` bootstrap
- `:R` ルート定義
- `:O` router-outlet（配置先）
- `:h` html
- `:@` 制御フロー

2個目（関係）

- `:V` 表示配置
- `:C` 条件分岐
- `:D` データ受け渡し

## exec command

npx github:mergelog/ng-wiring 'data-id="searchInputField"' --candidate 'cand:1c49da7ebf2c0892311b5e543afa70107755ed26907bebae8c0e7e17aa4a78e1'

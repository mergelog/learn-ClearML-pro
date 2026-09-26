# data-id="createNewTag" 解析結果

## createNewTag の 遷移

- 13. [▶️:h:V](./src/app/webapp-common/dashboard-search/global-search-dialog/global-search-dialog.component.html#L1) &lt;sm-dialog-template&gt;:1
- 12. [▶️:h:V](./src/app/webapp-common/dashboard-search/global-search-dialog/global-search-dialog.component.html#L47) &lt;sm-dashboard-search&gt;:47
- 11. [▶️:h:V](./src/app/features/dashboard-search/containers/dashboard-search/dashboard-search.component.html#L1) &lt;sm-search-results-table&gt;:1
- 10. [▶️:h:V](./src/app/webapp-common/dashboard-search/search-results-table/search-results-table.component.html#L33) &lt;mat-drawer-container&gt;:33
- 09. [▶️:h:V](./src/app/webapp-common/dashboard-search/search-results-table/search-results-table.component.html#L34) &lt;mat-drawer&gt;:34
- 08. [▶️:h:V](./src/app/webapp-common/dashboard-search/search-results-table/search-results-table.component.html#L35) &lt;sm-global-search-filter-container&gt;:35
- 07. [▶️:h:V](./src/app/webapp-common/dashboard-search/global-search-filter-container/global-search-filter-container.component.html#L1) &lt;sm-global-search-filter&gt;:1
- 06. [▶️:h:V](./src/app/webapp-common/dashboard-search/global-search-filter/global-search-filter.component.html#L1) &lt;form&gt;:1
- 05. [▶️:h:V](./src/app/webapp-common/dashboard-search/global-search-filter/global-search-filter.component.html#L100) &lt;sm-tags-menu&gt;:100
- 04. [▶️:h:V](./src/app/webapp-common/shared/ui-components/tags/tags-menu/tags-menu.component.html#L1) &lt;mat-menu&gt;:1
- 03. [▶️:@:C](./src/app/webapp-common/shared/ui-components/tags/tags-menu/tags-menu.component.html#L47) @if (!disableCreateNew() &amp;&amp; filterText()?.trim().length &gt; 0 &amp;&amp; !allTags()?.includes(filterText())):47
- 02. [▶️:h:V](./src/app/webapp-common/shared/ui-components/tags/tags-menu/tags-menu.component.html#L54) &lt;span data-id="createNewTag"&gt;:54
- 01. [▶️:h:D](./src/app/webapp-common/shared/ui-components/tags/tags-menu/tags-menu.component.html#L52) (click)/(keyup.arrowUp)/(keydown.tab)/(keydown.shift.tab) addTag(filterText()):2,52,53
- 操作: 入力と送信ボタンの click は別操作。output は送信メソッドが emit した場合に届く
- 通信: この探索範囲では未検出

## 凡例

1個目（種別）

- `:h` html
- `:@` 制御フロー

2個目（関係）

- `:V` 表示配置
- `:C` 条件分岐
- `:D` データ受け渡し

## exec command

npx github:mergelog/ng-wiring 'data-id="createNewTag"' --candidate 'cand:1ea7a115f28bca045149cb216bdb2e251dc01477e11ae2c8a7b81bd575dad447'

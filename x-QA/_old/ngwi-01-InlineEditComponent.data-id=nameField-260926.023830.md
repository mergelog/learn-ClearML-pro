# data-id=nameField 解析結果

## nameField の 遷移

- 27. [▶️:B:V](./src/main.ts#L44) bootstrapApplication(AppRootComponent):44
- 26. [▶️:R:V](./src/app/app.routes.ts#L31) route / → AppComponent:31
- 25. [▶️:O:V](./src/app/app.component.html#L18) &lt;router-outlet class="main-router"&gt;:18
- 24. [▶️:R:V](./src/app/webapp-common/experiments/experiment-routes.ts#L46) route /projects/:projectId/tasks → ExperimentsComponent:46
- 23. [▶️:L:V](./src/app/webapp-common/experiments/experiments.component.html#L52) &lt;as-split&gt;:52
- 22. [▶️:L:V](./src/app/webapp-common/experiments/experiments.component.html#L120) &lt;as-split-area [visible]="minimizedView()"&gt;:120
- 21. [▶️:O:V](./src/app/webapp-common/experiments/experiments.component.html#L126) &lt;router-outlet&gt;:126
- 20. [▶️:R:V](./src/app/webapp-common/experiments/experiment-routes.ts#L76) route /projects/:projectId/tasks/:experimentId → ExperimentOutputComponent:76
- 19. [▶️:h:V](./src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.html#L6) &lt;sm-experiment-info-header [editable]="!isExample"&gt;:6
- 18. [▶️:h:V](./src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.html#L8) &lt;sm-inline-edit [editable]="editable()"&gt;:8
- 17. [▶️:@:C](./src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L18) @if (editable()):18
- 16. [▶️:h:V](./src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L20) &lt;form #form&gt;:20
- 15. [▶️:@:C](./src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L21) @if (!multiline()):21
- 14. [▶️:h:V](./src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L22) &lt;input data-id="nameField" [(ngModel)]="inlineValue"&gt;:22
- 13. [▶️:h:D](./src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L34) (keydown.tab)/(keydown.enter) form.checkValidity() &amp;&amp; inlineSaved():34,36
- 12. [▶️:C:D](./src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.ts#L94) this.textChanged.emit(this.inlineValue()):94
- 11. [▶️:h:D](./src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.html#L14) ExperimentInfoHeaderComponent.onNameChanged($event):14
- 10. [▶️:C:D](./src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.ts#L121) this.experimentNameChanged.emit(name):121
- 09. [▶️:h:D](./src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.html#L13) ExperimentOutputComponent.updateExperimentName($event):13
- 08. [▶️:@:C](./src/app/webapp-common/experiments/containers/experiment-ouptut/base-experiment-output.component.ts#L179) 条件: if name.trim().length &gt; 2:179
- 07. [▶️:D:D](./src/app/webapp-common/experiments/containers/experiment-ouptut/base-experiment-output.component.ts#L179) this.store.dispatch(experimentDetailsUpdated({id: this.selectedExperiment().id, changes: {name}})):179
- 06. [▶️:E:D](./src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L450) updateExperimentDetails$（ofType(experimentDetailsUpdated)）:450
- 05. [▶️:E:D](./src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L459) this.apiTasks.tasksUpdate({task: action.id, ...action.changes}):459
- 04. [▶️:S:A](./src/app/business-logic/api-services/tasks.service.ts#L2186) POST ${this.basePath}/tasks.update:2186
- 03. [▶️:@:C](./src/app/webapp-common/experiments/containers/experiment-ouptut/base-experiment-output.component.ts#L181) 条件: else of name.trim().length &gt; 2:181
- 02. [▶️:D:D](./src/app/webapp-common/experiments/containers/experiment-ouptut/base-experiment-output.component.ts#L181) this.store.dispatch(addMessage(MESSAGES_SEVERITY.ERROR, 'Name must be more than three letters long')):181
- 01. [▶️:@:C](./src/app/webapp-common/experiments/containers/experiment-ouptut/base-experiment-output.component.ts#L181) 停止: メッセージ表示で終了（通信なし）:181

## 凡例

1個目（種別）

- `:B` bootstrap
- `:R` ルート定義
- `:O` router-outlet（配置先）
- `:L` 外部ライブラリ部品
- `:h` html
- `:@` 制御フロー
- `:C` コンポーネントクラスts
- `:D` ディスパッチ
- `:E` エフェクト
- `:S` サービス

2個目（関係）

- `:V` 表示配置
- `:C` 条件分岐
- `:D` データ受け渡し
- `:A` API通信

## selector path

- body
- sm-root
- sm-app-shell
- div
- div
- sm-common-experiments
- div
- as-split
- as-split-area:nth-child\(2\)
- sm-experiment-output
- div
- sm-experiment-info-header
- div.d-flex.align-items-center
- div.d-flex.align-items-center.experiment-name-cont
- sm-inline-edit
- div
- div.input
- form
- input

## exec command

npx github:mergelog/ng-wiring 'data-id=nameField' --project 'stackup' --selector 'body > sm-root > sm-app-shell > div > div > sm-common-experiments > div > as-split > as-split-area:nth-child(2) > sm-experiment-output > div > sm-experiment-info-header > div.d-flex.align-items-center > div.d-flex.align-items-center.experiment-name-cont > sm-inline-edit > div > div.input > form > input' --candidate 'cand:68e75ac70326ebe0157756ffdc6b7bfafa21a35d1b097f508dbe71dfa1ff9c9e'

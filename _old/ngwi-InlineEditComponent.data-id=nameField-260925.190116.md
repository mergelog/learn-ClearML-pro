# data-id=nameField 解析結果

## nameField の 遷移

- 23. [▶️:B:V](./src/main.ts#L44) bootstrapApplication(AppRootComponent):44
- 22. [▶️:R:V](./src/app/app.routes.ts#L30) route / → AppComponent:30
- 21. [▶️:O:V](./src/app/app.component.html#L18) &lt;router-outlet class="main-router"&gt;:18
- 20. [▶️:R:V](./src/app/webapp-common/experiments/experiment-routes.ts#L45) route /projects/:projectId/tasks → ExperimentsComponent:45
- 19. [▶️:L:V](./src/app/webapp-common/experiments/experiments.component.html#L52) &lt;as-split&gt;:52
- 18. [▶️:L:V](./src/app/webapp-common/experiments/experiments.component.html#L120) &lt;as-split-area [visible]="minimizedView()"&gt;:120
- 17. [▶️:O:V](./src/app/webapp-common/experiments/experiments.component.html#L126) &lt;router-outlet&gt;:126
- 16. [▶️:R:V](./src/app/webapp-common/experiments/experiment-routes.ts#L75) route /projects/:projectId/tasks/:experimentId → ExperimentOutputComponent:75
- 15. [▶️:h:V](./src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.html#L6) &lt;sm-experiment-info-header [editable]="!isExample"&gt;:6
- 14. [▶️:h:V](./src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.html#L8) &lt;sm-inline-edit [editable]="editable()"&gt;:8
- 13. [▶️:@:C](./src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L18) @if (editable()):18
- 12. [▶️:h:V](./src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L20) &lt;form #form&gt;:20
- 11. [▶️:@:C](./src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L21) @if (!multiline()):21
- 10. [▶️:h:V](./src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L22) &lt;input data-id="nameField" [(ngModel)]="inlineValue"&gt;:22
- 09. [▶️:h:D](./src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#L34) (keydown.tab)/(keydown.enter) form.checkValidity() &amp;&amp; inlineSaved():34,36
- 08. [▶️:C:D](./src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.ts#L94) this.textChanged.emit(this.inlineValue()):94
- 07. [▶️:h:D](./src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.html#L14) ExperimentInfoHeaderComponent.onNameChanged($event):14
- 06. [▶️:C:D](./src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.ts#L121) this.experimentNameChanged.emit(name):121
- 05. [▶️:h:D](./src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.html#L13) ExperimentOutputComponent.updateExperimentName($event):13
- 04. [▶️:D:D](./src/app/webapp-common/experiments/containers/experiment-ouptut/base-experiment-output.component.ts#L179) this.store.dispatch(experimentDetailsUpdated({id: this.selectedExperiment().id, changes: {name}})):179
- 03. [▶️:E:D](./src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L450) updateExperimentDetails$（ofType(experimentDetailsUpdated)）:450
- 02. [▶️:E:D](./src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L459) this.apiTasks.tasksUpdate({task: action.id, ...action.changes}):459
- 01. [▶️:S:A](./src/app/business-logic/api-services/tasks.service.ts#L2186) POST ${this.basePath}/tasks.update:2186

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

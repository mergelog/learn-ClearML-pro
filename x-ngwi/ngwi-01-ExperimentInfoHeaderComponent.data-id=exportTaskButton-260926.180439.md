# data-id=exportTaskButton 解析結果

## exportTaskButton の 遷移

- 19. [▶️:B:V](../src/main.ts#L44) bootstrapApplication(AppRootComponent):44
- 18. [▶️:R:V](../src/app/app.routes.ts#L31) route / → AppComponent:31
- 17. [▶️:O:V](../src/app/app.component.html#L18) &lt;router-outlet class="main-router"&gt;:18
- 16. [▶️:R:V](../src/app/webapp-common/experiments/experiment-routes.ts#L46) route /projects/:projectId/tasks → ExperimentsComponent:46
- 15. [▶️:L:V](../src/app/webapp-common/experiments/experiments.component.html#L52) &lt;as-split&gt;:52
- 14. [▶️:L:V](../src/app/webapp-common/experiments/experiments.component.html#L120) &lt;as-split-area [visible]="minimizedView()"&gt;:120
- 13. [▶️:O:V](../src/app/webapp-common/experiments/experiments.component.html#L126) &lt;router-outlet&gt;:126
- 12. [▶️:R:V](../src/app/webapp-common/experiments/experiment-routes.ts#L76) route /projects/:projectId/tasks/:experimentId → ExperimentOutputComponent:76
- 11. [▶️:h:V](../src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.html#L6) &lt;sm-experiment-info-header [editable]="!isExample"&gt;:6
- 10. [▶️:@:C](../src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.html#L60) @if (experiment()?.id):60
- 09. [▶️:h:V](../src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.html#L61) &lt;button data-id="exportTaskButton"&gt;:61
- 08. [▶️:h:D](../src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.html#L64) (click) exportTaskInfo():64
- 07. [▶️:@:C](../src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.ts#L168) 条件: if task?.id:168
- 06. [▶️:D:D](../src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.ts#L168) this.store.dispatch(exportTaskInfo({taskId: task.id})):168
- 05. [▶️:E:D](../src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L651) exportTaskInfo$:651
- 04. [▶️:E:D](../src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L655) ApiTasksService.tasksGetByIdEx():655
- 03. [▶️:S:A](../src/app/business-logic/api-services/tasks.service.ts#L1316) POST ${this.basePath}/tasks.get_by_id_ex:1316
- 02. [▶️:E:D](../src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L668) downloadObjectAsJson(exportData, filename, true):668
- 01. [▶️:E:D](../src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L670) return [addMessage('success', `${action.exportType ?? 'Task'} exported successfully`)]:670

## 凡例

1個目（種別）

- `:B` bootstrap
- `:R` ルート定義
- `:O` router-outlet（配置先）
- `:L` 外部ライブラリ部品
- `:h` html
- `:@` 制御フロー
- `:D` ディスパッチ
- `:E` エフェクト
- `:S` サービス

2個目（関係）

- `:V` 表示配置
- `:C` 条件分岐
- `:D` データ受け渡し
- `:A` API通信

## exec command

npx github:mergelog/ng-wiring 'data-id=exportTaskButton' --candidate 'cand:02a7a97efd772411cff7658af012857892aa721fdd97c74cdcff9ff801897a3f'

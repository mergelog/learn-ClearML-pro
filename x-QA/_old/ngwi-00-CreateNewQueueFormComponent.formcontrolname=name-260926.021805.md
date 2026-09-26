# formcontrolname=name 解析結果

## name の 遷移

- 17. [▶️:C:V](./src/app/webapp-common/workers-and-queues/containers/queues/queues.component.ts#L133) renameQueue() → MatDialog.open:133
- 16. [▶️:C:V](./src/app/webapp-common/workers-and-queues/containers/queues/queues.component.ts#L162) addQueue() → MatDialog.open:162
- 15. [▶️:h:V](./src/app/webapp-common/shared/queue-create-dialog/queue-create-dialog.component.html#L1) &lt;sm-dialog-template&gt;:1
- 14. [▶️:h:V](./src/app/webapp-common/shared/queue-create-dialog/queue-create-dialog.component.html#L2) &lt;sm-create-new-queue-form&gt;:2
- 13. [▶️:h:V](./src/app/webapp-common/shared/queue-create-dialog/create-new-queue-form/create-new-queue-form.component.html#L1) &lt;form&gt;:1
- 12. [▶️:h:V](./src/app/webapp-common/shared/queue-create-dialog/create-new-queue-form/create-new-queue-form.component.html#L2) &lt;mat-form-field&gt;:2
- 11. [▶️:h:V](./src/app/webapp-common/shared/queue-create-dialog/create-new-queue-form/create-new-queue-form.component.html#L4) &lt;input &gt;:4
- 10. [▶️:@:C](./src/app/webapp-common/shared/queue-create-dialog/queue-create-dialog.component.ts#L56) 条件: if this.queueForm.valid / route /workers-and-queues/queues is active / if this.queue.id:56
- 09. [▶️:D:D](./src/app/webapp-common/shared/queue-create-dialog/queue-create-dialog.component.ts#L56) this.store.dispatch(createNewQueueActions.updateQueue({queue: {queue: this.queue.id, name: queue.name, display_name: queue.display_name}})):56
- 08. [▶️:E:D](./src/app/webapp-common/shared/queue-create-dialog/queue-create-dialog.effects.ts#L42) updateQueue（ofType(updateQueue)）:42
- 07. [▶️:E:D](./src/app/webapp-common/shared/queue-create-dialog/queue-create-dialog.effects.ts#L44) mergeMap((action) =&gt; this.queuesApiService.queuesUpdate(action.queue):44
- 06. [▶️:S:A](./src/app/business-logic/api-services/queues.service.ts#L419) POST ${this.basePath}/queues.update:419
- 05. [▶️:@:C](./src/app/webapp-common/shared/queue-create-dialog/queue-create-dialog.component.ts#L58) 条件: if this.queueForm.valid / route /workers-and-queues/queues is active / else of this.queue.id:58
- 04. [▶️:D:D](./src/app/webapp-common/shared/queue-create-dialog/queue-create-dialog.component.ts#L58) this.store.dispatch(createNewQueueActions.createNewQueue(queue)):58
- 03. [▶️:E:D](./src/app/webapp-common/shared/queue-create-dialog/queue-create-dialog.effects.ts#L24) createQueue（ofType(createNewQueue)）:24
- 02. [▶️:E:D](./src/app/webapp-common/shared/queue-create-dialog/queue-create-dialog.effects.ts#L26) mergeMap((action) =&gt; this.queuesApiService.queuesCreate({name: action.name, display_name: action.display_name}):26
- 01. [▶️:S:A](./src/app/business-logic/api-services/queues.service.ts#L147) POST ${this.basePath}/queues.create:147
- 操作: 入力と送信ボタンの click は別操作。output は送信メソッドが emit した場合に届く

## 凡例

1個目（種別）

- `:C` コンポーネントクラスts
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

## selector path

- #mat-mdc-dialog-1
- div
- div
- sm-queue-create-dialog
- sm-dialog-template
- div
- div.generic-container
- sm-create-new-queue-form
- form
- mat-form-field.mat-mdc-form-field.mb-3.mat-mdc-form-field-type-mat-input.mat-mdc-form-field-label-always-float.mat-form-field-appearance-outline.mat-primary.ng-pristine.ng-invalid.mat-form-field-invalid.ng-touched
- div.mat-mdc-text-field-wrapper.mdc-text-field.mdc-text-field--outlined.mdc-text-field--invalid
- div
- div.mat-mdc-form-field-infix

## exec command

npx github:mergelog/ng-wiring 'formcontrolname=name' --project 'stackup' --selector '#mat-mdc-dialog-1 > div > div > sm-queue-create-dialog > sm-dialog-template > div > div.generic-container > sm-create-new-queue-form > form > mat-form-field.mat-mdc-form-field.mb-3.mat-mdc-form-field-type-mat-input.mat-mdc-form-field-label-always-float.mat-form-field-appearance-outline.mat-primary.ng-pristine.ng-invalid.mat-form-field-invalid.ng-touched > div.mat-mdc-text-field-wrapper.mdc-text-field.mdc-text-field--outlined.mdc-text-field--invalid > div > div.mat-mdc-form-field-infix' --candidate 'cand:fc6206bfacbd86ab22e04c854e183677303da35a48cf5b403e9e17599b6b6b81'

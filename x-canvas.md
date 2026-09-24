


欲しいのは以下のようなシンプルな追跡Mapです。
途中の divは不要
但し、以下を表現した行が欠けている
- route /projects/:projectId/tasks
- as-split
- as-split-area
- @ifとか@switchとか分岐のような、コードを読む上で重要な機能的記載

````md
## nameField の 遷移
- 09. [▶️:h:D](src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.html#34) InlineEditComponent.inlineSaved():24  
- 08. [▶️:C:D](src/app/webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.ts#94) this.textChanged.emit(this.inlineValue()):94  
- 07. [▶️:h:D](src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.html#14) ExperimentInfoHeaderComponent.onNameChanged():14  
- 06. [▶️:C:D](src/app/webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.ts#121) this.experimentNameChanged.emit(name):121  
- 05. [▶️:h:D](src/app/features/experiments/containers/experiment-ouptut/experiment-output.component.html#13) ExperimentOutputComponent.updateExperimentName():13  
- 04. [▶️:D:D](src/app/webapp-common/experiments/containers/experiment-ouptut/base-experiment-output.component.ts#179) this.store.dispatch(experimentDetailsUpdated({id: this.selectedExperiment().id, changes: {name}})):179  
- 03. [▶️:E:D](src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#451) CommonExperimentsInfoEffects.updateExperimentDetails$:451  
- 02. [▶️:E:D](src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#459) ApiTasksService.tasksUpdate():459  
- 01. [▶️:S:A](src/app/business-logic/api-services/tasks.service.ts#2186) POST ${basePath}/tasks.update:2186  
````

[▶️:h:D]のような記載は

1個目（必要に応じて追加してください）

:h - html
:C - コンポーネントクラスts
:D - ディスパッチ（コンポーネントより強い）
:E - エフェクト
:S - サービス
:? - 上記以外

2個目（必要に応じて追加してください）

:D  データ受け渡し
:A  API通信
:-  何もなし（何もなしなんてことあるかな as-split とか?）

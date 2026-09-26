# data-id="taskNameField" 解析結果

## taskNameField の 遷移

- 08. [▶️:C:V](../src/app/webapp-common/experiments/experiments.component.ts#L782) newExperiment() → MatDialog.open:782
- 07. [▶️:h:V](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.html#L1) &lt;sm-dialog-template&gt;:1
- 06. [▶️:@:C](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.html#L20) @else:20
- 05. [▶️:h:V](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.html#L21) &lt;mat-stepper&gt;:21
- 04. [▶️:h:V](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.html#L22) &lt;mat-step&gt;:22
- 03. [▶️:h:V](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.html#L23) &lt;form&gt;:23
- 02. [▶️:h:V](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.html#L25) &lt;mat-form-field&gt;:25
- 01. [▶️:h:V](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.html#L27) &lt;input data-id="taskNameField"&gt;:27
- 通信: この探索範囲では未検出

## 凡例

1個目（種別）

- `:C` コンポーネントクラスts
- `:h` html
- `:@` 制御フロー

2個目（関係）

- `:V` 表示配置
- `:C` 条件分岐

## exec command

npx github:mergelog/ng-wiring 'data-id="taskNameField"' --candidate 'cand:7e202fcee1019a1a7b74d25e6995c4a4cb0efd5fd37d53a9bbcaacedf77bb8df'

# API が一度失敗すると、タスクの作成・レポートの作成・キューの削除などが、再読み込みまで何もしなくなる

| 項目 | 内容 |
|---|---|
| カテゴリー | 状態 |
| 不具合内容 | タスクの作成・レポートの作成・キューの削除などで API が一度失敗すると、同じ操作をやり直しても要求が送られず、通知も出ない。キューの削除は確認ダイアログも開かず、レポートの作成は全画面のスピナーが消えない。比較画面の自動更新などは、失敗が累計11回に達すると止まる |
| 期待動作 | 失敗した操作は失敗の通知を出して終わり、次の操作は通常どおり API を呼ぶ |
| 直さないと困ること | 一時的なサーバの失敗や、条件を満たさない削除（タスクが残っているキュー）の後に、利用者はボタンが壊れたと感じるが、再読み込みで直ることに気付きにくい。作成とキュー投入を一度に行うダイアログでは、投入が一度失敗すると、以後に作成したタスクは投入されずに下書きのまま残る（コードから判断） |
| 修正規模 | 長大 |

| 項目 | 内容 |
|---|---|
| 画面 | タスクの作成、レポートの作成、キューの削除、プロファイルの名前の変更ほか（「影響範囲と同種箇所」の表） |
| 観点 | F（NgRx の状態の整合）、I（HTTP とエラー表示） |
| 重大度 | S2 |
| 確度 | 再現済み（タスクの作成・レポートの作成・キューの削除はモック API、比較画面の自動更新は実バックエンドで該当の要求だけを失敗させて確認） |
| 由来 | 上流 |
| 発生条件 | 各操作の API が一度失敗した後（外側の `catchError` の Effect）。または同じ Effect の API がセッション中に累計11回失敗した後（`catchError` の無い Effect）。どちらも再読み込みまで続く |
| 関連 | [07](./07_実験名の保存に失敗すると次の編集の初期値が失敗した名前になる.md)（保存の失敗後の状態の食い違い） |

## 症状

失敗させた後に同じ操作をやり直し、API の要求の数と画面の変化を記録した（[scripts/p2f-effect-dies.spec.ts](./scripts/p2f-effect-dies.spec.ts)）。

| 操作 | 1回目（API を失敗させる） | 2回目以降 | 確認 |
|---|---|---|---|
| タスクの作成（NEW TASK のダイアログを閉じた後の action） | `tasks.create` が失敗し、「Failed to create tasks」の通知が出る | `tasks.create` が送られない。通知も出ない（3回目も同じ） | 再現（モック API） |
| レポートの作成 | `reports.create` が失敗し、エラーの通知が出る | `reports.create` が送られず、全画面のスピナー（`sm-spinner`）が消えない（5秒後も表示中） | 再現（モック API） |
| キューの削除（キューの右クリックメニューの Delete） | 確認ダイアログで Delete を押すと `queues.delete` が失敗し、「Delete Queue failed」の通知が出る | メニューの Delete を押しても確認ダイアログが開かない | 再現（モック API） |
| 比較画面の自動更新（10秒ごとの `refreshIfNeeded`） | 要求を失敗させ続けると、失敗の累計11回目の直後から要求が出なくなる | 要求を失敗させるのをやめても、`refreshIfNeeded` の要求が出ない。10秒ごとの自動更新でも出ない（12秒待って0件） | 再現（実バックエンド。`only_fields: ['last_change']` の `tasks.get_all_ex` だけを `page.route` で 500 にした） |

タスクの作成では、ダイアログでキューを指定すると、作成に成功した後にキューへの投入（`tasks.enqueue`）を別の Effect が行う。投入が一度失敗すると、以後はダイアログでキューを指定してもタスクは作成されるが投入されず、通知も出ない（コードから判断。画面では確かめていない）。

## 再現手順

画面での手順（キューの削除。モック API で確かめた）：

1. ワーカーとキューの画面で QUEUES を開く
2. タスクの入っていないキューを右クリックし、Delete を選ぶ。確認ダイアログで Delete を押す
3. 削除が失敗する（手順2の一覧を取った後に、別の利用者や agent がタスクを積んだ場合など。サーバは `force` の無い `queues.delete` を、キューが空でなければ `QueueNotEmpty` で拒否する）。「Delete Queue failed」が出る
4. 同じキューか別の空のキューを右クリックし、Delete を選ぶ。確認ダイアログが開かない。再読み込みすると開く

スクリプトは [scripts/p2f-effect-dies.spec.ts](./scripts/p2f-effect-dies.spec.ts)。タスクの作成とレポートの作成は、ダイアログを閉じた後にコンポーネントが dispatch するものと同じ action を Store に直接 dispatch した（[experiments.component.ts:787](../src/app/webapp-common/experiments/experiments.component.ts#L787)、[reports-page.component.ts:94](../src/app/webapp-common/reports/reports-page/reports-page.component.ts#L94)）。比較画面は、10秒ごとの自動更新と同じ action（`refreshIfNeeded({payload: true, autoRefresh: true})`）を dispatch して失敗を積み、途中で自動更新の分が1回重なって、合計11回の失敗で止まった。

## 期待する動作

失敗した回の処理だけが失敗の通知で終わり、Effect は次の action を受け付ける。スピナーは失敗の時点で消える。

## 原因

NgRx の Effect は、Observable が完了すると以後その action に反応しない。Effect の書き方が2通りあり、どちらも失敗の後に止まる。

### 外側の `pipe` に `catchError` がある（1回の失敗で止まる）

例：タスクの作成（[common-experiments-view.effects.ts:868](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L868)）

```ts
createExperiment = createEffect(() => {
  return this.actions$.pipe(
    ofType(exActions.createExperiment),
    concatLatestFrom(() => this.store.select(selectSelectedProjectId)),
    switchMap(([action, projectId]) => this.apiTasks.tasksCreate({...}).pipe(
      map(res => exActions.createExperimentSuccess({...}))
    )),
    catchError(error => [addMessage(MESSAGES_SEVERITY.ERROR, `Failed to create tasks.\n...`)])  // ← actions$ の外側
  );
});
```

API の失敗は `switchMap` の内側から外側の流れにエラーとして伝わる。外側の `catchError` は、エラーの代わりに通知の action を1つ流して完了する配列を返すため、`this.actions$` からの流れ全体がそこで完了する。NgRx はエラーでは Effect を再購読するが、完了した Effect は再購読しない。

`EffectSources` は Effect のクラスごとに最初のインスタンスだけを動かす（`groupBy` と `exhaustMap`、`@ngrx/effects` の `toActions()`）。画面を移って同じクラスが再び登録されても、止まった Effect は動き出さない。再読み込みまで続くのはこのためである。

キューの削除は、確認ダイアログを開く処理も同じ Effect の中にある（[queues.effects.ts:89](../src/app/webapp-common/workers-and-queues/effects/queues.effects.ts#L89)）。そのため削除の失敗の後は、確認ダイアログも開かなくなる。レポートの作成は、読み込み中の表示を別の Effect（`activeLoader`、[reports.effects.ts:85](../src/app/webapp-common/reports/reports.effects.ts#L85)）が出し、消す処理だけが止まった Effect の中にあるため、スピナーが残る。

### `catchError` が無い（累計11回の失敗で止まる）

例：比較画面の自動更新（[compare-header-effects.ts:30](../src/app/webapp-common/experiments-compare/effects/compare-header-effects.ts#L30)）。`switchMap` の内側で `tasksGetAllEx` を呼ぶが、`catchError` がどこにも無い。

この場合、API のエラーは Effect のエラーになり、NgRx の既定のエラー処理（`defaultEffectsErrorHandler`）がエラーを `ErrorHandler` に渡して Effect を再購読する。再購読できる回数は10回で、成功しても元に戻らない（残りの回数を引数で減らしながら再購読する作り）。そのため、同じ Effect の API がセッション中に合計11回失敗すると、11回目のエラーで Effect が止まる。比較画面の自動更新は10秒ごとに呼ぶため、サーバの再起動やネットワークの切断が2分ほど続くと止まる。止まった後も、手動の更新ボタン（`refresh.trigger(false)`）はグラフを取り直すため、画面を開き直すまで自動更新だけが止まったことに利用者は気付きにくい。

失敗が11回に達する前も、失敗した回は通知も読み込み中の表示の解除も行われない（成功の側でしか解除の action を出さない Effect が多い）。

## 影響範囲と同種箇所

Effect の構文木を [scripts/p2f-classify-effects.cjs](./scripts/p2f-classify-effects.cjs) で分類した（§1.2 の対象外を除く269件）。

### 外側の `catchError` で1回の失敗で止まるもの（17件）

| Effect | 操作 | 止まった後の症状 | 失敗の起きやすさ |
|---|---|---|---|
| [createExperiment](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L868) | タスクの作成 | 作成されず、通知も出ない | サーバの失敗・通信の失敗 |
| [enqueueCreateExperiment](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L937) | 作成したタスクのキュー投入 | タスクは作成されるが投入されず、通知も出ない | キューが削除された後など |
| [createReport$](../src/app/webapp-common/reports/reports.effects.ts#L91) | レポートの作成 | 作成されず、全画面のスピナーが消えない | 新しいプロジェクト名を指定した場合のプロジェクトの作成の失敗も含む |
| [getReport](../src/app/webapp-common/reports/reports.effects.ts#L195) | レポートを開く | 以後どのレポートも読み込まれない | サーバの失敗 |
| [getReportsTags](../src/app/webapp-common/reports/reports.effects.ts#L175) | レポートのタグの一覧 | タグの一覧が更新されない | 同上 |
| [deleteQueues](../src/app/webapp-common/workers-and-queues/effects/queues.effects.ts#L89) | キューの削除 | 確認ダイアログが開かない | タスクが積まれたキュー（`QueueNotEmpty`）、別の利用者が削除済み |
| [updateCurrentUser](../src/app/webapp-common/core/effects/users.effects.ts#L63) | プロファイルの名前の変更 | 名前が変わらず、通知も出ない | サーバの失敗 |
| [getApiVersion](../src/app/webapp-common/core/effects/users.effects.ts#L54) | 設定画面の下部のバージョン表示 | 以後バージョンを取り直さない | 同上 |
| [fetchExperimentPlots$](../src/app/webapp-common/experiments/effects/common-experiment-output.effects.ts#L61) | タスクの PLOTS | 以後どのタスクのグラフも読み込まれない | サーバの失敗 |
| [fetchExperimentPlots$（モデル）](../src/app/webapp-common/models/effects/models-info.effects.ts#L229) | モデルの PLOTS | 同上 | 同上 |
| [getMultiPlotCharts](../src/app/webapp-common/experiments-compare/effects/experiments-compare-charts.effects.ts#L143) | 比較画面の PLOTS | 同上 | 同上 |
| [selectAll](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L642) | タスク一覧の「すべて選択」 | 選択されない | サーバの失敗 |
| [selectAll（モデル）](../src/app/webapp-common/models/effects/models-view.effects.ts#L379) | モデル一覧の「すべて選択」 | 同上 | 同上 |
| [updateProjectStats](../src/app/webapp-common/projects/common-projects.effects.ts#L240) | 「My Work」を切り替えたときのプロジェクトの統計 | 統計が更新されない | 同上 |
| [navigateToDataset](../src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L630) | 入力のデータセットへの移動 | 移動しない | 同上 |
| [downloadArtifact](../src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L403) | 成果物のダウンロード | 以後ダウンロードしない | 内側の `catchError` が fetch の失敗を受けるため、外側に届くのは `new URL()` が例外になる URI（スキームの無い相対パスなど）に限られる。実データでは確かめていない。届いた場合、外側の `catchError` の後ろの `map` が `downloadFailed` を `downloadArtifacts({url: <action>})` に変えるため、読み込み中の表示（`downloading`）も消えない |
| [deleteS3SourcesEffect](../src/app/webapp-common/shared/entity-page/entity-delete/base-delete-dialog.effects.ts#L282) | 削除時の S3 のファイルの削除 | — | dispatch 元がコメントアウトされており到達しない |

### `catchError` が無く、累計11回の失敗で止まるもの（24件）

分類の結果は27件で、`addMessage`（API ではなく通知の表示）と `signUrl`・`signUrls`（署名の処理で、失敗は S3 の資格情報の誤りなどに限られる）を除いた数である。このうち自動更新で繰り返し呼ばれ、11回に達しやすいのは次の6件である。

| Effect | 呼ばれ方 |
|---|---|
| [refreshIfNeeded](../src/app/webapp-common/experiments-compare/effects/compare-header-effects.ts#L30) | 比較画面で10秒ごと（再現済み） |
| [getExperimentInfo$](../src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L243) | 詳細の自動更新。開いているタスクが Store の一覧（`selectExperimentsList`）に無いときに `tasksGetByIdEx` を呼ぶ。止まると、どのタスクの詳細も読み込まれず、保存後の取り直しも行われない |
| [getModelInfo$](../src/app/webapp-common/models/effects/models-info.effects.ts#L100) | モデルの詳細の自動更新 |
| [fetchExperimentScalarSingleValue$](../src/app/webapp-common/experiments/effects/common-experiment-output.effects.ts#L87)・[fetchExperimentScalarMetricVariantsTableData$](../src/app/webapp-common/experiments/effects/common-experiment-output.effects.ts#L99)・[fetchModelScalarMetricVariantsTableData$](../src/app/webapp-common/experiments/effects/common-experiment-output.effects.ts#L110) | SCALARS の自動更新 |

残りの18件は、利用者の操作で呼ばれるもの（キューの選択欄の一覧 `getQueuesForEnqueue$`、プロジェクトの削除前の確認 `checkIfProjectExperiments`、全体検索の件数 `getResultsCount`、比較画面の凡例 `getGlobalLegendData$` など）で、11回に達するには失敗が重なる必要がある。一覧は [scripts/p2f-classify-effects.cjs](./scripts/p2f-classify-effects.cjs) の出力の判定 `NO_CATCH_API` の行。

### 問題の無い書き方

269件の多くは、`catchError` を `switchMap`・`mergeMap` の内側（API の Observable の `pipe`）に置いている。この場合、失敗はその回の内側の流れだけで終わり、外側の流れは続く（例：[updateExperimentDetails$](../src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L450)）。

## 対策案

第一案は、上の2つの表の Effect で、`catchError` を平坦化の演算子（`switchMap`・`mergeMap` など）の内側へ移し、失敗の回で読み込み中の表示を消す action も出すことである。対象は外側の `catchError` の16件（到達しない1件を除く）と、`catchError` の無い24件の計40件で、20ファイル・複数の機能にまたがるため、§7.5 により「長大」とした。1件ごとの変更は `catchError` を移すだけの機械的なもので、利用者の操作で止まる外側の `catchError` の16件を先に直すと効果が大きい。

```ts
switchMap(([action, projectId]) => this.apiTasks.tasksCreate({...}).pipe(
  map(res => exActions.createExperimentSuccess({...})),
  catchError(error => [addMessage(MESSAGES_SEVERITY.ERROR, `Failed to create tasks.\n...`)])  // 内側へ
)),
```

キューの削除のように、確認ダイアログの `switchMap` と API の `switchMap` を続けて並べているものは、API の呼び出しを確認ダイアログの内側の流れに入れてから `catchError` を付ける。

再発を防ぐには、導入済みの `@ngrx/eslint-plugin` には `catchError` の位置を検査する規則が無い（Effect の規則は `avoid-cyclic-effects` など7つ）ため、[scripts/p2f-classify-effects.cjs](./scripts/p2f-classify-effects.cjs) と同じ判定を CI の検査に加えるか、`EFFECTS_ERROR_HANDLER` を差し替えて再購読の上限を無くす（エラーを記録して再購読し続ける）方法がある。後者は外側の `catchError` による完了には効かないため、前者と組み合わせる。

## 検証範囲

- 確認したこと：Playwright（Chromium）で、タスクの作成・レポートの作成・キューの削除をモック API で失敗させた後に、要求が送られないこと、キューの確認ダイアログが開かないこと、レポートの全画面のスピナーが残ること。実バックエンドの比較画面で、`refreshIfNeeded` の要求だけを失敗させ、累計11回目の失敗の後は、失敗させるのをやめても要求が出ないこと、10秒ごとの自動更新でも出ないこと。NgRx の再購読の上限と、クラスごとに最初のインスタンスだけを動かす作りは、`@ngrx/effects` 22 の `defaultEffectsErrorHandler`・`EffectSources.toActions()` で確かめた
- 確認していないこと：タスクの作成とレポートの作成のダイアログの操作（ダイアログを閉じた後の action を直接 dispatch した）。作成とキュー投入を一度に行う場合の投入の停止。表の他の Effect の画面での症状（コードから判断した）。キューの削除が実際に `QueueNotEmpty` になる競合（モック API で失敗を返した。サーバの条件は起動中の apiserver のコード `bll/queue/queue_bll.py` の `delete()` で確かめた）
- 由来：表の Effect のファイルは、比較資料で上流と一致する。`defaultEffectsErrorHandler` の再購読の上限（10回、成功しても戻らない）と、クラスごとに最初のインスタンスだけを動かす `exhaustMap` は、`@ngrx/effects` 21.1.1 でも同じである（作業用ディレクトリに取得して確かめた）

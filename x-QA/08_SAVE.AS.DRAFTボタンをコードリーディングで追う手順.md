# SAVE AS DRAFT ボタンをコードリーディングで追う手順

## この資料の使い方

ソースに付けた `//:: (1)`〜`(14)` は、**SAVE AS DRAFT を押してから何が起きるか**を追う順序。
各番号では「今いる行から次をどう探すか」を読む。まず (1)〜(14) だけを一周し、ボタンの表示場所や押せる条件は後半で調べる。

最初に持つ問いは一つだけ。

> このボタンを押した結果は、どのコードに渡り、最後に何を起こすか？

### ダイアログが開くまで（SAVE を押す前）

ご指摘の通り、[`newExperiment()`](../src/app/webapp-common/experiments/experiments.component.ts#L781) は [親画面の `#addButton`](../src/app/webapp-common/experiments/experiments.component.html#L33) 内にある **NEW TASK ボタンの `(click)`** から呼ばれる。このテンプレートは同じ HTML の [`[addButtonTemplate]="addButton"`](../src/app/webapp-common/experiments/experiments.component.html#L15) でヘッダーに渡され、[ヘッダーの `ngTemplateOutlet`](../src/app/webapp-common/experiments/dumb/experiment-header/experiment-header.component.html#L4) で表示される。

```text
ヘッダーの NEW TASK をクリック
  → experiments.component.html の (click)="newExperiment()"
  → experiments.component.ts の newExperiment()
  → dialog.open(CreateExperimentDialogComponent) でダイアログを開く
  → afterClosed() で閉じた結果を待つ
```

`newExperiment()` の呼び出し元をコードから探すなら、メソッド名を検索する。

```bash
rg -n 'newExperiment\(' src/app --glob '*.ts' --glob '*.html' --glob '!*.spec.ts'
```

**NEW TASK が `newExperiment()` を呼ぶ。SAVE AS DRAFT はダイアログ内の `close('save')` を呼ぶ。** この2つは別のクリック。

### まず一本の経路をつかむ

| 順番 | 今いる場所で確認すること | 次をどう探すか |
|---|---|---|
| (1)→(2) | [HTML の `#saveButton`](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.html#L351) で `(click)="close('save')"` を見つける | 同名のコンポーネント TS で `close(` を探す |
| (3)→(4) | [`close()`](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.ts#L259) の中に `this.dialog.close(...)` がある | `dialog` を Ctrl+クリックして `MatDialogRef` と確認。次はコンポーネントのクラス名をプロジェクト全体で検索する |
| (5)→(7) | [`dialog.open(CreateExperimentDialogComponent)`](../src/app/webapp-common/experiments/experiments.component.ts#L782) のある `newExperiment()` を見つけ、直後の `afterClosed()` と `subscribe` を読む | `createExperiment` の定義を探し、次にその action を受ける `ofType` を探す |
| (8)→(10) | [action 定義](../src/app/webapp-common/experiments/actions/common-experiments-view.actions.ts#L309) で `data` の型を確認。[effect](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L870) で `ofType(exActions.createExperiment)` から `tasksCreate(...)` まで読む | API 成功時の `map` が次に何を発行するかを見る |
| (11)→(14) | [成功時](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L910) に `createExperimentSuccess` が発行される | 同じ action を受ける `ofType` を全て探す。通知、一覧更新、queue がある場合の enqueue の3箇所に分かれる |

**ここまでで分かること:** ボタン → ダイアログを閉じる → 閉じた値を受け取る → NgRx action → API でタスク作成 → 成功後の処理、という経路。各番号のコメントは、その行の処理の説明より**次に開く場所**を示す。

## 手がかりが途切れる2箇所

### (4) `this.dialog.close(...)` の先

**なぜクラス名で `open` を探すのか。** `MatDialog.open(CreateExperimentDialogComponent)` はそのダイアログの `MatDialogRef` を返す。開いた側はその参照の `afterClosed()` で結果を待つ。一方、ダイアログ内で `inject(MatDialogRef)` すると、開かれた**そのダイアログ自身の参照**を受け取る。`this.dialog.close(値)` はその参照を通じて閉じ、渡した値が開いた側の `afterClosed()` に届く。これは [Angular Material のダイアログの仕組み](https://v17.material.angular.dev/components/dialog)による。

だから `close()` の中に `newExperiment()` という呼び出しはない。`MatDialogRef` は多くのダイアログで使う共通の型なので、そこを Ctrl+クリックしても**このダイアログを開いた箇所**は特定できない。手元で分かっている固有情報は `CreateExperimentDialogComponent` というクラス名。これを引数にした `dialog.open(CreateExperimentDialogComponent, ...)` を探せば、開いた側に繋がる。

次の順番で操作する。

1. [`close(action: 'save' | 'run')`](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.ts#L259) の中で `this.dialog.close({...})` を確認する。`action` と各フォームの値を渡している。
2. `this.dialog` の `dialog` を Ctrl+クリックする。[宣言](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.ts#L143) は `inject(MatDialogRef)`。ここで「ダイアログの結果を返している」と判断する。`close` をさらに Ctrl+クリックしてもライブラリ側に進むだけ。
3. 同じファイルの [`export class CreateExperimentDialogComponent`](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.ts#L140) からクラス名をコピーする。
4. VS Code の **Ctrl+Shift+F** で `CreateExperimentDialogComponent` を検索する。「含めるファイル」に `src/app/**/*.ts`、「除外するファイル」に `**/*.spec.ts` を入れる。クラス名上の **Shift+F12**（すべての参照を検索）でも使用箇所を探せる。ターミナルなら次を実行する。

```bash
rg -n 'CreateExperimentDialogComponent' src/app --glob '*.ts' --glob '!*.spec.ts'
```

5. 検索結果のうち、`import` やクラス宣言ではなく、[`this.dialog.open(CreateExperimentDialogComponent, ...)`](../src/app/webapp-common/experiments/experiments.component.ts#L782) を開く。探したいのは「このクラスをダイアログとして開くコード」。より狭く探すなら次の検索でも直接見つかる。

```bash
rg -n 'dialog\.open\(CreateExperimentDialogComponent' src/app --glob '*.ts' --glob '!*.spec.ts'
```

6. `dialog.open(...)` の**一行上**を見る。そこが [`newExperiment()`](../src/app/webapp-common/experiments/experiments.component.ts#L781)。続く [`afterClosed()`](../src/app/webapp-common/experiments/experiments.component.ts#L785) と `subscribe(data => ...)` まで同じ式として読む。`this.dialog.close({...})` に渡した値が `afterClosed()` から出て、この `data` になる。`filter(res => !!res)` により、値がない場合は `dispatch` まで進まない。

実行時の順序は **NEW TASK を押す → `newExperiment()` → `dialog.open()` → 受け取りを登録 → SAVE AS DRAFT を押す → `this.dialog.close(...)` → `afterClosed()` の `subscribe` が動く**。コードを読むときは `close` から開き手を逆引きするため、`newExperiment()` に戻る形になる。`close()` から `newExperiment()` への直接の関数呼び出しはない。

### このプロジェクトのほかのダイアログも同じ？

**結果を返すダイアログでは、この形がよく使われている。** たとえば [ReportDialogComponent](../src/app/webapp-common/reports/report-dialog/report-dialog.component.ts#L46) は `close(report)` し、[開いた側](../src/app/webapp-common/reports/reports-page/reports-page.component.ts#L87) は `afterClosed()` で `report` を受け取って `createReport` を dispatch する。[QueueCreateDialogComponent](../src/app/webapp-common/shared/queue-create-dialog/queue-create-dialog.component.ts#L45) は作成成功後に `close(true)` し、[開いた側](../src/app/webapp-common/workers-and-queues/containers/queues/queues.component.ts#L133) は `afterClosed()` で受けて一覧を再取得する。

読む際はまず **`open(対象コンポーネント)` → `afterClosed()`** を探す。その後で、ダイアログ内のどの操作や状態変化が `close(値)` を呼ぶかを確認する。`close` のきっかけも戻り値の使い方もダイアログごとに異なる。

### (7) `dispatch(createExperiment(...))` の先

`dispatch` の行から effect へ直接ジャンプできない。action 名を手がかりに `ofType` を探す。

```bash
rg -n 'ofType\(exActions\.createExperiment' src/app/webapp-common/experiments
```

`createExperiment` と `createExperimentSuccess` の両方が検索結果に出る。**(7) から進む先は前者**。API 成功後、(11) の `createExperimentSuccess` を受ける3箇所を改めて読む。

## 一周した後の補助調査

### このボタンはどこに表示される？

`#saveButton` はボタンの**定義**で、表示場所ではない。同じ HTML で参照箇所を探す。

```bash
rg -n 'ngTemplateOutlet="saveButton"' src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.html
```

各ステップのフッタに5箇所ある。つまり同じボタンを5つのステップで使っている。クリック後の経路はどのステップでも同じ。

### いつ押せる？

HTML の `[disabled]="codeFormGroup.invalid || dockerFormGroup.invalid"` を見て、[`codeFormGroup`](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.ts#L170) と [`dockerFormGroup`](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.ts#L199) の定義を開く。`codeFormGroup` には必須項目などの validator がある。`dockerFormGroup` には validator がないため、現コードの通常の操作では後半の `invalid` は false。

初期定義だけでは不十分。`binary` の validator は [`effect()`](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.ts#L222) で、`branch/commit/tag` は [`typeChange()`](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.ts#L289) で変わる。`togglePoetry()` が変更するのは `envFormGroup` なので、このボタンの `[disabled]` を調べる経路には入らない。

### RUN とどこが違う？

[途中の RUN](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.html#L173) は `runStep.select()` で最終ステップに進む。[最終ステップの RUN](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.html#L337) は `close('run')` を呼び、`queueFormGroup.invalid` も押下条件に含める。

ただし API 側は `action: 'save' | 'run'` で分岐していない。[enqueue の effect](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L937) は **`queue` の有無**を見ている。したがって「SAVE なら絶対に enqueue されない」とは読めない。最終ステップで queue を選んでから SAVE を押した場合も、`queue` が渡されれば enqueue の条件を満たす。

## 迷ったときの戻り方

- `close('save')` はコンポーネント内のメソッドを探す。
- `this.dialog.close(...)` ではダイアログのクラス名から `dialog.open(...)` を探す。
- `dispatch(action)` では action 名から `ofType(action)` を探す。
- 成功 action が出たら、それを受ける `ofType` を**全て**探す。

番号付きコメントは追跡用の注釈。外す場合は、それぞれの `//::` コメントだけを削除する。ほかの変更も含めてファイル全体を戻す操作はしない。

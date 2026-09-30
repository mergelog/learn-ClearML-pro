# Action作法違反：プロジェクト操作の結果を状態設定にまとめている

## まず結論

`setCreationStatus({status: 'success'})`だけでは、**何が成功したのか**分からない。プロジェクトの作成・更新・移動という別々の出来事が、同じ「状態をsuccessにせよ」というActionに置き換わっている。

## 実際の流れ

```text
プロジェクト作成のAPI成功 ─┐
プロジェクト更新のAPI成功 ─┼→ setCreationStatus({status: 'success'})
プロジェクト移動のAPI成功 ─┘                ↓
                                  ReducerがcreationStatusを更新
```

Actionは[`project-dialog.actions.ts`の`setCreationStatus`](../src/app/webapp-common/shared/project-dialog/project-dialog.actions.ts#L10)で定義されている。[作成のEffect](../src/app/webapp-common/shared/project-dialog/project-dialog.effects.ts#L40)、[更新のEffect](../src/app/webapp-common/shared/project-dialog/project-dialog.effects.ts#L57)、[移動のEffect](../src/app/webapp-common/shared/project-dialog/project-dialog.effects.ts#L74)が、いずれも成功時に`SUCCESS`、失敗時に`FAILED`を渡す。[Reducer](../src/app/webapp-common/shared/project-dialog/project-dialog.reducer.ts#L22)は受け取った値を`creationStatus`へ代入する。

## 何が困るか

Actionの履歴を見ても「プロジェクトを作成できた」のか「移動できた」のか判別できない。例えば将来「作成成功時だけ一覧を更新するEffect」を追加しても、`setCreationStatus`だけでは作成成功を特定できない。

問題は`set`という綴りそのものではなく、**Actionに操作の種類と結果が残っていないこと**である。

## どう表すか

```text
作成API成功 → projectCreated         → ReducerはcreationStatusをsuccessにする
更新API成功 → projectUpdated         → ReducerはcreationStatusをsuccessにする
移動API失敗 → projectMoveFailed      → ReducerはcreationStatusをfailedにする
```

成功・失敗を各操作のイベントとして宣言し、状態への反映はReducerで決める。画面上の表示が同じ`success`でも、Actionには起きた出来事が残る。[キュー作成ダイアログ](../src/app/webapp-common/shared/queue-create-dialog/queue-create-dialog.effects.ts#L24)にも同じ種類の改善候補がある。

参考：[NgRxの教科書「Actionはイベントである」](https://zenn.dev/zzzzzzz/books/ngrx-textbook/viewer/06-action-design#action%E3%81%AF%E3%82%A4%E3%83%99%E3%83%B3%E3%83%88%E3%81%A7%E3%81%82%E3%82%8B)。この資料は設計上の指摘で、実装は変更していない。

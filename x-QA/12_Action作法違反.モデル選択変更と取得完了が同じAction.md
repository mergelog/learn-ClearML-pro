# Action作法違反：モデル選択変更と取得完了が同じAction

## まず結論

`setSelectedModels`は、**ユーザーがモデルの選択を変えた**ときにも、**APIから選択済みモデルが返った**ときにも発行される。Reducerで設定する値は同じでも、起きた出来事は異なる。

## 実際の流れ

```text
ユーザーが比較用モデルを選択 ─────┐
                                  ├→ setSelectedModels({models})
APIから選択済みモデルを取得 ──────┘            ↓
                                  ReducerがselectedModelsを更新
```

Actionは[`select-model.actions.ts`](../src/app/webapp-common/select-model/select-model.actions.ts#L23)で定義されている。[コンポーネントの`modelsSelectionChanged`](../src/app/webapp-common/select-model/select-model.component.ts#L171)はユーザー操作から発行する。[`getSelectedModels` Effect](../src/app/webapp-common/select-model/select-model.effects.ts#L123)はAPIの応答からも発行する。[Reducer](../src/app/webapp-common/select-model/select-model.reducer.ts#L65)は両者を区別せず`selectedModels`を更新する。

## 何が困るか

例えば「ユーザーが選択を変えたときだけ保存するEffect」を追加すると、`setSelectedModels`を監視しただけではAPI取得完了にも反応してしまう。Actionの履歴からも、選択変更と取得完了のどちらが起きたか分からない。

## どう表すか

```text
ユーザーが選択を変更 → modelSelectionChanged({models})
APIの取得が完了     → selectedModelsLoaded({models})
```

Reducerは両方のイベントを受けて`selectedModels`を更新できる。一方、ユーザー操作にだけ反応するEffectは`modelSelectionChanged`だけを監視できる。Actionには状態の代入方法ではなく、**値が届いた理由**を残す。

参考：[NgRxの教科書「Actionはイベントである」](https://zenn.dev/zzzzzzz/books/ngrx-textbook/viewer/06-action-design#action%E3%81%AF%E3%82%A4%E3%83%99%E3%83%B3%E3%83%88%E3%81%A7%E3%81%82%E3%82%8B)。この資料は設計上の指摘で、実装は変更していない。

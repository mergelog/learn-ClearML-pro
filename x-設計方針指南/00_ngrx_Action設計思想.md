# NgRx Action設計思想

## この文書の結論

新規開発でNgRx Storeを使うなら、**Actionは「発行者が知っている出来事」を表す**ことを強い標準とする。Reducerはその出来事を受けて状態を計算し、Effectsは必要な外部処理を行う。発行者がStore内部の更新手順を指定しない。

ただし、これは「全Actionを過去形にする」「`set`、`load`、`reset`という単語を禁止する」という意味ではない。要求やクリックも、**要求された／クリックされたという出来事**として表せる。重要なのは名前の文法ではなく、Actionの意味が一意で、発行元と処理段階を取り違えないことにある。NgRx公式はActionを固有のイベントと説明し、Redux公式はイベントとしてのモデルを推奨しつつ、setter形式も合法と明記する。[NgRx Store](https://ngrx.io/guide/store)、[Redux Style Guide](https://redux.js.org/style-guide/#model-actions-as-events-not-setters)

````md
ここで言っている `set` は、だいたい **「Storeのこの値を、この値にセットしろ」型のAction名** のことです。

たとえばこういうActionです。

`setSelectedProject({ projectId })`

意味としては、

> `selectedProjectId` というStore内部の値を、この `projectId` に変更しろ

という命令です。

Redux公式が言う「setter形式」はまさにこれで、合法ではあるものの、原則としては「何が起きたか」を表すActionのほうを推奨しています。:chatgpt-content-reference{index="0"}

たとえば画面でプロジェクトをクリックしたケースなら、

```ts
// setter的
setSelectedProject({ projectId })
```

より、

```ts
// event的
projectSelected({ projectId })
```

あるいは発行元まで明確にするなら、

```ts
createActionGroup({
  source: 'Projects Page',
  events: {
    'Project Selected': props<{ projectId: string }>(),
  },
});
```

のほうがNgRxらしい、という話です。

違いはかなり重要です。

`setSelectedProject` は、

> Storeの `selectedProject` を変えたい

という「更新方法」を発行側が知っています。

一方、

`projectSelected` は、

> ユーザーがプロジェクトを選択した

という「出来事」だけを知らせています。

その結果としてReducerが、

```ts
on(ProjectsPageActions.projectSelected, (state, { projectId }) => ({
  ...state,
  selectedProjectId: projectId,
}))
```

と判断してStoreを変えます。

つまり、

```text
Component
  ↓
「プロジェクトが選択された」
  ↓ Action
Reducer
  ↓
「じゃあ selectedProjectId を変えよう」
  ↓
Store更新
```

という役割分担です。

NgRx公式もActionを「コンポーネントやサービスからdispatchされる固有のevent」と説明しています。ReducerはそのActionと現在のstateから新しいstateを計算します。:chatgpt-content-reference{index="1"}

`set` が問題になりやすい理由を、もう少し極端な例にすると分かりやすいです。

```ts
this.store.dispatch(setSelectedProject({ projectId }));
this.store.dispatch(setLoading({ loading: true }));
this.store.dispatch(clearError());
```

これはComponent側が、

> selectedProjectを変えて  
> loadingをtrueにして  
> errorを消して

と、Store内部の更新手順まで指示しています。

つまりComponentがReducerの仕事を知りすぎています。

イベント型なら、

```ts
this.store.dispatch(
  ProjectsPageActions.projectSelected({ projectId })
);
```

だけです。

そしてReducer側で、

```ts
on(ProjectsPageActions.projectSelected, (state, { projectId }) => ({
  ...state,
  selectedProjectId: projectId,
  loading: true,
  error: null,
}))
```

とできます。

さらにEffectも同じActionを受けて、

```ts
projectSelected$ = createEffect(() =>
  this.actions$.pipe(
    ofType(ProjectsPageActions.projectSelected),
    switchMap(({ projectId }) =>
      this.api.loadProject(projectId)
    )
  )
);
```

と動けます。

つまり一つの出来事、

```text
Project Selected
```

に対して、

```text
Reducer → 状態変更
Effect  → API呼び出し
別Reducer → 他の状態変更
```

など、複数の処理が反応できます。

Redux公式もこの「event型」の利点として、1つの意味のある出来事を1 Actionとして扱い、複数のReducerがそれぞれ反応できる構造を推奨しています。setter方式だと発行側がStore構造や現在値を知る必要が増え、Action数も増えやすい、と説明しています。:chatgpt-content-reference{index="2"}

ただし、引用文にある

> `set`、`load`、`reset`という単語を禁止するわけではない

も重要です。

例えば、

```ts
filterReset()
```

は普通に「フィルターがリセットされた」というイベントとして読めます。

```ts
loadProjects()
```

もプロジェクトによっては、

> Projectsの読み込みが要求された

というActionとして意味が明確です。

より厳密にするなら、

```ts
projectsLoadRequested()
```

とも書けます。

だから、判断基準は単語ではありません。

私はコードリーディング時には、こう判定するとかなり分かりやすいと思います。

| Action | 見方 |
|---|---|
| `setLoading(true)` | Store内部操作っぽい |
| `setSelectedProject(id)` | Store内部操作っぽい |
| `clearError()` | Store内部操作っぽい |
| `projectSelected(id)` | 出来事 |
| `searchSubmitted(query)` | 出来事 |
| `refreshClicked()` | 出来事 |
| `projectsLoadRequested()` | 出来事 |
| `projectsLoaded(projects)` | 処理結果の出来事 |
| `projectsLoadFailed(error)` | 処理結果の出来事 |

一言でまとめると、

**`setXXX` = 「Storeをどう変えるか」になりやすい。  
`xxxSelected / xxxClicked / xxxRequested / xxxSucceeded` = 「何が起きたか」。**

新規NgRx設計なら、後者を基本にしよう、という話です。

なおRedux公式自身も `setUserName` のようなsetter Actionは「違法ではない」と明記しています。あくまで設計上、イベントとしてモデル化する方を強く推奨している、という位置づけです。:chatgpt-content-reference{index="3"}

ClearMLのNgRxコードを読むときも、Action名を見てまず **「これは出来事なのか、それともStore操作命令なのか」** と分類すると、Effect・Reducerを追うときかなり整理しやすくなります。
````

以下の「必須・原則・許容」は**この文書が提案する新規開発向けのチーム規約**であり、すべてがNgRxの技術的制約という意味ではない。

## 1. まずStoreに載せるべきか決める

短命な入力値や単一コンポーネントの開閉状態まで、イベント化のためにグローバルStoreへ載せない。複数箇所で共有する、画面を戻っても保持する、外部データ取得に関わる、他の機能の操作から影響を受けるなど、Storeを使う理由がある場合にAction設計を始める。NgRx公式もグローバルStoreの適用条件を示し、ローカル状態にはNgRx Signalsを挙げる。[NgRx「Why use Store?」](https://ngrx.io/guide/store/why)、[NgRx Store](https://ngrx.io/guide/store)

## 2. Actionを決める順序

1. **いつ起きたか**を確定する。ユーザー操作時、要求開始時、API応答時、タイマー発火時、ルート遷移時など。
2. **誰が知っている事実か**を決める。Page、Dialog、Router、API、WebSocketなど。APIの成功を、ボタンを押した時点のActionで表現しない。
3. **一文で言える出来事**をActionにする。「利用者が保存を要求した」「サーバーが保存を受け付けた」「保存に失敗した」など。
4. **その時点で分かる情報だけ**をpayloadに載せる。対象ID、入力、応答結果、失敗情報、必要な相関IDなど。Reducerに代入させたいState全体を組み立てて渡さない。
5. Reducer・EffectsはそのActionに**反応する側**として設計する。Action定義に特定のReducer名、次のAPI呼び出し、画面遷移の手順を埋め込まない。

Redux公式は、状態の計算をReducerへ寄せ、Action発行側がStateの形を知りすぎないよう勧める。[Redux Style Guide: Put as Much Logic as Possible in Reducers](https://redux.js.org/style-guide/#put-as-much-logic-as-possible-in-reducers)、[Reducers Should Own the State Shape](https://redux.js.org/style-guide/#reducers-should-own-the-state-shape)

## 3. 場面別の判断表

| 場面 | この文書の標準 | 理由・注意 |
| --- | --- | --- |
| 利用者がボタンを押した | `saveClicked`、`saveSubmitted`、`saveRequested`など、**押した／送信した事実**を表す | ここでは保存成功を宣言しない。`save`のような短い名前も、sourceと契約が明確なら許容する。NgRx公式のEffect例も`[Login Page] Login`を使う。[NgRx Effects](https://ngrx.io/guide/effects) |
| APIが成功・失敗を返した | `metadataSaved`／`metadataSaveFailed`など**結果を別Action**で表す | 成功は応答を確認した後に発行する。失敗を握りつぶさず、必要な画面状態へ反映する。[NgRx Effects](https://ngrx.io/guide/effects) |
| 違う操作が同じState値へ行き着く | 操作が異なれば、原則として別の結果イベントにする | `projectCreated`と`projectMoved`が同じ`status: success`を作っても、履歴と後続反応では区別できる。Reducerは両方を同じ処理で受けてよい。 |
| 同じ意味の出来事が複数箇所で起きる | **意味・payload・後続契約が同じ**ならActionを共有してよい | 発行元が将来の判断に重要ならsourceを分ける。場所ごとに無条件で増殖させない。 |
| 画面表示と保存後の再取得で同じAPIを呼ぶ | 出来事が違うならActionを分け、Effects内の取得処理を共有する | 「API呼び出しが同じ」は「発生した出来事が同じ」の根拠にならない。 |
| 入力欄の1文字、ダイアログの一時的な表示 | 原則としてローカル状態に置く | グローバルな履歴と依存を増やさない。[NgRx「Why use Store?」](https://ngrx.io/guide/store/why) |
| 単一所有者の単純な更新 | `setFilter`なども許容する | 利用者操作や取得結果との混同がなく、sourceと意味が明確であること。名前だけを理由にイベント名を増やさない。[Redux Style Guide](https://redux.js.org/style-guide/#model-actions-as-events-not-setters) |

## 4. 命名・source・payloadの規約

### 命名

- Action typeは開発者が履歴で読む契約なので、`SET_DATA`や`UPDATE_STORE`のような汎用名を避ける。[Redux Style Guide: Write Meaningful Action Names](https://redux.js.org/style-guide/#write-meaningful-action-names)
- 新規Actionは原則として`[発行元] 出来事`にする。例：`[Catalog Detail Page] Save Submitted`、`[Catalog API] Metadata Saved`。`createActionGroup`なら`source`を明示する。NgRxの資料でもPageとAPIのsourceを分ける例がある。[NgRx Effects](https://ngrx.io/guide/effects)、[NgRx v16 Migration Guide](https://ngrx.io/guide/migration/v16)
- `Requested`、`Succeeded`／`Saved`、`Failed`は処理段階を表す。**「要求した」と「成功した」を同じAction名にしない。**
- `Clicked`は純粋なUI操作が重要なとき、`Submitted`はフォームの妥当性確認後、`Requested`は業務上の処理要求が確定したときに使う。どの瞬間を記録するか先に決める。これはこの文書の命名規約である。

### payload

- その出来事を理解・処理するのに必要な値を載せる。対象ID、変更内容、APIが返した結果など。複数の同時要求が混在するなら、対象IDや要求IDを結果Actionにも入れて照合する。
- Reducerへ`isLoading: false`や`creationStatus: 'success'`だけを指示するpayloadは、元の出来事を失いやすい。`saveSucceeded({id, saved})`からReducerがloadingとデータを更新する形を優先する。
- StoreやActionのデバッグ・再現を妨げる関数、DOM要素、Promiseなどの非シリアライズ値を通常のpayloadに入れない。[Redux Style Guide: Do Not Put Non-Serializable Values in State or Actions](https://redux.js.org/style-guide/#do-not-put-non-serializable-values-in-state-or-actions)、[NgRx「Why use Store?」](https://ngrx.io/guide/store/why)

## 5. ReducerとEffectsへの接続

```ts
export const catalogPageActions = createActionGroup({
  source: 'Catalog Detail Page',
  events: {
    'save submitted': props<{id: string; edit: MetadataEdit}>(),
  },
});

export const catalogApiActions = createActionGroup({
  source: 'Catalog API',
  events: {
    'metadata saved': props<{id: string; saved: Metadata}>(),
    'metadata save failed': props<{id: string; reason: string}>(),
  },
});
```

流れは`saveSubmitted` → EffectがAPIを呼ぶ → `metadataSaved`または`metadataSaveFailed` → Reducerが状態を更新、となる。通知・キャッシュ更新など別の担当も、必要なら**同じ結果イベント**へ反応できる。NgRx公式はEffectsを外部処理の場所とし、Redux公式は一つのイベントに複数Reducerが反応できる構成を勧める。[NgRx Effects](https://ngrx.io/guide/effects)、[Redux Style Guide: Allow Many Reducers to Respond to the Same Action](https://redux.js.org/style-guide/#allow-many-reducers-to-respond-to-the-same-action)

Actionは**発行元で定義し、受信者の名前にしない**。例えばCatalog APIで保存が完了したなら`[Catalog API] Metadata Saved`を発行し、別機能を更新するためだけの`[Sidebar] Refresh Counts`を同時に発行しない。Sidebarが必要なら保存完了に反応する。複数Reducerが反応できるのは利点であり、すべてのActionに複数の受信者を作る義務ではない。これは上記の公式指針を、大規模開発の依存管理に適用したこの文書の規約である。

一つの意味ある出来事を、`setLoading(false)`、`setItem(saved)`、`showSuccess()`のような状態設定Actionの列に分解する設計は避ける。一つの結果イベントを複数Reducer／Effectsが受ければ、途中の不整合とAction履歴のノイズを減らせる。NgRxの`no-multiple-actions-in-effects`規則も、Effectから複数Actionを返す代わりに、起きた一つの出来事を表すActionを勧める。ただし、**本当に時間の異なる出来事**（要求・進捗・完了など）はそれぞれ別Actionでよい。[NgRx ESLint: no-multiple-actions-in-effects](https://ngrx.io/guide/eslint-plugin/rules/no-multiple-actions-in-effects)、[Redux Style Guide: Avoid Dispatching Many Actions Sequentially](https://redux.js.org/style-guide/#avoid-dispatching-many-actions-sequentially)

成功イベントが届いても、既に別の資産を開いている可能性がある。ReducerはActionだけを見て無条件に上書きせず、現在のStateと対象ID・要求IDを合わせて適用可否を決める。これはRedux公式の「Reducerを状態機械として扱う」指針を非同期画面へ適用した設計判断である。[Redux Style Guide: Treat Reducers as State Machines](https://redux.js.org/style-guide/#treat-reducers-as-state-machines)

## 6. レビューで使う判定質問

1. Action typeとpayloadだけを読んで、**何が、いつ、どこで起きたか**が説明できるか。
2. その事実は発行時点で確定しているか。要求時点で成功を名乗っていないか。
3. 同じActionの発行元ごとに意味が変わらないか。ユーザー操作とAPI応答を混ぜていないか。
4. 発行側がStateの内部構造や複数Reducerの更新順序を知る必要がないか。
5. 別のReducer／EffectがこのActionに反応しても、意図しない処理が起きないか。
6. そのActionはグローバルStoreに必要か。ローカル状態で完結するか。

1〜5で問題があれば、名前だけを変えず、**出来事の境界と発行元**を再設計する。すべて通るなら、過去形ではないという理由だけで書き換えない。

## 7. 既存コードへの適用

この文書は**新規設計時の標準**である。既存コードは一斉改名しない。新しいEffectを追加する、発行元が増える、誤反応が起きる、調査時に履歴を読めない、といった変更点でAction契約を見直す。互換性に影響する場合は、発行元・Reducer・Effects・テストを一緒に変更する。

本PJの個別例は[プロジェクト操作](../x-QA/11_Action作法違反.プロジェクト操作の結果を状態設定にまとめている.md)、[モデル選択](../x-QA/12_Action作法違反.モデル選択変更と取得完了が同じAction.md)、[詳細再取得](../x-QA/13_Action作法違反.保存後の再取得を詳細画面を開いたActionで表している.md)の資料を参照。ただし資料名の「作法違反」は優先度や不具合確定を意味しない。例の中では、ユーザー操作とAPI結果を混ぜる設計が最も実害に結び付きやすく、単なる命名のずれは低優先度である。**この方針資料の作成によって、既存実装を修正する必要は生じない。**

## 参考資料

- [NgRx Store](https://ngrx.io/guide/store)、[NgRx Effects](https://ngrx.io/guide/effects)、[NgRx「Why use Store?」](https://ngrx.io/guide/store/why)
- [NgRx ESLint: no-multiple-actions-in-effects](https://ngrx.io/guide/eslint-plugin/rules/no-multiple-actions-in-effects)
- [Redux Style Guide](https://redux.js.org/style-guide/)
- [NgRxの教科書「Actionをイベントとして設計する」](https://zenn.dev/zzzzzzz/books/ngrx-textbook/viewer/06-action-design#action%E3%81%AF%E3%82%A4%E3%83%99%E3%83%B3%E3%83%88%E3%81%A7%E3%81%82%E3%82%8B)（議論の起点）

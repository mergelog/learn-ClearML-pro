# exportTaskInfo$ の成功メッセージがトースト表示されるまでの経路

## 結論

`exportTaskInfo$` effect が返す `addMessage('success', ...)` は、それ自体では何も表示しない。
NgRx の action として actions ストリームに流れ、`layout.effects.ts` の `addMessage$` effect がこれを拾い、`NotifierService` 経由でトースト（スナックバー）として画面に表示される。

## 経路図

```text
exportTaskInfo$ (common-experiments-info.effects.ts)
  └─ addMessage('success', `${exportType} exported successfully`) を dispatch
       └─ layout.effects.ts の addMessage$ effect が ofType(layoutActions.addMessage) で受信
            ├─ bufferTime(500) で500ms内の複数addMessageをまとめる
            ├─ suppressNextMessages付き(403エラー等)があれば優先、なければ全件処理
            └─ NotifierService.show({type, message, actions}) を呼び出し
                 └─ NotifierQueueService.push({type:'SHOW', payload})
                      └─ notifier-container.component がキューを監視し
                           トースト（成功=緑）を描画・自動消去
```

## 各ステップの実装箇所

### 1. action の dispatch元

- [common-experiments-info.effects.ts:670](../src/app/webapp-common/experiments/effects/common-experiments-info.effects.ts#L670)

```ts
return [addMessage('success', `${action.exportType ?? 'Task'} exported successfully`)];
```

### 2. action定義

- [layout.actions.ts:90-101](../src/app/webapp-common/core/actions/layout.actions.ts#L90)

`severity`, `msg`, `userActions?`, `suppressNextMessages?` を積んだ `[add message]` action。`userActions`はトースト内に表示するボタンとその押下時アクションの組。

### 3. actionを拾うeffect

- [layout.effects.ts:77-90](../src/app/webapp-common/core/effects/layout.effects.ts#L77)

```ts
addMessage = createEffect(() => this.actions.pipe(
  ofType(layoutActions.addMessage),
  bufferTime(500),
  filter(messages => messages.length > 0),
  mergeMap((messages) => {
    const message403 = messages.find(message => message.suppressNextMessages);
    return message403 ? [message403] : messages;
  }),
  mergeMap(payload => payload ?
    this.notifierService.show({type: payload.severity, message: payload.msg, actions: payload.userActions}) :
    EMPTY
  ),
  mergeMap((actions: Action[]) => actions?.length > 0 ? actions : [emptyAction()])
));
```

- `bufferTime(500)` — 短時間に連続発火した複数の `addMessage` をまとめる
- 403エラー由来のメッセージ（`suppressNextMessages: true`）があれば、それ以外を捨てて優先表示する

### 4. 実際の表示

- [notifier.service.ts:63-70](../src/app/webapp-common/angular-notifier/src/services/notifier.service.ts#L63)

```ts
public show(notificationOptions: NotifierNotificationOptions): Subject<any> {
  const subject = new Subject();
  this.queueService.push({
    payload: {...notificationOptions, observer: subject},
    type: 'SHOW'
  });
  return subject;
}
```

`NotifierQueueService` にキューイングされ、`notifier-container.component` がそれを監視して実際のDOM（トースト）を描画する。

## userActions・戻りactionsの経路（今回は未使用）

`show()` が返す `Subject` は、トースト内のアクションボタンをユーザーがクリックした際に `Action[]` を emit する経路。`layout.effects.ts` 側で受け取り、`mergeMap((actions) => actions?.length > 0 ? actions : [emptyAction()])` として再度 store に dispatch する。

`exportTaskInfo$` の呼び出し（`addMessage('success', msg)`）は `userActions` を渡していないため、この経路は使われず単純にメッセージが表示されるだけ。

## 一言でいうと

「exportTaskInfo$ の成功時 return」→「layout.effects.ts の addMessage$ effect」→「NotifierService → notifier-container」の3段階でトースト表示に至る。

## AIチャット

Q. `return [addMessage('success', ...)]` の後、どこで何が起こるか知りたい。

A. `addMessage` は NgRx の action で、それ自体は表示処理を持たない。dispatch後、`layout.effects.ts` の `addMessage$` effect が `ofType(layoutActions.addMessage)` で購読しており、`bufferTime(500)` で複数メッセージをまとめた上で `NotifierService.show()` を呼ぶ。これが `NotifierQueueService` にキューイングされ、`notifier-container.component` が実際のトースト（成功=緑のスナックバー、"Task exported successfully"）を画面に描画する。`userActions` を渡していれば、ユーザーがボタン操作した際のactionが再度storeにdispatchされる経路もあるが、今回の呼び出しでは使われない。

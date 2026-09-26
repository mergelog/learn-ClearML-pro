# デバッグ画像で metric を続けて切り替えると、選択欄と違う前の metric の画像が表示される

| 項目 | 内容 |
|---|---|
| カテゴリー | 状態 |
| 不具合内容 | DEBUG SAMPLES で metric を選んだ直後に別の metric を選ぶと、前に選んだ metric の応答が後から届いた場合に、選択欄は後の metric のまま、前の metric の画像に置き換わる。更新ボタンを押すか metric を選び直すまで続く |
| 期待動作 | 表示される画像は常に選択欄の metric のものになる。前の選択の応答が遅れて届いても表示を置き換えない |
| 直さないと困ること | 利用者は選択欄の metric の画像だと思って別の metric の画像を見ることになり、学習の結果を読み違える。画像の欄の名前は variant だけで metric を出さないため、食い違いに気付きにくい |
| 修正規模 | 小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験管理 > DEBUG SAMPLES、比較画面の DEBUG SAMPLES（同じ部品） |
| 観点 | F（`mergeMap` の選び方、古い応答による上書き） |
| 重大度 | S3 |
| 確度 | 再現済み（モック API で応答の速さを metric ごとに変えて確認） |
| 由来 | 上流 |
| 発生条件 | 前に選んだ metric の `events.debug_images` の応答が、後に選んだ metric の応答より遅く届いたとき（画像の多い metric から少ない metric へすぐに切り替えた場合など） |
| 関連 | なし |

## 症状

モック API で、metric ごとに `events.debug_images` の応答の速さを変え（`metric-slow` だけ2.5秒、ほかは0.1秒）、選択欄で `metric-slow`、0.3秒後に `metric-other` を選んだ（[scripts/p2f-debug-images-stale.spec.ts](./scripts/p2f-debug-images-stale.spec.ts)）。画像の URL は存在しないものにしてあり、読み込みに失敗した欄にファイル名（`no-such-{metric}.png`）が表示される。

| 時点 | 選択欄 | 表示されている画像 | 確認 |
|---|---|---|---|
| 初期表示 | metric-fast | metric-fast | 再現（モック API） |
| `metric-slow` → `metric-other` と選んだ0.5秒後 | metric-other | metric-other | 同上 |
| `metric-slow` の応答が届いた後 | metric-other | **metric-slow** | 同上 |
| 右上の更新ボタンを押した後 | metric-other | metric-other（`metric-other` で取り直す） | 同上 |

10秒ごとの自動更新では取り直さないため、食い違いは更新ボタンを押すか metric を選び直すまで残る。この画面の自動更新の購読は `refresh.tick` の `null`（10秒ごとの tick）を除き、更新ボタン（`false`）とタスクの更新を検知したとき（`true`）だけ取り直す（[debug-images.component.ts:244](../src/app/webapp-common/debug-images/debug-images.component.ts#L244)）。

## 再現手順

1. 画像の多い metric と少ない metric を持つタスクの DEBUG SAMPLES を開く
2. Metric の選択欄で画像の多い metric を選び、読み込みが終わる前に画像の少ない metric を選ぶ
3. 画像の少ない metric の画像がいったん表示された後、画像の多い metric の画像に置き換わる。選択欄は画像の少ない metric のまま

スクリプトは [scripts/p2f-debug-images-stale.spec.ts](./scripts/p2f-debug-images-stale.spec.ts)。実バックエンドには metric の多いデバッグ画像のデータが無いため、モック API で応答の速さを変えた。

## 期待する動作

選択欄の metric と表示される画像が常に一致する。後から選んだ metric の応答だけを表示に使う。

## 原因

デバッグ画像の取得の Effect が `mergeMap` で、前の要求を取り消さず、届いた順に表示を置き換える。

- [debug-images-effects.ts:58](../src/app/webapp-common/debug-images/debug-images-effects.ts#L58) の `fetchDebugImages$` は、`setSelectedMetric`・`getNextBatch`・`getPreviousBatch`・`refreshMetric` を `mergeMap` で受けて `eventsDebugImages` を呼ぶ。metric を切り替えても、前の metric の要求は取り消されず、応答が届くと `setDebugImages({res, task})` を出す
- reducer は `debugImages[task] = res` とタスクごとに上書きするだけで、応答の metric が選択中の metric（`selectedMetricsForTask[task]`）と同じかを見ない（[debug-images-reducer.ts:68](../src/app/webapp-common/debug-images/debug-images-reducer.ts#L68)）
- 画面は `debugImages[task]` の画像をそのまま並べる（[debug-images.component.ts:202](../src/app/webapp-common/debug-images/debug-images.component.ts#L202)）。選択欄は部品の `selectedMetrics` を表示するため、表示と選択欄が食い違う

`mergeMap` になっているのは、比較画面で複数のタスクの画像を同時に取るためと考えられる。`switchMap` に変えると、別のタスクの要求まで取り消してしまう。

## 影響範囲と同種箇所

- 比較画面の DEBUG SAMPLES も同じ部品と Effect を使う。タスクごとに metric を選べるため、同じタスクで続けて切り替えた場合に同じ症状になる（コードから判断）
- 同じ Effect の `getNextBatch`・`getPreviousBatch`（古い画像・新しい画像の表示）も、続けて押すと応答の順序が入れ替わる可能性がある（コードから判断。確かめていない）
- エンドポイントの統計のグラフ（[serving.effects.ts:399](../src/app/webapp-common/serving/serving.effects.ts#L399) の `fetchGraphData$`）も `mergeMap` で、応答を統計の種類（`metricType`）ごとに上書きし、どのエンドポイント・期間の応答かを見ない。エンドポイントや期間を続けて切り替えると、前の応答が後から届いて表示を置き換える可能性がある。実バックエンドにエンドポイントが無いため確かめていない
- 表示中の値を置き換えるほかの `mergeMap`（`getSelectedExperiments`・`getExperimentsHyperParams$` など）は、続けて呼ばれる操作が見当たらず、候補にとどめた

## 対策案

第一案は、応答が届いた時点で、応答の metric が選択中の metric と同じかを確かめ、違えば捨てる。`fetchDebugImages$` の内側の `mergeMap` の前に `concatLatestFrom(() => this.store.select(selectSelectedMetricForTask))` を置き、`action.payload.metric` と選択中の metric が違う場合は `deactivateLoader` だけを返す。1ファイルの変更のため「小」とした。

別案は、タスクごとに `groupBy` してから `switchMap` にすることで、同じタスクの前の要求を取り消す。比較画面で複数のタスクを同時に取る動きは保たれる。

## 検証範囲

- 確認したこと：Playwright（Chromium）とモック API で、metric を続けて切り替えたときに、遅れて届いた前の metric の画像に置き換わり、選択欄と食い違うこと。10秒ごとの tick では取り直されず、更新ボタンで選択中の metric の画像に戻ること
- 確認していないこと：実データでの再現（応答の遅さは画像の数や保存先に左右される）。比較画面、`getNextBatch`・`getPreviousBatch`、エンドポイントの統計のグラフ
- 由来：`debug-images-effects.ts`・`debug-images-reducer.ts`・`debug-images.component.ts` は比較資料で上流と一致する。`mergeMap` の挙動は rxjs の版に依らない

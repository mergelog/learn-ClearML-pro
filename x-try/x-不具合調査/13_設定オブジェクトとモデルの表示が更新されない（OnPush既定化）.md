# CONFIGURATION の設定オブジェクトが読み込み中のまま表示されず、ARTIFACTS でモデルを切り替えても前のモデルの情報が残る

| 項目 | 内容 |
|---|---|
| カテゴリー | 画面UI |
| 不具合内容 | タスクの CONFIGURATION で設定オブジェクト（General など）を開くと、API の応答が届いた後もスピナーが回り続け、TYPE・DESCRIPTION・本文が空のまま表示されない。ARTIFACTS で同じタスクの別の入力モデル（出力モデル）を選ぶと、URL は切り替わるのに、名前・ID・作成タスク・MODEL CONFIGURATION は前のモデルのまま残る |
| 期待動作 | 設定オブジェクトは読み込みが終わった時点で表示される。モデルを選ぶと、そのモデルの情報が表示される |
| 直さないと困ること | 設定オブジェクトの内容を画面で確認できない。モデルの切り替えでは、利用者が別のモデルの ID や設定を、選んだモデルのものと誤解する |
| 修正規模 | 小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験管理 > 詳細 > CONFIGURATION > CONFIGURATION OBJECTS、実験管理 > 詳細 > ARTIFACTS > 入力モデル・出力モデル（どちらも詳細パネルと全画面表示） |
| 観点 | D（変更検知と描画） |
| 重大度 | S2 |
| 確度 | 再現済み |
| 由来 | 版上げ |
| 発生条件 | 設定オブジェクト：常に（URL で直接開いた場合も、左の一覧から選んだ場合も）。モデル：入力モデルまたは出力モデルを2つ以上持つタスクで、同じタスクの中で別のモデルを選んだとき |
| 関連 | [05](./05_Executionタブでタスクを切り替えるとrequirementsの選択がPIPに戻る.md)（同じ型の不具合を `experiment-info-execution` で `markForCheck()` を足して直した跡がある） |

## 症状

| 画面 | 起きること | 確認 |
|---|---|---|
| CONFIGURATION の設定オブジェクト | `tasks.get_configurations` が 200 で返った後もスピナーが回り続け、TYPE・DESCRIPTION・本文が空のまま。同じタスクで別の設定オブジェクトに切り替えても同じ | 再現（実バックエンド） |
| ARTIFACTS の入力モデル | 1つ目のモデル（モデル一号）を表示した状態で2つ目のモデル（in-b）を選ぶと、URL は `input-model/model-2` になるが、表示はモデル一号の名前・ID・作成タスク・設定のまま | 再現（モック API） |

どちらも、コンポーネントのフィールドには新しい値が入っている。開発モードの `ng.applyChanges()` でそのコンポーネントの変更検知を手動で走らせると、正しい内容が表示される。画面内の要素をクリックするなど、そのコンポーネントのテンプレートでイベントが起きたときにも表示が追いつく。

## 再現手順

設定オブジェクト（実バックエンドの既存タスク、読み取りだけ）：

1. 設定オブジェクトを持つタスク（例：`hyperparameter-optimization`）の詳細で CONFIGURATION を開く
2. 左の CONFIGURATION OBJECTS から General を選ぶ
3. 右側のスピナーが回り続け、本文が表示されない

モデルの切り替え（モック API。実バックエンドにモデルを2つ以上持つタスクが無いため）：

1. 入力モデルを2つ持つタスクの ARTIFACTS を開き、1つ目の入力モデルを表示する
2. 左の一覧で2つ目の入力モデルを選ぶ
3. URL は2つ目のモデルに変わるが、右側の表示は1つ目のモデルのまま

スクリプトは [scripts/p2d-config-object.spec.ts](./scripts/p2d-config-object.spec.ts) と [scripts/p2d-artifacts-model-switch.spec.ts](./scripts/p2d-artifacts-model-switch.spec.ts)。全ルートを巡回して同じ型を探すスクリプトは [scripts/p2d-stale-view-crawl.spec.ts](./scripts/p2d-stale-view-crawl.spec.ts)（検出の仕組みは [scripts/helpers/stale-view.ts](./scripts/helpers/stale-view.ts)）。

## 期待する動作

Store の値や URL が変わったときに、コンポーネントの表示がそれに追随する。

## 原因

2つのコンポーネントとも `@Component` に `changeDetection` の指定が無い。Angular 22 では指定の無いコンポーネントが OnPush として動く（プラン §3 D）。上流が使う Angular 21 では Default（毎回検査される）として動いていた。

どちらも、Store や URL の値を `subscribe` の中でプレーンなフィールドに代入し、`markForCheck()` を呼んでいない。

- [experiment-info-task-model.component.ts:68](../src/app/webapp-common/experiments/containers/experiment-info-task-model/experiment-info-task-model.component.ts#L68)：`configInfo$` の値を `this.formData` に代入する。テンプレートは `formData` を読むが（[同 .html:6](../src/app/webapp-common/experiments/containers/experiment-info-task-model/experiment-info-task-model.component.html#L6)）、`configInfo$` 自体はテンプレートで購読していない
- [experiment-info-model.component.ts:67](../src/app/webapp-common/experiments/containers/experiment-info-model/experiment-info-model.component.ts#L67)：URL の `modelId` と `modelInfo$` を `combineLatest` し、`this.model`・`this.source`・`this.inputDesign` などに代入する。同じタスクの中でモデルを切り替えると `modelId` だけが変わり、テンプレートが `ngrxPush` で購読している観測値（`saving$`・`editable$`・`selectedExperiment$`・`modelLabels$`）は発火しない

OnPush のビューは、入力の変更・テンプレートのイベント・`markForCheck()`（`ngrxPush` / `async` パイプを含む）のどれかで印が付かない限り、ほかの箇所で変更検知が走っても検査されない。上流の Default のビューは、どこかで変更検知が走るたびに検査されていたため、代入の後の変更検知（API の応答後のほかのコンポーネントの更新など）で表示が追いついていた。

## 影響範囲と同種箇所

changeDetection の指定が無い109コンポーネントを次の2つの方法で調べ、症状が出たのはこの2つだけだった。

- 静的な検出：`subscribe`・`setTimeout`・`setInterval`・`then`・`addEventListener`・`requestAnimationFrame`・Observer のコールバックと `ngAfterViewInit` などの中で、テンプレートが読むプレーンなフィールドに代入し、`markForCheck()` / `detectChanges()` を呼ばないもの（コールバックから呼ぶメソッドも1段たどる）。該当は8コンポーネントで、残りの6つはテンプレートが同じ Store の値を `ngrxPush` で購読していて同時に印が付く、または描画の流れの最後で `detectChanges()` を呼ぶため、症状は出ない（プラン §8 フェーズ2の結果 D）
- 動的な検出：全ルート（フェーズ0の61ルートと、設定オブジェクト・成果物・モデルなど11ルート）を実バックエンドで開き、109コンポーネントの画面上のインスタンスに `ng.applyChanges()` を掛けて、前後で DOM が変わるものを探した。変わったのは設定オブジェクトだけだった（モデルの切り替えは操作の後にだけ起きるため、別に確かめた）

動的な検出は各ルートの初期表示だけを見ており、操作の後にだけ古くなる表示は、静的な検出で拾えたものしか確かめていない。

## 対策案

第一案は、2つのコンポーネントの `subscribe` の中で `ChangeDetectorRef.markForCheck()` を呼ぶ。`experiment-info-execution.component.ts` で同じ型を直したとき（比較資料 §5）と同じ方法で、2ファイルの数行の変更のため「小」とした。

第二案は、`formData` や `model` を `toSignal()` や `computed()` にして、テンプレートから signal として読む。変更検知の既定に依存しない形になるが、`model` から派生する値（`source`・`inputDesign` など）が多く、第一案より変更が大きい。

109コンポーネントに一律で `changeDetection: ChangeDetectionStrategy.Eager` を付けて上流の挙動に戻す案もあるが、プロジェクトは OnPush を前提にしており（AGENTS.local.md の指摘）、症状の出る箇所を個別に直すほうがよい。

## 検証範囲

- 確認したこと：Playwright（Chromium）で、設定オブジェクト（実バックエンド）とモデルの切り替え（モック API）の症状。どちらもコンポーネントのフィールドに新しい値が入っていて、`ng.applyChanges()` の後に正しく表示されること。全ルートの初期表示で、109コンポーネントのうち表示が古いままのものが設定オブジェクトだけであること
- 確認していないこと：実バックエンドでのモデルの切り替え（モデルを2つ以上持つタスクが無く、調査用タスクへのモデルの追加は実行できなかった）。出力モデルの切り替え（入力モデルと同じコンポーネント・同じ処理のため同じ症状になると判断した）。上流（Angular 21）を実際に動かしての比較
- 由来：2つのコンポーネントは比較資料で上流と一致する。Angular 21.2.22 では changeDetection の指定が無いコンポーネントは Default として動くこと（プラン §3 D）から、版上げで生じた不具合と判断した

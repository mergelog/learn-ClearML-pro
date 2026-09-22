# My Work を有効にしたまま自分の作業が無いプロジェクトを開くと、表題が All Tasks になり、タスクの作成が失敗する

| 項目 | 内容 |
|---|---|
| カテゴリー | 状態 |
| 不具合内容 | My Work を有効にしたまま、自分のタスク・モデルが無い他人のプロジェクトを開くと、Store の選択中プロジェクトが All Tasks（ID `*`）に置き換わる。パンくずは「All Tasks」になり、NEW TASK で保存した下書きは `project: '*'` で送られ、`Invalid project id` で失敗する |
| 期待動作 | URL のプロジェクトが存在する限り、パンくずにはそのプロジェクト名を出し、作成はそのプロジェクトに対して行う。存在しないプロジェクトの場合は、All Tasks と偽らずに「見つからない」ことを示す |
| 直さないと困ること | 同僚から共有されたプロジェクトのリンクを My Work 有効のまま開くと、全タスクの一覧だと誤解し、タスクも作れない。失敗後はタスクの作成が再読み込みまで効かなくなる（[23](./23_APIが一度失敗するとタスクの作成やキューの削除などが再読み込みまで何もしなくなる.md)） |
| 修正規模 | 小 |

| 項目 | 内容 |
|---|---|
| 画面 | プロジェクト > TASKS（パンくず、NEW TASK）。同じ置き換えはプロジェクトを選ぶ全画面で起きる |
| 観点 | H（ルーティングと画面遷移）、F（状態の整合） |
| 重大度 | S2 |
| 確度 | 再現済み（モック API） |
| 由来 | 上流 |
| 発生条件 | プロジェクトの一覧などで My Work を有効にしている。開いたプロジェクトが、自分が作ったものでなく、自分のタスク・モデルも含まない。または URL のプロジェクト ID が存在しない |
| 関連 | [23](./23_APIが一度失敗するとタスクの作成やキューの削除などが再読み込みまで何もしなくなる.md)（作成の Effect が1回の失敗で止まる）、[21](./21_ダッシュボードを開いた後に一覧でMy_Workを選ぶとURLから絞り込みの条件が消える.md)（My Work の別件） |

## 症状

モック API で、他人のプロジェクト `他人のプロジェクト`（ID `other-project`）を開いて比べた。

| 状態 | パンくず | Store の選択中プロジェクト | 下書きの保存（`tasks.create` の `project`） |
|---|---|---|---|
| My Work なし | PROJECTS / 他人のプロジェクト | `other-project` | `other-project`（作成される） |
| My Work あり | PROJECTS / All Tasks | `*` | `*`（「Failed to create tasks. Invalid project id」の通知） |

My Work ありでは、URL は `/projects/other-project/tasks` のままで、一覧はそのプロジェクトのタスク（My Work で自分のものに絞った結果）を表示する。NEW TASK ボタンは URL の ID で表示を判定するため押せるが、作成は失敗する。

存在しないプロジェクト ID（`/projects/no-such-project/tasks`）でも、My Work の有無にかかわらず同じ置き換えが起き、パンくずが「All Tasks」、一覧は0件になる（実バックエンドで確認）。

## 再現手順

1. プロジェクトの一覧で、絞り込みのメニューから **My Work** を選ぶ
2. 自分のタスク・モデルが無い、他人が作ったプロジェクトを URL などで開く（例：共有されたリンク、全体検索の結果）
3. パンくずが「All Tasks」になる
4. **NEW TASK** で名前・バイナリ・スクリプトを入れて **SAVE AS DRAFT** を押す
5. 「Failed to create tasks. Invalid project id」の通知が出る。以後、再読み込みまで NEW TASK の作成が何もしなくなる（23）

Playwright の再現は [scripts/p4-my-work-foreign-project.spec.ts](./scripts/p4-my-work-foreign-project.spec.ts)。モック API はサーバと同じく、`active_users` を付けた `projects.get_all_ex` に空を返す。

## 原因

選択中プロジェクトを取る Effect は、My Work 有効時に `active_users: [user.id]` を付けて `projects.get_all_ex` を呼ぶ（[core/effects/projects.effects.ts:55](../src/app/core/effects/projects.effects.ts#L55)）。結果が空だと、プロジェクトが存在しないものとみなし、`ALL_PROJECTS_OBJECT`（`{id: '*', name: 'All Tasks'}`）を選択中にする（[同:60](../src/app/core/effects/projects.effects.ts#L60)、[同:69](../src/app/core/effects/projects.effects.ts#L69)）。

サーバ（apiserver 2.4.0 の `project_bll.get_projects_with_selected_children`）は、`active_users` を指定すると、その利用者が作ったプロジェクトか、その利用者のタスク・モデルを含むプロジェクト（とその親）だけを返す。つまり空の結果は「存在しない」ではなく「自分の作業が無い」場合にも返る。

置き換えの後、画面の部位によって参照する ID が分かれる。

| 部位 | 参照する ID | 値 |
|---|---|---|
| NEW TASK の表示判定（[experiments.component.html:34](../src/app/webapp-common/experiments/experiments.component.html#L34)） | URL（[base-entity-page.ts:108](../src/app/webapp-common/shared/entity-page/base-entity-page.ts#L108)） | `other-project` |
| タスクの一覧の取得 | URL（`selectRouterProjectId`） | `other-project` |
| パンくず（[experiments.component.ts:821](../src/app/webapp-common/experiments/experiments.component.ts#L821)） | Store の選択中プロジェクト | `*` → 「All Tasks」 |
| タスクの作成（[common-experiments-view.effects.ts:871](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L871)、[同:873](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L873)） | Store の選択中プロジェクト | `*` |

`*` はサーバに存在しないため、`tasks.create` は `InvalidProjectId` で失敗する。この Effect は外側に `catchError` を置いており（[同:912](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L912)）、1回の失敗で完了する（23）。

## 影響範囲と同種箇所

- 置き換えは `setSelectedProjectId` を受ける共通の Effect で起きるため、タスク以外（モデル、パイプライン、データセット、レポートのプロジェクト）でも、選択中プロジェクトは `*` になる。My Work の状態は画面の種類（`projects`・`pipelines` など）ごとに持つ
- Store の選択中プロジェクトを使うほかの処理：モデルのメタデータ列の絞り込みの候補（[models-view.effects.ts:157](../src/app/webapp-common/models/effects/models-view.effects.ts#L157)）は、`*` のため全プロジェクトの値を候補に出す（コード上確定。画面では確かめていない）
- 存在しない ID の場合も同じ分岐を通る。タスク ID が存在しないときは「Fetch task failed」を出すのに対し、プロジェクトは All Tasks に偽装される

## 対策案

第一案：`active_users` の絞り込みを、選択中プロジェクトの取得（ID を指定した `projects.get_all_ex`）には付けない。選択中プロジェクトの情報は、My Work の有無と無関係にそのプロジェクトのものである。統計（`include_stats`）を自分の作業に絞りたい場合は、統計の取得にだけ条件を付ける。

第二案：結果が空のときに `ALL_PROJECTS_OBJECT` へ置き換えず、404 画面へ遷移するか、「プロジェクトが見つからない」ことを表示する。第一案と組み合わせると、空の結果は本当に存在しない場合だけになる。

あわせて、タスクの作成の Effect は Store ではなく URL のプロジェクト ID を使うか、`*` のときに作成を止める。作成の Effect が1回の失敗で止まる件は 23 で扱う。

## 検証範囲

- 確認したこと：モック API で、My Work の有無によるパンくず・Store の選択中プロジェクト・`tasks.create` の `project` の違いと、失敗の通知を確認した。存在しないプロジェクト ID のパンくずと空の一覧は実バックエンドで確認した。サーバの `active_users` の絞り込みは、起動中の apiserver のコードを読んで確かめた（読み取りだけ）
- 確認していないこと：実バックエンドで他人のプロジェクトを My Work 有効で開くこと（My Work の切り替えは利用者設定をサーバに書き込み、調査用の別ユーザも無いため）。モデル・パイプライン・データセット・レポートの画面での症状
- 由来：`core/effects/projects.effects.ts`・`common-experiments-view.effects.ts`・`experiments.component.html` は比較資料で実質差分に含まれない

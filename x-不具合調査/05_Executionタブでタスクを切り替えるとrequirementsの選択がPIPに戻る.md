# Execution タブで、PYTHON PACKAGES の表示を Original PIP などに切り替えても、別のタスクを選ぶと PIP に戻る

| 項目 | 内容 |
|---|---|
| カテゴリー | 画面UI |
| 不具合内容 | PYTHON PACKAGES の選択（PIP / Original PIP / Conda / Original Conda）を変えてから一覧で別のタスクを選ぶと、選択が PIP に戻る。上流は、切り替え先のタスクにも同じ種類があれば選択を保っていた |
| 期待動作 | 仕様の判断が要る。上流と同じく選択を保つか、タスクごとに PIP へ戻すか |
| 直さないと困ること | Original PIP を並べて見比べたい利用者が、タスクを切り替えるたびに選び直す。上流の挙動を前提にした利用者には、選択が勝手に変わったように見える |
| 修正規模 | 極小 |

| 項目 | 内容 |
|---|---|
| 画面 | 実験管理 > 詳細 > EXECUTION > PYTHON PACKAGES |
| 観点 | F（状態の整合） |
| 重大度 | S4 |
| 確度 | 要確認（挙動は再現済み。仕様か不具合かの判断が要る） |
| 由来 | カスタマイズ |
| 発生条件 | requirements を2種類以上持つタスク同士で、一覧から選択を切り替える |
| 関連 | 比較資料 §5 の「挙動差が1つある」 |

## 症状

タスク A の EXECUTION タブで PYTHON PACKAGES を Original PIP に切り替え、一覧でタスク B を選ぶ。タスク B も Original PIP を持っていても、選択は PIP に戻り、B の PIP の内容が表示される。

## 再現手順

1. requirements に `pip` と `orgPip` の両方を持つタスクを2つ用意する
2. タスク A の EXECUTION タブを開き、PYTHON PACKAGES のセレクタで Original PIP を選ぶ
3. 一覧でタスク B をクリックする
4. セレクタが PIP に戻っている

Playwright（モック API）では [scripts/05-execution-requirements.spec.ts](./scripts/05-execution-requirements.spec.ts) で再現した。切り替え後のセレクタの表示は `PIP`、表示されたパッケージは `package-b==1.0`（B の PIP）だった。

## 期待する動作

仕様として次のどちらかを決める必要がある。

- 上流と同じく、切り替え先のタスクが同じ種類の requirements を持つなら選択を保つ
- タスクごとに PIP から表示する（現在のカスタマイズ版の挙動）。この場合は不具合ではなく、比較資料 §5 の注記どおり仕様として明記する

## 原因

タスクを切り替えると、`base-experiment-output.component.ts` が `resetExperimentInfo` を dispatch し（[base-experiment-output.component.ts:121](../src/app/webapp-common/experiments/containers/experiment-ouptut/base-experiment-output.component.ts#L121)）、`infoData` が一度 null になる。Execution タブの購読（[experiment-info-execution.component.ts:125](../src/app/webapp-common/experiments/containers/experiment-info-execution/experiment-info-execution.component.ts#L125)）には、切り替えのたびに `formData` が falsy の値として一度流れてくる。

カスタマイズ版で抽出した純関数 [createExecutionRequirementsState()](../src/app/webapp-common/experiments/containers/experiment-info-execution/execution-requirements-state.ts#L20) は、`formData` が falsy のとき選択を既定値 `'pip'` にして返す（同ファイル L24–31）。コンポーネントはこの値を `selectedRequirement` に代入するため、次に届くタスク B の `formData` では、前の選択（`orgPip`）ではなく `'pip'` を基準に判定する。

上流のコンポーネントは `if (formData) { … }` で falsy の値を読み飛ばしていたため、`selectedRequirement` は前のタスクの選択のまま残り、B が同じ種類を持てばそれを表示していた（比較資料 §5）。

## 影響範囲と同種箇所

Execution タブの PYTHON PACKAGES だけである。falsy の `formData` に対して返す `options: []`・`editable: true`・`resetTooltip: ''` は、テンプレートが `@if (formData)` で本体を囲んでおり、`formData` の無いあいだは描画しないため、画面には出ない。

## 対策案

上流の挙動に戻す場合は、`formData` が falsy のときに前回の選択を保つ（純関数に前回の状態を渡して返す、またはコンポーネント側で falsy の値を読み飛ばす）。1ファイルの数行で「極小」とした。単体テスト（`execution-requirements-state.spec.ts`）の期待値も合わせて変える。

現在の挙動を仕様とする場合は、コードは変えず、純関数のコメントか ADR に「タスク切り替え時は PIP に戻す」と明記する。

## 検証範囲

- 確認したこと：Playwright（モック API）で、Original PIP を選んでから別タスクへ切り替えると PIP に戻ること。タスク切り替えで `resetExperimentInfo` が dispatch されること（コード）
- 確認していないこと：上流のコードを実際に動かしての比較（上流は取得していない。上流の挙動は比較資料 §5 の記述とコードからの推論）
- 由来：`experiment-info-execution.component.ts` と `execution-requirements-state.ts` は比較資料 §5 のカスタマイズ（分類8）

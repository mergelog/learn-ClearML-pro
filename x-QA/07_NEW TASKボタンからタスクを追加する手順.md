# [+ NEW TASK] ボタンからタスクを追加する手順

## 結論

`[+ NEW TASK]` は `CreateExperimentDialogComponent`（5ステップの stepper）を開き、
入力内容を `tasks.create` に渡して Draft タスクを 1 件作る。Run ステップで Queue を
選んでいれば、続けて `tasks.enqueue` が走り Agent が実行する。

**このリポジトリの学習コードに対しては、ダイアログの Arguments ステップは効かない。**
引数は Code ステップの Module 欄にコマンドラインとして直接書く（理由は後述）。

---

## 1. ボタンから tasks.create までの経路

```text
[+ NEW TASK] (experiments.component.html:38-48)
  └─ newExperiment() (experiments.component.ts:781-788)
       └─ MatDialog.open(CreateExperimentDialogComponent)
            └─ 閉じたら createExperiment({data}) を dispatch
                 └─ createExperiment effect (common-experiments-view.effects.ts:868-915)
                      └─ apiTasks.tasksCreate(...)  → Draft タスク生成
                           ├─ createExperimentSuccess
                           │    ├─ 成功トースト（open task リンク付き）
                           │    └─ refreshExperiments で一覧更新
                           └─ enqueueCreateExperiment (queue 選択時のみ)
                                └─ apiTasks.tasksEnqueue(...)
```

### ボタンが出る条件

[experiments.component.html:35](../src/app/webapp-common/experiments/experiments.component.html#L35)

- `selectedProjectId !== '*'` … **個別プロジェクトを開いているときだけ**表示。All Projects では出ない
- `inArchivedMode()` / `exampleProject()` のとき disabled

---

## 2. 手順（このリポジトリの学習タスクを作る場合）

### 事前準備

```bash
pnpm backend:up          # ClearML サーバ
pnpm agent:up            # semiconductor-training キューの Agent
pnpm backend:data:status # Dataset のバージョン番号を確認
```

### ステップ 1: プロジェクトを開いて [+ NEW TASK]

`Semiconductor Quality Prediction` などの個別プロジェクトを開く。

### ステップ 2: Code

| 項目 | 値 |
|---|---|
| Task Name | 任意（3文字以上） |
| Task Type | Training |
| Git | 開かない（空のまま） |
| Working Directory | `.` |
| ラジオ | Python |
| Binary | `python3` |
| Type | **Module** |
| Module | `ml.semiconductor_quality.cli --dataset-version 1.0.0` |
| Add `Task.init` call | **OFF** |

Module 欄に引数を全部並べて書く。例:

```
ml.semiconductor_quality.cli --dataset-version 1.0.0 --algorithm random-forest --n-estimators 300 --class-weight balanced
```

- 必須は `--dataset-version` のみ。他はすべてデフォルトあり
- **`--queue` は書かない**。Agent 上でさらに自分を enqueue してしまう
- `Add Task.init call` を OFF にするのは、コード側が既に `Task.init` を呼んでいるため

### ステップ 3: Arguments

**何も入れない。**（効かない。理由は「3. Arguments が効かない理由」）

### ステップ 4: Environment

`Additional Packages` で **Manual** を選び、貼り付ける。

```
clearml>=2.0,<3
joblib>=1.4,<2
numpy>=2.0,<3
pyyaml>=6.0,<7
scikit-learn>=1.7,<2
```

Agent は venv モード（`daemon --foreground --queue ...`、`--docker` なし）で動き、
Agent イメージには `requirements/agent.txt` しか入っていない。ここを省くと
学習時に sklearn が無くて落ちる。

### ステップ 5: Container

全部空のまま。

### ステップ 6: Run

| 項目 | 値 |
|---|---|
| Queue | `semiconductor-training` |
| Destination | 空 |

`RUN` を押す。`SAVE AS DRAFT` なら作成のみで実行しない。

### ステップ 7: 確認

タスク詳細の CONSOLE タブ、または `pnpm agent:logs`。

---

## 3. Arguments ステップが効かない理由

ClearML 本来の仕組みでは、Args セクションの値は SDK が argparse にパッチを当てて
**パーサの default として注入**し、あわせて `required = False` にする
（`clearml/backend_interface/task/args.py` の `copy_to_parser`）。
Agent 側はコマンドラインに何も足さない（clearml-agent のソースに `Args` の参照なし）。

このリポジトリの学習コードは、その argparse 連携を明示的に切っている。

- [clearml_tracking.py:312-321](../ml/semiconductor_quality/clearml_tracking.py#L312) — `Task.init(..., auto_connect_arg_parser=False)`

したがって UI の Args は argparse に届かず、値を入れても無視される
（UI 上には残るので気付きにくい）。

さらに、パラメータは `task.connect(dict, name=...)` で名前付きセクションとして
記録されるが（[clearml_tracking.py:129-150](../ml/semiconductor_quality/clearml_tracking.py#L129)）、
渡しているのは `asdict(config.*)` のコピーであり、`config` 自体は
`build_command(sys.argv[1:])` の時点で確定済み。**CONFIGURATION セクションを
UI で書き換えても実行内容は変わらない。**

→ 引数を変える唯一の経路が Module 欄（= `script.entry_point`）。
Agent は `-m` で始まる entry_point を `shlex.split()` してコマンドに展開するため、
`-m ml.semiconductor_quality.cli --dataset-version 1.0.0` がそのまま
`python3 -m ml.semiconductor_quality.cli --dataset-version 1.0.0` として実行される
（clearml_agent `commands/worker.py` の entry_point 処理）。

---

## 4. ダイアログの入力項目と tasks.create へのマッピング

[create-experiment-dialog.component.ts:63-89](../src/app/webapp-common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component.ts#L63) が
ダイアログの返却値、[common-experiments-view.effects.ts:871-911](../src/app/webapp-common/experiments/effects/common-experiments-view.effects.ts#L871) が変換部分。

| ダイアログ | tasks.create |
|---|---|
| Task Name | `name` |
| Task Type | `type`（既定 `training`） |
| Repository URL / Branch・Commit・Tag | `script.repository` / `script.branch`・`version_num`・`tag` |
| Working Directory | `script.working_dir` |
| Binary | `script.binary` |
| Script / Module / Custom code | `script.entry_point`（Module は `-m ` 前置、Shell の Script は `-c ` 前置） |
| Custom code の中身 | `script.diff`（git diff 形式に整形して格納） |
| Arguments | `hyperparams.Args`（先頭の `--` は除去される） |
| Requirements = Manual | `script.requirements.pip` |
| Requirements = Skip | container args に `-e CLEARML_AGENT_SKIP_PYTHON_ENV_INSTALL=1` |
| Poetry / venv 指定 / Task.init | container args の `-e CLEARML_AGENT_FORCE_POETRY` 等 |
| 環境変数 | container args の `-e KEY:VALUE` |
| Docker image / script | `container.image` / `container.setup_shell_script` |
| Output Destination | `output_dest` |
| Queue | 作成後 `tasks.enqueue` に使用 |

---

## 5. この環境固有の前提

[infra/clearml/compose.yaml:157-244](../infra/clearml/compose.yaml#L157)

- Queue は `semiconductor-training`（学習）と `semiconductor-pipeline`（Pipeline 制御）の 2 本
- `CLEARML_AGENT_FORCE_CODE_DIR: /workspace` … **git clone せず、マウント済みの作業ツリーを使う**。
  そのため Repository URL は入れても意味がなく、Working Directory は `/workspace`
  （= リポジトリルート）からの相対パス
- 作業ツリーは read-only マウント
- Agent は `network_mode: host`。成果物 URL がホストのブラウザから開けるようにするため

---

## 6. 使える引数一覧

[cli.py:119-272](../ml/semiconductor_quality/cli.py#L119)

| 引数 | 既定 | 備考 |
|---|---|---|
| `--dataset-version` | **必須** | 登録済み Dataset のバージョン |
| `--dataset-project` | `Semiconductor Quality Prediction` | |
| `--dataset-name` | `semiconductor-quality-data` | |
| `--dataset-csv-path` | `semiconductor_quality.csv` | Dataset ルートからの相対 |
| `--task-project` | `Semiconductor Quality Prediction/Training` | |
| `--task-name` | `random-forest-quality-classifier` | |
| `--train-ratio` / `--validation-ratio` / `--test-ratio` | 設定既定 | 分割比 |
| `--algorithm` | `random-forest` | `random-forest` / `logistic-regression` / `hist-gradient-boosting` |
| `--max-depth` | なし | 木の深さ上限 |
| `--min-samples-leaf` | なし | 葉の最小サンプル数 |
| `--max-iterations` | なし | logistic-regression / boosting |
| `--n-estimators` | 設定既定 | random-forest のみ |
| `--learning-rate` | 設定既定 | hist-gradient-boosting のみ |
| `--regularisation` | 設定既定 | logistic-regression のみ |
| `--class-weight` | 設定既定 | `balanced` / `none` |
| `--decision-threshold` | なし | 確率のカット位置 |
| `--random-seed` | `20260906` | |
| `--queue` | なし | **UI から作るタスクでは使わない** |

# Runbook: QueueとAgentによるリモート学習

開発者の端末で直接学習する代わりに、ClearMLのQueueへTaskを投入し、
`clearml-agent` に実行させるための手順。

## この構成で何が変わるか

```text
[開発者の端末]                       [clearml-agent コンテナ]
python -m ml.semiconductor_quality.cli
  --dataset-version 1.0.0 --queue
        |
        | 1. Taskを作成し、契約と来歴を記録
        | 2. Queue "semiconductor-training" へ引き渡す
        v
   ClearML Server  ------------------->  3. Taskを取得
                                          4. requirements/training.txt から
                                             学習環境を用意
                                          5. /workspace のコードで学習
                                          6. Metrics / Artifact / Model を記録
```

投入した端末は学習しない。学習に必要なライブラリが端末に無くても、
同じ入力から同じ結果を得られる。

## 前提

- `pnpm backend:up` でClearML Serverが起動している
- `./clearml.conf` に有効な認証情報がある
- Datasetが登録されている（`pnpm seed:semiconductor:dataset`）

## 1. Agentのイメージを作る

```bash
corepack pnpm agent:build
```

`infra/training/Dockerfile` の `agent` ターゲットを作る。ベースイメージは
digestで固定してあるので、同じDockerfileからは同じ土台が得られる。

## 2. Agentを起動する

```bash
corepack pnpm agent:up
corepack pnpm agent:logs
```

ログに購読中のQueueが出れば起動できている。

```text
Worker "<host>:0" - Listening to queues:
| id  | name                   |
| ... | semiconductor-training |
```

`agent:up` は直接 `docker compose up` を呼ばず `scripts/backend-up.sh` を通す。
起動中のコンテナは自分がどのイメージから起動したかを読めないため、
digestを外から渡す必要があるからである。

## 3. QueueへTaskを投入する

```bash
corepack pnpm ml:train -- --dataset-version 1.0.0 --queue
```

`--queue` に値を付けなければ `semiconductor-training` へ入る。
別のQueueを使うときは `--queue gpu-training` のように名前を渡す。

投入したプロセスの出力。

```text
Queued ClearML Task <task id> on semiconductor-training.
Nothing was trained here. A ClearML Agent carries the Task out.
```

## 4. 正常終了を確認する

Web UI（<http://localhost:8080>）の
`Semiconductor Quality Prediction/Training` プロジェクトでTaskを開く。

| 見る場所 | 確認すること |
| --- | --- |
| STATUS | `Completed` |
| CONSOLE | `Environment setup completed successfully` の後に学習ログ |
| SCALARS | validation と test の accuracy / precision / recall / f1 |
| PLOTS | 両splitのconfusion matrix |
| ARTIFACTS | `data_validation` と `evaluation` |
| MODELS | `semiconductor-quality-classifier` |
| CONFIGURATION > HYPERPARAMETERS | 後述の来歴 |

コマンドラインからも確認できる。

```bash
corepack pnpm backend:data:status
```

## 5. Taskに残る来歴

`CONFIGURATION > HYPERPARAMETERS` に、次の2つの区画がある。
両者を分けているのは、投入した人と実行した環境が別だからである。

`Provenance` は「誰がどのコードから依頼したか」。Taskを複製しても変わらない。

| 名前 | 意味 |
| --- | --- |
| `git_commit` / `git_branch` / `git_remote` | 依頼時のコード |
| `git_working_tree` | `clean` か `dirty`。dirtyならcommitだけでは実行内容を特定できない |
| `executed_by` | 依頼した利用者 |
| `queue` | 投入先Queue。端末で直接実行した場合は `local` |

`Runtime` は「実際に動かした環境」。Agentが実行したときはAgentの値になる。

| 名前 | 意味 |
| --- | --- |
| `image_reference` / `image_digest` | 実行に使ったイメージ |
| `python_version` | 実行したPython |
| `hostname` | 実行したホスト |

`Execution/command_line` には、依頼時のコマンドラインがそのまま入る。
Agentは引数なしでエントリポイントを起動するため、この値を読み戻して実行する。

## 6. 失敗系を確認する

存在しないDataset Versionを指定すると、投入は成功し、Agent側で失敗する。

```bash
corepack pnpm ml:train -- --dataset-version 9.9.9 --queue --task-name failing-dataset-version
```

| 見る場所 | 確認すること |
| --- | --- |
| STATUS | `Failed` |
| STATUS REASON | 例外の型名 |
| CONSOLE | `Training failed: Could not find Dataset project/name/version ...` |
| MODELS | 何も登録されていない |

失敗したTaskも来歴を持つ。「動かなかった実行」も追跡できる状態を保つため、
Taskは学習を始める前に作られる。

## 7. 止める

```bash
corepack pnpm backend:down
```

Agentだけ止める場合は次のようにする。

```bash
docker compose -f infra/clearml/compose.yaml stop training-agent
```

## トラブルシュート

| 症状 | 原因と対処 |
| --- | --- |
| `No tasks in queue` のまま進まない | 投入先Queue名とAgentの購読Queue名が違う。`agent:logs` の一覧と `--queue` の値を合わせる |
| `Read-only file system: '/workspace/...'` | 作業ツリーは読み取り専用で渡している。書き込み先を `/home/app/.clearml` 配下へ向ける（`CLEARML_CACHE_DIR`） |
| Agentが `localhost:8008` へ繋がらない | Agentは `network_mode: host` でホストの公開ポートを使う。ClearML Serverが起動しているか確認する |
| Task状態が `Aborted` になる | 実行中にTaskの状態を外から変えるとAgentは中断とみなす。学習コードはAgent配下では最終状態をAgentに委ねる |
| 学習環境の構築が毎回遅い | `clearml-agent-home` ボリュームのvenvキャッシュが効いていない。ボリュームを消していないか確認する |

## 併存リポジトリへの影響

`../learn-ClearML` とはポート 8008 / 8080 / 8081 を共有する。
Agentは `network_mode: host` でそれらを使うため、あちらのClearML Serverが
起動している状態でこちらのAgentを動かしてはいけない。

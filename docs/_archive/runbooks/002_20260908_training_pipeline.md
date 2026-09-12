# Runbook: 学習Pipeline

Dataset検証から候補モデルの登録までを、5つの独立したTaskとして実行する。

## この構成で何が変わるか

単発の学習（`pnpm ml:train`）は、検証・分割・学習・評価・登録を1つのプロセスで
行う。再現はできるが、「どこで止まったか」「一部だけやり直す」「途中結果を
別の実行で使い回す」ができない。

Pipelineは同じ仕事を5つのTaskへ分ける。

```text
validate ──> preprocess ──> train ──┬─> evaluate ──> register-candidate
                                    └───────────────────^
```

| ステップ | 読むもの | 残すもの |
| --- | --- | --- |
| `validate` | Dataset Version | `Resolved Dataset/dataset_id`、`validation_report` |
| `preprocess` | validateが承認したDataset ID | `split`（npz）、`split_summary` |
| `train` | preprocessの `split` | `model_weights`（joblib） |
| `evaluate` | preprocessの `split`、trainの `model_weights` | scalars、confusion matrix、`evaluation` |
| `register-candidate` | trainの `model_weights`、evaluateの `evaluation` | Output Model、`registration_decision` |

ステップ間の受け渡しは、共有ディレクトリではなくArtifactで行う。
別のマシンで、別の時刻に動かしても同じように読める。

`preprocess` はDataset **Version** ではなく、validateが記録したDataset **ID**
で読み直す。Versionのラベルは後から別の行へ付け替えられるが、IDは変わらない。
これにより「学習した行は、検証に通った行そのもの」だと示せる。

## 前提

`docs/_archive/runbooks/001_20260908_queue_and_agent.md` の手順でAgentが起動していること。
Pipelineの各ステップはそのAgentが実行する。

## 1. ステップのテンプレートを作る

Pipelineはコードを持たない。ステップごとの「まだ実行していないTask」を複製し、
Parameterを書き換えて実行する。テンプレートは初回に一度だけ作る。

```bash
corepack pnpm ml:pipeline -- --dataset-version 1.0.0 --templates-only
```

作られたTaskは `Semiconductor Quality Prediction/Pipeline/Steps` にあり、
状態は `Created` のままである。

## 2. Pipelineを実行する

```bash
corepack pnpm ml:pipeline -- --dataset-version 1.0.0
```

引数は単発学習と同じものが使える（`--n-estimators`、`--train-ratio`、
`--random-seed` など）。同じ入力を与えれば、単発学習の結果と比較できる。

制御役（controller）はこのプロセスで動く。モデルもデータも持たず、
ステップTaskを複製してQueueへ入れ、終わるのを待つだけである。

出力。

```text
Pipeline semiconductor-quality-training finished with status completed.
Steps that ran: validate, preprocess, train, evaluate, register-candidate
```

## 3. 正常系を確認する

Web UIの **PIPELINES** から `semiconductor-quality-training` を開く。

| 見る場所 | 確認すること |
| --- | --- |
| DAGの図 | 5つのステップと依存の向き |
| 各ノード | 所要時間、状態、対応するTaskへのリンク |
| `validate` のARTIFACTS | `validation_report`（行数・列・ラベル分布） |
| `preprocess` のARTIFACTS | `split`（npz）と `split_summary` |
| `train` のARTIFACTS | `model_weights` |
| `evaluate` のSCALARS / PLOTS | validationとtestの指標、confusion matrix |
| `register-candidate` のMODELS | `semiconductor-quality-classifier` |
| `register-candidate` のARTIFACTS | `registration_decision`（根拠にした実行のID） |

## 4. 検証失敗で止まることを確認する

存在しないDataset Versionを指定する。

```bash
corepack pnpm ml:pipeline -- --dataset-version 9.9.9
```

```text
Pipeline semiconductor-quality-training finished with status failed.
Steps that ran: none
```

`validate` が失敗し、後続は起動すらしない。終了コードは1になる。
Pipelineの図では `validate` だけが赤く、他は未実行のまま残る。

## 5. 1ステップだけ手元で再実行する

原因を追うときは、ステップ単体でも実行できる。

```bash
CLEARML_CONFIG_FILE=$PWD/clearml.conf \
  .venv/bin/python -m ml.pipeline.step_cli --step validate
```

この場合の入力は、新しく作られるTaskのParameterから読む。
Web UIでTaskを複製してParameterを書き換え、Queueへ入れ直す方法でもよい。

## トラブルシュート

| 症状 | 原因と対処 |
| --- | --- |
| `this step needs Dataset/dataset_version to be set` | テンプレートのParameterが欠けている。`--templates-only` で作り直す |
| `preprocess_task_id` が空だと言われる | Pipelineの `${step.id}` が解決されていない。ステップ名と `parents` の綴りを確認する |
| `the 'split' artifact is missing from Task ...` | 上流ステップが成果物を残す前に落ちている。上流TaskのCONSOLEを見る |
| `the model artifact at ... cannot be read (EOFError: ...)` | 学習ステップが上げた重みが、この段に届くまでに壊れている。上流TaskのARTIFACTSでファイルの大きさを確認し、学習からやり直す |
| ステップがQueueで止まったまま | Agentが起動していない。`pnpm agent:logs` を見る |
| 実行のたびにステップが遅い | Agentがステップごとにvenvを作る。`clearml-agent-home` ボリュームのキャッシュが効いているか確認する |

## いまは実装していないこと

計画書のとおり、次は縦スライスを通した後の強化項目として残している。

- ステップ結果のキャッシュ（同じ入力なら再実行しない）
- 失敗時のretryとtimeout
- 完了・失敗の通知
- 評価ゲート（`register-candidate` は現時点で基準を見ずに登録する）

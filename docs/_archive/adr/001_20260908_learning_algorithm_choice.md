# ADR 001: 学習アルゴリズムに RandomForest を採用する

- 状態: 採用
- 日付: 2026-09-08
- 対象: `ml/semiconductor_quality`（半導体品質分類）

## 背景

Pipelineと評価ゲートを組み上げるまで、学習アルゴリズムはRandomForestに固定して
いた。基盤づくり中に論点を増やさないための固定であって、RandomForestが最適だと
確かめた結果ではない。

基盤が動いたので、期間を区切って比較する。目的は精度の追求ではなく、
次の2つを確かめることである。

1. 共通の契約からモデル固有の実装が分離できているか
2. Pipelineと評価ゲートがRandomForest専用になっていないか

## 比較した条件

scikit-learn内の3系統に限定した。XGBoost / LightGBM / CatBoost / SVM /
ニューラルネットワークへは広げない。

揃えたもの。

| 項目 | 値 |
| --- | --- |
| Dataset Version | 1.0.0（`3c913ea3...`、1,200行） |
| 分割 | train 0.6 / validation 0.2 / test 0.2、層化 |
| 乱数seed | 20260906（分割とモデルで共有） |
| 前処理 | 数値列 StandardScaler、カテゴリ列 OneHotEncoder |
| 評価契約 | 陽性ラベルは `fail`、accuracy / precision / recall / f1 |

変えたものは `--algorithm` だけである。HPOも特徴量追加も行っていない。

## 結果

判定は validation で行う。test は採用したモデルの最終確認に一度だけ使う。

| アルゴリズム | recall | f1 | precision | 学習時間 | 推論時間 | モデルサイズ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `logistic-regression` | 0.2418 | 0.3465 | 0.6111 | 0.01秒 | 4.6 µs/行 | 3 KB |
| `random-forest` | **0.6264** | **0.7215** | 0.8507 | 0.37秒 | 185.7 µs/行 | 3,092 KB |
| `hist-gradient-boosting` | 0.6154 | 0.6707 | 0.7368 | 0.17秒 | 11.9 µs/行 | 663 KB |

評価ゲートの基準（validation の recall >= 0.55、f1 >= 0.65）を満たすのは
`random-forest` と `hist-gradient-boosting` の2つで、`logistic-regression` は
満たさない。

ClearML Task: `c186a154...`（linear）/ `4037754...`（forest）/ `c97f6b21...`（boosting）

## 決定

**`random-forest` を採用する。**

理由。

- 不良の検出率（recall 0.6264）と釣り合い（f1 0.7215）がいずれも最も高い
- precision も最も高く、良品を不良と誤判定する量が最も少ない
- 現在のデータ量では推論時間 185.7 µs/行 が問題にならない。
  1,200行の全件推論でも 0.2 秒程度である

採用したモデルの test での最終確認: accuracy 0.8167 / precision 0.8406 /
recall 0.6374 / f1 0.7250。validation と大きくずれておらず、
validation で選んだ判断が test でも保たれている。

## 見送った選択肢

**`logistic-regression`**: 学習も推論も桁違いに速く、モデルは3KBで説明もしやすい。
しかし recall 0.2418 は「不良の4分の3を見逃す」ことを意味し、品質判定として
成立しない。線形の基準線としては役に立った。RandomForestの重さが、
確かに精度を買っていることを示せた。

**`hist-gradient-boosting`**: recall は RandomForest とほぼ同等（0.6154 対 0.6264）
でありながら、推論は約15倍速く、モデルは約4.7分の1である。
今回は f1 と precision の差で RandomForest を採った。ただし次の条件が変われば
再検討する価値がある。

- 推論の応答時間や単価が制約になったとき
- モデルを配布する経路の容量が問題になったとき
- データ量が増え、RandomForest の推論時間が線形に効いてきたとき

## 設計上の確認

このスパイクで確かめたかったことの結果。

| 確認したいこと | 結果 |
| --- | --- |
| trainerの共通契約からモデル固有実装を分離できているか | できている。`config.EstimatorConfig` が設定、`algorithms.build_classifier` が生成を持ち、`train.py` はどちらにも依存しない |
| PipelineやゲートがRandomForest専用になっていないか | なっていない。Pipelineは `Model/algorithm` を読むだけで、ゲートは指標名しか見ない |
| 同じ条件の実験をClearML上で比較できるか | できる。3TaskはDataset・分割・seedが同一で、`Model` セクションだけが違う |
| 採用モデルからDataset・Task・コード・評価結果へ遡れるか | 遡れる。W4の昇格フローで確認済み |

## 影響

- `TrainingConfig.forest` は `TrainingConfig.estimator` になった
- Task Parameter のセクション名は `RandomForest` から `Model` になった
- 精度に加えて `Cost`（学習時間・推論時間・モデルサイズ）が記録されるようになった
- アルゴリズムを変えても Pipeline・ゲート・Registry は変更不要である

## この先の扱い

スパイクはここで終える。精度の追求は続けない。
探索的なハイパーパラメータ調整は計画書 P2-12（HPO）で扱う。

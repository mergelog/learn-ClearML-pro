# stackup

ClearML WebをAngular 22へ更新し、ローカルのClearML Serverと接続して動かすためのプロジェクトです。

## 目次

- [公式docs](#公式docs)
- [構成](#構成)
- [使用バージョン](#使用バージョン)
- [検証](#検証)
- [リモート学習（Queue / Agent）](#リモート学習queue--agent)
- [学習Pipeline](#学習pipeline)
- [データ品質・lineage・drift](#データ品質lineagedrift)
- [モデルの昇格とrollback](#モデルの昇格とrollback)
- [学習アルゴリズムの比較](#学習アルゴリズムの比較)
- [ハイパーパラメータ探索](#ハイパーパラメータ探索)
- [推論サービス](#推論サービス)
- [AngularからPipelineを起動する](#angularからpipelineを起動する)
- [観測性と運用アラート](#観測性と運用アラート)
- [認証・認可・秘密・供給網](#認証認可秘密供給網)
- [初回セットアップ](#初回セットアップ)
- [起動方法](#起動方法)
- [ログインする](#5-ログインする)
- [URL](#url)
- [よく使うコマンド](#よく使うコマンド)
- [環境変数](#環境変数)
- [ポートを変更する](#ポートを変更する)
- [WSLから家庭内LANへ公開する](#wslから家庭内lanへ公開する)
- [ブラウザに400エラーが表示される場合](#ブラウザに400エラーが表示される場合)
- [補足](#補足)

## 公式docs

公式Web UI全体解説: https://clear.ml/docs/latest/docs/webapp/webapp_overview/
Projects画面: https://clear.ml/docs/latest/docs/webapp/webapp_projects_page/
Project Overview画面: https://clear.ml/docs/latest/docs/webapp/webapp_project_overview/
Datasets画面: https://clear.ml/docs/latest/docs/webapp/datasets/webapp_dataset_page/
Workers・Queues画面: https://www.clear.ml/docs/latest/docs/webapp/webapp_workers_queues/

## 構成

```text
.
├── apps/web/             # Angular 22版 ClearML Web
├── docs/                 # 設計判断(adr)と運用手順(runbooks)
├── infra/clearml/        # ClearML ServerとAgent用Docker Compose
├── infra/training/       # 学習・Agentイメージのビルド定義
├── infra/serving/        # 推論サービスイメージのビルド定義
├── ml/semiconductor_quality/  # 学習のドメインとClearML境界
├── ml/pipeline/          # 学習Pipelineのステップと制御
├── ml/model_lifecycle/   # 評価ゲートとモデルの昇格・rollback
├── ml/data_quality/      # データ品質契約・drift検知・lineage
├── ml/experiment/        # ハイパーパラメータ探索（設定・試行・引き渡し）
├── config/               # 運用が編集する設定（合格基準など）
├── config/experiment/    # 実験設定（共通の意味と環境別の予算）
├── services/prediction_api/  # 推論サービス（FastAPI）
├── tools/                # 上流データ準備（テストデータ作成）スクリプト
├── scripts/              # リポジトリ共通のスクリプト
├── requirements/         # Python依存の宣言（*.in）と固定（*.txt）
├── .github/workflows/    # CI定義
├── .env.example          # 環境変数のサンプル
├── pyproject.toml        # Pythonのlint・型・カバレッジ設定
└── package.json          # プロジェクト共通コマンド
```

## 使用バージョン

- Node.js 24（`.nvmrc`）
- pnpm 10
- Python 3.10（`.python-version`）
- Angular 22.1
- ClearML Server 2.4.0
- Docker Compose v2

Pythonのパッケージは `requirements/*.in` で互換範囲を宣言し、
`requirements/*.txt` に実際の版数を固定しています。学習、推論、
clearml-agent はすべてこの固定版を使います。

## 検証

ローカルとCIは同じコマンドを同じ順序で実行します。`.github/workflows/ci.yml` は
ここにあるscriptを**呼びます**。中身を書き写しません。

```bash
corepack pnpm verify
```

| コマンド | 内容 |
| --- | --- |
| `pnpm verify:python` | `ruff` によるlint、`mypy` による型検査、カバレッジ付き単体テスト |
| `pnpm verify:web` | ゲート自身のテスト、CIの一致、テストの層、ESLint基準値、依存境界、Pipeline契約、`strict` 型検査、Angular単体テスト、E2E型検査、本番ビルド、生成物の秘密検査 |
| `pnpm verify:security` | 追跡されているファイル全体の秘密検査 |

E2E（Playwright、27件）は `verify` に入っていません。理由と動かし方は
「[E2E](#e2e)」にあります。

`verify:web` はPython仮想環境（`pnpm py:setup`）を必要とします。最後の
「生成物に資格情報が残っていないこと」の確認に、秘密検査の道具を使うためです。

### CIがこの検証を本当に走らせていること

CIがscriptを呼ばず中身を書き写していた頃、書き写す過程で検証が落ちていました。
`services/tests`（認可13件を含む133件）と `web:contract` はCIで一度も走らず、
それでもCIは緑であり続けました。**走っていないことは、走っていないという理由では
表に出てきません。**

足りない行を足すだけでは、script が1つ増えるたびに同じことが起きます。
そこで一致そのものをゲートにしました。

```bash
corepack pnpm ci:parity
```

`verify:python` / `verify:web` / `verify:security` の各要素が、`ci.yml` の
担当ジョブで同じ順序で呼ばれていることを確かめます。落ちていれば失敗します。
`verify:web` の先頭近くに入っているので、手元でもCIでも毎回走ります。

見るのは片方向だけです。`requirements` のlock検証やTrivy走査のように
**手元の `verify` に無いCI固有の手順**は、そのまま置けます。揃えたいのは
「手元にある検証がCIで必ず走ること」であって、CIから固有の手順を無くすことでは
ありません。

### E2E

E2Eは `verify` に入れず、CIでも独立したジョブ（`e2e`）で走らせます。

```bash
corepack pnpm web:e2e
```

`verify` に入れないのは、本番相当のビルドとサーバ起動で数分かかるためです。
`verify` は変更のたびに手元で回す速さで作ってあり、ここへ入れると回されなく
なります。CIで web ジョブへ足さないのも同じ理由の裏返しで、lintや単体テストの
結果がE2Eの待ち時間の後ろに隠れます。

ClearMLのAPI応答は `apps/web/e2e/fixtures` が差し替えるので、backendは
要りません。Playwrightは `CI` が立っているときだけdev serverを自前で起動し
（`apps/web/playwright.config.ts`）、手元では起動済みのものを使い回します。
**ソースを変えてから測るときは `ng serve` を落としてください。**
落とさないと、直したはずの変更が反映されていない結果を見ます。

`verify` の外にあっても、CIから落ちたときに気付けないままにはしません。
`ci:parity` の `COVERAGE` が `web:e2e` と `e2e` ジョブの対応を固定しています。

`apps/web/e2e/accessibility.spec.ts` は、**自作画面**（`sm-quality-pipeline-page`
の中）に axe の違反が無いことを見ます。取り込んだ ClearML Web の外枠には違反が
残っていますが、そこは凍結領域で、直しても取り込み直しのたびに消えます。
自分たちが書いた範囲は baseline を作らず0件で固定します。

`apps/web/e2e/smoke.spec.ts` は、1本の流れ（Dataset登録 → Queue学習 → 比較 →
昇格 → 推論への受け渡し）が縦に繋がっていることだけを5件で見ます。すべての
画面が `e2e/fixtures/smoke.fixture.ts` の**同じ1つの世界**を見るので、どこかで
取り違えが起きれば後ろの画面が別のものを出します。最後の節目が推論そのもの
ではないのは、画面が推論サービスを呼んでいないためです。画面が言える最後の
ことは「どのモデルのどのバージョンが提供されるか」で、推論が実際に答えるかは
`services/tests` と `scripts/serving-smoke.sh` が見ます。

### テストの層

どの層で何を確かめるかを `test-pyramid.json` に宣言し、実際の置き場所が
それと合っていることをゲートで確かめます。判断の経緯は
[docs/adr/005_20260911_test_pyramid.md](docs/adr/005_20260911_test_pyramid.md)
にあります。

```bash
corepack pnpm test:pyramid          # 宣言と実態が合っているか
corepack pnpm test:pyramid:report   # 層ごとのファイル数・ケース数を見る
```

| 層 | 確かめること | 走らせ方 |
| --- | --- | --- |
| ゲート自身 | 検査スクリプトが、落とすべきものを本当に落とすこと | `pnpm web:gates:test` |
| `ml` 単体 | 学習・評価・昇格・driftの**判断**（しきい値・境界・失敗時にどちらへ倒すか） | `pnpm ml:test` |
| `services` 単体 | `prediction_api` / `ops_exporter` の入出力・認可・失敗応答 | `pnpm services:test` |
| `tools` 単体 | CLIの判断（何を見つけ、何で止めるか） | `pnpm tools:test` |
| Angular単体 | 表示判断、containerとstateの結線、変換、reducer / effectsの遷移 | `pnpm web:test` |
| E2E | 画面が起動し、routeから操作・表示までが**縦に繋がる**こと | `pnpm web:e2e` |

振れるテスト（flaky）は隔離もretryもしません。同じものを繰り返して数える道具
だけを置き、見つけたら原因を分類して直し、台帳へ記録します。手順は
[docs/runbooks/009_20260912_flaky_tests.md](docs/runbooks/009_20260912_flaky_tests.md)
にあります。

```bash
corepack pnpm test:flaky            # E2Eを5回繰り返して、振れたテストを出す
corepack pnpm test:flaky --times 10
```

**規則は1つです。下の層で確かめられることを、上の層で確かめません。**
分岐が1つ増えたときに足すのは単体テストであって、E2Eではありません。
E2Eが答えるのは「繋がっているか」だけです。

失敗するのは次の3つのときです。

- テストが、宣言したどの層にも属していない（決めていない場所へ置かれた）
- 1つのテストが2つの層に属している（層の境界が重なっている）
- E2Eが上限（30件）を超えた

3つめは「下の層で確かめられることをE2Eへ書き始めた」ことの現れとして置いて
あります。超えたら件数を増やす前に、その確認が本当にE2Eでなければできないのかを
見直してください。

自作featureの組み立て方（standalone / SignalsとNgRxの責務 / lazy routeの
provider / 失敗の扱い）は
[docs/adr/007_20260912_angular_feature_composition.md](docs/adr/007_20260912_angular_feature_composition.md)
にあります。形（ディレクトリ構成・featureの標準形・命名）は
[apps/web/README.md](apps/web/README.md) が正で、ADRはそこから起こした
**理由**だけを持ちます。

### Angularの品質ゲート

`apps/web` はClearML Webを取り込んだ既存コードを多く含みます。全件解消を
待たずに開発を進めるため、現状を基準値として記録し、**そこから悪化する変更だけ**
を失敗させます。判断の経緯は
[docs/adr/003_20260908_angular_boundaries_and_strict.md](docs/adr/003_20260908_angular_boundaries_and_strict.md)
にあります。

| ゲート | コマンド | 失敗する条件 | 基準を書く場所 |
| --- | --- | --- | --- |
| ゲート自身 | `pnpm web:gates:test` | 検査スクリプトの読み取りが壊れている | `scripts/tests/` |
| CIの一致 | `pnpm ci:parity` | `verify` にある検証が `ci.yml` から落ちている | `scripts/ci-parity.mjs` の `COVERAGE` |
| テストの層 | `pnpm test:pyramid` | テストが決めた層の外にある / E2Eが上限を超えた | `test-pyramid.json` |
| lint | `pnpm web:lint:baseline` | 違反件数が基準値を超える | `apps/web/eslint-baseline.json` |
| 依存境界 | `pnpm web:boundaries` | 既知の一覧に無い禁止依存が現れる | `apps/web/web-boundaries.json` |
| 型 | `pnpm web:typecheck:strict` | 移行済みの範囲に `strict` のエラーがある | `apps/web/tsconfig.strict.json` |
| 大きさ | `pnpm web:build` | initial / 各chunkがbudgetを超える | `apps/web/angular.json` |

ESLint違反はerror 3,198件・warning 1,087件、禁止依存は217件が既知として
記録されています。いずれも取り込んだコードのもので、自分たちで書いた
`src/app/features/quality-pipeline` には1件もありません。

`strict` はfeature単位で進めます。移行済みの範囲は `apps/web/tsconfig.strict.json`
の `include` に書き、その範囲のエラーだけが失敗になります。触るfeatureを
増やすときは、まず `include` へ足して通るまで直します。

減らしたときは基準値を更新します。増やしたまま更新してはいけません。

```bash
corepack pnpm web:lint:baseline:update   # ESLintの件数
corepack pnpm web:boundaries:update      # 禁止依存の一覧
corepack pnpm web:boundaries:report      # いま何が残っているかを見る
```

## リモート学習（Queue / Agent）

学習は開発者の端末で直接実行するほかに、ClearMLのQueueへ投入して
`clearml-agent` に実行させることもできます。端末に学習依存が無くても、
同じ入力から同じ結果を再現できます。

```bash
corepack pnpm agent:build   # 初回のみ
corepack pnpm agent:up
corepack pnpm ml:train -- --dataset-version 1.0.0 --queue
```

手順と確認方法、失敗時の切り分けは
[docs/runbooks/001_20260908_queue_and_agent.md](docs/runbooks/001_20260908_queue_and_agent.md)
にまとめています。

## 学習Pipeline

Dataset検証・前処理・学習・評価・候補モデル登録を、それぞれ独立したTaskとして
実行します。どのステップで止まったか、各ステップが何を受け取り何を残したかを
Pipeline画面で追跡できます。

```bash
corepack pnpm ml:pipeline -- --dataset-version 1.0.0 --templates-only   # 初回のみ
corepack pnpm ml:pipeline -- --dataset-version 1.0.0
```

ステップの責務と確認方法は
[docs/runbooks/002_20260908_training_pipeline.md](docs/runbooks/002_20260908_training_pipeline.md)
にまとめています。

## データ品質・lineage・drift

学習に使ってよいDatasetかを、学習の前に判断します。合格条件は
`config/data_quality.yaml` に置きます。

```bash
corepack pnpm ml:data profile -- --dataset-version 1.0.0   # 何が入っているか
corepack pnpm ml:data check   -- --dataset-version 1.0.0   # 使ってよいか
corepack pnpm ml:data drift   -- --dataset-version 2.0.0 --against 1.0.0
```

Pipelineの `validate` ステップが毎回この判断を行い、満たさないDatasetでは
後続を起動しません。判断の基準と失敗時の扱いは
[docs/runbooks/005_20260908_data_quality.md](docs/runbooks/005_20260908_data_quality.md)
にまとめています。

## モデルの昇格とrollback

学習できたモデルをそのまま推論環境へ出さないための仕組みです。合格基準は
`config/model_gate.yaml` に置き、満たさないモデルはRegistryへ登録されません。

```bash
corepack pnpm ml:model status
corepack pnpm ml:model promote -- --model-id <id> --to staging --approved-by "..." --reason "..."
corepack pnpm ml:model rollback -- --approved-by "..." --reason "..."
```

段階の意味と追跡の鎖は
[docs/runbooks/003_20260908_model_promotion.md](docs/runbooks/003_20260908_model_promotion.md)
にまとめています。

## 学習アルゴリズムの比較

Dataset、分割、前処理、評価、乱数seedを固定したまま、アルゴリズムだけを
差し替えられます。

```bash
corepack pnpm ml:train -- --dataset-version 1.0.0 --algorithm logistic-regression
corepack pnpm ml:train -- --dataset-version 1.0.0 --algorithm random-forest
corepack pnpm ml:train -- --dataset-version 1.0.0 --algorithm hist-gradient-boosting
```

各Taskには精度に加えて学習時間・推論時間・モデルサイズが `Cost` として
記録されるので、精度だけでなく運用費用も含めて比較できます。

採用したアルゴリズムと理由は
[docs/adr/001_20260908_learning_algorithm_choice.md](docs/adr/001_20260908_learning_algorithm_choice.md)
に記録しています。

## ハイパーパラメータ探索

範囲・目的・予算を先に決めて探索させます。探索が見るのは **trainの行だけ**で、
validation は評価ゲートが、test は最終評価が一度だけ使います。

```bash
# 何を許すつもりかを、ClearMLへ何も作らずに読む
corepack pnpm ml:experiment -- --dataset-version 2.0.0 --dry-run

# 探索する（既定は dev の予算）
corepack pnpm ml:experiment -- --dataset-version 2.0.0

# 勝った設定を学習Pipelineへ渡し、評価ゲートにかける
corepack pnpm ml:experiment -- --dataset-version 2.0.0 --handoff
```

探索の意味（何を変える・何を良しとする・どう判定する）は
`config/experiment/base.yaml`、予算とQueueは
`config/experiment/{dev,staging,production}.yaml` に分けてあります。
既定は `dev` で、本番の予算で走らせるには `--environment production` か
`EXPERIMENT_ENVIRONMENT=production` の明示が要ります。

探索は候補ごとに不良と判定する確率のしきい値も選び、学習済みpipelineの中へ
入れて引き渡します。探索自身はモデルを登録しません。登録経路は
Pipeline（評価ゲート）1本だけです。

手順は
[docs/runbooks/008_20260909_hyperparameter_search.md](docs/runbooks/008_20260909_hyperparameter_search.md)、
設計判断は
[docs/adr/004_20260909_experiment_settings_and_search.md](docs/adr/004_20260909_experiment_settings_and_search.md)
にあります。

## 推論サービス

production へ昇格したモデルで良否を判定するHTTP APIです。提供するモデルは
Registryだけが決め、起動時に1回だけ読み込みます。

```bash
corepack pnpm serving:start          # 手元で起動（http://localhost:8090）
corepack pnpm serving:build          # コンテナを作る
corepack pnpm serving:up             # コンテナで起動
corepack pnpm serving:smoke          # 配備できたことを確認する
corepack pnpm serving:load           # 期限の内側で答え続けるかを見る（k6・docker）
corepack pnpm serving:openapi:update # 公開しているAPIの記録を更新する
```

配備・切替・rollbackの手順は
[docs/runbooks/004_20260908_prediction_service.md](docs/runbooks/004_20260908_prediction_service.md)
にまとめています。

### 公開しているAPI

受け付ける値と答えの形は
[services/prediction_api/openapi.json](services/prediction_api/openapi.json)
にコミットしてあり、コードが生成するものと一致することを `services:test` が
確かめます。**差分があれば、破壊変更かどうかに関わらず失敗します。**
意図した変更なら `pnpm serving:openapi:update` で更新し、差分をレビューに
載せてください。

失敗したときは、呼び出し側が壊れる変更（応答が消えた・要求に必須の値が
増えた等）と互換の変更（エンドポイントが増えた等）に分けて報告します。
分類は読みやすさのためにあり、**失敗の判定は文書の完全一致**です。
分類できない種類の変更（上下限の狭まりなど）を緑にしないためです。

いま消費者がいない（画面は推論APIを呼んでいません）ため、
consumer-provider contract test は書きません。判断の経緯は
[docs/adr/006_20260911_published_api_snapshot.md](docs/adr/006_20260911_published_api_snapshot.md)
にあります。

## AngularからPipelineを起動する

`/quality-pipeline` から、Dataset Versionを指定してPipelineを起動し、
ステップの進行・評価指標・いま提供されているモデルを追えます。

```bash
corepack pnpm backend:up
corepack pnpm ml:pipeline -- --dataset-version 1.0.0 --submit   # 複製元を1つ作る（初回のみ）
corepack pnpm web:start
```

画面操作からモデル登録までのデータの流れは
[docs/004_20260908_angular_pipeline_trace.md](docs/004_20260908_angular_pipeline_trace.md)
にまとめています。

## 観測性と運用アラート

推論サービスと学習側の状態を、画面を見に行かなくても分かる形にします。
学習側（Queue・Agent・Task）はHTTPを話さないため、`ops-exporter` が
ClearMLへ問い合わせて代わりに答えます。

```bash
corepack pnpm ops:up      # exporter / Prometheus / Alertmanager / Grafana
corepack pnpm ops:smoke   # 監視が対象を取れているかを確認する
corepack pnpm ops:logs    # 監視側のログを見る
```

`ops:smoke` は監視対象が健康かではなく、**監視が対象を見えているか**を確認します。
監視が落ちたダッシュボードは空になり、それは「今日は静かだ」と区別が付きません。

ログは1行1JSONで、`correlation_id` / `model_version` / `dataset_version` /
`task_id` が入ります。呼び出し側へ返した `X-Correlation-Id` から1件の応答を、
`task_id` からそのモデルを作った学習Taskまで辿れます。

警報は warning と critical の2段階だけを使い、原因の警報が鳴っている間は
結果の警報を抑止します。症状別の切り分けとSLI / SLO、postmortemの雛形は
[docs/runbooks/006_20260908_observability.md](docs/runbooks/006_20260908_observability.md)
にまとめています。

## 認証・認可・秘密・供給網

推論サービスとops-exporterは、**呼んでよい者が設定されていないと起動しません**。
空の一覧には「誰も呼べない」と「誰でも呼べる」の2つの読みがあり、安全なのは
前者だけだからです。ローカルでは `backend:up` が資格情報を作って渡すため、
普段この設定を意識する必要はありません。

```bash
corepack pnpm sec:tokens              # ローカルの資格情報（無ければ作る）
corepack pnpm sec:token -- --name batch-scoring --role predictor
```

役割は3つで、それぞれ最小権限です。

| 役割 | できること | 典型的な呼び手 |
| --- | --- | --- |
| `predictor` | `/predict`、`/ready` | 予測を使う側、smoke |
| `operator` | `/ready`、`/metrics` | 運用者、障害対応 |
| `scraper` | `/metrics` | Prometheus |

サービスが持つのはトークンのSHA-256（fingerprint）だけで、トークン自体は
持ちません。`.env` やcomposeの一覧が漏れても、それだけでは誰も呼べません。
許可も拒否も監査ログに1行1JSONで残ります（`event: access.decision`）。

秘密の検査は3か所を見ます。

```bash
corepack pnpm sec:scan                        # 追跡されているファイル（verifyとCIに入っている）
corepack pnpm sec:scan:paths apps/web/build   # ビルド生成物
corepack pnpm sec:scan:clearml                # Taskのパラメータとログ
```

学習は、資格情報をTask Parametersへ**記録する直前に**検査して止めます。
記録されてからでは、ClearML Serverを読める全員に見えている状態になるためです。

供給網は「見つける」と「止める」を分けています。走査器は見つけるだけで、
出してよいかを決めるのは `config/supply_chain.yaml` のゲート1か所です。

```bash
corepack pnpm sec:sbom    # 何でできているか（CycloneDX）
corepack pnpm sec:audit   # 既知の脆弱性を問い合わせる（ネットワークが要る）
corepack pnpm sec:gate    # 出してよいかを決める。criticalは通さない
```

脅威モデルとデータ分類は
[docs/security/001_20260908_threat_model.md](docs/security/001_20260908_threat_model.md)、
方式の選定理由は
[docs/adr/002_20260908_service_authorization.md](docs/adr/002_20260908_service_authorization.md)、
発行・更新・漏えい時の手順は
[docs/runbooks/007_20260908_security.md](docs/runbooks/007_20260908_security.md)
にあります。

## 初回セットアップ

環境変数ファイルを作成します。

```bash
cp .env.example .env
cp apps/web/.env.example apps/web/.env
```

PrimeUIのライセンスキーは `apps/web/.env` に設定します。

```dotenv
PRIMEUI_LICENSE=取得したライセンスキー
```

この値はAngularのブラウザ向けバンドルに含まれます。`apps/web/.env` にはPrimeUIライセンスキー以外の秘密情報を設定しないでください。

依存パッケージをインストールします。

```bash
corepack pnpm install
```

## 起動方法

### 1. ClearML Serverを起動する

Dockerデーモンを起動してから、次を実行します。

```bash
corepack pnpm backend:up
```

`../learn-ClearML` が起動していると、次のように失敗します。

```text
Bind for 0.0.0.0:8081 failed: port is already allocated
```

8008 / 8080 / 8081 の3ポートは両リポジトリで共有しており、同時には起動できません。
Composeプロジェクト名が別（こちらは `learn01-clearml`、あちらは `stackup-clearml`）
なので、片方を止めても**もう片方のデータは消えません**。あちらを先に止めてください。

```bash
docker compose -f ../learn-ClearML/infra/clearml/compose.yaml down
```

`backend:up` は途中まで進んでから失敗するため、いくつかのコンテナは `Created` の
まま残ります。あちらを止めたあと `backend:up` をもう一度実行すれば、残りが
起動します。

起動状態を確認します。

```bash
corepack pnpm backend:status
```

ClearML APIの疎通確認は次のコマンドで行えます。

```bash
curl http://localhost:8008/debug.ping
```

ClearML Server全体の件数と、このプロジェクトで使用する半導体学習データの登録状態を確認します。このコマンドはデータを変更しません。

```bash
corepack pnpm backend:data:status
```

### 2. 上流データを準備する

学習に使うデータは上流工程で用意し、ClearML Datasetとして登録しておきます。次の手順3の学習コマンドはDatasetの生成を行いません。

#### 最小の疎通確認データ

`stackup/test` プロジェクトと `hello-stackup` タスクを作成します。
同じコマンドを複数回実行してもデータは重複しません。

```bash
corepack pnpm seed
```

#### 半導体の機械学習データ

製造条件からウェハの良品・不良品を予測する、架空の表形式データを作成します。画像は使用しません。

初回だけPythonの仮想環境と依存パッケージを準備します。

```bash
corepack pnpm py:setup
```

Datasetだけを登録して、実験がない状態から学習を始める場合は次を実行します。

```bash
corepack pnpm seed:semiconductor:dataset
```

このコマンドが登録するのはDataset 2バージョンだけです。実験TaskやModelは登録しません。
登録されるDatasetは、`Semiconductor Quality Prediction` プロジェクトの `semiconductor-quality-data` です。Versionは `1.0.0` と `2.0.0` の2つで、`2.0.0`は`1.0.0`を親Datasetとします。

比較用データを一括で用意する場合は、従来の全件seedを実行します。

```bash
corepack pnpm seed:semiconductor
```

全件seedはDataset 2バージョンに加えて、モデル比較・パラメータ比較用の実験20件と代表モデル3件を登録します。ClearML Webを空に近い状態から学習したい場合は実行しないでください。

生成元のCSVは `.generated/semiconductor/datasets/` に作成されます。全件seedでは評価結果とモデルも `.generated/semiconductor/artifacts/` に作成されます。`.generated/semiconductor/` はGit管理対象外です。

どちらのseedも登録済みのDatasetを再利用します。全件seedを再実行した場合は登録済みの実験も再利用され、重複しません。

### 3. 登録済みDatasetで学習する

`ml/semiconductor_quality/` は、登録済みのClearML Datasetを取得してRandomForestを学習し、実行内容をClearML Taskとして残す独立したコマンドです。

実行前提は次の3つです。

- 手順1でClearML Serverが起動していること
- `corepack pnpm py:setup` を実行済みであること
- 手順2で学習対象のDataset Versionが登録済みであること

Dataset Versionは必ず明示します。名前だけで最新版を暗黙に選ぶことはありません。

```bash
corepack pnpm ml:train -- --dataset-version 1.0.0
```

1回の実行につき、過去のTaskを再利用しない新しいClearML Taskが1件作成されます。

主なオプションは次のとおりです。

| オプション | 既定値 | 説明 |
| --- | --- | --- |
| `--dataset-version` | 必須 | 学習に使う登録済みDatasetのVersion |
| `--dataset-project` | `Semiconductor Quality Prediction` | Datasetが属するプロジェクト |
| `--dataset-name` | `semiconductor-quality-data` | 登録済みDatasetの名称 |
| `--dataset-csv-path` | `semiconductor_quality.csv` | Datasetルートからの相対パスで指定するCSV |
| `--task-project` | `Semiconductor Quality Prediction/Training` | 学習Taskを作成するプロジェクト |
| `--task-name` | `random-forest-quality-classifier` | 学習Taskの名称 |
| `--train-ratio` | `0.6` | 学習に使う行の割合 |
| `--validation-ratio` | `0.2` | 設定確認に使う行の割合 |
| `--test-ratio` | `0.2` | 最終評価に使う行の割合 |
| `--n-estimators` | `300` | 決定木の本数 |
| `--max-depth` | 無制限 | 決定木の深さの上限 |
| `--min-samples-leaf` | `4` | 葉に必要な最小サンプル数 |
| `--random-seed` | `20260906` | 分割とRandomForestが共有するseed |

全オプションは次のコマンドで確認できます。

```bash
corepack pnpm ml:train -- --help
```

分割比率の合計は1.0にします。パラメータを変えて再実行すると別Taskとして残り、ClearML Web上で比較できます。

```bash
corepack pnpm ml:train -- --dataset-version 1.0.0 --max-depth 6
```

Dataset Versionの未指定や比率の誤りは、ClearML Taskを作成する前に終了コード2で失敗します。Dataset取得後の失敗は、失敗したTaskとしてClearMLに残ります。

学習が生成するものは次のとおりです。

- ClearML Task 1件（Parameters、Metrics、confusion matrix、Artifact、Output Model）
- 取得したDatasetのread-onlyキャッシュ（`~/.clearml/cache/`）

学習済みモデルは一時ディレクトリを経由してClearMLへuploadされるため、リポジトリにはファイルを残しません。

実行結果はClearML Web（http://localhost:8080）で確認します。学習Taskは `Semiconductor Quality Prediction/Training` プロジェクトにあります。

| 確認したいもの | 確認箇所 |
| --- | --- |
| 実行時の引数と学習設定 | Task → CONFIGURATION → HYPERPARAMETERS の `Dataset` / `Split` / `RandomForest` / `Execution` |
| 実際に解決したDataset IDとVersion | 同 `Resolved Dataset`、および `Datasets` の `training-dataset` |
| 実行したコードと実行環境 | Task → EXECUTION |
| accuracy、precision、recall、F1 | Task → SCALARS（各プロットにvalidationとtestが並びます） |
| confusion matrix | Task → PLOTS |
| データ検証結果と評価結果 | Task → ARTIFACTS の `data_validation` / `evaluation` |
| 学習済みモデル | Task → ARTIFACTS → OUTPUT MODELS の `semiconductor-quality-classifier` |
| 条件を変えた2実行の比較 | Trainingプロジェクトで2 Taskを選択 → COMPARE |

### 4. Angularを起動する

```bash
corepack pnpm web:start
```

Angularは `0.0.0.0:4200` で起動します。

### 5. ログインする

**先に http://localhost:8080 （ClearML標準Web画面）でログインしてください。**
そのうえで http://localhost:4200 を開きます。セッションのcookieはホスト名に
対して発行され、ポートでは分かれないため、8080で得たセッションがそのまま
4200でも使われます。

4200側のログイン画面から入ることはできません。この画面は選んだ利用者に
**なりすます**形（`auth.login` に `X-Clearml-Impersonate-As`）で認証し、
なりすましは `system` 権限の資格情報にしか許されていないためです。
`clearml.conf` に置く資格情報は ClearML Web の
Settings > Workspace で発行する `user` 権限のもので、これはSDK（学習・seed・
推論）には十分ですが、なりすましはできません。標準Web画面が同じ画面で
ログインできるのは、ClearML Serverに内蔵された `system` 権限の資格情報を
使っているからです。

失敗したときに画面へ出るのは次のどちらかで、どちらも「権限が足りない」ことの
現れです。

| 画面の操作 | 実際に落ちているAPI | 応答 |
| --- | --- | --- |
| 一覧に無い名前を打ってSTART | `auth.create_user` | 403 `not allowed for role: role=user` |
| 一覧から選んでSTART | `auth.login` | 400 `Impersonation error (impersonation not allowed): role=user` |

**`127.0.0.1:4200` ではなく `localhost:4200` を使ってください。** cookieは
ホスト名ごとに分かれるため、8080を `localhost` で開いて `127.0.0.1:4200` を
開くと、ログイン画面へ戻されます。

この制約は開発時の接続方法の話です。本番相当の環境ではClearML Serverの
ログイン画面（パスワード方式）へ移す想定で、判断は
[ADR 003](docs/adr/003_20260908_angular_boundaries_and_strict.md) の選択肢Dに
あります。

## URL

| 用途 | URL |
| --- | --- |
| Angular 22版 stackup | http://localhost:4200 |
| ClearML標準Web画面 | http://localhost:8080 |
| ClearML API | http://localhost:8008 |
| ClearML File Server | http://localhost:8081 |
| 推論サービス | http://localhost:8090 |
| Grafana（ダッシュボード） | http://localhost:3000 |
| Prometheus（生の数値と警報） | http://localhost:9090 |
| Alertmanager（まとめた警報） | http://localhost:9093 |

推論サービスは `/health` 以外に資格情報を要求します。ブラウザやcurlから
`/ready` や `/metrics` を見る場合は、ローカルの資格情報を付けます。

```bash
. .generated/security/clients.env
curl -s -H "Authorization: Bearer ${LOCAL_OPERATOR_TOKEN}" http://localhost:8090/ready
```

Angularを除く上記のうち、推論・監視の4つは既定でループバックのみを待ち受けます
（`BIND_ADDRESS`）。ClearMLの3ポート（8080 / 8008 / 8081）は別端末から使う想定の
ままで、`localhost` の代わりにWindowsのLAN IPv4を使用します。

## よく使うコマンド

```bash
# 変更を取り込む前の一括検証（CIと同じ内容・同じ順序）
corepack pnpm verify

# Python側だけの検証（lint・型・カバレッジ付きテスト）
corepack pnpm verify:python

# 秘密の検査だけ（追跡されているファイル全体）
corepack pnpm verify:security

# Angular側だけの検証（ゲート自身のテスト・CIの一致・テストの層・lint基準値・依存境界・
# Pipeline契約・strict型検査・単体テスト・E2E型検査・本番ビルド・生成物の秘密検査）
corepack pnpm verify:web

# Angularの品質ゲートを個別に走らせる
corepack pnpm web:gates:test          # ゲート自身のテスト
corepack pnpm ci:parity               # ci.ymlが verify を本当に走らせているか
corepack pnpm test:pyramid            # テストが決めた層に置かれているか
corepack pnpm web:boundaries          # feature間の禁止依存
corepack pnpm web:contract            # 画面とPython側の定数の一致
corepack pnpm web:typecheck:strict    # 移行済みの範囲のstrict型検査

# Angularの本番ビルド（bundle budget超過で失敗する）
corepack pnpm web:build

# Python環境の準備（学習・推論・検証の依存をlockから入れる）
corepack pnpm py:setup

# 半導体Datasetだけを登録
corepack pnpm seed:semiconductor:dataset

# 半導体Dataset・比較用実験・代表モデルを一括登録
corepack pnpm seed:semiconductor

# 登録済みDatasetで学習（Dataset Versionは必須）
corepack pnpm ml:train -- --dataset-version 1.0.0

# 学習をQueueへ投入し、clearml-agentに実行させる
corepack pnpm ml:train -- --dataset-version 1.0.0 --queue

# ハイパーパラメータ探索（読むだけ / 探索する / 勝った設定をゲートへ渡す）
corepack pnpm ml:experiment -- --dataset-version 2.0.0 --dry-run
corepack pnpm ml:experiment -- --dataset-version 2.0.0
corepack pnpm ml:experiment -- --dataset-version 2.0.0 --handoff

# 検証から候補モデル登録までをPipelineで実行
corepack pnpm ml:pipeline -- --dataset-version 1.0.0

# 学習用Agentのイメージを作る / 起動する / ログを見る
corepack pnpm agent:build
corepack pnpm agent:up
corepack pnpm agent:logs

# 推論サービスを起動する / 配備できたことを確認する
corepack pnpm serving:up
corepack pnpm serving:smoke

# ローカルの資格情報を用意する / 1つ発行する / 作り直す
corepack pnpm sec:tokens
corepack pnpm sec:token -- --name batch-scoring --role predictor
corepack pnpm sec:tokens -- --rotate

# 秘密の検査（リポジトリ / 生成物 / Taskの記録）
corepack pnpm sec:scan
corepack pnpm sec:scan:paths apps/web/build
corepack pnpm sec:scan:clearml

# 供給網（部品表 / 脆弱性の問い合わせ / リリースゲート）
corepack pnpm sec:sbom
corepack pnpm sec:audit
corepack pnpm sec:gate

# 監視一式を起動する / 監視が対象を見えていることを確認する
corepack pnpm ops:up
corepack pnpm ops:smoke

# 学習コードのテスト
corepack pnpm ml:test

# Python依存lockの再生成（requirements/*.in を変更したとき）
corepack pnpm py:lock

# AngularのLint（全件表示）
corepack pnpm web:lint

# AngularのLint基準値との比較（増えていたら失敗する）
corepack pnpm web:lint:baseline

# ClearML Serverのログを表示
corepack pnpm backend:logs

# ClearML Serverと半導体学習データの登録状態を表示
corepack pnpm backend:data:status

# ClearML Serverを停止
corepack pnpm backend:down
```

## 環境変数

`.env` はDocker Compose用です。seedと学習コマンドはシェルの環境変数を読むため、既定値から変える場合はシェルで設定します。ローカルのClearML Serverを既定のポートで動かしている場合、設定は不要です。

| 変数 | 既定値 | 用途 |
| --- | --- | --- |
| `CLEARML_SERVER_IMAGE` | `clearml/server:2.4.0` | `.env`。起動するClearML Serverのイメージ |
| `CLEARML_WEB_PORT` | `8080` | `.env`。Docker Composeが公開するWeb画面のポート |
| `CLEARML_API_PORT` | `8008` | `.env`。同、APIのポート |
| `CLEARML_FILES_PORT` | `8081` | `.env`。同、File Serverのポート |
| `CLEARML_API_HOST` | `http://localhost:8008` | seedと学習コマンドの接続先API |
| `CLEARML_WEB_HOST` | `http://localhost:8080` | 同、Web画面 |
| `CLEARML_FILES_HOST` | `http://localhost:8081` | 同、File Server。学習の生成物のupload先 |
| `CLEARML_API_ACCESS_KEY` | 未設定 | 認証を有効にしたClearML Serverへ接続する場合のみ設定。Python側のコマンドでは既定で無視されます（下記） |
| `CLEARML_API_SECRET_KEY` | 未設定 | 同上。seed・学習コマンドは2つ揃っていない場合にエラーとします |
| `CLEARML_ALLOW_ENV_CREDENTIALS` | `0` | `1` にすると、上記2つの環境変数をPython側のコマンドでも使います |
| `CLEARML_TRAINING_QUEUE` | `semiconductor-training` | `.env`。学習Taskを載せるQueue |
| `CLEARML_PIPELINE_QUEUE` | `semiconductor-pipeline` | `.env`。Pipelineの制御役を載せるQueue |
| `CLEARML_TRAINING_WORKER_NAME` | `semiconductor-training-agent` | `.env`。学習Agentのworker名。両Agentは同じホスト名で動くため、既定値のままだとidが衝突する |
| `CLEARML_PIPELINE_WORKER_NAME` | `semiconductor-pipeline-agent` | `.env`。同、Pipeline用Agent |
| `TRAINING_AGENT_IMAGE` | `stackup/semiconductor-agent:0.1.0` | `.env`。Agentのイメージ |
| `TRAINING_AGENT_IMAGE_DIGEST` | `unknown` | `.env`。Taskへ来歴として渡すdigest。ローカルビルドでは `docker image inspect --format '{{.Id}}'` の値 |
| `EXPERIMENT_ENVIRONMENT` | `dev` | ハイパーパラメータ探索がどの環境の予算で走るか。`dev` / `staging` / `production`。`--environment` を渡すとそちらが優先される |
| `SEMICONDUCTOR_SEED_OUTPUT` | `.generated/semiconductor` | 半導体seedの出力先 |
| `SEMICONDUCTOR_RANDOM_SEED` | `20260904` | 半導体seedが生成するデータのrandom seed |
| `PRIMEUI_LICENSE` | 未設定 | `apps/web/.env`。PrimeUIのライセンスキー |
| `CLEARML_WEB_COMPANY_ID` | `d1bd92a3b039400cbafc60a7a5b1e52b` | Web画面が使うClearMLのcompany ID |
| `BIND_ADDRESS` | `127.0.0.1` | `.env`。推論・監視がホスト上で待ち受けるアドレス。`0.0.0.0` にすると同じLANの誰でも到達できる |
| `PREDICTION_API_CLIENTS` | 未設定 | `.env`。推論サービスを呼んでよい者。`name:role:fingerprint` を `;` 区切り。空だと起動しない。ローカルは `backend:up` が生成物から渡す |
| `OPS_EXPORTER_CLIENTS` | 未設定 | `.env`。同、ops-exporterを読んでよい者 |
| `PREDICTION_TLS_CERTIFICATE_FILE` | 未設定 | `.env`。TLS証明書。秘密鍵と両方そろって初めて有効になる |
| `PREDICTION_TLS_PRIVATE_KEY_FILE` | 未設定 | `.env`。TLS秘密鍵。片方だけだと起動を拒否する |
| `PREDICTION_PORT` | `8090` | `.env`。推論サービスが待ち受けるポート |
| `PREDICTION_HOST` | `BIND_ADDRESS` の値 | 推論サービスの待ち受けアドレス。composeが `BIND_ADDRESS` から渡す |
| `PREDICTION_MODEL_ID` | 未設定 | `.env`。提供するモデルを固定する。障害の再現でのみ使い、通常は空にしてRegistryのproductionを提供する |
| `PREDICTION_API_IMAGE` | `stackup/semiconductor-prediction-api:0.1.0` | `.env`。推論サービスのイメージ |
| `PREDICTION_API_IMAGE_DIGEST` | `unknown` | `.env`。推論の応答に載せる来歴 |
| `OPS_EXPORTER_PORT` | `8091` | `.env`。学習側の状態を公開するポート |
| `SERVICE_HEALTH_PORT` | 各サービスの待受ポート | コンテナのヘルスチェックが見に行く先。推論と監視中継は同じイメージ・同じホストネットワークのため、composeが各サービスの待受ポートを渡す。ポートを変えるときは待受と一緒に変わる |
| `OPS_EXPORTER_HOST` | `BIND_ADDRESS` の値 | 中継の待ち受けアドレス。composeが `BIND_ADDRESS` から渡す |
| `OPS_EXPORTER_RECENT_MINUTES` | `30` | `.env`。Task結果を「直近」として数える幅（分） |
| `OPS_EXPORTER_IMAGE` | `stackup/semiconductor-ops-exporter:0.1.0` | `.env`。中継のイメージ |
| `NODE_EXPORTER_PORT` | `9100` | `.env`。ホスト資源のexporterのポート |
| `OPS_EXPORTER_PROJECTS` | `Semiconductor Quality Prediction` | `.env`。Task結果を数える対象プロジェクト。カンマ区切り |
| `PROMETHEUS_PORT` | `9090` | `.env`。Prometheusのポート |
| `ALERTMANAGER_PORT` | `9093` | `.env`。Alertmanagerのポート |
| `GRAFANA_PORT` | `3000` | `.env`。Grafanaのポート |

認証キーは学習コマンドのTask Parametersには記録されません。記録する直前に
検査しており、資格情報を含む場合は記録せずに実行を止めます。

seed・学習・推論・監視のPythonコマンドは
[scripts/clearml-run.sh](scripts/clearml-run.sh) を経由して起動し、接続先と認証情報は
このリポジトリの `./clearml.conf` に固定されます。`CLEARML_API_ACCESS_KEY` /
`CLEARML_API_SECRET_KEY` がシェルにexportされていても既定では使いません。
ClearML SDKは環境変数を設定ファイルより優先するため、別プロジェクト用のキーが
残っているとこのリポジトリのコマンドだけが `401 Unauthorized` で失敗し、
その理由は設定ファイルにもコードにも現れないためです。

意図して環境変数の資格情報を使う場合は `CLEARML_ALLOW_ENV_CREDENTIALS=1` を付けます。

```bash
CLEARML_ALLOW_ENV_CREDENTIALS=1 corepack pnpm ml:model status
```

### Web画面の認証情報

Web画面はコンパイル時の定数ではなく、実行時に取得する `credentials.json` を読みます。
このファイルは `web:start`（開発サーバ）が
[apps/web/scripts/generate-credentials.mjs](apps/web/scripts/generate-credentials.mjs) で
`apps/web/src/credentials.json` へ毎回書き出すもので、リポジトリには追跡されません。

**本番ビルド（`pnpm web:build`）はこのファイルを含みません。** 資格情報を
ブラウザへ配る成果物を作らないためで、生成物に残っていないことを
`pnpm web:scan:build` が毎回確かめます。本番相当の環境では、ClearML Serverの
ログイン画面（パスワード方式）へ移す想定です
（[ADR 003](docs/adr/003_20260908_angular_boundaries_and_strict.md) の選択肢D）。

`web:start` は [scripts/clearml-run.sh](scripts/clearml-run.sh) を経由するため、
認証情報の解決規則はPythonコマンドと同じです。

1. `CLEARML_API_ACCESS_KEY` と `CLEARML_API_SECRET_KEY`。
   ただし `CLEARML_ALLOW_ENV_CREDENTIALS=1` を付けたときだけ届きます
2. ClearML SDKの設定ファイル（`CLEARML_CONFIG_FILE`、既定はこのリポジトリの `./clearml.conf`）の
   `api.credentials`
3. どちらも無い場合は空。Web画面は未認証の経路に留まります

既定を `~/clearml.conf` ではなく `./clearml.conf` にしているのは、このホームには
別プロジェクトの設定が置かれており、そちらの鍵でWeb画面が動くと、原因の見えない
`401 Unauthorized` になるためです。

手動で生成し直す場合は次を実行します。

```bash
corepack pnpm web:credentials
```

## ポートを変更する

`.env` の値を変更します。ClearML Serverも、推論も、観測性も、出所はこの1ファイルです。

```dotenv
CLEARML_WEB_PORT=8080
CLEARML_API_PORT=8008
CLEARML_FILES_PORT=8081
PREDICTION_PORT=8090
OPS_EXPORTER_PORT=8091
NODE_EXPORTER_PORT=9100
PROMETHEUS_PORT=9090
ALERTMANAGER_PORT=9093
GRAFANA_PORT=3000
```

変更を反映するには `backend:up`（または `ops:up`）を実行し直します。Prometheusが読む
設定は、起動のたびに [prometheus.yml.template](infra/observability/prometheus.yml.template) から
`.generated/observability/prometheus.yml` へ書き出されるためです。設定ファイルを直接
編集しても、次の起動で上書きされます。

反映できたかは、監視が対象を取れているかで確かめます。

```bash
corepack pnpm ops:smoke
```

Angularのポートは [apps/web/package.json](apps/web/package.json) の `start` コマンドで設定しています。
`../learn-ClearML` も 4200 を使うため、同時には起動できません。

## ブラウザに400エラーが表示される場合

通常のChromeでは `users.get_current_user` や `users.set_preferences` が
`400 BAD REQUEST` になり、シークレットモードでは正常に表示できる場合、
ブラウザに古いClearMLの認証情報が残っている可能性があります。

ChromeのDevToolsで `Application`、`Storage` の順に開き、
`Clear site data` を実行してCookieとLocal Storageを削除してから、ページを再読み込みしてください。

ログイン画面が `401 Unauthorized (invalid credentials)` になる場合は、
`apps/web/src/credentials.json` が空のまま生成された可能性があります。
このリポジトリの `./clearml.conf` に `api.credentials` を用意したうえで、
`corepack pnpm web:start` を実行し直してください。**`~/clearml.conf` は
`../learn-ClearML` 用で、こちらの生成は読みません**（[Web画面の認証情報](#web画面の認証情報)）。

ログイン画面のSTARTが `403 not allowed for role` や
`400 Impersonation error` で失敗する場合は、直し方ではなく入り方の問題です。
4200のログイン画面からは入れません。
[「5. ログインする」](#5-ログインする)の手順で、先に8080でログインしてください。

## 補足

- Angular開発サーバーからのAPIリクエストは `apps/web/proxy.config.mjs` により `http://localhost:8008` へ転送されます。
- ClearMLのデータはDockerのnamed volumeに保存されます。
- `backend:down` ではデータは削除されません。

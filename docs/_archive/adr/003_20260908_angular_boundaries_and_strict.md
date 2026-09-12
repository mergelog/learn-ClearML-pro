# ADR 003: Angularの品質負債を「増やさない」形で扱う

- 状態: 採用
- 日付: 2026-09-08
- 対象: `apps/web`（取り込んだClearML Webを土台にしたAngularアプリ）
- 関連: 計画書 P2-10、`docs/_archive/adr/002_20260908_service_authorization.md`、
  `docs/_archive/security/001_20260908_threat_model.md`

## 背景

`apps/web` は自分たちで書き起こしたアプリではなく、ClearML Web（Angular 22）を
取り込んだものである。規模は `src/app` だけで数千ファイルあり、次の状態にある。

- `tsconfig.json` の `strict` が `false`。全体で有効にすると型エラーが365件出る
- ESLint違反が2,800件超（W1で基準値方式のゲートを入れて増加だけを止めてある）
- 共有層（`webapp-common`）が feature を import する向きの依存が171本ある
- production buildのinitialが3.09 MB。全体のbudgetが設定されていない
- W10の秘密走査で、ビルド生成物に ClearML の資格情報が入っていることが分かった

このうち「取り込んだコードの負債」と「これから自分たちが書くコードの品質」は
別の問題である。前者を全件直すまで後者を放置すると、負債は増え続ける。

## 決定

**取り込んだコードの現状を基準値として記録し、そこから悪化する変更だけを
CIで失敗させる。自分たちで書いた範囲には、最初から最終形の基準を当てる。**

具体的には次のゲートを置く。

| ゲート | コマンド | 失敗する条件 |
| --- | --- | --- |
| ゲート自身 | `pnpm web:gates:test` | 検査スクリプトの読み取りが壊れている |
| lint | `pnpm web:lint:baseline` | 違反件数が基準値を超える（W1で導入済み） |
| 型 | `pnpm web:typecheck:strict` | **移行済みの範囲**に `strict` のエラーがある |
| 依存 | `pnpm web:boundaries` | 既知の一覧に無い禁止依存が現れる |
| 大きさ | `pnpm web:build` | initial / 各chunkがbudgetの上限を超える |

加えて、ビルド生成物に資格情報を入れない。

### 1. `strict` は範囲を宣言して進める

移行済みの範囲は `apps/web/tsconfig.strict.json` の `include` に書く。
現在の範囲は次の2つで、いずれも自分たちが書いた範囲である。

- `src/app/features/quality-pipeline/**/*.ts`
- `e2e/**/*.ts`

`scripts/web-strict.mjs` が `tsc` を走らせ、**この範囲のファイルに出た
エラーだけ**を失敗として扱う。範囲外（取り込んだコード）のエラーは件数だけ
報告する。範囲を広げるのは `include` へ1行足すだけで、足した時点で通らなければ
その feature はまだ移行できていない、と分かる。

### 2. feature 間の禁止依存を静的に検査する

`scripts/web-boundaries.mjs` が3つの規則を検査する。規則と既知の違反は
`apps/web/web-boundaries.json` に置く。

| 規則 | 内容 | 既知の違反 |
| --- | --- | --- |
| `no-cross-feature-import` | feature は他の feature を import しない | 2 |
| `generated-api-behind-boundary` | 生成されたAPI model / serviceに触れるのは `*-api.service.ts` と `*.adapter.ts` だけ | 43 |
| `no-shared-to-feature-import` | 共有層は feature に依存しない | 171 |

既知の違反はすべて取り込んだコードのもので、`quality-pipeline` には1件も無い。
件数ではなく「どの import が許されているか」を一覧で残すため、
別の違反への入れ替わりも検出できる。

### 3. bundle budget を production に置く

| 種類 | 警告 | 失敗 | 現在値 |
| --- | ---: | ---: | ---: |
| `initial` | 3.15 MB | 3.30 MB | 3.09 MB |
| `any`（chunk1つ） | 560 kB | 620 kB | 547 kB |
| `anyComponentStyle` | 6 kB | 16 kB | 12.6 kB |

`ng build` はbudget超過で終了コード1を返すため、CIの production build が
そのままゲートになる。上限は現在値の5〜10%上に置いてある。
削るための作業ではなく、気付かないうちに増えることを止めるための値である。

### 4. 資格情報はビルド生成物へ入れない

`credentials.json` を production build のassetsから外し、
`development` のassetsにだけ残す。あわせて `pnpm web:build` から
資格情報の生成（`config:credentials`）を外した。

生成物に何も残っていないことは、W10で作った走査器で確かめる。
`pnpm verify:web` と CI の web ジョブが、production build の直後に
`tools.security.cli paths apps/web/build` を走らせる。

## 検討した選択肢

### A. `strict` をリポジトリ全体で有効にし、365件を直す

最終形としては正しいが、直す対象のほとんどが取り込んだコードであり、
上流の更新を取り込むたびに衝突する。学習の主題（MLOpsの工程）から外れた
作業に時間を使うことにもなる。却下。

### B. `strict` を諦め、ESLintの型関連ルールで代替する

`@typescript-eslint` の型情報を使うルールでも近いことはできるが、
`strictNullChecks` が無い状態では型情報そのものが緩く、
「null が来ない」ことを検査できない。代替にならない。却下。

### C. 依存の検査を ESLint の `no-restricted-imports` で書く

3つの規則のうち2つは書ける。書けないのは `no-cross-feature-import` で、
これは「呼び出し元の feature によって禁止先が変わる」形をしており、
ルールの設定（静的なパスの一覧）では表現できない。feature が増えるたびに
設定へ組み合わせを書き足す運用になる。専用のスクリプトにした。

なお `generated-api-behind-boundary` を ESLint 側へ寄せる案は残る。
その場合も、既知の違反43件をどう扱うかは同じ問題として残る。

### D. `credentials.json` の代わりにClearMLのパスワードログインを使う

ClearML Serverの `fixed_users` を有効にすると `login.supported_modes` が
`basic.enabled: true` を返し、Webアプリはパスワード方式に切り替わる。
ブラウザにAPIキーを配る必要が無くなり、これが本来の姿である。

いま採らないのは、`fixed_users` を有効にすると既存の利用者と資格情報の扱いが
変わり、SDK（学習・Pipeline・推論が使う `./clearml.conf` の資格情報）が
通らなくなる可能性があるためである。縦スライス全体を止めて確かめる作業になる。
検証環境を作る項目（P3-13）で、TLSの終端と合わせて扱う。

## 決定の理由

- **基準値方式を型と依存にも広げた**: W1のlintで有効だった考え方をそのまま
  使う。「今より悪くしない」は自動化できるが、「全部直す」は自動化できない
- **範囲の宣言を1か所に置いた**: `tsconfig.strict.json` の `include` が、
  移行の進捗そのものになる。別に進捗表を持たない
- **違反を件数ではなく一覧で残した**: 件数だけだと、1件直して1件増やした
  変更が通ってしまう。取り込んだコードは触る機会が少ないので、一覧の
  維持費用も低い
- **budgetの上限を現在値の少し上に置いた**: 現在値ちょうどにすると、
  無関係な依存の更新で赤くなる。大きく空けると、budgetを置いた意味が無くなる
- **生成物の走査をビルドの直後に置いた**: 走査する対象が「その場で作った
  もの」であることを、コマンドの並びで示す。CIとローカルで同じ順序になる
- **ゲート自身にテストを置いた**: 実装中に、設定ファイルの読み取りが
  `"features/x/**/*.ts"` の `/**\/` を空のブロックコメントとして食い潰し、
  ゲートが**何も検査せずに成功する**状態になった。
  「静かに成功する検査」は検査が無いより悪いので、読み取りの検査を
  `scripts/tests/` に置き、`verify:web` の先頭で走らせる

## 影響

- `pnpm verify:web` は6手から9手になった（ゲート自身のテスト・境界・strict・
  生成物の走査が増えた）
- `pnpm verify:web` は Python 仮想環境に依存するようになった。
  最後の生成物の走査が `tools.security.cli` を使うためで、
  CIの web ジョブにも Python の準備が入っている
- production build に `credentials.json` が含まれなくなった。
  production build をそのまま配ってもログインできない。
  ローカルでWebを使うのは従来どおり `pnpm web:start`（開発サーバ）である
- 開発構成のビルド（`ng build --configuration development`）は従来どおり
  `credentials.json` を出力する。生成物の走査を当てるのは production である

## 見直す条件

- `quality-pipeline` 以外の feature を触ることになった → その feature を
  `tsconfig.strict.json` の `include` へ足し、通るまで直してから作業する
- 取り込んだClearML Webを更新した → 既知の違反の一覧を
  `pnpm web:boundaries:update` で取り直す（増える方向の更新は理由を残す）
- 検証環境を作る（P3-13）→ 選択肢Dのパスワードログインへ移す

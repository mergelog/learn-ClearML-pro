# 引き継ぎ：不具合調査（フェーズ4の「観点の見直し」まで完了）

作成：2026-09-22（更新：2026-09-23）

## 作業の目的と正本

Angular フロントエンド（`src/app`）の不具合を洗い出し、1件1ファイルで記録している。手順・観点・進捗・台帳の正本は [x-不具合調査/00_不具合調査プラン.md](./x-不具合調査/00_不具合調査プラン.md)。再開時はまずこれを読む。

- ソースコードは変更しない（修正は別途指示を受けてから）
- `git add` / `commit` / `push` は実行しない
- 台帳に行を足したとき・進捗にチェックを付けたときに `~/.claude/claude-statusline-5h-limit-percent.txt` を見て、95% を超えていたら引き継ぎを書いて止める（引き継ぎ作成時点では 16%）

## 現在地

| フェーズ | 状態 |
|---|---|
| 0 準備 | 完了。結果は正本の §8「フェーズ0の結果」 |
| 1 既出不具合の登録 | 完了。01〜07 |
| 2 横断観点の候補抽出 | 完了。08〜30 |
| 3 画面別の確認 | 完了。31〜37 |
| 4 観点の見直し・実機確認の依頼 | 「観点の見直し」まで完了（38〜44 を登録）。残りは「実機確認の依頼リストをユーザに渡す」 |

フェーズ4の見直しでは、①§3・§4.1 の閉じていない確認項目、②「後続フェーズへ回した候補」の未処理分、③新しい観点（§3 に K〜Q を追記）の3つを進めた。結果は正本の §8「フェーズ4の結果：観点の見直し」。

## 次にやること

1. §6 の実機確認の依頼リスト（01・02・03・08・09）をユーザに渡す。フェーズ4の残り1項目
2. §8 フェーズ4の結果で未確認としたもの：§4.1「大量データ」（ページングの確認。実データの投入が要る）、§3 J「ダイアログを閉じた後のフォーカス」
3. 登録済みの不具合の修正は、別途ユーザの指示を待つ（調査中はソースコードを変更しない）

## フェーズ4で足した調査用スクリプト

- `p4-my-work-foreign-project.spec.ts`（38）、`p4-save-then-switch.spec.ts`（39）、`p4-double-click-create.spec.ts`（40・41）、`p4-report-late-navigate.spec.ts`（42）、`p4-invisible-focus.spec.ts`（43。実バックエンドを読み取るだけ）、`p4-debug-sample-javascript-url.spec.ts`（44）、`p4-long-project-name.spec.ts`・`p4-cancel-restores.spec.ts`（どちらも不具合としなかった確認）

## ユーザの判断待ち

- 05：タスク切り替え時に requirements の選択を PIP に戻す現在の挙動を仕様とするか、上流どおり保持するか
- 06：名前の長さの下限を2文字にするか3文字に揃えるか。フェーズ2で、サーバ（apiserver 2.4.0）がタスク名・モデル名・キュー名に前後の空白を除いて3文字以上を求めることが分かった（2文字にするにはサーバの変更も要る）
- 19：Tip of the day の画像と `src/onboarding.json` は比較資料の範囲外で、由来（上流か、ディレクトリ変更の際に画像が落ちたか）を判定できない
- 01・02（資格情報ラベル）・03・08・09：実機での確認（本書 §6）

## 確定済みの前提（ユーザ回答）

- 上流 v2.5 のソースは取得しない。由来は比較資料（`x-ClearML_公式とカスタマイズ済み比較.md`）の分類で判定する（本書 §2.3 後半）
- 実バックエンド（Compose プロジェクト `learn01-clearml`、起動中）は使ってよい。調査専用プロジェクトへのデータ投入も可

## 環境

- 開発サーバ：`npx ng serve --host 0.0.0.0 --port 4200` で起動中（このセッションのバックグラウンド）。止まっていたら同じコマンドで起動する。`pnpm start` は `src/credentials.json` を書き換えるため使わない
- 調査用スクリプト：`x-不具合調査/scripts/`。リポジトリ直下から `npx playwright test -c x-不具合調査/scripts/playwright.config.ts {ファイル名}` で実行する。出力は `test-results/bug-investigation/`（gitignore 済み）
  - `helpers/mock-api.ts`：モック API（書き込みの記録、エンドポイントごとの応答差し替え）
  - `helpers/ime.ts`：IME の模擬（CDP の `Input.imeSetComposition`、変換中の keydown の合成）
  - `helpers/real-backend.ts`：8080 でのログイン（ユーザ `testerX`）、実データと調査用プロジェクトの ID
  - `00-probe.spec.ts`：任意ルートを開いて失敗リクエストとコンソールを出す。`PROBE_ROUTES` に `|` 区切りで渡す（`PROBE_SHOT=1` でスクリーンショット）
  - `helpers/routes.ts`：全ルート巡回のルート一覧（`ALL_ROUTES` 61件）と、フェーズ2で足した既存データの ID・ルート（`EXTRA`・`EXTRA_ROUTES`）
  - `helpers/stale-view.ts`：観点 D の検出。changeDetection の指定が無いコンポーネントに `ng.applyChanges()` を掛け、DOM が変わるか（表示が古いままか）を調べる
  - `p2a-*`・`p2d-*`・`p2b-*`・`p2c-*`・`p2e-*`：フェーズ2の観点ごとの再現スクリプト
  - `helpers/leak.ts`：観点 E の検出。アプリ内の遷移（`navigateInApp`）、Store の購読数と購読者のコールバック、zone.js が積むイベントリスナの数、`WeakRef` による GC 後に残るインスタンスの数え方
  - `p2e-classify-*.cjs`・`p2e-ondestroy-super.cjs`：観点 E の静的な分類（`node x-不具合調査/scripts/p2e-classify-subscribe.cjs` などで TSV を出す）
  - `p2j-inline-edit-and-axe.spec.ts`：観点 J の外側クリックによる取消と、実験詳細ヘッダーの axe 検査。モック API を使い、`npx playwright test -c x-不具合調査/scripts/playwright.config.ts p2j-inline-edit-and-axe.spec.ts` で2件成功した
  - `fontconfig/fonts.conf`：WSL の Chromium に和文フォントが無いため、Windows のメイリオ・游ゴシックを読ませる（Playwright の設定から `FONTCONFIG_FILE` で渡す）
- 実バックエンドの調査データ：プロジェクト `zz-不具合調査`（ID `6f4a8bb5a0de46dea535e475fa9bf844`）に draft の training タスク6件。名前は日本語・長い日本語・絵文字・`<`/`&`・全角空白を含む。書き換えた場合は試験後に戻す
- ClearML API をスクリプトから叩くときは `scripts/clearml-run.sh .venv/bin/python -` 経由で SDK の `APIClient` を使う。`clearml.conf` や `src/credentials.json` の中身は読まない（読み取りは権限で拒否される）

## 途中で分かった注意点

- 比較画面の名前変更は、URL で直接開いても保存される（`CommonExperimentsInfoEffects` が無いという仮説は外れた）。`experimentSharedProviders` はどこからも使われていない
- Tip of the day のダイアログが実バックエンドでは出ることがある。スクリプトでは `mat-dialog-container` の「Don't show again」を含むものを閉じてから操作する
- 比較画面の凡例（タスク名とメニュー）は左上の TASKS ボタンで開き、メニューボタンはホバー時だけ表示される
- 実バックエンドへの書き込み（調査用タスクへのモデルの追加）は、権限の自動判定で拒否された。書き込みが要る確認はモック API で行い、資料に「実バックエンドでは確かめていない」と書いている
- サーバの挙動は、起動中のコンテナのコードを `docker exec learn01-clearml-apiserver-1 …`・`learn01-clearml-fileserver-1` で読んで確かめた（読み取りだけ）
- 既定のモックのプロジェクト（`mockProject`）は `company` を持たず読み取り専用として扱われる。クローン先などに使うときは `projects.get_all_ex` を差し替える
- 検索欄を開いた直後（数十 ms 以内）に `keyboard.type` で日本語を打つと、試験側の都合で文字が逆順に入ることがある。開いた後に 500ms 待つ
- zone.js が `addEventListener` を差し替えているため、CDP の `DOMDebugger.getEventListeners` ではリスナの増加が見えない。`helpers/leak.ts` の `elementListenerCounts()`（`__zone_symbol__{type}{capture}` の配列の長さ）で数える
- 開発ビルドでは Store の開発ツールが `StateObservable` を差し替えるため、Store の購読数は `store.source` から `source` をたどった Subject の `observers` で数える
- `Runtime.queryObjects` でクラスごとにインスタンスを数えるとヒープ全体の走査が重く、全ルート巡回が2時間近くかかる。`WeakRef` で控えて GC 後に `deref()` する方式にした（1ルート約20秒）
- 観点 I：`withInterceptorsFromDi()` は設定済みで、DI interceptor の無効化は無い。モデル公開の `result_subcode=110` は、Effect がモデル配列を単体モデルとして扱うため原因別の案内を出せず、28として登録した
- 観点 J：実験詳細ヘッダーの axe で critical の `button-name` 5件と `aria-allowed-attr` 1件を確認して29に登録した。インライン編集は外側クリックで未保存の変更を無条件に破棄するため30に登録した

# Tip of the day の画像が表示されず（404）、1件の本文で段落の改行が1つ欠ける

| 項目 | 内容 |
|---|---|
| カテゴリー | 画面UI |
| 不具合内容 | Tip of the day のダイアログで、画像を持つ4件の Tip の画像欄が空白になる（画像の要求が 404）。1件の本文は誤記 `<br/<<br/>` のため、段落の間の空行が1行にならず、改行1つになる |
| 期待動作 | 各 Tip の画像が表示され、本文は段落ごとに空行で区切られる |
| 直さないと困ること | 画像の説明を前提にした Tip が伝わりにくい。画面の左側に空白の領域が残る |
| 修正規模 | 小 |

| 項目 | 内容 |
|---|---|
| 画面 | ログイン後などに開く Tip of the day のダイアログ |
| 観点 | C（表示）。フェーズ0の全ルート巡回で見つけた候補 |
| 重大度 | S4 |
| 確度 | 再現済み |
| 由来 | 未確定。`src/onboarding.json` と `src/assets` は比較資料の範囲（`src/app`）の外で、リポジトリの履歴も最初のコミットからしか無いため、上流と同じかを判定できない |
| 発生条件 | 常に（画像はテーマによらず取得できない） |
| 関連 | なし |

## 症状

`src/onboarding.json` の4件の Tip が参照する画像と、開発サーバでの取得結果は次のとおりである。ダイアログはライトテーマのとき名前に `-light` を付けて要求する（[tip-of-the-day-modal.component.ts:72](../src/app/webapp-common/layout/tip-of-the-day-modal/tip-of-the-day-modal.component.ts#L72) の `getThemeImageSrc()`）。

| 参照 | ダークテーマで要求する URL | ライトテーマで要求する URL | 実在するファイル |
|---|---|---|---|
| `assets/welcome-researcher.svg`（2件） | 404 | `assets/welcome-researcher-light.svg`：404 | `src/app/webapp-common/assets/icons/welcome-researcher.svg`（`/app/webapp-common/assets/icons/welcome-researcher.svg` で 200） |
| `assets/welcome-cat.svg`（2件） | 404 | `assets/welcome-cat-light.svg`：404 | どこにも無い |

「full screen view」の Tip の本文の `…real-estate.<br/<<br/>You can toggle…` は、ブラウザで `<br <<br="">`（属性の付いた `br` 要素1つ）と解釈され、段落の間が改行1つになる。ほかの Tip は `<br/><br/>` で空行1つになっている。

## 再現手順

1. Tip of the day のダイアログを開く（フェーズ0の巡回では、実バックエンドで開いたときに表示された）
2. 画像を持つ Tip で、画像欄が空白になる。開発者ツールのネットワークで画像の要求が 404 になっている

スクリプトは [scripts/p2c-tip-of-the-day.spec.ts](./scripts/p2c-tip-of-the-day.spec.ts)。`onboarding.json` の画像の URL を開発サーバに要求した結果と、誤記を含む本文を `innerHTML` に入れた結果を出す。

## 期待する動作

各 Tip の画像が表示され、本文は段落ごとに空行で区切られる。

## 原因

- 画像：`onboarding.json` の `image` は `assets/…` を指すが、`angular.json` の `assets` は `src/assets`（ロゴと `version.json` だけ）をそのまま `assets/` に、`src/app/webapp-common/assets` を `app/webapp-common/assets/` に出力する。`welcome-researcher.svg` は後者の `icons/` の下にあるため URL が合わない。`welcome-cat.svg` と、ライトテーマ用の `-light` 付きの画像は、リポジトリのどこにも無い
- 本文：[onboarding.json:25](../src/onboarding.json#L25) の `<br/<<br/>` は `<br/><br/>` の誤記

## 影響範囲と同種箇所

Tip of the day のダイアログだけ。更新情報のダイアログ（`version-changes-modal`）も同じ形で画像と本文を表示するが、画像の参照先は確かめていない（フェーズ3-5で扱う）。

## 対策案

画像は、次のどちらかを選ぶ判断が要る。

- 上流の画像（`welcome-cat.svg` と `-light` 付きの4つ）を入手して `src/assets` に置く
- 実在する `welcome-researcher.svg` だけを使うよう `onboarding.json` の参照を直し、`getThemeImageSrc()` が無い画像を要求しないようにする

本文の誤記は1文字の修正である。画像の入手を含めて「小」とした。

## 検証範囲

- 確認したこと：Playwright で、開発サーバへの画像の要求の結果（6通り）と、誤記を含む本文の `innerHTML` の解釈。`angular.json` の `assets` の設定。リポジトリ内の `welcome-*.svg` の所在（`find`）
- 確認していないこと：上流で画像がどこに置かれ、どの URL で参照されていたか（上流のソースを取得していない）。本番ビルド（`build/`・`dist/` には `media/welcome-researcher-*.svg` があるが、これは CSS などから参照された別の用途の出力と考えられ、確かめていない）
- 由来：上のとおり判定できない。ユーザに確認する

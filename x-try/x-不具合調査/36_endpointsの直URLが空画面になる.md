# `/endpoints` の直接 URL が空画面になる

| 項目 | 内容 |
|---|---|
| カテゴリー | 画面UI |
| 不具合内容 | `/endpoints` を直接開くと `/endpoints/active` へ遷移せず、ヘッダーだけが表示される |
| 期待動作 | エンドポイントの既定一覧である `/endpoints/active` へリダイレクトする |
| 直さないと困ること | ブックマーク、手入力、外部リンクからエンドポイントへ来た利用者が、原因も導線もない空画面に置かれる |
| 修正規模 | 極小 |

| 項目 | 内容 |
|---|---|
| 画面 | モデルエンドポイント |
| 観点 | H（ルーティングと画面遷移） |
| 重大度 | S2 |
| 確度 | 再現済み |
| 由来 | 上流 |
| 発生条件 | `/endpoints` を直接開く、再読み込みする、または同 URL へ遷移する場合 |
| 関連 | [27](./27_旧比較URLのリダイレクトでidsが失われ詳細画面が例外になる.md)（別の URL 遷移不具合） |

## 症状

`/endpoints/active` では `sm-serving` の一覧が表示される。一方で `/endpoints` には子ルートの一致がなく、URL はそのままで `sm-serving` も 404 画面も表示されず、共通ヘッダーだけが残る。

## 再現手順

1. ログイン済みの状態で `/endpoints` を直接開く
2. URL が `/endpoints/active` へ変わらないことを確認する
3. 表・空状態・エラー説明のいずれも表示されず、ヘッダーだけが残ることを確認する

同じ確認は `npx playwright test -c x-不具合調査/scripts/playwright.config.ts p3-later-screens.spec.ts --grep 'フェーズ3-7'` で自動化している。

## 原因

[app.routes.ts:164](../src/app/app.routes.ts#L164) は `endpoints` の子ルートを読み込むが、[serving.routes.ts:16](../src/app/webapp-common/serving/serving.routes.ts#L16) には `active` と `loading` しかなく、空パスを `active` へ送る `redirectTo` がない。

## 影響範囲と同種箇所

エンドポイント一覧を URL から開く全利用者に影響する。サイドナビは `/endpoints/active` をリンクしているため、通常のサイドナビ操作では回避される。

## 対策案

`serving.routes.ts` の `children` の先頭に `{path: '', redirectTo: 'active', pathMatch: 'full'}` を追加し、`/endpoints`、`/endpoints/active`、存在しない子パスを個別に回帰テストする。

## 検証範囲

- 確認したこと：実バックエンドにログインした Playwright（Chromium）で両 URL のコンポーネント生成と URL を確認した
- 確認していないこと：修正後のリダイレクト
- 由来：対象のルート定義は比較資料で実質差分に含まれない

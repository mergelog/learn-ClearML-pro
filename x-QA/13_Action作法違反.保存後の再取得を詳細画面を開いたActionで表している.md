# Action作法違反：保存後の再取得を詳細画面を開いたActionで表している

## まず結論

データカタログの`openDetail`は、詳細ページを開く際だけでなく、メタデータ保存後の再取得にも使われている。保存後には詳細ページを「開いた」わけではないため、Action名が出来事を正確に表さない。

## 実際の流れ

```text
詳細ページを開く → openDetail → 詳細をAPIから取得

メタデータ保存成功 → metadataSaved → openDetail → 詳細をAPIから再取得
```

[詳細ページのコンポーネント](../src/app/features/data-catalog/containers/catalog-asset-detail-page/catalog-asset-detail-page.component.ts#L73)はURLの対象が決まると`openDetail`を発行する。[`loadDetail` Effect](../src/app/features/data-catalog/state/data-catalog.effects.ts#L108)がこれを受けてAPIから詳細を読む。一方、[`reloadAfterSave` Effect](../src/app/features/data-catalog/state/data-catalog.effects.ts#L166)は`metadataSaved`を受けて同じ`openDetail`を発行し、再取得の経路を再利用する。

## 何が困るか

Actionの履歴に`openDetail`が出ても、ページを開いたのか、保存後に同じ詳細を読み直したのか分からない。例えば「ページを開いたときだけ記録するEffect」が`openDetail`を監視すると、保存後の再取得もページ表示として数えてしまう。

なお、保存後に最新の詳細を読み直す処理自体には理由がある。[Effectのコメント](../src/app/features/data-catalog/state/data-catalog.effects.ts#L166)にも、他の画面からの編集を反映する意図が書かれている。[Reducer](../src/app/features/data-catalog/state/data-catalog.reducer.ts#L84)も同じ資産の再取得では既存の詳細を消さないようにしている。

## どう表すか

`metadataSaved`を受けたEffectから直接APIを呼んで`detailLoaded`を発行する方法がある。再取得の要求をActionとして流すなら、`detailRefreshRequested`など、`openDetail`と区別できる名前にする。その場合は既存のReducerが担う`detailLoading`やエラーの更新も維持する必要がある。

```text
ページを開く       → openDetail          → 詳細を取得
メタデータ保存成功 → metadataSaved       → 詳細を再取得
```

参考：[NgRxの教科書「Actionはイベントである」](https://zenn.dev/zzzzzzz/books/ngrx-textbook/viewer/06-action-design#action%E3%81%AF%E3%82%A4%E3%83%99%E3%83%B3%E3%83%88%E3%81%A7%E3%81%82%E3%82%8B)。この資料は設計上の指摘で、実装は変更していない。

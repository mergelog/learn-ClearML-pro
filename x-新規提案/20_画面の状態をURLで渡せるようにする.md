# 画面の状態をURLで渡せるようにする

| 項目 | 内容 |
| --- | --- |
| 分類 | UX体験 |
| 領域 | 自作（両 feature） |
| 直る体験 | 見ているものを人に渡せる。詳細から戻っても絞り込みが残る |
| 規模 | 小（台帳）〜中（品質パイプライン） |
| 状態 | 未着手 |

## いま画面で起きていること

### 台帳：条件はURLに乗るが、画面を移ると落ちる

台帳の絞り込みは URL のクエリに乗る。この判断は明文化されていて、[data-catalog-page.component.ts:35-39](../src/app/features/data-catalog/containers/data-catalog-page/data-catalog-page.component.ts#L35) は「一覧を引く条件は、常にURLから読む」と書き、経路を2本にしない理由まで述べている。クエリの名前は外向きの名前として扱われている（[data-catalog.consts.ts](../src/app/features/data-catalog/data-catalog.consts.ts) の `QUERY_KEYS`）。

その条件が、詳細へ移った時点で消える。資産へのリンクはクエリを引き継がない。

```html
<a [routerLink]="[catalogRoute, asset.kind, asset.id]">{{ asset.name }}</a>
```

［[catalog-assets-table.component.html:23](../src/app/features/data-catalog/components/catalog-assets-table/catalog-assets-table.component.html#L23)］

戻るリンクも同じである。

```html
<a [routerLink]="[catalogRoute]">Back to the catalog</a>
```

［[catalog-asset-detail-page.component.html:4](../src/app/features/data-catalog/containers/catalog-asset-detail-page/catalog-asset-detail-page.component.html#L4)］

`queryParamsHandling` は、どちらにも、アプリ全体の既定（[app.config.ts:38-40](../src/app/app.config.ts#L38)）にも指定が無い。そのため `/data-catalog?q=wafer&kind=model` から資産を開き、「Back to the catalog」で戻ると `/data-catalog` になる。`DataCatalogPageComponent` は URL を正本として読むので、空の条件で一覧を引き直す。絞り込みは失われる。

state の側は、一覧を残すように作られている。[catalog-asset-detail-page.component.ts:84](../src/app/features/data-catalog/containers/catalog-asset-detail-page/catalog-asset-detail-page.component.ts#L84) は「一覧はそのまま残す。詳細から戻ったときに一覧を引き直さないため」と書いている。URL が空になるため、その意図は働かない。

### 品質パイプライン：URLに何も乗らない

`features/quality-pipeline` には `Router` も `ActivatedRoute` も現れない。画面が常に見せるのは「直近の実行」1件で（[quality-pipeline.model.ts:102](../src/app/features/quality-pipeline/quality-pipeline.model.ts#L102)）、特定の実行を指す URL が無い。

そのため、次のことができない。実行の結果を人に渡すこと、あとで同じ実行をもう一度開くこと、失敗した実行を指して相談すること。新しい実行が始まれば、前の実行は画面から消える。

## なぜ変えるか

URL は、この種の画面における共有と再訪の唯一の手段である。ブックマーク、チャットへの貼り付け、報告書からの参照、ブラウザの戻る、どれも URL を前提にしている。

台帳については、方針は既に決まっていて、実装がリンク3本ぶん足りていない。決めた方針が働いていない状態なので、費用は小さく、効き目は方針そのものの価値と等しい。

品質パイプラインについては、実行が積み上がることを前提にしていない作りになっている。1件しか持たない state は、2件目が現れた瞬間に「前の1件を捨てる」という判断を暗黙に選ぶ。

## 解決とみなす状態

1. 台帳の一覧から詳細へ、詳細から一覧へ、どちらの移動でもクエリを引き継ぐ。`queryParamsHandling: 'preserve'` を指定するか、戻り先を組み立てるときに現在のクエリを付ける
2. 来歴のリンク（[catalog-lineage.component.html:6](../src/app/features/data-catalog/components/catalog-lineage/catalog-lineage.component.html#L6)）も同じ扱いにする。詳細から詳細へ渡り歩いても、元の一覧へ戻れる
3. 品質パイプラインの実行を URL で指せるようにする。`/quality-pipeline` は直近の実行、`/quality-pipeline/run/:taskId` はその実行、という形で足りる
4. 3を入れるなら、state が持つ実行を1件から複数へ変える必要がある。[12](./12_評価指標を比較として読めるようにする.md) が同じ変更を必要とするため、まとめて行う
5. 並べ替えと読み足しの位置も URL に乗せる（[05](./05_一覧の続きへ辿り着けるようにする.md)）

## 変更の範囲

* 変更：台帳の `routerLink` 3箇所。1〜2はこれだけで終わる
* 変更：`quality-pipeline.routes.ts` に子の経路を足し、container が `taskId` を読む
* 変更：`quality-pipeline` の reducer（実行を1件から複数へ）

## 確かめ方

* E2E：[e2e/data-catalog.spec.ts](../e2e/data-catalog.spec.ts) に、絞り込んだ状態で詳細を開き、戻ったときに絞り込みが残っていることを足す
* 単体：クエリを引き継ぐリンクの組み立て

## 注意

1と2は、動いていない仕様として `x-不具合調査` に登録する筋のものでもある。「条件は常にURLから読む」という明文化された方針に対して、リンクがそれを運んでいない状態だからである。提案として扱うか不具合として扱うかは、着手の順に影響する。

## 関連

* [05_一覧の続きへ辿り着けるようにする.md](./05_一覧の続きへ辿り着けるようにする.md)
* [12_評価指標を比較として読めるようにする.md](./12_評価指標を比較として読めるようにする.md)
* [x-不具合調査/21_ダッシュボードを開いた後に一覧でMy_Workを選ぶとURLから絞り込みの条件が消える.md](../x-不具合調査/21_ダッシュボードを開いた後に一覧でMy_Workを選ぶとURLから絞り込みの条件が消える.md)

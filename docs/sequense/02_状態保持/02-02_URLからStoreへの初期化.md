# 02-02 URL から Store への初期化

画面に入った直後と、URL のクエリが変わったときに走る復元処理。
`ExperimentsComponent` のコンストラクタで組んだ 1 本の購読がすべてを担当する。

監視対象は 3 つの合成で、`distinctParamsUntilChanged$` を通してから購読する。

- `selectRouterProjectId`（ルートの `:projectId`）
- `route.queryParams`
- `selectCustomColumns`（プロジェクト別のカスタム列）

## 図1: 復元の分岐

```mermaid
sequenceDiagram
    autonumber
    participant Router
    participant EC as ExperimentsComponent
    participant Util as distinctParamsUntilChanged$
    participant Store
    participant ViewEff as ViewEffects

    Router-->>EC: projectId / queryParams が届く
    EC->>Util: combineLatest([projectId, queryParams, customColumns])
    Util->>Util: q / qreg / gq / gqreg / tab / gsfilter を除去
    Util->>Util: pairwise() で前回値と比較
    Note right of Util: 検索語だけの変化ではここを通らない<br/>（検索は syncAppSearch の別購読が拾う）
    Util-->>EC: [prevProjectId, projectId, params]

    alt プロジェクトが変わり、かつクエリが空
        EC->>EC: emptyUrlInit()
        EC->>Store: dispatch updateUrlParams()
        EC->>EC: shouldOpenDetails = true
        Note right of Store: Store の現在値（＝設定から復元済み）を<br/>URL へ書き出す。ここでは取得しない
    else それ以外
        EC->>EC: setupHeaderTabs('tasks', params.archive === 'true')
        opt params.columns
            EC->>EC: decodeColumns(params.columns, tableCols)
            EC->>Store: dispatch setVisibleColumnsForProject({visibleColumns, projectId})
            EC->>Store: dispatch setExtraColumns({columns: メトリクス列＋ハイパーパラメータ列})
            EC->>Store: dispatch setColsOrderForProject({cols: allIds})
        end
        opt params.order
            EC->>Store: dispatch setTableSort({orders: decodeOrder(...), projectId})
        end
        alt params.filter がある
            EC->>Store: dispatch setTableFilters({filters: decodeFilter(...), projectId})
        else params.order だけある
            EC->>Store: dispatch setTableFilters({filters: [], projectId})
        end
        opt params.deep
            EC->>Store: dispatch setDeep({deep: true})
        end
        EC->>Store: dispatch setArchive({archive: params.archive === 'true'})
        EC->>Store: dispatch getExperiments()
        Store->>ViewEff: reFetchExperiment effect（04-01 へ）
    end
```

## 図2: 空 URL のときに 2 周する理由

```mermaid
sequenceDiagram
    autonumber
    participant EC as ExperimentsComponent
    participant Store
    participant ViewEff as ViewEffects
    participant RouterEff as RouterEffects
    participant Router

    Note over EC: 1周目 — /tasks（クエリなし）
    EC->>Store: dispatch updateUrlParams()
    Store->>ViewEff: setURLParams effect
    ViewEff->>ViewEff: Store の cols / hiddenCols / metricsCols / colsOrder を encodeColumns
    ViewEff->>Store: dispatch setURLParams({columns, filters, orders, isDeep, update: true})
    Store->>RouterEff: setTableParams effect
    RouterEff->>Router: navigate([], {replaceUrl: true, queryParamsHandling: 'merge'})

    Note over EC: 2周目 — /tasks?columns=...&order=...
    Router-->>EC: queryParams が変わったので購読が再発火
    EC->>Store: decode した値で setVisibleColumnsForProject / setTableSort / ...
    EC->>Store: dispatch getExperiments()
```

`replaceUrl: true` は `queryParams.order` が未設定のときだけ付く。
初回の URL 補完で履歴を 1 つ消費しないための扱いで、ブラウザバックが
「クエリなしの URL」に戻らないようにしている。

## 読みどころ

- 購読本体: [experiments.component.ts:284](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/experiments/experiments.component.ts:284)
- 空 URL の分岐: [experiments.component.ts:355](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/experiments/experiments.component.ts:355)
- 比較用ユーティリティ: [common-projects.utils.ts:55](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/projects/common-projects.utils.ts:55)
- デコード関数群: [tableParamEncode.ts](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/shared/utils/tableParamEncode.ts)
- URL 書き込み: [router.effects.ts:28](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/core/effects/router.effects.ts:28)

検索語（`q`）だけが別扱いになっているのは、
`syncAppSearch()` が `selectSearchQuery` を購読して `globalFilterChanged` を発行し、
そこから直接再取得に入るためである（[experiments.component.ts:467](/home/mtrysd/work_2026/000-learn-ClearML-pro/src/app/webapp-common/experiments/experiments.component.ts:467)）。
除外していないと、検索のたびに列・ソート・フィルタの復元処理まで走り直す。

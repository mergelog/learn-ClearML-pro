---
name: bulletin
description: 指定された処理について、開始地点から処理対象までの振る舞いを一本線で追跡するコードリーディング資料「Bulletin解析」(ngbi-*.md) を作成する。30秒で分かる結論・mermaid全体図・コードを追うN地点の構成で出力する。「/bulletin {処理内容}」「Bulletin解析を作って」「この処理がどこから始まってどこへ届くか追跡して」「処理の流れを一本線で資料化して」といった依頼で使用する。
---

# Bulletin解析

指定された処理について、**処理対象までの振る舞いを一本線で追跡するコードリーディング資料**を作成する。

目的は、関連コードを網羅的に説明することではない。

> **「この振る舞いは、どこから始まり、どのコードを通り、どこへ到達するのか」**

を、実コード上の根拠を確認しながら一本道として追える資料にする。**クラスを追うのではなく、振る舞いを追う。**

## 表記

資料内で Bulletin と表示する箇所は、すべて **「Bulletin解析」** と書く（タイトル、到達点の見出し、本文）。
ファイル名の接頭辞 `ngbi-` は変えない。

## 出力ファイル

プロジェクトルート直下に次の形式で作成する。

```text
ngbi-{2桁連番}-{日本語タイトル}.{YYMMDD}.md
```

| 要素 | 決め方 |
| --- | --- |
| `{2桁連番}` | プロジェクトルート直下の `ngbi-[0-9][0-9]-*.md` の最大番号 + 1。該当がなければ `01` |
| `{日本語タイトル}` | 資料タイトル `# Bulletin解析: ...` の `...` と同じ文。空白と `/ \ : * ? " < > \|` および `` ` `` は除く |
| `{YYMMDD}` | 作成日（`date +%y%m%d`） |

- `ngbi-01-実験一覧の行を右クリックしてメニューを表示する.260917.md`
- `ngbi-02-実験一覧の検索条件を変更して再取得する.260918.md`

連番は次のコマンドで確認する。

```bash
ls ngbi-[0-9][0-9]-*.md 2>/dev/null | sed -E 's/^ngbi-([0-9]{2})-.*/\1/' | sort -n | tail -1
```

## 完成形の見本

[references/example-experiment-row-context-menu-display.md](references/example-experiment-row-context-menu-display.md)

構成・粒度・文体はこの見本に合わせる。見本内のリンクはプロジェクトルート基準の相対パス。

## 作業手順

1. **終了地点を確定する** — 指示された「処理内容」がどのコードへの到達を指すのかを決める。
2. **開始地点を特定する** — ボタンクリック、右クリック、入力値変更、`formControl` 変更、`output` イベント、Route遷移、Component初期化、Signal変更、Store Action、外部イベント、APIレスポンスなど。開始地点そのものが不明な場合は、確認できた最上流地点から開始し、その旨を明記する。
3. **接続を実コードで1本ずつ裏取りしながら前進する** — テンプレートのバインド、`emit` の受け手、`dispatch` を監視する Effect、呼び出されるメソッドを grep 等で確認する。推測で経路を繋がない。
4. **本線の地点と結論を確定する** — 本線の地点を並べ、この振る舞いで読み手が最初に知るべき構造上の要点を1つに絞る。
5. **資料構成どおりに書く。**
6. **自己レビューして修正する**（末尾のチェックリスト）。

## 資料構成

次の順序で、次の節だけを置く。

```text
# Bulletin解析: {振る舞いを1文で}
## 30秒で分かる結論
## 全体図
## コードを追う{N}地点
## {条件}による分岐          ← 本線の理解に分岐が必要な場合のみ
## 補足: {要点を言い切る}     ← 本線外の前提を書く必要がある場合のみ
## Bulletin解析到達点
```

### タイトル

クラス名ではなく、利用者視点の振る舞いを1文で書く。

`# Bulletin解析: 実験一覧の行を右クリックしてメニューを表示する`

### 30秒で分かる結論

この節だけで振る舞いの要点が分かるようにする。

- 1文目で処理の骨格を言う。
- 表 `担当 | 技術 | 実際の役割` で、振る舞いを2〜4個程度の役割に分け、どの技術（ライブラリ、Angular機能、NgRx等）が何を担っているかを示す。
- 最後に、引用＋太字の1行で結論を言い切る。

```markdown
## 30秒で分かる結論

この処理では、2種類のメニュー機能を使い分けている。

| 担当 | 技術 | 実際の役割 |
|---|---|---|
| 右クリック検出 | PrimeNG `p-context-menu` | 対象行とマウス座標を取得する。自身は非表示 |
| メニュー表示 | Angular Material `mat-menu` | 右クリック位置に実際のメニューを表示する |

> **PrimeNGで検出し、Angular Materialで表示する。**
```

### 全体図

mermaid の `flowchart LR` で、本線全体を1枚にする。

````markdown
## 全体図

```mermaid
---
config:
  flowchart:
    nodeSpacing: 214
---
flowchart LR
    User["{開始のトリガー}"]

    subgraph Phase1["① {段階名} — {主な技術・層}"]
        A["{Class}<br>{method() または役割}"]
        B["{Class}<br>{method() または役割}"]
    end

    subgraph Phase2["② {段階名} — {主な技術・層}"]
        C["{Class}<br>{役割}"]
    end

    User --> A --> B
    B -->|{output名・payload・呼び出すメソッド}| C

    classDef {layer1} fill:#e8f4ff,stroke:#2774ae,color:#123;
    classDef {layer2} fill:#fff4d6,stroke:#b7791f,color:#321;
    class A,B {layer1};
    class C {layer2};
```
````

- **先頭の frontmatter `nodeSpacing: 214` は必ず入れる。** 既定値（50）の横長の図は表示幅に縮小されて縦幅が不足するため、既定描画の2倍の縦幅にする設定。横幅は変わらない。
- 開始のトリガー（ユーザー操作など）は subgraph の外に1ノード置く。
- 処理の段階ごとに subgraph を作る。IDは英語、ラベルは `"① 検出 — PrimeNG"` のように「丸数字 段階名 — 主な技術・層」にする。
- ノードのラベルは必ずダブルクォートで囲み、`"クラス名<br>メソッド名() または役割"` の2行にする。
- エッジのラベルには、地点間を渡るもの（output名、payload、呼び出すメソッド）を書く。同じ段階内で自明な接続はラベルを省略してよい。
- classDef で技術・層ごとに色分けする。classDef名は技術・層を表す名前（見本では `prime` / `angular` / `material`）にする。配色は次の3色を段階順に使い、足りなければ同系統の淡色を追加する。
  - `fill:#e8f4ff,stroke:#2774ae,color:#123;`
  - `fill:#fff4d6,stroke:#b7791f,color:#321;`
  - `fill:#f3e8ff,stroke:#805ad5,color:#213;`
- **トリガー以外のノードと「コードを追うN地点」を、同じ順序・同じ数で1対1に対応させる。**

### コードを追うN地点

````markdown
## コードを追う6地点

### 1. 行の右クリックを検出

`<tr>` の `pContextMenuRow` が対象行をPrimeNGへ登録する。右クリックすると、`p-table` の `onContextMenuSelect` から `openContext($event)` へ進む。

- [`pContextMenuRow`](./src/app/webapp-common/shared/ui-components/data/table/table.component.html#L127)
- [`onContextMenuSelect`](./src/app/webapp-common/shared/ui-components/data/table/table.component.html#L36)

### 3. 対象実験と座標を確定

`ExperimentsTableComponent.openContextMenu()` が次の3つを行う。

1. 対象実験を `contextExperiment` Signalへ保存
2. `preventDefault()` でブラウザ標準メニューを抑止
3. `clientX` / `clientY` を `contextMenu` outputで親へ通知

- [`ExperimentsTableComponent.openContextMenu()`](./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L349)
- [`contextMenu.emit({x, y})`](./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L361)

### 5. 非表示トリガーを右クリック位置へ移動

`BaseContextMenuComponent.openMenu()` が座標を `position` Signalへ設定する。テンプレートでは、その値が `position: fixed` の非表示トリガーへ反映される。

- [`BaseContextMenuComponent.openMenu()`](./src/app/webapp-common/shared/components/base-context-menu/base-context-menu.component.ts#L48)
- [座標を受け取る非表示トリガー](./src/app/webapp-common/experiments/shared/components/experiment-menu/experiment-menu.component.html#L11)

```text
MouseEvent.clientX / clientY
        ↓
position Signal
        ↓
非表示トリガーの left / top
```
````

- 見出しは `## コードを追う{N}地点`。N は実際の地点数と一致させる。
- 各地点の見出しは `### {番号}. {その地点で起きること}`。動詞句で書き、クラス名を見出しにしない。
- 本文は1〜3文。**この地点で何をするか**と、**次の地点へ進む根拠**（`(rowRightClick)="openContextMenu($event)"` のようなバインド、`emit`、`dispatch`、メソッド呼び出し）を文中のインラインコードで示す。「次は FooComponent」とだけ書かない。
- 1地点で複数の処理を順に行う場合は番号付きリストにする。
- 本文の後にリンクの箇条書きを1〜3個置く。処理を行うコードと、次の地点へ接続する根拠のコードを優先する。
  - コード識別子で表せる箇所: ``[`TableComponent.openContext()`](./path#L421)``、``[`rowRightClick` の受信](./path#L31)``
  - 識別子で表しにくい箇所: `[座標を受け取る非表示トリガー](./path#L11)`
- 値が層をまたいで形を変える場合に限り、`text` コードブロックと `↓` で小さな変換図を入れてよい。
- Angular / RxJS / NgRx の技術は、本文中で**何のために使っているか**が分かる形で触れる。技術名の一覧は作らない。

### {条件}による分岐

本線の理解に分岐が必要な場合だけ置く。

````markdown
## 選択状態による分岐

右クリック時の違いは、Step 3の対象確定だけである。表示までの経路は変わらない。

```text
チェック済みの行を右クリック
  → 現在の複数選択を維持

未チェックの行を右クリック
  → 選択を右クリックした1件へ変更
```

該当処理: [`openContextMenu():350-358`](./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.ts#L350)
````

- 1文目で、どの地点で分岐し、本線の経路が変わるかどうかを言う。
- 条件と結果を `text` コードブロックで並べる。
- 該当処理は `method():開始行-終了行` のラベルで、リンク先は開始行にする。
- 本線でない分岐先は深追いしない。

### 補足: {要点}

本線より前に準備されている前提（テンプレートの受け渡し、初期化、providerなど）で、本線の理解に必要なものだけを書く。

```markdown
## 補足: メニュー本体は事前に準備されている

右クリックより前に、親が定義した `contextMenuExtendedTemplate` を実験テーブルが `ngTemplateOutlet` で描画している。そのため、右クリック時は既存のメニューComponentに対して `openMenu()` を呼ぶだけでよい。

[`contextMenuExtendedTemplate`](./src/app/webapp-common/experiments/experiments.component.html#L140)
→ [`contextMenuTemplate` input](./src/app/webapp-common/experiments/experiments.component.html#L94)
→ [`ngTemplateOutlet` で描画](./src/app/webapp-common/experiments/dumb/experiments-table/experiments-table.component.html#L1)
```

- 見出しは要点を言い切る形にする。
- 1〜2文の説明と、`→` でつないだリンクの経路を書く。
- 追跡中に本線外の重要そうな処理を見つけた場合も、ここに一言で記録するにとどめ、深追いしない。

### Bulletin解析到達点

```markdown
## Bulletin解析到達点

{開始地点}から、{終了地点}までを確認した。

{その先の処理}は、このBulletin解析の対象外とする。
```

その先にも処理が存在していても、今回の目的外なら追跡しない。

### 追跡不能時

途中でコード上の接続関係が確認できなくなった場合、推測して先へ進まない。
全体図と「コードを追うN地点」は確認できた地点までとし、「Bulletin解析到達点」の代わりに次を置く。

```markdown
## 追跡不能

ここから次の処理への接続を実コード上で確認できなかった。

確認済み:

- FooComponent
- `foo.emit()`
- BarComponent

不明:

- `foo.emit()` を受け取る処理

推測による補完は行わず、ここで追跡を停止する。
```

## 追跡ルール

### 本線だけを追う

関連コードを全部調査しない。常に **「今回追っている振る舞いの一本線はどこか」** を基準にする。

- 対象Componentが多数の子Componentを持っていても、今回の処理に関係しないものは追跡しない。
- Serviceに多数のメソッドがあっても、今回呼ばれるメソッドだけを追跡する。
- Effectに複数Actionの処理があっても、今回のActionに関係する処理だけを追跡する。

### 実コードで確認できた経路だけを書く

`ユーザー操作 → Template → Component → output → 親Component → Store Action → Effect → Service → API` は一例にすぎない。実際のコードをこの形へ当てはめない。
確認できない箇所は `不明` とし、推測を事実として書かない。

### 上方向へ戻ってよい

子Componentから親へ `output()` される場合など、一時的にComponent階層を上へ戻ってよい。
`子 → 親 → メニューComponent` のように、**実際の処理方向**に従って追跡する。Componentツリーの上下関係と処理の進行方向を混同しない。

## 調査時の確認観点

次は接続根拠と各地点の役割を把握するための観点であり、本文に列挙するものではない。本文には今回の振る舞いに必要なものだけを書く。

| 対象 | 確認すること |
| --- | --- |
| Component | 何を表示するか / 誰から受け取り誰へ通知するか / `input()` `model()` `output()` / Signal・`computed` / Store・Serviceとの接続 |
| Store Action | 誰がdispatchするか / payload / 誰が受け取るか |
| Effect | 受け取るAction / RxJS Operator / Service・APIを呼ぶ位置 / 成功時・失敗時のdispatch |
| Reducer | どのActionで / Stateの何を / どう変更するか |
| Selector | どのStateから / 何を抽出・変換するか / 誰が利用するか |
| Service | 呼び出し元 / 引数 / 戻り値 / 次に呼ぶ処理 |
| API | HTTP method / endpoint / request / response / 呼び出し元 |

## リンクと文体

- プロジェクト内のファイルへは `./src/...#L{行}` の相対リンクを使う。
- 行番号は `grep -n` 等で実コードと一致することを確認してから書く。
- コードの引用は本文中の短いインラインコードにとどめ、コードブロックで転載しない。Bulletin解析はソースコードのコピーではなく、**ソースコードへ案内する地図**。
- 常体（である調）で、短い文で書く。

## 完成時の自己レビュー

ファイル作成後、必ず次を確認し、問題があれば修正してから完成とする。

- [ ] ファイル名が `ngbi-{2桁連番}-{日本語タイトル}.{YYMMDD}.md` で、連番が既存と重複せず、日本語タイトルが資料タイトルと一致しているか
- [ ] 表記がすべて「Bulletin解析」になっているか
- [ ] 「30秒で分かる結論」だけで振る舞いの要点が分かるか
- [ ] 全体図に frontmatter `nodeSpacing: 214` が入っているか
- [ ] 全体図のノード（トリガー以外）と「コードを追うN地点」が同じ順序・同じ数で対応し、見出しの N が地点数と一致しているか
- [ ] 各地点の本文に、次の地点へ進む実コード上の根拠が書かれているか
- [ ] 関係ない処理を深追いしていないか（Componentツリー調査やクラス説明集になっていないか）
- [ ] 推測を事実として記載していないか
- [ ] リンク先が実在し、行番号が実コードと一致しているか
- [ ] 指定された処理対象へ到達し、「Bulletin解析到達点」で終了しているか

読者が途中で迷っても、**結論と全体図を見る → 該当地点を読む → リンクでコードを開く → 次の地点へ戻る**の流れで追跡へ復帰できる資料にする。

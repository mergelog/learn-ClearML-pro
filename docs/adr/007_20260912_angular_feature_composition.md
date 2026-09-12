# ADR 007: 自作 feature の組み立て方（standalone / Signals と NgRx / lazy route / 失敗の扱い）

- 状態: 採用
- 日付: 2026-09-12
- 対象: `apps/web/src/app/features/**`（自作分。`quality-pipeline` と `data-catalog` の2つ）
  および自作の共有層 `apps/web/src/app/shared/**`
- 関連: 計画書 W12-10、`docs/adr/003_20260908_angular_boundaries_and_strict.md`、
  `apps/web/README.md`（「ディレクトリ構成」「feature の標準形」
  「変更検知とコンポーネントの命名」）、
  `docs/adr/009_20260912_shared_layer_and_deferred_decisions.md`（Stage P の判定）

## 背景

この画面は取り込んだ ClearML Web の中へ自作の feature を足したものである。
**周りは Angular 13 世代の書き方（NgModule・`*ngIf`・Observable の直接購読）**
で書かれており、凍結領域として触らないと決めている（ADR 003）。

そのため自作分をどう書くかは、周りに合わせるか現行推奨に合わせるかの選択に
なる。ここを都度決めると、feature が2つ目・3つ目と増えたときに書き方が割れる。
割れた書き方は、規約が無いことより読み手を迷わせる。

`apps/web/README.md` には**形**（ディレクトリ構成・feature の標準形・命名）が
既に書いてある。ここに書くのは、その形を選んだ**理由**と、形だけでは決まらない
4つの判断である。二重に書かない。

## 決定

### 1. 自作 component は standalone で書く（`imports` を持つ）

NgModule を新しく作らない。凍結領域には NgModule が残っているが、自作分から
そこへ足さない。

理由は、**依存が component の中に書いてあること**である。NgModule 経由だと、
ある component が何に依存しているかを知るのに module まで遡る必要があり、
遡った先は feature を跨いで共有されている。`web-boundaries` が見ている
「feature を跨いだ import」を、module 経由で回避できてしまうことも避けたい。

### 2. state は NgRx、画面が読むのは Signal

**両方使う。責務で分ける。**

| 何を | どこで | 理由 |
| --- | --- | --- |
| 何が起きたら state がどう変わるか | reducer | 遷移は1か所で読めること |
| 派生した問い（起動できるか、止められるか） | selector | 同じ問いを container と template に散らさない |
| 外の世界との往復（ClearML API） | Effects | component から非同期を追い出す |
| 画面が読む値 | `store.selectSignal(...)` | template で購読を書かない |

Signal を「NgRx の代わり」には使わない。どちらの feature も
**複数の非同期が同じ state を触る**（`quality-pipeline` は起動・再取得・停止・
指標の読み直し、`data-catalog` は一覧・選択肢・詳細・lineage・保存）もので、
遷移の記録が要る。逆に、component から `async` パイプや `subscribe` で
Observable を読むこともしない。読む側は Signal に揃える。

**store の外から来る値も Signal に揃える**（2本目で出た追加）。`data-catalog` は
route を `toSignal` で読む。`initialValue` を置くかどうかは好みではなく、
**その型に「まだ無い」を表す値があるかで決まる**。`queryParams`（`Params`）には
空オブジェクトという自然な初期値があるので置く。`paramMap`（`ParamMap`）には無い
ので置かず、`undefined` のまま扱う。**無いものを作って埋めない。** 偽の初期値を
置くと、まだ決まっていないことと空であることが同じ値になる。

`selectSignal` で読む以上、component は変更検知の都合を書かなくてよい。
`OnPush` を明示するのは意図の表明としてであり、実行時には no-op である
（Angular 22 の既定。README「変更検知とコンポーネントの命名」）。

### 3. state・Effects・API 境界は lazy route の provider として用意する

アプリ全体へ登録しない。`features/<name>/<name>.routes.ts` の
`loadComponent` と同じ場所で `provideState` / `provideEffects` /
API サービスを渡す。

- **この画面を開かない利用者にとっては、存在しないほうが正しい**（どちらの
  feature もナビの1項目で、多くの利用者は開かない）
- どの state がどこで生まれるかが、route を見れば分かる
- 取り込んだ画面の state と混ざらない

**feature が複数の画面を持つときは、provider を親の route に置く**（2本目で出た
追加）。`data-catalog` は一覧と詳細の2つの container が同じ state を共有する。
それぞれの route に置くと、詳細へ移った瞬間に state が作り直され、戻ったときに
一覧を引き直すことになる。**画面の数ではなく、state の寿命で置き場所を決める。**

一方 `data`（breadcrumb など）は子ごとに置く。Angular の既定
（`paramsInheritanceStrategy: 'emptyOnly'`）では、パラメータを持つ子は親の `data`
を受け継がない。**provider は親・`data` は子**で、同じ route ファイルの中でも
向きが逆になる。

### 4. 失敗は state に載せる。握り潰さない、投げっぱなしにしない

Effects は `catchError` で**必ず action に変換する**。例外を外へ投げない
（Effects が死んで、以後その効果だけが静かに動かなくなる）。画面に出す文言は
Effects の中で決める。

**失敗の重さで扱いを分ける。分ける基準は「利用者の操作が成立したか」である。**
成立していないなら `error` に載せ、`role="alert"` で出す。成立しているのに
付随する読みだけが失敗したのなら `EMPTY` で流す。**画面全体を失敗にすると、
読めているものまで読めないように見える。**

| feature | `error` に載せる | `EMPTY` で流す |
| --- | --- | --- |
| `quality-pipeline` | 概況の取得・起動・停止 | 指標の取得（実行そのものの失敗ではない） |
| `data-catalog` | 一覧・詳細・メタデータの保存 | 絞り込みの選択肢・lineage |

`data-catalog` の2つが `EMPTY` なのは、選択肢が出なくても絞り込みは自由入力から
成立し、出所が辿れないことは資産が読めないことではないからである。
**どちらも「一覧は読めているのに赤い文字が出る」を避けている。**

**成功したら `error` を消す。失敗しても直前の結果は消さない。** 前者を忘れると
成功している画面に赤い文字が残り、後者を忘れると再取得の失敗で見えていた結果まで
消える。

文言は「何が起きたか」を言う。ClearML は失敗も `meta.result_msg` で説明するので、
まずそれを出す。状態コード 0 は「サーバまで届かなかった」であり、コードを
出しても何も言っていないので、通信そのものの説明を出す。どちらも読めないときだけ
`The request failed, and the server did not say why.` を出す。
**黙って空の画面にしない。** まだ何も無いのか繋がっていないのかが区別できなくなる。

**この文言の作り方は feature ごとに書かない。** 実体は
`shared/clearml/clearml-failure.ts` の1つだけである（Stage P-2 で2箇所から寄せた。
経緯は ADR 009）。**方針の実体が2つあるものは方針ではない。** 一方、どの失敗を
どちらの扱いにするか（上の表）は feature の判断なので、共有層では決めない。

## 影響

- **2つ目（`data-catalog`）はこの4つを引き継ぎ、沿えなかった点は無かった**
  （Stage P-1 の点検結果）。足りなかったのは禁止ではなく明示で、上の
  「2本目で出た追加」3点をここへ書き足した。形は README の「feature の標準形」に
  従う（`tsconfig.strict.json` の `include` へ足すことを含む）
- **3つ目からは、この文書は実例ではなく規約として読む。** 沿わない書き方を
  するなら、先にこの文書を直す
- `store.selectSignal` に揃えているため、container の単体テストは state を
  差し替えるだけで書ける（`apps/web` 単体の層。ADR 005）
- 失敗を state に載せる形にしているので、失敗時の表示は E2E ではなく
  単体テストで確かめられる。E2E が見るのは「説明が支援技術へ届くか」だけである

## 代案と、採らなかった理由

- **NgRx をやめて Signal だけにする**: 複数の非同期が同じ state を触るため、
  遷移の記録が無いと「なぜこの状態になったか」を追えない。採らない
- **state をアプリ全体へ登録する**: 開かない画面の state を全員が持つことになる。
  取り込んだ画面の state とも混ざる。採らない
- **周り（凍結領域）の書き方へ揃える**: NgModule と Observable 購読へ戻すことに
  なる。凍結領域は追従のために凍結しているのであって、**書き方の手本ではない**
- **失敗を握り潰して空表示にする**: 「まだ無い」と「繋がっていない」が区別
  できなくなる。採らない

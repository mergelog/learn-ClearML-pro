# 04_lodash 以外の外部汎用モジュール調査

## Q

このプロジェクトで使っている lodash のような「外部の汎用便利モジュール」は、lodash 以外に何があるか。

## A（結論）

ある。ただし lodash-es のような「広く浅く使う万能ユーティリティ」はほぼ lodash-es 1 本で、
それ以外は **用途が 1 つに絞られた単機能ライブラリ** が多数、という構成になっている。

汎用度で並べると次の 3 層に分かれる（`rxjs` は Angular / NgRx の前提ライブラリのため本資料では対象外）。

| 層 | パッケージ | 位置づけ |
| --- | --- | --- |
| 汎用ユーティリティ | `lodash-es` / `ngxtension` | アプリ全体に薄く広く分布 |
| 準汎用（領域ユーティリティ） | `date-fns` / `uuid` / `@ctrl/tinycolor` / `semver` / `filesize` / `dompurify` | 「日付」「色」など領域は限定されるが、複数機能から呼ばれる |
| 単機能（1〜2 ファイル専用） | `marked` / `diff` / `lucene` / `hocon-parser` / `export-to-csv` / `dom-to-image` / `ansi-to-html` ほか | 特定画面のためだけに入っている |

---

## 1. 汎用ユーティリティ層

| パッケージ | import しているファイル数 | 用途 |
| --- | --- | --- |
| `lodash-es` | 114 | オブジェクト・配列操作全般 |
| `ngxtension` | 34 | Angular Signal 系の補助ユーティリティ |

### lodash-es の実際の使われ方

import 行 116 本のうち、実際に使われている関数の上位は以下。
「値の比較」「安全な取り出し」「深いコピー」が大半で、
Angular の変更検知・NgRx のイミュータブル更新を支える目的に偏っている。

| 関数 | 出現数 |
| --- | --- |
| `isEqual` | 37 |
| `get` | 30 |
| `cloneDeep` | 14 |
| `merge` | 9 |
| `pick` | 7 |
| `uniq` / `uniqBy` | 10 |

※ CommonJS 版の `lodash` ではなく ESM 版の `lodash-es` を使用（tree-shaking が効く）。型は `@types/lodash-es`。

### ngxtension（Angular 専用の便利モジュール）

lodash が「JS の汎用」なのに対し、こちらは「Angular Signal の汎用」。サブパス単位で import する。

| サブパス | import 数 | 用途 |
| --- | --- | --- |
| `ngxtension/computed-previous` | 14 | Signal の前回値を参照する |
| `ngxtension/resize` | 11 | 要素サイズ変更の購読 |
| `ngxtension/explicit-effect` | 7 | 依存を明示した `effect` |
| `ngxtension/inject-query-params` | 4 | クエリパラメータの Signal 化 |
| `ngxtension/inject-params` / `inject-route-data` / `map-array` | 各 1〜2 | ルーティング・配列変換 |

---

## 2. 準汎用（領域ユーティリティ）層

| パッケージ | ファイル数 | 用途 | 代表的な利用箇所 |
| --- | --- | --- | --- |
| `date-fns` | 4 | 日付整形・加算・相対表示 | [period-selector.component.ts](src/app/webapp-common/shared/components/period-selector/period-selector.component.ts) |
| `uuid` | 7 | v1 / v4 / v5 の ID 生成 | [uuid.pipe.ts](src/app/webapp-common/shared/pipes/uuid.pipe.ts) |
| `@ctrl/tinycolor` | 7 | 色の変換・明度調整 | [color-hash.service.ts](src/app/webapp-common/shared/services/color-hash/color-hash.service.ts) |
| `dompurify` | 3 | HTML サニタイズ（XSS 対策） | [safe.pipe.ts](src/app/webapp-common/shared/pipes/safe.pipe.ts) |
| `semver` | 2 | バージョン比較・妥当性検証 | [semver.validator.ts](src/app/webapp-common/shared/validators/semver.validator.ts) |
| `filesize` | 2 | バイト数の人間可読化 | [filesize.pipe.ts](src/app/webapp-common/shared/pipes/filesize.pipe.ts) |
| `@ngneat/dag` | 3 | DAG（パイプライン図）のレイアウト計算 | [dag-manager-unsorted.service.ts](src/app/webapp-common/shared/services/dag-manager-unsorted.service.ts) |

`semver` は `semver/functions/valid` のようにサブパス単位で import しており、パッケージ全体は取り込んでいない。

---

## 3. 単機能層（1〜2 ファイル専用）

| パッケージ | 用途 | 利用箇所 |
| --- | --- | --- |
| `marked` | Markdown → HTML | [markdown-editor.component.ts](src/app/webapp-common/shared/components/markdown-editor/markdown-editor.component.ts) |
| `diff` | テキスト差分計算 | [jsonToDiffConvertor.ts](src/app/webapp-common/experiments-compare/jsonToDiffConvertor.ts) |
| `lucene` | Lucene クエリ構文の解析 | [lucene-parser.service.ts](src/app/webapp-common/shared/services/lucene-parser/lucene-parser.service.ts) |
| `hocon-parser` | HOCON 設定の解析 | [model-details-reverter.service.ts](src/app/webapp-common/experiments-compare/services/model-details-reverter.service.ts) |
| `export-to-csv` | テーブルの CSV 出力 | [table.component.ts](src/app/webapp-common/shared/ui-components/data/table/table.component.ts) |
| `dom-to-image` | グラフの画像化（ダウンロード） | [compare-scatter-plot.component.ts](src/app/webapp-common/experiments-compare/containers/compare-scatter-plot/compare-scatter-plot.component.ts) |
| `ansi-to-html` / `has-ansi` | コンソールログの ANSI カラー変換 | [experiment-log-info.component.ts](src/app/webapp-common/experiments/dumb/experiment-log-info/experiment-log-info.component.ts) |
| `string-to-color` | 文字列から色を決定 | [color-hash.service.ts](src/app/webapp-common/shared/services/color-hash/color-hash.service.ts) |
| `d3-selection` | DOM 選択（グラフ操作） | [single-graph.component.ts](src/app/webapp-common/shared/single-graph/single-graph.component.ts) |
| `d3-interpolate` | 値の補間 | [single-graph.utils.ts](src/app/webapp-common/shared/single-graph/single-graph.utils.ts) |
| `curved-arrows` | ノード間の曲線矢印の座標計算 | [pipeline-controller-info.component.ts](src/app/webapp-common/pipelines-controller/pipeline-controller-info/pipeline-controller-info.component.ts) |
| `url` | Node の `url.parse` をブラウザで使う polyfill | [amazon-s3-uri.ts](src/app/webapp-common/shared/utils/amazon-s3-uri.ts) |

---

## 4. 調査で分かった注意点

### 4-1. package.json にあるが使われていないもの

| パッケージ | 状況 |
| --- | --- |
| `object-hash` | ソース・設定のどこからも参照されていない（完全な未使用） |
| `taira` | `src/` からの import は 0。[angular.json](angular.json) の `allowedCommonJsDependencies` に名前が残っているだけ |

どちらも ClearML 公式からフォークした際の残骸と考えられる。`taira` はオブジェクトの
フラット化ライブラリで、lodash と役割が被るため使われなくなった可能性が高い。

### 4-2. plotly.js は「型だけの依存」

`src/` に `import plotly from 'plotly.js'` が 9 ファイルあるが、
`dependencies` には入っておらず `@types/plotly.js`（devDependencies）だけが存在する。
実行時は [load-external-library.ts](src/app/webapp-common/shared/utils/load-external-library.ts) が
`<script>` タグを動的に挿入して読み込み、コード側は `declare let Plotly;`（グローバル変数）で扱っている。
つまり **型定義のためだけの import** で、バンドルには含まれない。

### 4-3. フロント以外のレイヤー

| レイヤー | 外部汎用モジュール |
| --- | --- |
| [scripts/](scripts/)（Node の検証スクリプト群） | なし。`node:fs` / `node:path` / `node:test` など標準モジュールのみ |
| [e2e/](e2e/) | `@playwright/test` と `@axe-core/playwright` のみ |

ビルド・検証まわりは意図的に外部依存ゼロで書かれている。

### 4-4. 自前ユーティリティも併存する

[src/app/webapp-common/shared/utils/](src/app/webapp-common/shared/utils/) に 20 ファイルの自前ヘルパーがある
（`escape-regex.ts` `time-util.ts` `statistics.ts` `ts-utils.ts` など）。
lodash で足りる部分は lodash、ClearML のドメイン知識が要る部分は自前、という切り分け。

---

## 5. 再現手順（調査コマンド）

```bash
# src 配下の外部 import をパッケージ単位で集計
grep -rhoP "from\s+'([^'\.][^']*)'" --include=*.ts src/ \
  | sed -E "s/from\s+'//; s/'$//" \
  | sed -E "s#^(@[^/]+/[^/]+).*#\1#; s#^([^@][^/]*)/.*#\1#" \
  | sort | uniq -c | sort -rn

# lodash-es から実際に import している関数の集計
grep -rhoP "import\s*\{[^}]*\}\s*from\s*'lodash-es'" --include=*.ts src/ \
  | grep -oP "(?<=\{)[^}]*" | tr ',' '\n' | sed 's/ //g' | sort | uniq -c | sort -rn
```

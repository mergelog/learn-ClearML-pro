# services

配備単位のアプリケーションを置く。

`ml/` が学習・評価・モデルライフサイクルのドメインを持ち、`services/` は
それを利用する実行体という役割分担にする。

| ディレクトリ | 役割 |
| --- | --- |
| `prediction_api/` | production へ昇格したモデルで良否を判定するHTTP API（計画書の項目5） |
| `ops_exporter/` | Queue・Agent・Taskの状態をPrometheusが読める形で公開する中継（同 項目8） |
| `contracts/` | 公開しているAPIの差分を、呼び出し側が壊れるかどうかで読む |
| `security/` | 資格情報からHTTPの応答を決める、サービス共通の部品 |

`prediction_api/openapi.json` は公開しているAPIの記録である。コードから
生成されるので手で書かない（`pnpm serving:openapi:update`）。一致しなく
なったら `services:test` が落ちる。判断の経緯は
`docs/_archive/adr/006_20260911_published_api_snapshot.md` にある。

`ops_exporter` は読み取りしか行わない。監視対象を変えられる監視は、
システムが壊れる経路をもう1つ増やすためである。

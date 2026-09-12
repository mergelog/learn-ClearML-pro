# BL-05: zoneless への移行

| 項目 | 内容 |
| --- | --- |
| 種別 | 実装 |
| 状態 | 動かさない（条件つきで再検討する） |
| 起票日 | 2026-09-12 |

## 何をしないと決めたか

Angular を zoneless で動かすこと。

## なぜしないか

費用が自作分ではなく凍結領域に出るためである。

自作分はすでに zoneless 相当で、`.subscribe(`・`detectChanges()`・`setTimeout`・
`async` パイプのいずれも0件である。読むのは `selectSignal` と `toSignal` と `input()` だけである。

移行で検証が要るのは凍結領域（1687ファイル）のうち、次の箇所である。

| 凍結領域で zone に依存しうるもの | ファイル数 |
| --- | --- |
| `.subscribe(` で直接購読している | 129 |
| `setTimeout` / `setInterval` を使っている | 83 |
| `detectChanges()` / `markForCheck()` を呼んでいる | 94 |
| `NgZone` を直接参照している | 7 |

## 再検討する条件

`webapp-common` の `.subscribe(` 依存が実際に減ったとき。

当初のトリガーは「`webapp-common` の OnPush 比率が上がったら」だったが、
Angular 22 では OnPush が既定であり、比率はほぼ100%になる。比率を見ても何も分からないため、
zoneless で壊れる書き方そのものを数える形へ差し替えてある。

描画性能の問題が実測された場合も、再検討の契機になる。現時点では出ていない。

## 関連

* `../_archive/adr/009_20260912_shared_layer_and_deferred_decisions.md`

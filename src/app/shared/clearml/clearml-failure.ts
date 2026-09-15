import {HttpErrorResponse} from '@angular/common/http';

/**
 * ClearML API の失敗を、画面に出せる1行にする。
 *
 * **自作の共有層に置いている唯一の判断である。** 元は
 * `quality-pipeline.effects.ts` と `data-catalog.effects.ts` に同じものが
 * 2つあった（Stage P-2 で寄せた）。寄せた理由は行数ではなく、これが
 * **方針**だからである。ADR 007 は「失敗は state に載せる」と決めており、
 * その文言の作り方が feature ごとに割れると、同じ失敗が画面によって
 * 違う言い方をする。方針の実体は1つでなければ方針ではない。
 *
 * ClearML の API は失敗の形が一定ではない。読める文字列が取れないときに
 * `[object Object]` を出すくらいなら、何が起きたか言えないと明示する。
 *
 * ここが ClearML の語彙（`meta.result_msg`）を知っているのは意図的である。
 * 失敗の形は ClearML 側の約束であって、feature ごとの都合ではない。
 * 逆に、どの失敗を画面に出すか（state へ載せるか `EMPTY` で流すか）は
 * feature の判断なので、ここでは決めない。
 */
export const describeClearmlFailure = (error: unknown): string => {
  if (typeof error === 'string') {
    return error;
  }
  // `HttpErrorResponse` を `Error` より先に見る。
  //
  // 元の2箇所には「順序を逆にすると通信の失敗が固定文言へ落ちる」と書いてあったが、
  // **これは誤りだった**（Stage P-2 で入れ替えて確かめたところ、テストは落ちない）。
  // `HttpErrorResponse` は `Error` を implements しているだけで継承はしていないので
  // `instanceof Error` に掛からず、順序は結果を変えない。
  // それでも先に見るのは、狭いほうから順に見るという並びを保つためである。
  if (error instanceof HttpErrorResponse) {
    return describeHttpFailure(error);
  }
  if (error instanceof Error) {
    return error.message;
  }
  const meta = (error as {error?: {meta?: {result_msg?: string}}})?.error?.meta?.result_msg;
  return meta ?? UNEXPLAINED_FAILURE;
};

/**
 * 接続断・タイムアウト・502のように `meta` を伴わない失敗では、状態コードを出す。
 * 運用画面で切り分けに使えるのはここだけである。
 */
const describeHttpFailure = (error: HttpErrorResponse): string => {
  const meta = (error.error as {meta?: {result_msg?: string}} | null)?.meta?.result_msg;
  if (meta) {
    return meta;
  }

  // 状態コード0は、要求がサーバまで届かなかったということである。
  // その場合コードを出しても何も言っていないので、通信そのものの説明を出す。
  if (error.status === 0) {
    return error.message || UNEXPLAINED_FAILURE;
  }

  return `${error.status} ${error.statusText ?? ''}`.trim();
};

export const UNEXPLAINED_FAILURE = 'The request failed, and the server did not say why.';

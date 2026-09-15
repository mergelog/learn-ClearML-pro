import {HttpErrorResponse} from '@angular/common/http';
import {
  describeClearmlFailure,
  UNEXPLAINED_FAILURE,
} from '~/shared/clearml/clearml-failure';

/**
 * 失敗の文言の作り方を確かめる。
 *
 * ここが壊れても型では気付けない。壊れ方は「例外が出る」ではなく
 * **「利用者に `[object Object]` と言う」**である。2つの feature が
 * これを共有している以上（Stage P-2）、確かめる場所も1つでよい。
 */
describe('describeClearmlFailure', () => {
  it('文字列はそのまま出す', () => {
    expect(describeClearmlFailure('Queue is not available')).toBe('Queue is not available');
  });

  it('ClearMLが理由を言っているなら、それを出す', () => {
    const error = new HttpErrorResponse({
      status: 400,
      statusText: 'Bad Request',
      error: {meta: {result_msg: 'Invalid task id'}},
    });

    expect(describeClearmlFailure(error)).toBe('Invalid task id');
  });

  it('理由が無いHTTP失敗は、状態コードで切り分けられるようにする', () => {
    const error = new HttpErrorResponse({status: 502, statusText: 'Bad Gateway'});

    expect(describeClearmlFailure(error)).toBe('502 Bad Gateway');
  });

  it('状態コード0は、コードではなく通信そのものの説明を出す', () => {
    // 0は「サーバまで届かなかった」であり、コードを出しても何も言っていない。
    const error = new HttpErrorResponse({status: 0, statusText: 'Unknown Error'});

    expect(describeClearmlFailure(error)).toBe(error.message);
  });

  it('HttpErrorResponse を Error より先に見る（Error を継承していないため）', () => {
    const error = new HttpErrorResponse({
      status: 404,
      statusText: 'Not Found',
      error: {meta: {result_msg: 'No such model'}},
    });

    expect(error instanceof Error).toBe(false);
    expect(describeClearmlFailure(error)).toBe('No such model');
  });

  it('素のErrorはメッセージを出す', () => {
    expect(describeClearmlFailure(new Error('boom'))).toBe('boom');
  });

  it('HttpErrorResponse でない入れ子の meta も読む', () => {
    expect(describeClearmlFailure({error: {meta: {result_msg: 'nested'}}})).toBe('nested');
  });

  it('どこにも読める理由が無いときは、言えないと明示する', () => {
    expect(describeClearmlFailure({})).toBe(UNEXPLAINED_FAILURE);
    expect(describeClearmlFailure(null)).toBe(UNEXPLAINED_FAILURE);
  });
});

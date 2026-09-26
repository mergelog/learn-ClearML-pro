import type {CDPSession, Locator, Page} from '@playwright/test';

/**
 * IME の模擬（プラン §2.1）。
 * ① 変換中の印（isComposing: true / keyCode: 229）を持つ keydown を合成して dispatch する
 * ② CDP の Input.imeSetComposition で変換中の状態（compositionstart〜compositionupdate）を作る
 * ③ ②の状態のまま①の keydown を dispatch する
 *
 * ②は keydown を発生させない。Enter・Esc・Tab・矢印キーの判定は①か③で確かめる。
 */

export async function cdp(page: Page): Promise<CDPSession> {
  return page.context().newCDPSession(page);
}

/** 変換中の文字列を置く（未確定のまま）。compositionstart / compositionupdate / input が届く */
export async function setComposition(session: CDPSession, text: string): Promise<void> {
  await session.send('Input.imeSetComposition', {text, selectionStart: text.length, selectionEnd: text.length});
}

/** 変換を確定する。compositionend が届き、確定文字列が入る */
export async function commitComposition(session: CDPSession, text: string): Promise<void> {
  await session.send('Input.insertText', {text});
}

export interface ComposingKey {
  key: string;
  code?: string;
  /** 既定は 229 */
  keyCode?: number;
  /** 既定は true */
  isComposing?: boolean;
  shiftKey?: boolean;
}

/** 変換中の keydown（と keyup）を合成して dispatch する。ハンドラの判定だけを確かめる用途 */
export async function dispatchComposingKey(target: Locator, key: ComposingKey, withKeyup = false): Promise<void> {
  await target.evaluate((el, k) => {
    const init = {
      key: k.key,
      code: k.code ?? k.key,
      keyCode: k.keyCode ?? 229,
      which: k.keyCode ?? 229,
      isComposing: k.isComposing ?? true,
      shiftKey: k.shiftKey ?? false,
      bubbles: true,
      cancelable: true,
      composed: true
    };
    el.dispatchEvent(new KeyboardEvent('keydown', init));
    if (k.withKeyup) {
      el.dispatchEvent(new KeyboardEvent('keyup', init));
    }
  }, {...key, withKeyup});
}

/**
 * Chromium で多く報告される「変換確定の Enter」の届き方を模擬する：
 * keydown(Enter, isComposing: true, 229) → compositionend（確定）→ keyup(Enter)
 */
export async function commitWithEnterChromiumOrder(page: Page, session: CDPSession, target: Locator, text: string): Promise<void> {
  await dispatchComposingKey(target, {key: 'Enter'});
  await commitComposition(session, text);
  await target.evaluate(el => el.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true})));
  await page.waitForTimeout(0);
}

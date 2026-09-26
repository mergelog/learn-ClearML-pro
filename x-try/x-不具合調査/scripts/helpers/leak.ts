import type {CDPSession, Page} from '@playwright/test';

/**
 * 観点E（購読・タイマー・イベントリスナの破棄）の検出。
 * 開発モード（ng serve）の window.ng と CDP を使い、画面を離れた後に残るものを数える。
 *
 * - Store の購読数：store.select(...) を購読するたびに1つ増え、解除で減る（storeObserverCount）。購読者ごとのコールバックも区別できる（storeObserverCallbacks）
 * - 残っているインスタンス：画面にいるあいだにコンポーネントを WeakRef で控え、GC の後も生きていて DOM 上に無いものを数える（trackComponentInstances・retainedByWeakRef）
 * - イベントリスナ数：zone.js が要素に積む配列の長さで数える（globalListenerCounts・elementListenerCounts）
 */

/** アプリ内の遷移（再読み込みしない）。AppComponent（sm-app-shell）の router を使う */
export async function navigateInApp(page: Page, url: string): Promise<boolean> {
  return page.evaluate(async target => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    return app.router.navigateByUrl(target);
  }, url);
}

/**
 * Store の購読数。store.source から source をたどり、最初に見つかった Subject の observers の数を返す。
 * 開発ビルドでは Store の開発ツールが StateObservable を liftedStateSubject.asObservable().pipe(map(...)) に差し替えるため、
 * NgRx の State ではなく liftedStateSubject の observers を数えることになる（store.select の購読ごとに1つ増える点は同じ）。
 */
export async function storeObserverCount(page: Page): Promise<number> {
  return page.evaluate(() => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    let src = app.store.source;
    for (let i = 0; i < 10 && src && !Array.isArray(src.observers); i++) {
      src = src.source;
    }
    return src?.observers?.length ?? -1;
  });
}

/**
 * Store の購読者ごとに、subscribe に渡したコールバックのソースの先頭を返し、同じものの数を数える。
 * rxjs 7 の Subscriber は destination をたどると SafeSubscriber の ConsumerObserver（partialObserver.next が利用者のコールバック）に着く。
 * subscribe() に引数が無いものは、途中の演算子のうち最後の tap 等を区別できないため '(no next)' になる。
 */
export async function storeObserverCallbacks(page: Page): Promise<Record<string, number>> {
  return page.evaluate(() => {
    const app = (window as any).ng.getComponent(document.querySelector('sm-app-shell'));
    let src = app.store.source;
    for (let i = 0; i < 10 && src && !Array.isArray(src.observers); i++) {
      src = src.source;
    }
    const counts: Record<string, number> = {};
    for (const observer of src?.observers ?? []) {
      let cur = observer;
      let label = '(no next)';
      for (let i = 0; i < 40 && cur; i++) {
        const next = cur.partialObserver?.next;
        if (typeof next === 'function') {
          label = next.toString().replace(/\s+/g, ' ').slice(0, 140);
          break;
        }
        cur = cur.destination;
      }
      counts[label] = (counts[label] ?? 0) + 1;
    }
    return counts;
  });
}

/** dispatch された action の type を window.__actions に記録し始める */
export async function recordActions(page: Page): Promise<void> {
  await page.evaluate(() => {
    const w = window as any;
    if (w.__actionsSub) {
      return;
    }
    w.__actions = [];
    const app = w.ng.getComponent(document.querySelector('sm-app-shell'));
    w.__actionsSub = app.store.actionsObserver.subscribe((a: {type: string}) => w.__actions.push(a.type));
  });
}

export async function takeActions(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const w = window as any;
    const list = w.__actions ?? [];
    w.__actions = [];
    return list;
  });
}

/**
 * 画面上のコンポーネントのインスタンスを WeakRef で window.__leakRefs に控える（インスタンスは保持しない）。
 * label には何往復目かなどを入れ、後で retainedByWeakRef で残っているものを数える。
 */
export async function trackComponentInstances(page: Page, label: string): Promise<number> {
  return page.evaluate(tag => {
    const w = window as any;
    w.__leakRefs ??= [];
    let n = 0;
    for (const el of Array.from(document.querySelectorAll('*'))) {
      const inst = w.ng.getComponent(el);
      if (inst) {
        w.__leakRefs.push({label: tag, name: inst.constructor?.name ?? '?', ref: new WeakRef(inst)});
        n++;
      }
    }
    return n;
  }, label);
}

/**
 * GC の後、控えたインスタンスのうち、まだ生きていて DOM 上にも無いものを label・クラス名ごとに数える。
 * WeakRef は作った処理（ジョブ）が終わるまで対象を保持するため、控えた evaluate とは別の evaluate で調べる。
 */
export async function retainedByWeakRef(page: Page, cdp: CDPSession): Promise<Record<string, Record<string, number>>> {
  await cdp.send('HeapProfiler.enable');
  for (let i = 0; i < 3; i++) {
    await cdp.send('HeapProfiler.collectGarbage');
  }
  return page.evaluate(() => {
    const w = window as any;
    const inDom = new Set<unknown>();
    for (const el of Array.from(document.querySelectorAll('*'))) {
      const inst = w.ng.getComponent(el);
      if (inst) {
        inDom.add(inst);
      }
    }
    const result: Record<string, Record<string, number>> = {};
    for (const {label, name, ref} of w.__leakRefs ?? []) {
      const inst = ref.deref();
      if (inst && !inDom.has(inst)) {
        result[label] ??= {};
        result[label][name] = (result[label][name] ?? 0) + 1;
      }
    }
    return result;
  });
}

/**
 * 要素に登録されたイベントリスナの数を type ごとに返す。
 * zone.js（polyfills で読み込まれている）は EventTarget.prototype.addEventListener を差し替え、
 * 同じ要素・同じ type・同じ capture には実際のリスナを1つだけ登録して、登録された処理を
 * `__zone_symbol__{type}{capture}` の配列に積む。そのため CDP の DOMDebugger.getEventListeners では増えたことが分からず、この配列の長さで数える。
 */
const zoneListenerCountsSource = `(target) => {
  const counts = {};
  if (!target) { return counts; }
  for (const key of Object.getOwnPropertyNames(target)) {
    const m = key.match(/^__zone_symbol__(.+?)(true|false)$/);
    if (m && Array.isArray(target[key])) {
      counts[m[1] + (m[2] === 'true' ? '(capture)' : '')] = target[key].length;
    }
  }
  return counts;
}`;

/** window と document に登録されたイベントリスナの数を type ごとに返す（zone.js の配列で数える） */
export async function globalListenerCounts(page: Page): Promise<Record<string, number>> {
  return page.evaluate(src => {
    const count = eval(src);
    const counts: Record<string, number> = {};
    for (const [name, target] of [['window', window], ['document', document]] as const) {
      for (const [type, n] of Object.entries(count(target) as Record<string, number>)) {
        counts[`${name}:${type}`] = n;
      }
    }
    return counts;
  }, zoneListenerCountsSource);
}

/** 式で指定した要素（例：`document.querySelector('...')`）に登録されたイベントリスナの数を type ごとに返す（zone.js の配列で数える） */
export async function elementListenerCounts(page: Page, elementExpression: string): Promise<Record<string, number>> {
  return page.evaluate(([src, expr]) => eval(src)(eval(expr)), [zoneListenerCountsSource, elementExpression] as const);
}

/** Tip of the day などのダイアログが出ていたら閉じる */
export async function closeStartupDialogs(page: Page): Promise<void> {
  const dialog = page.locator('mat-dialog-container', {hasText: "Don't show again"});
  if (await dialog.count()) {
    await page.keyboard.press('Escape');
    await dialog.waitFor({state: 'detached', timeout: 5_000}).catch(() => undefined);
  }
}

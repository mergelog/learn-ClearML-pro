import type {Page} from '@playwright/test';
import {readdirSync, readFileSync, statSync} from 'node:fs';
import {join, resolve} from 'node:path';

/**
 * 観点D（Angular 22 の OnPush 既定化）の検出。
 * changeDetection を指定していないコンポーネント（上流では Default、現在は OnPush）について、
 * 画面上のインスタンスに ng.applyChanges() を掛け、前後で DOM が変わるか（＝表示が古いままだったか）を調べる。
 * 開発モード（ng serve）の window.ng を使う。
 */

/** src/app から、@Component に changeDetection の指定が無いクラス名を集める（対象外の feature は除く） */
export function componentsWithoutChangeDetection(root = resolve('src/app')): string[] {
  const names: string[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const path = join(dir, entry);
      if (statSync(path).isDirectory()) {
        if (!/features[\\/](data-catalog|quality-pipeline)$/.test(path)) {
          walk(path);
        }
      } else if (path.endsWith('.ts') && !path.endsWith('.spec.ts')) {
        const src = readFileSync(path, 'utf8');
        let index = 0;
        while ((index = src.indexOf('@Component(', index)) >= 0) {
          let depth = 0;
          let end = index + '@Component'.length;
          for (; end < src.length; end++) {
            if (src[end] === '(') {
              depth++;
            } else if (src[end] === ')' && --depth === 0) {
              break;
            }
          }
          const block = src.slice(index, end);
          const className = src.slice(end).match(/class\s+(\w+)/)?.[1];
          if (className && !/changeDetection/.test(block)) {
            names.push(className);
          }
          index = end;
        }
      }
    }
  };
  walk(root);
  return names;
}

export interface StaleView {
  name: string;
  tag: string;
  before: string;
  after: string;
}

/**
 * 対象のコンポーネントの表示が古いままかを調べる。
 * 1秒おいて DOM が変わらないこと（自然に変わる表示を除く）を確かめてから applyChanges を掛け、変わったものを返す。
 */
export async function findStaleViews(page: Page, classNames: string[]): Promise<StaleView[]> {
  return page.evaluate(async names => {
    const ng = (window as any).ng;
    if (!ng?.getComponent) {
      return [{name: '(ng API なし)', tag: '', before: '', after: ''}];
    }
    const text = (el: Element) => (el as HTMLElement).innerText ?? '';
    const found: {el: Element; comp: any; name: string; html: string; text: string}[] = [];
    for (const el of Array.from(document.querySelectorAll('*'))) {
      const comp = ng.getComponent(el);
      if (!comp) {
        continue;
      }
      const name = comp.constructor.name.replace(/^_+/, '');
      if (names.includes(name)) {
        found.push({el, comp, name, html: el.innerHTML, text: text(el)});
      }
    }
    await new Promise(r => setTimeout(r, 1000));
    const stable = found.filter(f => f.el.isConnected && f.el.innerHTML === f.html);
    for (const f of stable) {
      try {
        ng.applyChanges(f.comp);
      } catch {
        // 破棄済みのビューなどは無視する
      }
    }
    await new Promise(r => setTimeout(r, 300));
    const firstDiff = (a: string, b: string) => {
      let i = 0;
      while (i < a.length && i < b.length && a[i] === b[i]) {
        i++;
      }
      return [a.slice(Math.max(0, i - 40), i + 80), b.slice(Math.max(0, i - 40), i + 80)];
    };
    return stable
      .filter(f => f.el.isConnected && f.el.innerHTML !== f.html)
      .map(f => {
        const [before, after] = f.text !== text(f.el) ? firstDiff(f.text, text(f.el)) : firstDiff(f.html, f.el.innerHTML);
        return {name: f.name, tag: f.el.tagName.toLowerCase(), before, after};
      });
  }, classNames);
}

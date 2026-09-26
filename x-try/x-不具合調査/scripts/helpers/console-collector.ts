import type {Page} from '@playwright/test';

export interface ConsoleEntry {
  url: string;
  type: string;
  text: string;
}

/**
 * ページのコンソール出力（error / warning）と未捕捉の例外を集める。
 * 開発モードの NG0xxx もここに出る。
 */
export function collectConsole(page: Page): ConsoleEntry[] {
  const entries: ConsoleEntry[] = [];
  page.on('console', message => {
    if (message.type() === 'error' || message.type() === 'warning') {
      entries.push({url: page.url(), type: message.type(), text: message.text()});
    }
  });
  page.on('pageerror', error => {
    entries.push({url: page.url(), type: 'pageerror', text: `${error.name}: ${error.message}\n${error.stack ?? ''}`});
  });
  return entries;
}

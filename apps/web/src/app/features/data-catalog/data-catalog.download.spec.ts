import {TestBed} from '@angular/core/testing';
import {CatalogDownloadService} from '~/features/data-catalog/data-catalog.download';

/**
 * ブラウザ側の境界を確かめる。
 *
 * 判断は持たない層だが、**取り消しを忘れると書き出すたびに Blob が残る**。
 * 残っていることは画面にも型にも出ない。ここだけがそれを見る。
 */

describe('catalog download', () => {
  const created: Blob[] = [];
  const revoked: string[] = [];
  const originalCreate = URL.createObjectURL;
  const originalRevoke = URL.revokeObjectURL;

  beforeEach(() => {
    created.length = 0;
    revoked.length = 0;
    URL.createObjectURL = (blob: Blob) => {
      created.push(blob);
      return 'blob:catalog';
    };
    URL.revokeObjectURL = (url: string) => void revoked.push(url);
  });

  afterEach(() => {
    URL.createObjectURL = originalCreate;
    URL.revokeObjectURL = originalRevoke;
  });

  const save = (): HTMLAnchorElement[] => {
    const clicked: HTMLAnchorElement[] = [];
    const create = document.createElement.bind(document);
    const spy = (tag: string) => {
      const element = create(tag);
      if (element instanceof HTMLAnchorElement) {
        element.click = () => void clicked.push(element);
      }
      return element;
    };
    document.createElement = spy as typeof document.createElement;

    try {
      TestBed.resetTestingModule();
      TestBed.configureTestingModule({providers: [CatalogDownloadService]});
      TestBed.inject(CatalogDownloadService).save('catalog.json', 'application/json', '{}\n');
    } finally {
      document.createElement = create;
    }

    return clicked;
  };

  it('hands over one file under the name it was given', async () => {
    const [link] = save();

    expect(link.download).toBe('catalog.json');
    expect(created).toHaveLength(1);
    expect(created[0].type).toBe('application/json');
    expect(await created[0].text()).toBe('{}\n');
  });

  it('gives the object URL back, so exporting twice does not leak twice', () => {
    save();

    expect(revoked).toEqual(['blob:catalog']);
  });
});

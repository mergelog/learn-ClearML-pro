import {DOCUMENT} from '@angular/common';
import {inject, Injectable} from '@angular/core';

/**
 * 組み立てた文書を、利用者の手元へ渡す。
 *
 * 台帳の外向きの境界は2つある。1つはClearMLで、それは
 * `data-access/data-catalog-api.service.ts` が持つ。もう1つが**ブラウザ**で、
 * それがここである。どちらも「外の世界に触るのはこの1ファイルだけ」という
 * 同じ理由で分けてある。
 *
 * 分けているのは差し替えるためでもある。`Blob` と `URL.createObjectURL` を
 * container の中に書くと、書き出しの判断（何を出すか）を確かめるのに
 * ダウンロードを起こす必要が出る。ここを差し替えれば、container は
 * 「何を、どの名前で渡したか」だけで確かめられる。
 *
 * state は持たない。ここに来る時点で文書は決まっていて、渡した後に
 * 画面が変わることも無い。だから Effects でも action でもない（ADR 010）。
 */
@Injectable()
export class CatalogDownloadService {
  private readonly document = inject(DOCUMENT);

  /**
   * 文字列を1つのファイルとして渡す。
   *
   * `revokeObjectURL` を必ず呼ぶ。呼ばないと、書き出すたびに Blob が
   * ページを離れるまで残る。`click()` は同期に始まるので、この時点で
   * 取り消してよい。
   */
  save(filename: string, mediaType: string, text: string): void {
    const url = URL.createObjectURL(new Blob([text], {type: mediaType}));
    const link = this.document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }
}

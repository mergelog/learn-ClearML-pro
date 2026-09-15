import {ChangeDetectionStrategy, Component, computed, input} from '@angular/core';
import {DatePipe} from '@angular/common';
import {RouterLink} from '@angular/router';
import {CatalogAssetDetail} from '@features/data-catalog/data-catalog.model';
import {KIND_LABELS, vendorLinkOf} from '@features/data-catalog/data-catalog.consts';

/**
 * 1つの資産の中身。
 *
 * 台帳が出すのは**横断して引くために要る分だけ**である。深い情報（成果物、
 * ログ、指標の推移）は持っている既存のClearML画面へ渡す（プランの §1.2）。
 * 渡し先が作れない資産ではリンクを出さない。押しても404になるリンクは、
 * リンクが無いことより悪い。
 *
 * 説明が空のときに欄ごと消さない。「説明が無い」ことは台帳にとって事実であり、
 * 欄が消えると「この種別には説明という概念が無い」ように読める。
 */
@Component({
  selector: 'sm-catalog-asset-facts',
  templateUrl: './catalog-asset-facts.component.html',
  styleUrls: ['./catalog-asset-facts.component.scss'],
  imports: [DatePipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CatalogAssetFactsComponent {
  protected readonly timeFormat = 'yyyy-MM-dd HH:mm z';
  protected readonly timeZone = 'UTC';
  protected readonly kindLabels = KIND_LABELS;

  readonly detail = input<CatalogAssetDetail | null>(null);

  /** 既存のClearML画面への行き先。作れないときは `null`。 */
  protected readonly vendorLink = computed(() => {
    const detail = this.detail();
    return detail === null ? null : vendorLinkOf(detail.asset);
  });
}

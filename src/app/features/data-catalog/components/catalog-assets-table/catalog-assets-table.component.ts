import {ChangeDetectionStrategy, Component, input} from '@angular/core';
import {DatePipe} from '@angular/common';
import {RouterLink} from '@angular/router';
import {CatalogAsset} from '@features/data-catalog/data-catalog.model';
import {
  CATALOG_PAGE_SIZE,
  CATALOG_ROUTE,
  KIND_LABELS,
} from '@features/data-catalog/data-catalog.consts';

/**
 * 台帳の一覧。Dataset / Model / Run を1つの表に並べる。
 *
 * この表が持っている判断は3つある。どれも壊れても型では気付けない。
 *
 * **空である理由を言い分ける。** 「まだ何も無い」と「条件に合うものが無い」を
 * 同じ文で済ませると、絞り込みを外せば見えるものを、存在しないものとして
 * 読ませることになる。理由そのものは selector が決める。ここは受け取った
 * 理由に対応する文を出すだけである。
 *
 * **打ち切りを黙らない。** 上限で切ったことを言わないと、絞り込みの結果が
 * 「これで全部」に見える。
 *
 * **時刻はUTCのまま出し、基準も書く。** ローカル時刻へ寄せると、ClearML側の
 * 画面と突き合わせたときに読み違える。
 */
@Component({
  selector: 'sm-catalog-assets-table',
  templateUrl: './catalog-assets-table.component.html',
  styleUrls: ['./catalog-assets-table.component.scss'],
  imports: [DatePipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CatalogAssetsTableComponent {
  protected readonly timeFormat = 'yyyy-MM-dd HH:mm z';
  protected readonly timeZone = 'UTC';

  /** 1度に読む件数。注記に出すため、表そのものが知っている必要がある。 */
  protected readonly pageLimit = CATALOG_PAGE_SIZE;

  protected readonly kindLabels = KIND_LABELS;
  protected readonly catalogRoute = CATALOG_ROUTE;

  readonly assets = input<readonly CatalogAsset[]>([]);

  /** 上限で打ち切られたか。 */
  readonly hasMore = input(false);

  /** 読み込み中。空である理由をまだ言えない状態と区別するために要る。 */
  readonly loading = input(false);

  /**
   * 空である理由。`null` は「空ではない、またはまだ言えない」。
   *
   * 真偽値2つ（絞っているか・空か）を渡して表の中で組み合わせない。
   * 組み合わせの判断が表と selector の2箇所に分かれると、片方だけが直る。
   */
  readonly emptyReason = input<'nothing-yet' | 'no-match' | null>(null);
}

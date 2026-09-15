import {ChangeDetectionStrategy, Component, input} from '@angular/core';
import {RouterLink} from '@angular/router';
import {CatalogLineageNode} from '@features/data-catalog/data-catalog.model';
import {CATALOG_ROUTE, KIND_LABELS} from '@features/data-catalog/data-catalog.consts';

/**
 * `Dataset → Run → Model` の鎖。
 *
 * **この表示がこの feature の存在理由である。** ClearML の画面は Dataset は
 * Dataset、Model は Model と縦に割れていて、「このモデルはどのデータから
 * 来たのか」を一画面で答える場所が無い（プランの §1）。
 *
 * 判断は2つある。
 *
 * **並びは常に `Dataset → Run → Model` である。** どの資産から開いても
 * 変えない。台帳が答えたいのはデータからモデルへ流れる向きで、起点を先頭へ
 * 置き換えると、同じ鎖が開いた場所によって逆向きに見える。
 *
 * **切れていることを黙らない。** 辿れなかった節を消して繋げると、出所が
 * 分からない資産が、出所を辿る必要が無い資産のように見える。節が消えている
 * ことと、節はあるが実体が消えていることも、別の文で言う。
 */
@Component({
  selector: 'sm-catalog-lineage',
  templateUrl: './catalog-lineage.component.html',
  styleUrls: ['./catalog-lineage.component.scss'],
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CatalogLineageComponent {
  protected readonly kindLabels = KIND_LABELS;
  protected readonly catalogRoute = CATALOG_ROUTE;

  /** `Dataset → Run → Model` の順に並んだ節。 */
  readonly nodes = input<readonly CatalogLineageNode[]>([]);

  /** 鎖が3つ揃っていないか。 */
  readonly partial = input(false);

  /** 読み込み中。まだ辿っていないことと、辿れなかったことを分ける。 */
  readonly loading = input(false);
}

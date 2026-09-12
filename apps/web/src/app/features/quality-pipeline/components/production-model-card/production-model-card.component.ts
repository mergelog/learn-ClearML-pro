import {ChangeDetectionStrategy, Component, input} from '@angular/core';
import {ProductionModel} from '~/features/quality-pipeline/quality-pipeline.model';

/**
 * いま提供されているモデル。
 *
 * 「まだ無い」を空白ではなく文で出す。空欄のままだと、読み込みに失敗したのか
 * 一度も採用されていないのかが利用者から区別できない。
 */
@Component({
  selector: 'sm-production-model-card',
  templateUrl: './production-model-card.component.html',
  styleUrls: ['./production-model-card.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProductionModelCardComponent {
  readonly model = input<ProductionModel | null>(null);
}

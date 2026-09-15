import {ChangeDetectionStrategy, Component, input} from '@angular/core';
import {DecimalPipe} from '@angular/common';
import {EvaluationScore} from '@features/quality-pipeline/quality-pipeline.model';

/**
 * splitごとの評価指標を出す。
 *
 * validation と test を並べて出すのは、どちらで選んでどちらで確かめたかを
 * 読む人が自分で見比べられるようにするためである。片方だけ出すと、
 * 選んだ根拠と確かめた結果の区別が画面から消える。
 */
@Component({
  selector: 'sm-evaluation-scores-table',
  templateUrl: './evaluation-scores-table.component.html',
  styleUrls: ['./evaluation-scores-table.component.scss'],
  imports: [DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EvaluationScoresTableComponent {
  /**
   * 指標の桁。
   *
   * 生値は `0.8123456789012345` のような形で返ってくる。そのまま並べると
   * 桁数が行ごとに変わり、validation と test を目で見比べられない。
   * 小数第3位に揃える。採用の判断でそれより下の桁が効くことはない。
   */
  protected readonly scoreFormat = '1.3-3';

  readonly scores = input<readonly EvaluationScore[]>([]);
}

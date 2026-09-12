import {ChangeDetectionStrategy, Component, input} from '@angular/core';
import {DatePipe} from '@angular/common';
import {PipelineStep} from '~/features/quality-pipeline/quality-pipeline.model';
import {MAXIMUM_STEPS} from '~/features/quality-pipeline/quality-pipeline.consts';

/** 1回の実行に属するステップを、実行順のまま出す。 */
@Component({
  selector: 'sm-pipeline-steps-table',
  templateUrl: './pipeline-steps-table.component.html',
  styleUrls: ['./pipeline-steps-table.component.scss'],
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PipelineStepsTableComponent {
  /**
   * 時刻の書式と、それを読む基準。
   *
   * ClearMLが返すのはUTCである。ローカル時刻に寄せて描くと、ステップの
   * 開始と終了をClearML側の画面やログと突き合わせたときに読み違える。
   * UTCのまま出し、基準そのものも画面に書く。
   */
  protected readonly timeFormat = 'HH:mm z';
  protected readonly timeZone = 'UTC';

  /** 1度に読める上限。注記に出すため、表そのものが知っている必要がある。 */
  protected readonly stepLimit = MAXIMUM_STEPS;

  readonly steps = input<readonly PipelineStep[]>([]);

  /**
   * 上限で打ち切られたかどうか。
   *
   * 打ち切りを黙っていると、表から消えたステップが「走らなかったステップ」と
   * 区別できなくなる。件数が合わないことは、表の中で言う。
   */
  readonly truncated = input(false);
}

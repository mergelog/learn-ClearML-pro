import {ChangeDetectionStrategy, Component, input, output} from '@angular/core';
import {DatePipe} from '@angular/common';
import {PipelineRun} from '~/features/quality-pipeline/quality-pipeline.model';

/**
 * 1回の実行の状態を読める形で出し、読み直しと停止の押下を返す。
 *
 * 実行があることは親が確かめてから使う。ここで「実行が無いとき」まで
 * 引き受けると、無い状態の見せ方が親と二重に決まる。
 */
@Component({
  selector: 'sm-run-summary',
  templateUrl: './run-summary.component.html',
  styleUrls: ['./run-summary.component.scss'],
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RunSummaryComponent {
  /**
   * 時刻の書式と、それを読む基準。
   *
   * ClearMLが返すのはUTCである。ブラウザのローカル時刻に寄せて描くと、
   * 別拠点のログやClearMLの画面と突き合わせたときに、同じ実行が違う時刻に
   * 見える。UTCのまま出し、基準そのものも画面に書く。
   */
  protected readonly timestampFormat = 'y-MM-dd HH:mm:ss z';
  protected readonly timeZone = 'UTC';

  readonly run = input.required<PipelineRun>();
  readonly canCancel = input(false);
  readonly cancelling = input(false);

  readonly refresh = output<void>();
  readonly cancelRun = output<void>();
}

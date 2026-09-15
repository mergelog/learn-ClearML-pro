import {ChangeDetectionStrategy, Component, computed, inject, input, output} from '@angular/core';
import {FormBuilder, ReactiveFormsModule, Validators} from '@angular/forms';
import {toSignal} from '@angular/core/rxjs-interop';
import {
  DATASET_VERSION_FORMAT_HINT,
  DATASET_VERSION_PATTERN,
} from '@features/quality-pipeline/quality-pipeline.consts';
import {PipelineTemplate} from '@features/quality-pipeline/quality-pipeline.model';

/**
 * 起動する版数を受け取り、押されたことを伝えるだけのcomponent。
 *
 * storeには触れない。何が起動できる状態かは親から受け取り、押されたことは
 * そのまま親へ返す。ここが持っているのは「まだ送られていない入力値」だけで、
 * それは共有stateへ置くべき事実ではない。
 *
 * 入力の妥当性はReactive Formsで持つ。押せるのに何も起きないボタンを
 * 作らないためで、受け付けられる書式は `aria-describedby` で入力欄に
 * 結び付けて常に出しておく。押してから初めて知らせるのでは遅い。
 */
@Component({
  selector: 'sm-start-run-form',
  templateUrl: './start-run-form.component.html',
  styleUrls: ['./start-run-form.component.scss'],
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StartRunFormComponent {
  private readonly formBuilder = inject(FormBuilder);

  /** 複製元。無ければ何も起動できない。 */
  readonly template = input<PipelineTemplate | null>(null);
  /** 複製元と直近の実行が同じTaskを指しているか。 */
  readonly runIsTemplate = input(false);
  readonly loading = input(false);
  readonly starting = input(false);
  /** state から見て起動を受け付けられるか。入力の妥当性はここで足す。 */
  readonly canStart = input(false);

  readonly start = output<string>();
  readonly reload = output<void>();

  protected readonly form = this.formBuilder.nonNullable.group({
    datasetVersion: ['1.0.0', [Validators.required, Validators.pattern(DATASET_VERSION_PATTERN)]],
  });

  protected readonly formatHint = DATASET_VERSION_FORMAT_HINT;

  private readonly status = toSignal(this.form.statusChanges, {initialValue: this.form.status});

  /** 押せるのは、stateが受け付けられて、かつ入力が版数として読めるときだけ。 */
  protected readonly canSubmit = computed(() => this.canStart() && this.status() === 'VALID');

  protected submit(): void {
    // Enterキーからも来るため、押せない状態をここでもう一度確かめる。
    if (!this.canSubmit()) {
      return;
    }
    this.start.emit(this.form.getRawValue().datasetVersion);
  }
}

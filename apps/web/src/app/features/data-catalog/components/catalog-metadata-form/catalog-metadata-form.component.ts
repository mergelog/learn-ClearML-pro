import {ChangeDetectionStrategy, Component, effect, inject, input, output} from '@angular/core';
import {FormBuilder, ReactiveFormsModule} from '@angular/forms';
import {CatalogAssetDetail, CatalogMetadataEdit} from '~/features/data-catalog/data-catalog.model';
import {QUERY_VALUE_SEPARATOR} from '~/features/data-catalog/data-catalog.consts';

/**
 * tags と description を直す欄。台帳が書き込むのはこの2つだけである。
 *
 * storeには触れない。いまの値は親から受け取り、保存したいという意思だけを返す。
 *
 * **保存されるまで、表示は変えない。** 押した直後に画面だけ新しい値へ
 * 変わると、ClearMLが受け付けなかったときに台帳が嘘をついたことになる。
 * ここが持つのは入力中の値で、それが事実になるのはサーバが受け付けてからである
 * （ADR 008）。
 *
 * **外から新しい値が来たら入力欄を書き戻す。** 保存の後、同じ資産を読み直した
 * 結果がここへ届く。誰かが別の画面から直していた場合、手元の入力が古い値の
 * ままだと、次に保存したときにその古い値で上書きしてしまう。
 */
@Component({
  selector: 'sm-catalog-metadata-form',
  templateUrl: './catalog-metadata-form.component.html',
  styleUrls: ['./catalog-metadata-form.component.scss'],
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CatalogMetadataFormComponent {
  private readonly formBuilder = inject(FormBuilder);

  readonly detail = input<CatalogAssetDetail | null>(null);
  /** state から見て保存を受け付けられるか。 */
  readonly canSave = input(false);
  readonly saving = input(false);

  readonly save = output<CatalogMetadataEdit>();

  protected readonly tagSeparator = QUERY_VALUE_SEPARATOR;

  protected readonly form = this.formBuilder.nonNullable.group({
    tags: [''],
    description: [''],
  });

  constructor() {
    effect(() => {
      const detail = this.detail();
      this.form.setValue(
        {
          tags: (detail?.asset.tags ?? []).join(QUERY_VALUE_SEPARATOR),
          description: detail?.description ?? '',
        },
        {emitEvent: false}
      );
    });
  }

  protected submit(): void {
    // Enterキーからも来るため、押せない状態をここでもう一度確かめる。
    if (!this.canSave()) {
      return;
    }

    const value = this.form.getRawValue();
    this.save.emit({
      tags: value.tags
        .split(QUERY_VALUE_SEPARATOR)
        .map((tag) => tag.trim())
        .filter((tag) => tag !== ''),
      description: value.description,
    });
  }
}

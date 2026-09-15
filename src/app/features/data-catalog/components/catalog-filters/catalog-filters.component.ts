import {ChangeDetectionStrategy, Component, effect, inject, input, output} from '@angular/core';
import {FormBuilder, ReactiveFormsModule} from '@angular/forms';
import {
  CATALOG_ASSET_KINDS,
  CatalogAssetKind,
  CatalogFilter,
  emptyCatalogFilter,
} from '@features/data-catalog/data-catalog.model';
import {
  KIND_LABELS,
  QUERY_VALUE_SEPARATOR,
} from '@features/data-catalog/data-catalog.consts';

/**
 * 絞り込みの入力欄。
 *
 * storeには触れない。いま効いている条件は親から受け取り、変えたことは
 * そのまま親へ返す。ここが持っているのは「まだ適用していない入力値」だけである。
 *
 * **押したときにだけ親へ返す。** 1文字ごとに返すと、その都度URLが書き換わり、
 * サーバへの問い合わせも同じ回数だけ飛ぶ。台帳の検索はサーバ側で絞る前提なので
 * （プランの §4.2）、打っている途中の語で毎回問い合わせても、答えが返るころには
 * 条件が変わっている。
 *
 * **外から来た条件は入力欄へ書き戻す。** 条件つきURLを渡されて開いた場合、
 * 入力欄が空のままだと「絞られているのに、何で絞られているか分からない」画面に
 * なる。書き戻すときは `emitEvent: false` で、書き戻し自体が変更として
 * 跳ね返らないようにする。
 */
@Component({
  selector: 'sm-catalog-filters',
  templateUrl: './catalog-filters.component.html',
  styleUrls: ['./catalog-filters.component.scss'],
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CatalogFiltersComponent {
  private readonly formBuilder = inject(FormBuilder);

  /** いま効いている条件。URLのクエリと同じものを指す。 */
  readonly filter = input<CatalogFilter>(emptyCatalogFilter);
  /** 選択肢。読めなかったときは空で、そのときは自由入力だけが残る。 */
  readonly projects = input<readonly string[]>([]);
  readonly availableTags = input<readonly string[]>([]);
  readonly loading = input(false);

  readonly filterChange = output<CatalogFilter>();

  protected readonly kinds = CATALOG_ASSET_KINDS;
  protected readonly kindLabels = KIND_LABELS;
  protected readonly tagSeparator = QUERY_VALUE_SEPARATOR;

  protected readonly form = this.formBuilder.nonNullable.group({
    text: [''],
    project: [''],
    tags: [''],
    updatedFrom: [''],
    updatedTo: [''],
    dataset: [false],
    model: [false],
    run: [false],
  });

  constructor() {
    effect(() => {
      const filter = this.filter();
      this.form.setValue(
        {
          text: filter.text,
          project: filter.project,
          tags: filter.tags.join(QUERY_VALUE_SEPARATOR),
          updatedFrom: filter.updatedFrom,
          updatedTo: filter.updatedTo,
          dataset: filter.kinds.includes('dataset'),
          model: filter.kinds.includes('model'),
          run: filter.kinds.includes('run'),
        },
        {emitEvent: false}
      );
    });
  }

  protected apply(): void {
    this.filterChange.emit(this.readForm());
  }

  /**
   * すべての条件を外す。
   *
   * 入力欄を空にするだけでは済まない。空にしたことを親へ返さないと、
   * URLと画面に古い条件が残り続ける。
   */
  protected clear(): void {
    this.filterChange.emit(emptyCatalogFilter);
  }

  private readForm(): CatalogFilter {
    const value = this.form.getRawValue();
    const kinds: CatalogAssetKind[] = [
      ...(value.dataset ? (['dataset'] as const) : []),
      ...(value.model ? (['model'] as const) : []),
      ...(value.run ? (['run'] as const) : []),
    ];

    return {
      text: value.text.trim(),
      kinds,
      project: value.project.trim(),
      tags: splitTags(value.tags),
      updatedFrom: value.updatedFrom,
      updatedTo: value.updatedTo,
    };
  }
}

/**
 * 入力されたタグを並びに直す。
 *
 * 空の要素を残さない。`a,,b` から生まれる空文字のタグは、ClearMLへ送ると
 * 「空という名前のタグが付いているもの」を求めたことになり、結果が黙って
 * 0件になる。
 */
const splitTags = (value: string): string[] =>
  value
    .split(QUERY_VALUE_SEPARATOR)
    .map((tag) => tag.trim())
    .filter((tag) => tag !== '');

import {ComponentFixture, TestBed} from '@angular/core/testing';
import {CatalogAssetDetail, CatalogMetadataEdit} from '~/features/data-catalog/data-catalog.model';
import {CatalogMetadataFormComponent} from './catalog-metadata-form.component';

/**
 * 書き込む欄の振る舞いを確かめる。
 *
 * **台帳が嘘をつかないことがここの仕様である。** 押した直後に表示だけ変わると、
 * ClearMLが受け付けなかったときに、画面は存在しない値を事実として見せる
 * （ADR 008）。
 */

const detail = (overrides: Partial<CatalogAssetDetail> = {}): CatalogAssetDetail => ({
  asset: {
    kind: 'model',
    id: 'model-id',
    name: 'model',
    project: {id: 'project-id', name: 'Pipeline'},
    updatedAt: null,
    tags: ['stage:production'],
    state: 'completed',
  },
  description: 'the trial went well',
  facts: [],
  ...overrides,
});

const setUp = async (
  inputs: {detail?: CatalogAssetDetail | null; canSave?: boolean; saving?: boolean} = {}
): Promise<{
  fixture: ComponentFixture<CatalogMetadataFormComponent>;
  emitted: CatalogMetadataEdit[];
  element: HTMLElement;
}> => {
  TestBed.resetTestingModule();
  await TestBed.configureTestingModule({
    imports: [CatalogMetadataFormComponent],
  }).compileComponents();

  const fixture = TestBed.createComponent(CatalogMetadataFormComponent);
  const emitted: CatalogMetadataEdit[] = [];
  fixture.componentRef.setInput('detail', inputs.detail ?? detail());
  fixture.componentRef.setInput('canSave', inputs.canSave ?? true);
  fixture.componentRef.setInput('saving', inputs.saving ?? false);
  fixture.componentInstance.save.subscribe((value) => emitted.push(value));
  fixture.detectChanges();

  return {fixture, emitted, element: fixture.nativeElement as HTMLElement};
};

const setValue = (element: HTMLElement, id: string, value: string): void => {
  const field = element.querySelector(`#${id}`) as HTMLInputElement | HTMLTextAreaElement;
  field.value = value;
  field.dispatchEvent(new Event('input'));
};

describe('catalog metadata form', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('starts from the values the asset already has', async () => {
    const {element} = await setUp();

    expect((element.querySelector('#catalog-edit-tags') as HTMLInputElement).value).toBe(
      'stage:production'
    );
    expect((element.querySelector('#catalog-edit-description') as HTMLTextAreaElement).value).toBe(
      'the trial went well'
    );
  });

  it('writes a newer value back over what is being typed', async () => {
    // 古い値のまま保存すると、他の画面からの変更を上書きしてしまう。
    const {fixture, element} = await setUp();
    setValue(element, 'catalog-edit-tags', 'mine');

    fixture.componentRef.setInput('detail', detail({asset: {...detail().asset, tags: ['theirs']}}));
    fixture.detectChanges();

    expect((element.querySelector('#catalog-edit-tags') as HTMLInputElement).value).toBe('theirs');
  });

  it('reports the edit only when it is submitted', async () => {
    const {element, emitted} = await setUp();
    setValue(element, 'catalog-edit-tags', 'seed, checked');
    setValue(element, 'catalog-edit-description', 'looked at it');

    expect(emitted).toEqual([]);

    (element.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));

    expect(emitted).toEqual([{tags: ['seed', 'checked'], description: 'looked at it'}]);
  });

  it('refuses to submit while a save is already in flight', async () => {
    const {element, emitted} = await setUp({canSave: false, saving: true});

    (element.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));

    expect(emitted).toEqual([]);
    expect((element.querySelector('[data-id="catalogSave"]') as HTMLButtonElement).disabled).toBe(
      true
    );
  });

  it('says the asset can also be edited elsewhere', async () => {
    // 二重編集は防げない。防げないことを黙るのではなく、書いておく。
    const {element} = await setUp();

    expect(element.textContent ?? '').toContain('can also be edited from its');
  });
});

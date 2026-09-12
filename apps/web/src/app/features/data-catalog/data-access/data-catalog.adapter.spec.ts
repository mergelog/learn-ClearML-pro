import {
  ApiModel,
  ApiTask,
  toDatasetAsset,
  toDatasetDetail,
  toModelAsset,
  toModelDetail,
  toModelState,
  toRunAsset,
  toRunDetail,
  toTaskState,
} from '~/features/data-catalog/data-access/data-catalog.adapter';

/**
 * 3つの実体を1つの語彙へ揃える変換を確かめる。
 *
 * ここが壊れても型では気付けない。ClearMLの応答は「あるはずのフィールドが
 * 無い」「型が違う」「知らない値が入っている」ことが普通にあり、その扱いを
 * 間違えると、台帳は黙って違うものを並べる。
 */

const task = (overrides: Partial<ApiTask> = {}): ApiTask => ({
  id: 'task-id',
  name: 'semiconductor-quality-training',
  status: 'completed',
  project: {id: 'project-id', name: 'Semiconductor Quality Prediction'},
  last_update: '2026-09-12T00:00:00Z',
  tags: ['seed'],
  ...overrides,
});

const model = (overrides: Partial<ApiModel> = {}): ApiModel => ({
  id: 'model-id',
  name: 'semiconductor-quality-classifier',
  project: {id: 'project-id', name: 'Semiconductor Quality Prediction'},
  last_update: '2026-09-12T00:00:00Z',
  tags: ['stage:production'],
  ready: true,
  ...overrides,
});

describe('data catalog adapter', () => {
  describe('putting the three entities in one vocabulary', () => {
    it('reads a dataset task as a dataset', () => {
      expect(toDatasetAsset(task()).kind).toBe('dataset');
    });

    it('reads the same task shape as a run when it is asked to', () => {
      // 種別を決めるのは問い合わせた側である。Task自身は自分がDatasetか
      // Runかを言わない。
      expect(toRunAsset(task()).kind).toBe('run');
    });

    it('keeps the project name and id, because one shows and one links', () => {
      expect(toModelAsset(model()).project).toEqual({
        id: 'project-id',
        name: 'Semiconductor Quality Prediction',
      });
    });

    it('leaves the project name empty when ClearML only sent an id', () => {
      // IDを名前の位置に出すと、利用者はそれをプロジェクト名だと思って検索する。
      expect(toRunAsset(task({project: 'project-id'})).project).toEqual({
        id: 'project-id',
        name: '',
      });
    });
  });

  describe('saying what state an asset is in', () => {
    it('calls a status it does not know unknown rather than dropping it', () => {
      // 落とすと「使ってよいのか分からない」ことすら分からなくなる。
      expect(toTaskState('annotating')).toBe('unknown');
    });

    it('separates a draft from a run that finished', () => {
      expect(toTaskState('created')).toBe('draft');
      expect(toTaskState('completed')).toBe('completed');
    });

    it('treats a model that is not ready as a draft', () => {
      // 未確定のものを completed として並べると、まだ書き換わりうるモデルを
      // 使ってよいものとして見せることになる。
      expect(toModelState(model({ready: false}))).toBe('draft');
    });
  });

  describe('saying when an asset last changed', () => {
    it('falls back to the creation time when there is no update time', () => {
      expect(toRunAsset(task({last_update: undefined, created: '2026-09-01T00:00:00Z'})).updatedAt)
        .toBe('2026-09-01T00:00:00Z');
    });

    it('leaves the time null rather than inventing one', () => {
      // 既定の日付で埋めると「更新されていない」と「いつか分からない」が
      // 区別できなくなる。
      expect(toRunAsset(task({last_update: undefined, created: undefined})).updatedAt).toBeNull();
    });

    it('turns a Date into a string so the same time stays the same value', () => {
      const asset = toRunAsset(task({last_update: new Date('2026-09-12T00:00:00Z')}));

      expect(asset.updatedAt).toBe('2026-09-12T00:00:00.000Z');
    });
  });

  describe('showing what is specific to one kind', () => {
    it('shows the dataset version from where ClearML keeps it', () => {
      const detail = toDatasetDetail(task({runtime: {version: '2.0.0'}}));

      expect(detail.facts).toContainEqual({label: 'Version', value: '2.0.0'});
    });

    it('shows which dataset version a run used', () => {
      const detail = toRunDetail(
        task({hyperparams: {Dataset: {dataset_version: {value: '1.0.0'}}}})
      );

      expect(detail.facts).toContainEqual({label: 'Dataset version', value: '1.0.0'});
    });

    it('leaves out a fact it has no value for, rather than showing a blank row', () => {
      // 空欄を並べると、「その資産には無い情報」と「読めなかった情報」が
      // 同じ見た目になる。
      const detail = toModelDetail(model({metadata: {}}));

      expect(detail.facts.map((fact) => fact.label)).not.toContain('Model version');
    });

    it('keeps the description out of the list vocabulary', () => {
      const detail = toModelDetail(model({comment: 'the trial went well'}));

      expect(detail.description).toBe('the trial went well');
      expect(Object.keys(detail.asset)).not.toContain('description');
    });
  });
});

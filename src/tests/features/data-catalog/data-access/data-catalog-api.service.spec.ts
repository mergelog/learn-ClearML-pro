import {TestBed} from '@angular/core/testing';
import {Observable, firstValueFrom, of} from 'rxjs';
import {ApiTasksService} from '~/business-logic/api-services/tasks.service';
import {ApiModelsService} from '~/business-logic/api-services/models.service';
import {ApiProjectsService} from '~/business-logic/api-services/projects.service';
import {DataCatalogApiService} from '@features/data-catalog/data-access/data-catalog-api.service';
import {
  CatalogFilter,
  emptyCatalogFilter,
  CatalogAsset,
} from '@features/data-catalog/data-catalog.model';
import {
  CATALOG_PAGE_SIZE,
  PER_KIND_PAGE_SIZE,
} from '@features/data-catalog/data-catalog.consts';

/**
 * API境界が「ClearMLへ何を送るか」を確かめる。
 *
 * `HttpTestingController` は使わない。確かめたいのはHTTPの組み立て方ではなく、
 * 生成済みサービスへ渡す要求の中身だからである。
 *
 * **この層の仕事の半分は「絞り込みをサーバへ渡していること」**である
 * （プランの §4.2）。手元で絞ってしまうと、件数が増えたときに「途中までしか
 * 無い」という形で壊れる。それは応答の形からは見えないので、送った要求を見る。
 */

type RequestBody = Record<string, unknown>;

class StubTasks {
  readonly requests: {method: string; body: RequestBody}[] = [];

  getAllExResponse: Observable<unknown> = of({tasks: []});
  getByIdExResponse: Observable<unknown> = of({tasks: []});
  updateResponse: Observable<unknown> = of({updated: 1});

  tasksGetAllEx = (body: RequestBody) => this.record('tasks.get_all_ex', body, this.getAllExResponse);
  tasksGetByIdEx = (body: RequestBody) =>
    this.record('tasks.get_by_id_ex', body, this.getByIdExResponse);
  tasksUpdate = (body: RequestBody) => this.record('tasks.update', body, this.updateResponse);

  bodiesOf(method: string): RequestBody[] {
    return this.requests.filter((sent) => sent.method === method).map((sent) => sent.body);
  }

  private record(method: string, body: RequestBody, response: Observable<unknown>) {
    this.requests.push({method, body});
    return response;
  }
}

class StubModels {
  readonly requests: RequestBody[] = [];
  getAllExResponse: Observable<unknown> = of({models: []});
  updateResponse: Observable<unknown> = of({updated: 1});

  modelsGetAllEx = (body: RequestBody) => {
    this.requests.push(body);
    return this.getAllExResponse;
  };

  modelsUpdate = (body: RequestBody) => {
    this.requests.push(body);
    return this.updateResponse;
  };
}

class StubProjects {
  readonly requests: RequestBody[] = [];
  getAllExResponse: Observable<unknown> = of({projects: [{id: 'project-id', name: 'Pipeline'}]});

  projectsGetAllEx = (body: RequestBody) => {
    this.requests.push(body);
    return this.getAllExResponse;
  };

  projectsGetTaskTags = () => of({tags: ['seed']});
  projectsGetModelTags = () => of({tags: ['stage:production', 'seed']});
}

const setUp = (): {
  api: DataCatalogApiService;
  tasks: StubTasks;
  models: StubModels;
  projects: StubProjects;
} => {
  const tasks = new StubTasks();
  const models = new StubModels();
  const projects = new StubProjects();

  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      DataCatalogApiService,
      {provide: ApiTasksService, useValue: tasks},
      {provide: ApiModelsService, useValue: models},
      {provide: ApiProjectsService, useValue: projects},
    ],
  });

  return {api: TestBed.inject(DataCatalogApiService), tasks, models, projects};
};

const filter = (overrides: Partial<CatalogFilter> = {}): CatalogFilter => ({
  ...emptyCatalogFilter,
  ...overrides,
});

const apiTask = (id: string, lastUpdate: string) => ({
  id,
  name: id,
  status: 'completed',
  project: {id: 'project-id', name: 'Pipeline'},
  last_update: lastUpdate,
  tags: [],
});

const apiModel = (id: string, lastUpdate: string) => ({
  id,
  name: id,
  ready: true,
  project: {id: 'project-id', name: 'Pipeline'},
  last_update: lastUpdate,
  tags: [],
});

describe('data catalog api', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('asking ClearML to do the filtering', () => {
    it('sends the name, the tags and the date range instead of filtering here', async () => {
      const {api, tasks} = setUp();

      await firstValueFrom(
        api.search(
          filter({
            text: 'wafer',
            kinds: ['run'],
            tags: ['seed'],
            updatedFrom: '2026-01-01',
            updatedTo: '2026-09-12',
          })
        )
      );

      const [body] = tasks.bodiesOf('tasks.get_all_ex');
      expect(body['name']).toBe('wafer');
      expect(body['tags']).toEqual(['seed']);
      expect(body['last_update']).toEqual(['>=2026-01-01', '<=2026-09-12']);
    });

    it('sends only one side of the range when only one end is set', () => {
      const {api, tasks} = setUp();

      void firstValueFrom(api.search(filter({kinds: ['run'], updatedFrom: '2026-01-01'})));

      expect(tasks.bodiesOf('tasks.get_all_ex')[0]['last_update']).toEqual(['>=2026-01-01']);
    });

    it('asks only the kinds that were selected', async () => {
      const {api, tasks, models} = setUp();

      await firstValueFrom(api.search(filter({kinds: ['model']})));

      expect(tasks.bodiesOf('tasks.get_all_ex')).toHaveLength(0);
      expect(models.requests).toHaveLength(1);
    });

    it('asks all three kinds when none is selected', async () => {
      const {api, tasks, models} = setUp();

      await firstValueFrom(api.search(filter()));

      expect(tasks.bodiesOf('tasks.get_all_ex')).toHaveLength(2);
      expect(models.requests).toHaveLength(1);
    });

    it('turns a project name into ids, because ClearML does not take names', async () => {
      const {api, tasks, projects} = setUp();

      await firstValueFrom(api.search(filter({kinds: ['run'], project: 'Pipeline'})));

      expect(projects.requests[0]['name']).toBe('^Pipeline$');
      expect(tasks.bodiesOf('tasks.get_all_ex')[0]['project']).toEqual(['project-id']);
    });

    it('returns nothing when the named project does not exist', async () => {
      const {api, tasks, projects} = setUp();
      projects.getAllExResponse = of({projects: []});

      const page = await firstValueFrom(api.search(filter({project: 'missing'})));

      // 空の `project` を送ると「絞らない」と解釈され、全件が返ってくる。
      expect(tasks.bodiesOf('tasks.get_all_ex')).toHaveLength(0);
      expect(page.assets).toEqual([]);
    });

    it('keeps datasets and runs apart so the same task is not listed twice', async () => {
      const {api, tasks} = setUp();

      await firstValueFrom(api.search(filter()));

      const [datasetBody, runBody] = tasks.bodiesOf('tasks.get_all_ex');
      expect(datasetBody['system_tags']).toEqual(['dataset']);
      expect(runBody['system_tags']).toEqual(['-dataset']);
    });
  });

  describe('putting the three kinds in one list', () => {
    it('orders everything by when it last changed, not by kind', async () => {
      const {api, tasks, models} = setUp();
      tasks.getAllExResponse = of({tasks: [apiTask('task-old', '2026-01-01T00:00:00Z')]});
      models.getAllExResponse = of({models: [apiModel('model-new', '2026-09-12T00:00:00Z')]});

      const page = await firstValueFrom(api.search(filter()));

      expect(page.assets.map((asset: CatalogAsset) => asset.id)).toEqual([
        'model-new',
        'task-old',
        'task-old',
      ]);
    });

    it('puts assets with no known time last', async () => {
      const {api, models} = setUp();
      models.getAllExResponse = of({
        models: [
          {id: 'no-time', name: 'no-time', ready: true, tags: []},
          apiModel('dated', '2026-09-12T00:00:00Z'),
        ],
      });

      const page = await firstValueFrom(api.search(filter({kinds: ['model']})));

      expect(page.assets.map((asset: CatalogAsset) => asset.id)).toEqual(['dated', 'no-time']);
    });

    it('says the list was cut short when one kind filled its page', async () => {
      const {api, models} = setUp();
      models.getAllExResponse = of({
        models: Array.from({length: PER_KIND_PAGE_SIZE}, (_, index) =>
          apiModel(`model-${index}`, '2026-09-12T00:00:00Z')
        ),
      });

      const page = await firstValueFrom(api.search(filter({kinds: ['model']})));

      expect(page.assets).toHaveLength(CATALOG_PAGE_SIZE);
      expect(page.hasMore).toBe(true);
    });
  });

  describe('writing metadata back', () => {
    it('sends tags and description, and nothing else', async () => {
      const {api, tasks} = setUp();

      await firstValueFrom(
        api.updateMetadata('run', 'task-id', {tags: ['seed'], description: 'checked'})
      );

      const [body] = tasks.bodiesOf('tasks.update');
      expect(body).toEqual({task: 'task-id', tags: ['seed'], comment: 'checked'});
    });

    it('uses the model endpoint for a model, because tasks and models are separate', async () => {
      const {api, models} = setUp();

      await firstValueFrom(
        api.updateMetadata('model', 'model-id', {tags: [], description: ''})
      );

      expect(models.requests[0]['model']).toBe('model-id');
    });

    it('fails when ClearML says it changed nothing', async () => {
      // 存在しないIDへの更新でも200が返る。応答を読まないと、消された資産への
      // 編集が成功として画面に残る。
      const {api, tasks} = setUp();
      tasks.updateResponse = of({updated: 0});

      await expect(
        firstValueFrom(api.updateMetadata('run', 'gone', {tags: [], description: ''}))
      ).rejects.toThrow(/did not apply the change/);
    });
  });

  describe('tracing where an asset came from', () => {
    it('looks the dataset up by the version the run recorded', async () => {
      const {api, tasks} = setUp();
      tasks.getByIdExResponse = of({
        tasks: [
          {
            ...apiTask('run-id', '2026-09-12T00:00:00Z'),
            hyperparams: {Dataset: {dataset_version: {value: '1.0.0'}}},
          },
        ],
      });

      await firstValueFrom(
        api.getLineage({
          kind: 'run',
          id: 'run-id',
          name: 'run',
          project: {id: 'project-id', name: 'Pipeline'},
          updatedAt: null,
          tags: [],
          state: 'completed',
        })
      );

      const versionLookup = tasks
        .bodiesOf('tasks.get_all_ex')
        .find((body) => body['runtime.version'] !== undefined);
      expect(versionLookup?.['runtime.version']).toEqual(['1.0.0']);
    });

    it('keeps the node when the dataset it names has been deleted', async () => {
      // 節ごと落とすと、切れている鎖が繋がっているように見える。
      const {api, tasks} = setUp();
      tasks.getByIdExResponse = of({
        tasks: [
          {
            ...apiTask('run-id', '2026-09-12T00:00:00Z'),
            hyperparams: {Dataset: {dataset_version: {value: '9.9.9'}}},
          },
        ],
      });
      tasks.getAllExResponse = of({tasks: []});

      const lineage = await firstValueFrom(
        api.getLineage({
          kind: 'run',
          id: 'run-id',
          name: 'run',
          project: {id: 'project-id', name: 'Pipeline'},
          updatedAt: null,
          tags: [],
          state: 'completed',
        })
      );

      expect(lineage.dataset).toEqual({kind: 'dataset', id: '9.9.9', asset: null});
    });

    it('stops at the run when it never recorded a dataset version', async () => {
      const {api, tasks} = setUp();
      tasks.getByIdExResponse = of({tasks: [apiTask('run-id', '2026-09-12T00:00:00Z')]});

      const lineage = await firstValueFrom(
        api.getLineage({
          kind: 'run',
          id: 'run-id',
          name: 'run',
          project: {id: 'project-id', name: 'Pipeline'},
          updatedAt: null,
          tags: [],
          state: 'completed',
        })
      );

      expect(lineage.dataset).toBeNull();
      expect(lineage.run?.id).toBe('run-id');
    });
  });

  describe('offering the filter options', () => {
    it('joins task tags and model tags, because the catalog lists both', async () => {
      // 片方だけを出すと、存在するのに選べないタグができる。
      const {api} = setUp();

      const tags = await firstValueFrom(api.getTags());

      expect(tags).toEqual(['seed', 'stage:production']);
    });
  });
});

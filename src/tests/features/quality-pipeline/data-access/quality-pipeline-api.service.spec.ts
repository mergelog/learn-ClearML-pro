import {TestBed} from '@angular/core/testing';
import {Observable, of, throwError} from 'rxjs';
import {ApiTasksService} from '~/business-logic/api-services/tasks.service';
import {ApiModelsService} from '~/business-logic/api-services/models.service';
import {ApiEventsService} from '~/business-logic/api-services/events.service';
import {ApiProjectsService} from '~/business-logic/api-services/projects.service';
import {QualityPipelineApiService} from '@features/quality-pipeline/data-access/quality-pipeline-api.service';
import {MAXIMUM_STEPS} from '@features/quality-pipeline/quality-pipeline.consts';

/**
 * API境界が「ClearMLへ何を送るか」を確かめる。
 *
 * `HttpTestingController` は使わない。確かめたいのはHTTPの組み立て方ではなく、
 * 生成済みサービスへ渡す要求の中身だからである。生成サービスを差し替えれば、
 * 送った引数をそのまま読める。
 *
 * 返す形は実際の応答に合わせる。ここで形を単純化すると、画面が読めない形を
 * 返されても気付けないテストになる。
 */

type RequestBody = Record<string, unknown>;

class StubTasks {
  readonly requests: {method: string; body: RequestBody}[] = [];

  getAllExResponse: Observable<unknown> = of({tasks: []});
  getByIdExResponse: Observable<unknown> = of({tasks: []});
  cloneResponse: Observable<unknown> = of({id: 'cloned-task'});
  enqueueResponse: Observable<unknown> = of({queued: 1});
  stopResponse: Observable<unknown> = of({updated: 1});

  tasksGetAllEx = (body: RequestBody) =>
    this.record('tasks.get_all_ex', body, this.getAllExResponse);
  tasksGetByIdEx = (body: RequestBody) =>
    this.record('tasks.get_by_id_ex', body, this.getByIdExResponse);
  tasksClone = (body: RequestBody) => this.record('tasks.clone', body, this.cloneResponse);
  tasksEnqueue = (body: RequestBody) => this.record('tasks.enqueue', body, this.enqueueResponse);
  tasksStop = (body: RequestBody) => this.record('tasks.stop', body, this.stopResponse);

  bodyOf(method: string): RequestBody {
    const request = this.requests.find((sent) => sent.method === method);
    if (!request) {
      throw new Error(
        `${method} was never called. Sent: ${this.methods().join(', ') || 'nothing'}`
      );
    }
    return request.body;
  }

  methods(): string[] {
    return this.requests.map((request) => request.method);
  }

  private record(method: string, body: RequestBody, response: Observable<unknown>) {
    this.requests.push({method, body});
    return response;
  }
}

class StubProjects {
  readonly requests: RequestBody[] = [];
  response: Observable<unknown> = of({projects: [{id: 'project-id'}]});

  projectsGetAllEx = (body: RequestBody) => {
    this.requests.push(body);
    return this.response;
  };
}

class StubModels {
  readonly requests: RequestBody[] = [];
  response: Observable<unknown> = of({models: []});

  modelsGetAllEx = (body: RequestBody) => {
    this.requests.push(body);
    return this.response;
  };
}

class StubEvents {
  readonly requests: RequestBody[] = [];
  response: Observable<unknown> = of({metrics: []});

  eventsGetTaskLatestScalarValues = (body: RequestBody) => {
    this.requests.push(body);
    return this.response;
  };
}

interface Harness {
  api: QualityPipelineApiService;
  tasks: StubTasks;
  projects: StubProjects;
  models: StubModels;
  events: StubEvents;
}

const setUp = (): Harness => {
  const tasks = new StubTasks();
  const projects = new StubProjects();
  const models = new StubModels();
  const events = new StubEvents();

  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      QualityPipelineApiService,
      {provide: ApiTasksService, useValue: tasks},
      {provide: ApiProjectsService, useValue: projects},
      {provide: ApiModelsService, useValue: models},
      {provide: ApiEventsService, useValue: events},
    ],
  });

  return {
    api: TestBed.inject(QualityPipelineApiService),
    tasks,
    projects,
    models,
    events,
  };
};

const PIPELINE_PROJECT = 'Semiconductor Quality Prediction/Pipeline';
const PIPELINE_NAME = 'semiconductor-quality-training';

const templateTask = {
  id: 'template-task',
  name: PIPELINE_NAME,
  status: 'completed',
  hyperparams: {Dataset: {dataset_version: {value: '1.0.0'}}},
};

describe('quality pipeline api service', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('finding the task to clone from', () => {
    it('resolves the project by name before asking for tasks', async () => {
      const {api, tasks, projects} = setUp();
      tasks.getAllExResponse = of({tasks: [templateTask]});

      await firstValue(api.getTemplate(PIPELINE_PROJECT, PIPELINE_NAME));

      // プロジェクト名は正規表現として渡る。名前に含まれる記号は、そのままの
      // 文字として扱わせる必要がある。
      expect(projects.requests[0]['name']).toBe('^Semiconductor Quality Prediction/Pipeline$');
      expect(tasks.bodyOf('tasks.get_all_ex')['project']).toEqual(['project-id']);
    });

    it('asks for the exact name, so another task cannot be cloned by accident', async () => {
      const {api, tasks} = setUp();
      tasks.getAllExResponse = of({tasks: [templateTask]});

      await firstValue(api.getTemplate(PIPELINE_PROJECT, PIPELINE_NAME));

      expect(tasks.bodyOf('tasks.get_all_ex')['name']).toBe(`^${PIPELINE_NAME}$`);
    });

    it('asks for names that only start with it when looking for the latest run', async () => {
      // 実行は `<name> <version>` で作られるので、末尾で留めると1件も引けない。
      const {api, tasks} = setUp();
      tasks.getAllExResponse = of({tasks: [templateTask]});

      await firstValue(api.getLatestRun(PIPELINE_PROJECT, PIPELINE_NAME));

      expect(tasks.bodyOf('tasks.get_all_ex')['name']).toBe(`^${PIPELINE_NAME}`);
    });

    it('escapes a name that would otherwise be read as a pattern', async () => {
      const {api, tasks} = setUp();

      await firstValue(api.getTemplate(PIPELINE_PROJECT, 'a.b+c'));

      expect(tasks.bodyOf('tasks.get_all_ex')['name']).toBe('^a\\.b\\+c$');
    });

    it('leaves out drafts, which have never been put on a queue', async () => {
      const {api, tasks} = setUp();

      await firstValue(api.getTemplate(PIPELINE_PROJECT, PIPELINE_NAME));

      expect(tasks.bodyOf('tasks.get_all_ex')['status']).not.toContain('created');
    });

    it('takes the newest one', async () => {
      const {api, tasks} = setUp();

      await firstValue(api.getLatestRun(PIPELINE_PROJECT, PIPELINE_NAME));

      const body = tasks.bodyOf('tasks.get_all_ex');

      expect(body['order_by']).toEqual(['-created']);
      expect(body['page_size']).toBe(1);
    });

    it('reports nothing, rather than failing, when the project does not exist', async () => {
      const {api, tasks, projects} = setUp();
      projects.response = of({projects: []});

      const template = await firstValue(api.getTemplate(PIPELINE_PROJECT, PIPELINE_NAME));

      expect(template).toBeNull();
      expect(tasks.methods()).toEqual([]);
    });

    it('reports nothing when the project holds no matching task', async () => {
      const {api} = setUp();

      expect(await firstValue(api.getTemplate(PIPELINE_PROJECT, PIPELINE_NAME))).toBeNull();
      expect(await firstValue(api.getLatestRun(PIPELINE_PROJECT, PIPELINE_NAME))).toBeNull();
    });
  });

  describe('reading a run and its steps', () => {
    it('reads the run by id, keeping the parameters the version is stored in', async () => {
      const {api, tasks} = setUp();
      tasks.getByIdExResponse = of({tasks: [templateTask]});

      const run = await firstValue(api.getRun('run-id'));

      const body = tasks.bodyOf('tasks.get_by_id_ex');

      expect(body['id']).toEqual(['run-id']);
      expect(body['only_fields']).toContain('hyperparams');
      expect(run.datasetVersion).toBe('1.0.0');
    });

    it('finds the steps by the run that owns them, in the order they were made', async () => {
      const {api, tasks} = setUp();

      await firstValue(api.getSteps('run-id'));

      const body = tasks.bodyOf('tasks.get_all_ex');

      expect(body['parent']).toBe('run-id');
      expect(body['order_by']).toEqual(['created']);
    });

    it('says nothing was cut off when the run fits under the limit', async () => {
      const {api, tasks} = setUp();
      tasks.getAllExResponse = of({tasks: [{id: 'step-id', name: 'validate'}]});

      const page = await firstValue(api.getSteps('run-id'));

      expect(page.steps).toHaveLength(1);
      expect(page.truncated).toBe(false);
    });

    it('reports that the steps were cut off when the page came back full', async () => {
      // 黙って切り捨てると、消えたステップが「走らなかった」ものに見える。
      const {api, tasks} = setUp();
      const pageSize = MAXIMUM_STEPS;
      tasks.getAllExResponse = of({
        tasks: Array.from({length: pageSize}, (_, index) => ({
          id: `step-${index}`,
          name: `step-${index}`,
        })),
      });

      const page = await firstValue(api.getSteps('run-id'));

      expect(page.steps).toHaveLength(pageSize);
      expect(page.truncated).toBe(true);
    });

    it('does not carry every parameter of every step on the polling path', async () => {
      // 5秒ごと × ステップ数の経路なので、表に出さないものは運ばせない。
      const {api, tasks} = setUp();

      await firstValue(api.getSteps('run-id'));

      expect(tasks.bodyOf('tasks.get_all_ex')['only_fields']).not.toContain('hyperparams');
    });
  });

  describe('reading the metrics', () => {
    it('asks the evaluation step for what it recorded', async () => {
      const {api, events} = setUp();

      await firstValue(api.getScores('evaluate-task'));

      expect(events.requests[0]).toEqual({task: 'evaluate-task'});
    });
  });

  describe('reading the model that is serving', () => {
    it('asks for the exact model name carrying the production tag', async () => {
      const {api, models} = setUp();

      await firstValue(
        api.getProductionModel('semiconductor-quality-classifier', 'stage:production')
      );

      const body = models.requests[0];

      expect(body['name']).toBe('^semiconductor-quality-classifier$');
      expect(body['tags']).toEqual(['stage:production']);
      expect(body['order_by']).toEqual(['-last_update']);
    });

    it('reports nothing when no model has been promoted', async () => {
      const {api} = setUp();

      expect(
        await firstValue(
          api.getProductionModel('semiconductor-quality-classifier', 'stage:production')
        )
      ).toBeNull();
    });
  });

  describe('starting a run', () => {
    const request = {
      templateTaskId: 'template-task',
      runName: 'semiconductor-quality-training 2.0.0',
      datasetVersion: '2.0.0',
      queueName: 'semiconductor-pipeline',
      reason: 'started from the page',
    };

    it('clones the template with the version the caller asked for', async () => {
      const {api, tasks} = setUp();

      await firstValue(api.startRun(request));

      expect(tasks.bodyOf('tasks.clone')).toMatchObject({
        task: 'template-task',
        new_task_name: 'semiconductor-quality-training 2.0.0',
        new_task_hyperparams: {
          Dataset: {
            dataset_version: {
              section: 'Dataset',
              name: 'dataset_version',
              value: '2.0.0',
            },
          },
        },
      });
    });

    it('puts the clone on the queue, in that order', async () => {
      // 複製しただけでは誰も拾わない。順序が入れ替わると起動そのものが起きない。
      const {api, tasks} = setUp();

      const taskId = await firstValue(api.startRun(request));

      expect(tasks.methods()).toEqual(['tasks.clone', 'tasks.enqueue']);
      expect(tasks.bodyOf('tasks.enqueue')).toEqual({
        task: 'cloned-task',
        queue_name: 'semiconductor-pipeline',
      });
      expect(taskId).toBe('cloned-task');
    });

    it('refuses to report a start when the clone came back without an id', async () => {
      const {api, tasks} = setUp();
      tasks.cloneResponse = of({});

      await expectFailure(api.startRun(request));
      expect(tasks.methods()).toEqual(['tasks.clone']);
    });

    it('refuses to call it started when ClearML did not queue it', async () => {
      const {api, tasks} = setUp();
      tasks.enqueueResponse = of({queued: 0});

      await expectFailure(api.startRun(request));
    });

    it('does not enqueue when the clone itself failed', async () => {
      const {api, tasks} = setUp();
      tasks.cloneResponse = throwError(() => new Error('clone refused'));

      await expectFailure(api.startRun(request));
      expect(tasks.methods()).toEqual(['tasks.clone']);
    });
  });

  describe('stopping a run', () => {
    it('sends the reason with the stop and answers with the task it stopped', async () => {
      const {api, tasks} = setUp();

      const taskId = await firstValue(api.stopRun('run-id', 'stopped from the page'));

      expect(tasks.bodyOf('tasks.stop')).toEqual({
        task: 'run-id',
        status_reason: 'stopped from the page',
        force: true,
      });
      expect(taskId).toBe('run-id');
    });
  });
});

const firstValue = <T>(source: Observable<T>): Promise<T> =>
  new Promise<T>((resolve, reject) => {
    source.subscribe({next: resolve, error: reject});
  });

const expectFailure = async (source: Observable<unknown>): Promise<void> => {
  let failed = false;
  try {
    await firstValue(source);
  } catch {
    failed = true;
  }
  expect(failed).toBe(true);
};

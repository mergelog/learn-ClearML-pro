import {inject, Injectable} from '@angular/core';
import {Observable, of} from 'rxjs';
import {concatMap, map, mergeMap} from 'rxjs/operators';
import {ApiTasksService} from '~/business-logic/api-services/tasks.service';
import {ApiModelsService} from '~/business-logic/api-services/models.service';
import {ApiEventsService} from '~/business-logic/api-services/events.service';
import {ApiProjectsService} from '~/business-logic/api-services/projects.service';
import {TaskStatusEnum} from '~/business-logic/model/tasks/taskStatusEnum';
import {TasksCloneResponse} from '~/business-logic/model/tasks/tasksCloneResponse';
import {TasksEnqueueResponse} from '~/business-logic/model/tasks/tasksEnqueueResponse';
import {TasksGetAllExResponse} from '~/business-logic/model/tasks/tasksGetAllExResponse';
import {TasksGetByIdExResponse} from '~/business-logic/model/tasks/tasksGetByIdExResponse';
import {ModelsGetAllExResponse} from '~/business-logic/model/models/modelsGetAllExResponse';
import {ProjectsGetAllExResponse} from '~/business-logic/model/projects/projectsGetAllExResponse';
import {EventsGetTaskLatestScalarValuesResponse} from '~/business-logic/model/events/eventsGetTaskLatestScalarValuesResponse';
import {
  ApiModel,
  ApiTask,
  DATASET_SECTION,
  DATASET_VERSION_PARAMETER,
  toProductionModel,
  toRun,
  toScores,
  toStep,
  toTemplate,
} from '~/features/quality-pipeline/data-access/quality-pipeline.adapter';
import {
  EvaluationScore,
  PipelineRun,
  PipelineStep,
  PipelineTemplate,
  ProductionModel,
} from '~/features/quality-pipeline/quality-pipeline.model';
import {MAXIMUM_STEPS} from '~/features/quality-pipeline/quality-pipeline.consts';

/**
 * 品質判定パイプラインを操作するためのAPI境界。
 *
 * 生成済みのAPIサービス（ApiTasksService など）をそのままEffectsから呼ぶことも
 * できるが、そうすると「Pipelineを起動する」という1つの操作が
 * 「Taskを複製してからQueueへ入れる」という手順としてEffectsに散る。
 *
 * ここでは操作の単位で公開し、ClearMLの語彙（Task、Queue、hyperparams）は
 * この層の内側に留める。戻り値はすべて画面用の形にしてから返す。
 *
 * 応答は生成済みの型で受ける。生成サービスの公開シグネチャは `Observable<any>`
 * なので、`map` の引数に手書きの型を書いても検査されない。実際の応答と
 * 食い違っていても気付けないため、必ず `TasksGetAllExResponse` のような
 * 生成型を経由させる。
 */
@Injectable()
export class QualityPipelineApiService {
  private readonly tasks = inject(ApiTasksService);
  private readonly models = inject(ApiModelsService);
  private readonly events = inject(ApiEventsService);
  private readonly projects = inject(ApiProjectsService);

  /**
   * 複製元になるPipeline Taskを1つ探す。
   *
   * 名前だけで探さずプロジェクトで絞るのは、同じ名前のTaskが別の場所に
   * あったときに、意図しないものを複製して起動しないためである。
   *
   * draftを複製元にしない。draftはまだ一度もQueueへ入っておらず、実行時の
   * 設定が固まったことを誰も確かめていない。それを複製して起動すると、
   * 「動いたことのない設定」を本番のQueueへ流すことになる。
   */
  getTemplate(project: string, name: string): Observable<PipelineTemplate | null> {
    return this.findTasks(project, `^${escapeForSearch(name)}$`, 1).pipe(
      map((tasks) => firstTemplate(tasks))
    );
  }

  /**
   * いちばん新しい実行を1つ取る。画面を開いた直後に見せるもの。
   *
   * こちらもdraftを除く。Queueへ入る前のdraftを「直近の実行」として見せると、
   * 進むことのない状態を進行中として追いかけ続けることになる。
   */
  getLatestRun(project: string, name: string): Observable<PipelineRun | null> {
    return this.findTasks(project, `^${escapeForSearch(name)}`, 1).pipe(
      map((tasks) => firstRun(tasks))
    );
  }

  /** 1つの実行の状態を読み直す。 */
  getRun(taskId: string): Observable<PipelineRun> {
    return this.tasks
      .tasksGetByIdEx({id: [taskId], only_fields: RUN_FIELDS})
      .pipe(map((response: TasksGetByIdExResponse) => toRun(response.tasks?.[0] ?? {})));
  }

  /**
   * 1つの実行に属するステップを、実行順に読む。
   *
   * PipelineはステップのTaskに、制御役のTaskを親として記録する。
   * これが「この実行のステップ」を他の実行と取り違えずに引く手掛かりになる。
   *
   * 読むのは表に出す項目だけである。ここは実行中に繰り返し呼ばれるので、
   * 使わない `hyperparams` まで運ばせると、その分だけ毎回無駄に重くなる。
   *
   * 上限に達したことを一緒に返す。件数だけを返して切り捨てを隠すと、
   * 表から消えたステップが「走らなかったステップ」と区別できなくなる。
   */
  getSteps(runTaskId: string): Observable<PipelineStepPage> {
    return this.tasks
      .tasksGetAllEx({
        parent: runTaskId,
        only_fields: STEP_FIELDS,
        order_by: ['created'],
        page: 0,
        page_size: MAXIMUM_STEPS,
      })
      .pipe(
        map((response: TasksGetAllExResponse) => {
          const tasks = response.tasks ?? [];
          return {
            steps: tasks.map((task) => toStep(task)),
            truncated: tasks.length >= MAXIMUM_STEPS,
          };
        })
      );
  }

  /** 評価ステップが記録した指標を読む。 */
  getScores(evaluateTaskId: string): Observable<EvaluationScore[]> {
    return this.events
      .eventsGetTaskLatestScalarValues({task: evaluateTaskId})
      .pipe(
        map((response: EventsGetTaskLatestScalarValuesResponse) => toScores(response.metrics ?? []))
      );
  }

  /** いま提供されているモデルを読む。 */
  getProductionModel(modelName: string, stageTag: string): Observable<ProductionModel | null> {
    return this.models
      .modelsGetAllEx({
        name: `^${escapeForSearch(modelName)}$`,
        tags: [stageTag],
        only_fields: MODEL_FIELDS,
        order_by: ['-last_update'],
        page: 0,
        page_size: 1,
      })
      .pipe(map((response: ModelsGetAllExResponse) => firstModel(response.models)));
  }

  /**
   * Pipelineを1回起動する。
   *
   * ClearML上では「テンプレートを複製し、Dataset Versionを書き換え、Queueへ
   * 入れる」の3つだが、利用者にとっては1つの操作である。複製せずに元のTaskを
   * 動かすことはしない。元が消えると次から起動できなくなるためである。
   *
   * 2段目を `concatMap` でつなぐ。1段目の複製はサーバの状態を変えてしまうので、
   * そこで打ち切られると、Queueに入っていないTaskだけがClearMLに残る。
   * 送り始めた操作は最後まで送り切る。
   */
  startRun(request: StartRunRequest): Observable<string> {
    return this.tasks
      .tasksClone({
        task: request.templateTaskId,
        new_task_name: request.runName,
        new_task_comment: request.reason,
        new_task_hyperparams: {
          [DATASET_SECTION]: {
            [DATASET_VERSION_PARAMETER]: {
              section: DATASET_SECTION,
              name: DATASET_VERSION_PARAMETER,
              value: request.datasetVersion,
            },
          },
        },
      })
      .pipe(
        map((response: TasksCloneResponse) => requireTaskId(response.id)),
        // 複製しただけでは走らない。Queueへ入れて初めてAgentが拾う。
        concatMap((taskId) => this.enqueue(taskId, request.queueName))
      );
  }

  /**
   * 走っている実行を止める。
   *
   * 応答は読まない。止まったかどうかは次の再取得が見るので、ここで
   * 応答の形に依存する必要がない。
   */
  stopRun(taskId: string, reason: string): Observable<string> {
    return this.tasks
      .tasksStop({task: taskId, status_reason: reason, force: true})
      .pipe(map(() => taskId));
  }

  /**
   * 複製したTaskをQueueへ入れる。
   *
   * 入らなかったことを成功として返さない。複製だけできてQueueに載っていない
   * Taskを「起動した」と表示すると、利用者は誰も拾わないものを待ち続ける。
   */
  private enqueue(taskId: string, queueName: string): Observable<string> {
    return this.tasks.tasksEnqueue({task: taskId, queue_name: queueName}).pipe(
      map((response: TasksEnqueueResponse) => {
        if (response.queued !== 1) {
          throw new Error(
            `The pipeline was cloned as ${taskId}, but ClearML did not put it on the ` +
              `${queueName} queue. Check that the queue exists.`
          );
        }
        return taskId;
      })
    );
  }

  /**
   * プロジェクト名からTaskを引く。
   *
   * ClearML APIはプロジェクトを名前ではなくIDで受け取るため、先に名前から
   * IDを引き当てる。プロジェクトが見つからなければ空で返す。存在しない
   * プロジェクトを問い合わせることと、Taskが1件も無いことは、画面にとって
   * 同じ「まだ何もない」である。
   */
  private findTasks(project: string, namePattern: string, limit: number): Observable<ApiTask[]> {
    return this.projects
      .projectsGetAllEx({
        name: `^${escapeForSearch(project)}$`,
        only_fields: ['id'],
        page: 0,
        page_size: 1,
      })
      .pipe(
        map((response: ProjectsGetAllExResponse) => response.projects?.[0]?.id),
        mergeMap((projectId) =>
          projectId === undefined
            ? of<ApiTask[]>([])
            : this.tasks
                .tasksGetAllEx({
                  project: [projectId],
                  name: namePattern,
                  status: STARTED_STATUSES,
                  only_fields: RUN_FIELDS,
                  order_by: ['-created'],
                  page: 0,
                  page_size: limit,
                })
                .pipe(map((response: TasksGetAllExResponse) => response.tasks ?? []))
        )
      );
  }
}

/**
 * 1回の問い合わせで読めたステップ。
 *
 * `truncated` は「まだ続きがある」ことだけを言う。何件あるのかは
 * この問い合わせでは分からないし、表に出すのに要るのは
 * 「見えているものが全部ではない」という一言だけである。
 */
export interface PipelineStepPage {
  steps: PipelineStep[];
  truncated: boolean;
}

export interface StartRunRequest {
  templateTaskId: string;
  runName: string;
  datasetVersion: string;
  queueName: string;
  reason: string;
}

/**
 * 一度でもQueueへ入ったTaskの状態。
 *
 * ClearMLの `created` はdraftで、Queueへ入れるまで誰も動かさない。
 * 複製元としても、直近の実行としても、draftは対象にしない。
 */
const STARTED_STATUSES: TaskStatusEnum[] = [
  TaskStatusEnum.Queued,
  TaskStatusEnum.InProgress,
  TaskStatusEnum.Stopped,
  TaskStatusEnum.Publishing,
  TaskStatusEnum.Published,
  TaskStatusEnum.Closed,
  TaskStatusEnum.Failed,
  TaskStatusEnum.Completed,
];

/** 実行そのものを読むときの項目。Dataset Versionのために hyperparams が要る。 */
const RUN_FIELDS = ['id', 'name', 'status', 'status_reason', 'started', 'completed', 'hyperparams'];

/** ステップを読むときの項目。表に出すものだけで足りる。 */
const STEP_FIELDS = ['id', 'name', 'status', 'started', 'completed'];

const MODEL_FIELDS = ['id', 'name', 'metadata'];

/** 正規表現として渡す名前を、そのままの文字列として扱わせる。 */
const escapeForSearch = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const firstTemplate = (tasks: ApiTask[] | undefined): PipelineTemplate | null => {
  const task = tasks?.[0];
  return task ? toTemplate(task) : null;
};

const firstRun = (tasks: ApiTask[] | undefined): PipelineRun | null => {
  const task = tasks?.[0];
  return task ? toRun(task) : null;
};

const firstModel = (models: ApiModel[] | undefined): ProductionModel | null => {
  const model = models?.[0];
  return model ? toProductionModel(model) : null;
};

const requireTaskId = (id: string | undefined): string => {
  if (!id) {
    throw new Error('ClearML did not return the id of the cloned pipeline task');
  }
  return id;
};

import {inject, Injectable} from '@angular/core';
import {forkJoin, Observable, of} from 'rxjs';
import {map, mergeMap} from 'rxjs/operators';
import {ApiTasksService} from '~/business-logic/api-services/tasks.service';
import {ApiModelsService} from '~/business-logic/api-services/models.service';
import {ApiProjectsService} from '~/business-logic/api-services/projects.service';
import {TasksGetAllExResponse} from '~/business-logic/model/tasks/tasksGetAllExResponse';
import {TasksGetByIdExResponse} from '~/business-logic/model/tasks/tasksGetByIdExResponse';
import {TasksUpdateResponse} from '~/business-logic/model/tasks/tasksUpdateResponse';
import {ModelsGetAllExResponse} from '~/business-logic/model/models/modelsGetAllExResponse';
import {ModelsUpdateResponse} from '~/business-logic/model/models/modelsUpdateResponse';
import {ProjectsGetAllExResponse} from '~/business-logic/model/projects/projectsGetAllExResponse';
import {
  ApiModel,
  ApiTask,
  DATASET_SECTION,
  DATASET_VERSION_PARAMETER,
  DATASET_VERSION_RUNTIME_KEY,
  readDatasetVersion,
  readRuntimeVersion,
  toDatasetAsset,
  toDatasetDetail,
  toModelAsset,
  toModelDetail,
  toRunAsset,
  toRunDetail,
} from '~/features/data-catalog/data-access/data-catalog.adapter';
import {
  CATALOG_ASSET_KINDS,
  CatalogAsset,
  CatalogAssetDetail,
  CatalogAssetKind,
  CatalogFilter,
  CatalogLineage,
  CatalogLineageNode,
  CatalogMetadataEdit,
  CatalogPage,
} from '~/features/data-catalog/data-catalog.model';
import {
  CATALOG_PAGE_SIZE,
  FILTER_OPTION_LIMIT,
  PER_KIND_PAGE_SIZE,
} from '~/features/data-catalog/data-catalog.consts';

/**
 * 台帳がClearMLに触れる唯一の境界。
 *
 * 公開するのは台帳の操作単位（引く・詳細を見る・辿る・直す）であり、
 * ClearMLの語彙（Task、`data_processing`、hyperparams、runtime）はこの層の
 * 内側に留める。戻り値はすべて台帳用の形にしてから返す。
 *
 * **絞り込みはサーバへ渡す。** 全件を取って手元で `filter` しない。手元で絞ると、
 * 件数が増えたときに「画面が重い」ではなく「途中までしか無い」という形で壊れる
 * （プランの §4.2）。ここで手元に残しているのは、3種別の結果を1つの表へ
 * 混ぜて並べ替える処理だけである。混ぜる先はClearMLに無いので、これは
 * サーバへ渡しようがない。
 *
 * 応答は生成済みの型で受ける。生成サービスの公開シグネチャは `Observable<any>`
 * なので、`map` の引数に手書きの型を書いても検査されない。
 */
@Injectable()
export class DataCatalogApiService {
  private readonly tasks = inject(ApiTasksService);
  private readonly models = inject(ApiModelsService);
  private readonly projects = inject(ApiProjectsService);

  /**
   * 条件に合う資産を、種別をまたいで引く。
   *
   * 3種別へ別々に問い合わせ、更新日時の新しい順に混ぜて1ページへ切る。
   * ClearMLには「Dataset と Model と Run をまとめて引く」APIが無いためである。
   *
   * 種別を絞ってあるときは、その種別にだけ問い合わせる。絞ってあるのに
   * 3つ投げると、捨てるためだけの往復が2つ増える。
   */
  search(filter: CatalogFilter): Observable<CatalogPage> {
    const kinds = filter.kinds.length > 0 ? filter.kinds : CATALOG_ASSET_KINDS;

    return this.resolveProjectIds(filter.project).pipe(
      mergeMap((projectIds) => {
        // 名前を指定したのに1つも見つからないなら、結果は必ず空である。
        // 空の `project` を送ると「絞らない」と解釈され、全件が返ってくる。
        if (projectIds !== null && projectIds.length === 0) {
          return of<CatalogPage>({assets: [], hasMore: false});
        }

        return forkJoin(
          kinds.map((kind: CatalogAssetKind) => this.searchOneKind(kind, filter, projectIds))
        ).pipe(map((perKind: CatalogPage[]) => mergePages(perKind)));
      })
    );
  }

  /** 絞り込みに出すプロジェクト名。 */
  getProjectNames(): Observable<string[]> {
    return this.projects
      .projectsGetAllEx({
        only_fields: ['name'],
        order_by: ['name'],
        page: 0,
        page_size: FILTER_OPTION_LIMIT,
      })
      .pipe(
        map((response: ProjectsGetAllExResponse) =>
          (response.projects ?? []).map((project) => project.name ?? '').filter(isNotEmpty)
        )
      );
  }

  /**
   * 絞り込みに出すタグ。
   *
   * TaskのタグとModelのタグは別に管理されている。台帳は両方を並べるので、
   * 選択肢も両方を合わせたものでなければならない。片方だけを出すと、
   * 存在するのに選べないタグができる。
   */
  getTags(): Observable<string[]> {
    return forkJoin([
      this.projects.projectsGetTaskTags({}).pipe(map(readTags)),
      this.projects.projectsGetModelTags({}).pipe(map(readTags)),
    ]).pipe(map(([taskTags, modelTags]) => unique([...taskTags, ...modelTags]).sort()));
  }

  /** 1つの資産の詳細。一覧に無い資産でも、URLで直接開ける。 */
  getDetail(kind: CatalogAssetKind, id: string): Observable<CatalogAssetDetail | null> {
    if (kind === 'model') {
      return this.getModelById(id).pipe(map((model) => (model ? toModelDetail(model) : null)));
    }
    return this.getTaskById(id).pipe(
      map((task) => {
        if (!task) {
          return null;
        }
        return kind === 'dataset' ? toDatasetDetail(task) : toRunDetail(task);
      })
    );
  }

  /**
   * `Dataset → Run → Model` の鎖を組み立てる。
   *
   * どの種別から呼ばれても同じ形を返す。繋がりの手掛かりは2つしかない。
   *
   * - Model は生成元の Run を `task` に持つ
   * - Run は使った Dataset の版数を hyperparams に持つ（`DATASET_SECTION`）
   *
   * 逆向き（Dataset から Run、Run から Model）は、その値で絞り込んで引き当てる。
   * ClearMLは入れ子のフィールドを `a.b.c` の形で条件に取れるので、ここも
   * サーバ側で絞る。
   *
   * 辿った先が見つからなくても、節は残して `asset: null` で返す。黙って
   * 節ごと落とすと、切れている鎖が繋がっているように見える。
   */
  getLineage(asset: CatalogAsset): Observable<CatalogLineage> {
    switch (asset.kind) {
      case 'model':
        return this.lineageFromModel(asset);
      case 'run':
        return this.lineageFromRun(asset.id).pipe(map((lineage) => ({...lineage, origin: 'run'})));
      case 'dataset':
        return this.lineageFromDataset(asset);
    }
  }

  /**
   * tags と description を書き換える。
   *
   * 台帳が書き込むのはこの2つだけである。名前・プロジェクト・状態は
   * ClearML側の実体が決めるものであって、台帳が上書きしてよいものではない。
   *
   * 更新の成否を応答から読む。ClearMLは存在しないIDへの更新でも200を返し、
   * `updated: 0` で「何も変えなかった」と言う。応答を読まないと、消された
   * 資産への編集が成功として画面に残る。
   */
  updateMetadata(
    kind: CatalogAssetKind,
    id: string,
    edit: CatalogMetadataEdit
  ): Observable<CatalogMetadataEdit> {
    const updated$: Observable<number | undefined> =
      kind === 'model'
        ? this.models
            .modelsUpdate({model: id, tags: [...edit.tags], comment: edit.description})
            .pipe(map((response: ModelsUpdateResponse) => response.updated))
        : this.tasks
            .tasksUpdate({task: id, tags: [...edit.tags], comment: edit.description})
            .pipe(map((response: TasksUpdateResponse) => response.updated));

    return updated$.pipe(
      map((updated) => {
        if (updated !== 1) {
          throw new Error(
            `ClearML did not apply the change to ${id}. It may have been deleted or ` +
              `changed by someone else. Reload the asset before editing it again.`
          );
        }
        return edit;
      })
    );
  }

  /** 1つの種別だけを引く。条件はすべてClearMLへ渡す。 */
  private searchOneKind(
    kind: CatalogAssetKind,
    filter: CatalogFilter,
    projectIds: string[] | null
  ): Observable<CatalogPage> {
    if (kind === 'model') {
      return this.models
        .modelsGetAllEx(
          withExtraCriteria(
            {
              ...commonCriteria(filter, projectIds),
              only_fields: MODEL_FIELDS,
              order_by: ['-last_update'],
              page: 0,
              page_size: PER_KIND_PAGE_SIZE,
            },
            updatedRange(filter)
          )
        )
        .pipe(
          map((response: ModelsGetAllExResponse) => {
            const models = (response.models ?? []) as ApiModel[];
            return {assets: models.map(toModelAsset), hasMore: models.length >= PER_KIND_PAGE_SIZE};
          })
        );
    }

    return this.tasks
      .tasksGetAllEx(
        withExtraCriteria(
          {
            ...commonCriteria(filter, projectIds),
            ...kindCriteria(kind),
            only_fields: TASK_LIST_FIELDS,
            order_by: ['-last_update'],
            page: 0,
            page_size: PER_KIND_PAGE_SIZE,
          },
          updatedRange(filter)
        )
      )
      .pipe(
        map((response: TasksGetAllExResponse) => {
          const tasks = (response.tasks ?? []) as ApiTask[];
          const toAsset = kind === 'dataset' ? toDatasetAsset : toRunAsset;
          return {assets: tasks.map(toAsset), hasMore: tasks.length >= PER_KIND_PAGE_SIZE};
        })
      );
  }

  /**
   * プロジェクト名からIDを引く。
   *
   * ClearML APIはプロジェクトを名前ではなくIDで受け取る。名前を指定して
   * いないときは `null` を返し、呼び出し側は条件そのものを送らない。
   * 空配列を送ると「どのプロジェクトにも属さないもの」を求めたことになる。
   */
  private resolveProjectIds(name: string): Observable<string[] | null> {
    if (name === '') {
      return of(null);
    }

    return this.projects
      .projectsGetAllEx({
        name: `^${escapeForSearch(name)}$`,
        only_fields: ['id'],
        page: 0,
        page_size: FILTER_OPTION_LIMIT,
      })
      .pipe(
        map((response: ProjectsGetAllExResponse) =>
          (response.projects ?? []).map((project) => project.id ?? '').filter(isNotEmpty)
        )
      );
  }

  private getTaskById(id: string): Observable<ApiTask | null> {
    return this.tasks
      .tasksGetByIdEx({id: [id], only_fields: TASK_DETAIL_FIELDS})
      .pipe(map((response: TasksGetByIdExResponse) => (response.tasks?.[0] as ApiTask) ?? null));
  }

  private getModelById(id: string): Observable<ApiModel | null> {
    return this.models
      .modelsGetAllEx({id: [id], only_fields: MODEL_DETAIL_FIELDS, page: 0, page_size: 1})
      .pipe(map((response: ModelsGetAllExResponse) => (response.models?.[0] as ApiModel) ?? null));
  }

  /** Modelから見た鎖。生成元のRunを辿り、そこからDatasetへ戻る。 */
  private lineageFromModel(asset: CatalogAsset): Observable<CatalogLineage> {
    return this.getModelById(asset.id).pipe(
      mergeMap((model) => {
        const runId = model?.task ?? '';
        if (runId === '') {
          return of<CatalogLineage>({
            origin: 'model',
            dataset: null,
            run: null,
            model: nodeOf('model', asset.id, asset),
          });
        }
        return this.lineageFromRun(runId).pipe(
          map((lineage) => ({
            ...lineage,
            origin: 'model' as const,
            model: nodeOf('model', asset.id, asset),
          }))
        );
      })
    );
  }

  /** Runから見た鎖。使ったDatasetへ戻り、生み出したModelへ進む。 */
  private lineageFromRun(runId: string): Observable<CatalogLineage> {
    return this.getTaskById(runId).pipe(
      mergeMap((run) => {
        const version = run ? readDatasetVersion(run) : '';
        return forkJoin([this.findDatasetByVersion(version), this.findModelOfRun(runId)]).pipe(
          map(([dataset, model]) => ({
            origin: 'run' as const,
            dataset,
            run: nodeOf('run', runId, run ? toRunAsset(run) : null),
            model,
          }))
        );
      })
    );
  }

  /** Datasetから見た鎖。その版数で走ったRunを引き、そこからModelへ進む。 */
  private lineageFromDataset(asset: CatalogAsset): Observable<CatalogLineage> {
    return this.getTaskById(asset.id).pipe(
      mergeMap((dataset) => {
        const version = dataset ? readRuntimeVersion(dataset) : '';
        return this.findRunOfDatasetVersion(version).pipe(
          mergeMap((run) => {
            const node = nodeOf('dataset', asset.id, dataset ? toDatasetAsset(dataset) : asset);
            if (run === null) {
              return of<CatalogLineage>({
                origin: 'dataset',
                dataset: node,
                run: null,
                model: null,
              });
            }
            return this.findModelOfRun(run.id).pipe(
              map((model) => ({origin: 'dataset' as const, dataset: node, run, model}))
            );
          })
        );
      })
    );
  }

  /** 版数でDatasetを引き当てる。ClearMLは版数を `runtime` に置いている。 */
  private findDatasetByVersion(version: string): Observable<CatalogLineageNode | null> {
    if (version === '') {
      return of(null);
    }

    return this.tasks
      .tasksGetAllEx(
        withExtraCriteria(
          {
            ...kindCriteria('dataset'),
            only_fields: TASK_LIST_FIELDS,
            order_by: ['-last_update'],
            page: 0,
            page_size: 1,
          },
          {[`runtime.${DATASET_VERSION_RUNTIME_KEY}`]: [version]}
        )
      )
      .pipe(
        map((response: TasksGetAllExResponse) => {
          const task = (response.tasks?.[0] as ApiTask) ?? null;
          // 版数は分かっているのに実体が見つからない。消されたということなので、
          // 節は残して「もう無い」と言えるようにする。
          return nodeOf('dataset', task?.id ?? version, task ? toDatasetAsset(task) : null);
        })
      );
  }

  /** その版数で走った学習Runを引き当てる。 */
  private findRunOfDatasetVersion(version: string): Observable<CatalogLineageNode | null> {
    if (version === '') {
      return of(null);
    }

    return this.tasks
      .tasksGetAllEx(
        withExtraCriteria(
          {
            only_fields: TASK_LIST_FIELDS,
            order_by: ['-last_update'],
            page: 0,
            page_size: 1,
          },
          {[`hyperparams.${DATASET_SECTION}.${DATASET_VERSION_PARAMETER}.value`]: [version]}
        )
      )
      .pipe(
        map((response: TasksGetAllExResponse) => {
          const task = (response.tasks?.[0] as ApiTask) ?? null;
          return task === null ? null : nodeOf('run', task.id ?? '', toRunAsset(task));
        })
      );
  }

  /** その実行が生み出したModelを引き当てる。 */
  private findModelOfRun(runId: string): Observable<CatalogLineageNode | null> {
    return this.models
      .modelsGetAllEx({
        task: [runId],
        only_fields: MODEL_FIELDS,
        order_by: ['-last_update'],
        page: 0,
        page_size: 1,
      })
      .pipe(
        map((response: ModelsGetAllExResponse) => {
          const model = (response.models?.[0] as ApiModel) ?? null;
          return model === null ? null : nodeOf('model', model.id ?? '', toModelAsset(model));
        })
      );
  }
}

/**
 * 3種別の結果を1つのページへ混ぜる。
 *
 * 並べ替えの基準は更新日時の新しい順だけである。種別を優先順位にしない。
 * 台帳は「最近動いたもの」を見に来る場所で、「Datasetを先に見たい」なら
 * それは絞り込みで言うことである。
 *
 * 更新日時の無いものは最後に置く。先頭に来ると、一覧を開くたびに
 * 「いつのものか分からないもの」が目に入る。
 */
export const mergePages = (pages: readonly CatalogPage[]): CatalogPage => {
  const assets = pages
    .flatMap((page) => page.assets)
    .sort((left, right) => compareUpdatedAt(left, right));

  return {
    assets: assets.slice(0, CATALOG_PAGE_SIZE),
    // 種別のどれかが上限に届いたか、混ぜた結果が1ページに収まらなかったか。
    // どちらも「見えているものが全部ではない」である。
    hasMore: pages.some((page) => page.hasMore) || assets.length > CATALOG_PAGE_SIZE,
  };
};

const compareUpdatedAt = (left: CatalogAsset, right: CatalogAsset): number => {
  if (left.updatedAt === right.updatedAt) {
    return 0;
  }
  if (left.updatedAt === null) {
    return 1;
  }
  if (right.updatedAt === null) {
    return -1;
  }
  return left.updatedAt < right.updatedAt ? 1 : -1;
};

/**
 * 種別に依らない絞り込み条件。
 *
 * 日付は2要素の範囲として渡す。ClearMLは日時フィールドに
 * `[下限, 上限]` を取り、片側だけのときは `null` を置く。
 * 両方とも空のときは条件そのものを送らない。
 */
const commonCriteria = (filter: CatalogFilter, projectIds: string[] | null): CommonCriteria => ({
  ...(filter.text === '' ? {} : {name: escapeForSearch(filter.text)}),
  ...(projectIds === null ? {} : {project: projectIds}),
  ...(filter.tags.length === 0 ? {} : {tags: [...filter.tags]}),
});

interface CommonCriteria {
  name?: string;
  project?: string[];
  tags?: string[];
}

/**
 * 更新日時の範囲。
 *
 * ClearMLは日時の条件を「比較記号を前に付けた文字列の並び」で取る
 * （`modelsGetAllExRequest` の `last_update` の説明）。2要素の配列を
 * 範囲として渡す書き方ではない。片側だけのときは、その1つだけを送る。
 */
const updatedRange = (filter: CatalogFilter): Record<string, unknown> => {
  const constraints = [
    ...(filter.updatedFrom === '' ? [] : [`>=${filter.updatedFrom}`]),
    ...(filter.updatedTo === '' ? [] : [`<=${filter.updatedTo}`]),
  ];
  return constraints.length === 0 ? {} : {last_update: constraints};
};

/**
 * 生成された要求型が知らない条件を渡すための、ただ1つの口。
 *
 * ClearMLが受け付ける条件は生成型より広い。`tasks.get_all_ex` の
 * `last_update` や、`runtime.version` のような入れ子のフィールド指定は
 * 生成型に現れないが、サーバは解釈する。
 *
 * それでも各所に `as` を散らさない。散らすと、型が守っている範囲と
 * 外れている範囲の境目が見えなくなる。**外れるのはここだけ**にして、
 * 呼び出し側は「余分な条件を足している」と読める形にしておく。
 */
const withExtraCriteria = <T extends object>(request: T, extra: Record<string, unknown>): T =>
  ({...request, ...extra}) as T;

/**
 * Dataset と Run を分ける条件。
 *
 * ClearMLのDatasetは `data_processing` のTaskで、`dataset` というシステムタグが
 * 付く。型だけで絞ると、Datasetでない前処理Taskまで混ざる。
 *
 * Runはその裏返しで、`dataset` の付いたTaskを除く。除かないと、同じ実体が
 * Datasetの行とRunの行として2回並ぶ。
 */
const kindCriteria = (kind: 'dataset' | 'run'): KindCriteria =>
  kind === 'dataset'
    ? {type: ['data_processing'], system_tags: [DATASET_SYSTEM_TAG]}
    : {system_tags: [`-${DATASET_SYSTEM_TAG}`]};

interface KindCriteria {
  type?: string[];
  system_tags?: string[];
}

const DATASET_SYSTEM_TAG = 'dataset';

/** 一覧に出す項目。7項目を埋めるのに要るものだけ。 */
const TASK_LIST_FIELDS = [
  'id',
  'name',
  'type',
  'status',
  'tags',
  'system_tags',
  'project',
  'last_update',
  'created',
  'runtime',
];

/** 詳細に出す項目。一覧には要らない `comment` と `hyperparams` が要る。 */
const TASK_DETAIL_FIELDS = [...TASK_LIST_FIELDS, 'comment', 'started', 'completed', 'hyperparams'];

const MODEL_FIELDS = [
  'id',
  'name',
  'tags',
  'system_tags',
  'project',
  'last_update',
  'created',
  'ready',
  'task',
];

const MODEL_DETAIL_FIELDS = [...MODEL_FIELDS, 'comment', 'framework', 'uri', 'metadata'];

const nodeOf = (
  kind: CatalogAssetKind,
  id: string,
  asset: CatalogAsset | null
): CatalogLineageNode => ({kind, id, asset});

const readTags = (response: {tags?: string[]}): string[] => response.tags ?? [];

const unique = (values: readonly string[]): string[] => [...new Set(values)];

const isNotEmpty = (value: string): boolean => value !== '';

/** 正規表現として渡す名前を、そのままの文字列として扱わせる。 */
const escapeForSearch = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

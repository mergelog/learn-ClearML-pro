import {REAL} from './real-backend';

/**
 * 実バックエンドで巡回するルート。フェーズ0の全ルート巡回（00-route-crawl）と、
 * フェーズ2の観点D（p2d-stale-view-crawl）で使う。data-catalog・quality-pipeline は対象外（プラン §1.2）。
 */
const R = REAL;
export const ALL_ROUTES: string[] = [
  '/dashboard',
  '/projects',
  `/projects/${R.projectBaseline}`,
  `/projects/${R.projectBaseline}/overview`,
  `/projects/${R.projectBaseline}/workloads`,
  `/projects/${R.projectBaseline}/projects`,
  `/projects/${R.projectBaseline}/tasks`,
  `/projects/*/tasks`,
  `/projects/${R.projectBaseline}/tasks/${R.taskBaselineV1}`,
  `/projects/${R.projectBaseline}/tasks/${R.taskBaselineV1}/execution`,
  `/projects/${R.projectBaseline}/tasks/${R.taskBaselineV1}/hyper-params/hyper-param/_all_`,
  `/projects/${R.projectBaseline}/tasks/${R.taskBaselineV1}/artifacts`,
  `/projects/${R.projectBaseline}/tasks/${R.taskBaselineV1}/general`,
  `/projects/${R.projectBaseline}/tasks/${R.taskBaselineV1}/scalars`,
  `/projects/${R.projectBaseline}/tasks/${R.taskBaselineV1}/plots`,
  `/projects/${R.projectBaseline}/tasks/${R.taskBaselineV1}/debugImages`,
  `/projects/${R.projectBaseline}/tasks/${R.taskBaselineV1}/log`,
  `/projects/${R.projectBaseline}/tasks/${R.taskBaselineV1}/output/execution`,
  `/projects/${R.projectBaseline}/tasks/${R.taskBaselineV1}/output/scalars`,
  `/projects/${R.projectBaseline}/tasks/${R.taskBaselineV1}/output/log`,
  `/projects/${R.projectBaseline}/experiments`,
  `/projects/${R.projectModelComparison}/models`,
  `/projects/${R.projectModelComparison}/models/${R.model}/general`,
  `/projects/${R.projectModelComparison}/models/${R.model}/network`,
  `/projects/${R.projectModelComparison}/models/${R.model}/labels`,
  `/projects/${R.projectModelComparison}/models/${R.model}/metadata`,
  `/projects/${R.projectModelComparison}/models/${R.model}/tasks`,
  `/projects/${R.projectModelComparison}/models/${R.model}/scalars`,
  `/projects/${R.projectModelComparison}/models/${R.model}/output/general`,
  `/projects/${R.projectTraining}/compare-tasks;ids=${R.taskCompareA},${R.taskCompareB}/details`,
  `/projects/${R.projectTraining}/compare-tasks;ids=${R.taskCompareA},${R.taskCompareB}/hyper-params/values`,
  `/projects/${R.projectTraining}/compare-tasks;ids=${R.taskCompareA},${R.taskCompareB}/hyper-params/graph`,
  `/projects/${R.projectTraining}/compare-tasks;ids=${R.taskCompareA},${R.taskCompareB}/scalars/values`,
  `/projects/${R.projectTraining}/compare-tasks;ids=${R.taskCompareA},${R.taskCompareB}/scalars/graph`,
  `/projects/${R.projectTraining}/compare-tasks;ids=${R.taskCompareA},${R.taskCompareB}/metrics-plots`,
  `/projects/${R.projectTraining}/compare-tasks;ids=${R.taskCompareA},${R.taskCompareB}/debug-images`,
  `/projects/${R.projectTraining}/compare-experiments;ids=${R.taskCompareA},${R.taskCompareB}/details`,
  `/projects/${R.projectModelComparison}/compare-models;ids=${R.model},${R.modelB}/models-details`,
  `/projects/${R.projectModelComparison}/compare-models;ids=${R.model},${R.modelB}/network`,
  `/projects/${R.projectModelComparison}/compare-models;ids=${R.model},${R.modelB}/scalars/graph`,
  '/pipelines',
  `/pipelines/${R.pipelineProject}/tasks`,
  `/pipelines/${R.pipelineProject}/tasks/${R.pipelineRun}`,
  `/pipelines/${R.projectPipelineTop}/projects`,
  '/datasets',
  `/datasets/simple/${R.datasetProject}/tasks`,
  `/datasets/simple/${R.datasetProject}/tasks/${R.datasetVersion}`,
  '/reports',
  '/workers-and-queues/workers',
  '/workers-and-queues/queues',
  '/endpoints',
  '/endpoints/active',
  '/settings/profile',
  '/settings/webapp-configuration',
  '/settings/workspace-configuration',
  '/settings/storage-credentials',
  '/enterprise',
  '/404',
  '/no-such-route',
  `/projects/no-such-project/tasks`,
  `/projects/${R.projectBaseline}/tasks/no-such-task/execution`
];

/** フェーズ2で足したデータ（REAL に無い既存データ。2026-09-22 時点の learn01-clearml） */
export const EXTRA = {
  hpoProject: '53f9b62a0687460290bac474f2ec8c77',
  hpoTask: '6287d954f8db44d98acd877fad386470',
  trainingTaskWithModel: '0d9a969515ac4449b611b8034b4fc152',
  trainingOutputModel: 'aa7fc34b51af4fb7874367582a351a67'
} as const;

/** 観点D で ALL_ROUTES に足すルート（設定オブジェクト・パラメータの節・成果物・モデル） */
export const EXTRA_ROUTES: string[] = [
  `/projects/${EXTRA.hpoProject}/tasks/${EXTRA.hpoTask}/hyper-params/configuration/General`,
  `/projects/${EXTRA.hpoProject}/tasks/${EXTRA.hpoTask}/hyper-params/hyper-param/General`,
  `/projects/${EXTRA.hpoProject}/tasks/${EXTRA.hpoTask}/output/hyper-params/configuration/General`,
  `/projects/${R.projectTraining}/tasks/${EXTRA.trainingTaskWithModel}/artifacts/output-model/${EXTRA.trainingOutputModel}`,
  `/projects/${R.projectTraining}/tasks/${EXTRA.trainingTaskWithModel}/output/artifacts/output-model/${EXTRA.trainingOutputModel}`,
  `/projects/${R.projectTraining}/tasks/${R.taskCompareA}/artifacts/other/evaluation/output`,
  `/projects/${R.projectTraining}/tasks/${R.taskCompareA}/info-output`,
  `/projects/${R.projectModelComparison}/models/${R.model}/general`,
  `/projects/${R.projectTraining}/compare-tasks;ids=${R.taskCompareA},${R.taskCompareB}/scalars/values`,
  `/projects/${R.projectTraining}/compare-tasks;ids=${R.taskCompareA},${R.taskCompareB}/metrics-plots`,
  '/dashboard'
];

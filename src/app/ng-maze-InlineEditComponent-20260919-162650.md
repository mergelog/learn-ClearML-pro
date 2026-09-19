# <a href="./webapp-common/shared/ui-components/inputs/inline-edit/inline-edit.component.ts">InlineEditComponent</a>

parent path: `./webapp-common/shared/ui-components/inputs/inline-edit/`

<pre>
├── <a href="./features/settings/containers/admin/profile-name/profile-name.component.ts">ProfileNameComponent</a>
│   └── <a href="./features/settings/settings.component.ts">SettingsComponent</a> [route: 'settings/profile']
│       └── <a href="./app.component.ts">AppComponent</a> <code>./</code> [route: 'settings']
├── <a href="./webapp-common/datasets/open-dataset-card/open-dataset-card.component.ts">OpenDatasetCardComponent</a> [extends <a href="./webapp-common/pipelines/pipeline-card/pipeline-card.component.ts">PipelineCardComponent</a>]
│   └── <a href="./webapp-common/datasets/open-datasets/open-datasets.component.ts">OpenDatasetsComponent</a> [extends <a href="./webapp-common/pipelines/pipelines-page/pipelines-page.component.ts">PipelinesPageComponent</a>]
│       └── <a href="./app.component.ts">AppComponent</a> <code>./</code> ×2 [route: 'datasets', 'datasets/simple/:projectId/datasets']
├── <a href="./webapp-common/experiments/dumb/experiment-info-header/experiment-info-header.component.ts">ExperimentInfoHeaderComponent</a>
│   └── <a href="./features/experiments/containers/experiment-ouptut/experiment-output.component.ts">ExperimentOutputComponent</a> [extends <a href="./webapp-common/experiments/containers/experiment-ouptut/base-experiment-output.component.ts">BaseExperimentOutputComponent</a>]
│       ├── <a href="./app.component.ts">AppComponent</a> <code>./</code> [route: 'projects/:projectId/tasks/:experimentId/output']
│       └── <a href="./webapp-common/experiments/experiments.component.ts">ExperimentsComponent</a> [extends <a href="./webapp-common/shared/entity-page/base-entity-page.ts">BaseEntityPageComponent</a>] [route: 'projects/:projectId/tasks/:experimentId']
│           └── <a href="./app.component.ts">AppComponent</a> <code>./</code> [route: 'projects/:projectId/tasks']
├── <a href="./webapp-common/models/dumbs/model-general-info/model-general-info.component.ts">ModelGeneralInfoComponent</a>
│   └── <a href="./webapp-common/models/containers/model-info-general/model-info-general.component.ts">ModelInfoGeneralComponent</a>
│       └── <a href="./webapp-common/models/containers/model-info/model-info.component.ts">ModelInfoComponent</a> ×2 [route: 'projects/:projectId/models/:modelId/general', 'projects/:projectId/models/:modelId/output/general']
│           ├── <a href="./app.component.ts">AppComponent</a> <code>./</code> [route: 'projects/:projectId/models/:modelId/output']
│           └── <a href="./webapp-common/models/models.component.ts">ModelsComponent</a> [extends <a href="./webapp-common/shared/entity-page/base-entity-page.ts">BaseEntityPageComponent</a>] [route: 'projects/:projectId/models/:modelId']
│               └── <a href="./app.component.ts">AppComponent</a> <code>./</code> [route: 'projects/:projectId/models']
├── <a href="./webapp-common/models/dumbs/model-info-header/model-info-header.component.ts">ModelInfoHeaderComponent</a>
│   └── <a href="./webapp-common/models/containers/model-info/model-info.component.ts">ModelInfoComponent</a>
│       ├── <a href="./app.component.ts">AppComponent</a> <code>./</code> [route: 'projects/:projectId/models/:modelId/output']
│       └── <a href="./webapp-common/models/models.component.ts">ModelsComponent</a> [extends <a href="./webapp-common/shared/entity-page/base-entity-page.ts">BaseEntityPageComponent</a>] [route: 'projects/:projectId/models/:modelId']
│           └── <a href="./app.component.ts">AppComponent</a> <code>./</code> [route: 'projects/:projectId/models']
├── <a href="./webapp-common/nested-project-view/nested-card/nested-card.component.ts">NestedCardComponent</a>
│   └── <a href="./webapp-common/nested-project-view/nested-project-view-page/nested-project-view-page.component.ts">NestedProjectViewPageComponent</a> (参照元: 4)
│       ├── <a href="./features/datasets/nested-datasets-page/nested-datasets-page.component.ts">NestedDatasetsPageComponent</a> [extends <a href="./webapp-common/projects/containers/projects-page/projects-page.component.ts">ProjectsPageComponent</a>]
│       ├── <a href="./webapp-common/datasets/nested-open-datasets-page/nested-open-datasets-page.component.ts">NestedOpenDatasetsPageComponent</a> [extends <a href="./webapp-common/projects/containers/projects-page/projects-page.component.ts">ProjectsPageComponent</a>]
│       │   └── <a href="./app.component.ts">AppComponent</a> <code>./</code> [route: 'datasets/simple/:projectId/projects']
│       ├── <a href="./webapp-common/pipelines/nested-pipeline-page/nested-pipeline-page.component.ts">NestedPipelinePageComponent</a> [extends <a href="./webapp-common/pipelines/pipelines-page/pipelines-page.component.ts">PipelinesPageComponent</a>]
│       │   └── <a href="./app.component.ts">AppComponent</a> <code>./</code> [route: 'pipelines/:projectId/projects']
│       └── <a href="./webapp-common/reports/nested-reports-page/nested-reports-page.component.ts">NestedReportsPageComponent</a> [extends <a href="./webapp-common/reports/reports-page/reports-page.component.ts">ReportsPageComponent</a>]
│           └── <a href="./app.component.ts">AppComponent</a> <code>./</code> [route: 'reports/:projectId/projects']
├── <a href="./webapp-common/pipelines/pipeline-card/pipeline-card.component.ts">PipelineCardComponent</a> [extends <a href="./webapp-common/shared/ui-components/panel/project-card/project-card.component.ts">ProjectCardComponent</a>]
│   └── <a href="./webapp-common/pipelines/pipelines-page/pipelines-page.component.ts">PipelinesPageComponent</a> [extends <a href="./webapp-common/projects/containers/projects-page/projects-page.component.ts">ProjectsPageComponent</a>]
│       └── <a href="./app.component.ts">AppComponent</a> <code>./</code> ×2 [route: 'pipelines', 'pipelines/:projectId/pipelines']
└── <a href="./webapp-common/reports/report-card/report-card.component.ts">ReportCardComponent</a> (参照元: 2)
    ├── <a href="./webapp-common/dashboard/containers/dashboard-reports/dashboard-reports.component.ts">DashboardReportsComponent</a>
    │   └── <a href="./features/dashboard/dashboard.component.ts">DashboardComponent</a>
    │       └── <a href="./app.component.ts">AppComponent</a> <code>./</code> [route: 'dashboard']
    └── <a href="./webapp-common/reports/reports-list/reports-list.component.ts">ReportsListComponent</a>
        └── <a href="./webapp-common/reports/reports-page/reports-page.component.ts">ReportsPageComponent</a> [extends <a href="./webapp-common/projects/containers/projects-page/projects-page.component.ts">ProjectsPageComponent</a>]
            └── <a href="./app.component.ts">AppComponent</a> <code>./</code> ×2 [route: 'reports', 'reports/:projectId/reports']
</pre>

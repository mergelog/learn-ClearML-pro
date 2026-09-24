````ts
import {inject, Injectable} from '@angular/core';                                                      // injectはDI取得、InjectableはEffectクラスをDI対象にするデコレータ
import {Actions, createEffect, ofType} from '@ngrx/effects';                                           // ActionsはActionの流れ、createEffectはEffect登録、ofTypeはAction種別の絞り込み
import {concatLatestFrom} from '@ngrx/operators';                                                      // Action到着時にStore側の最新値を遅延取得するNgRx演算子
import {Store} from '@ngrx/store';                                                                     // NgRx Storeから画面・実験の状態を参照する
import {catchError, filter, map, mergeMap, shareReplay, switchMap, take, tap} from 'rxjs/operators';   // RxJS演算子。API応答の変換、エラー処理、購読切替などに使用
import {ApiTasksService} from '~/business-logic/api-services/tasks.service';                           // 実験・タスクAPIへのアクセスをまとめたサービス
import {getExperimentInfoOnlyFields, getTaskExportOnlyFields} from '@features/experiments/experiments.consts'; // 詳細取得・エクスポートで要求するフィールド一覧を生成
import {
  experimentInfo,                                                                                      // 設定タブの保存対象を含む実験情報State
  selectExperimentFormValidity,                                                                        // 編集フォームが保存可能かを返すセレクタ
  selectExperimentInfoData,                                                                            // 編集フォーム上の実験データを返すセレクタ
  selectExperimentInfoDataFreeze,                                                                      // 編集中に保持する元データを返すセレクタ
  selectSelectedExperiment                                                                             // 現在詳細表示中の実験を返すセレクタ
} from '@features/experiments/reducers';
import {ExperimentReverterService} from '@features/experiments/shared/services/experiment-reverter.service'; // APIの実験データを編集フォーム向けに戻すサービス
import {requestFailed} from '../../core/actions/http.actions';                                         // HTTP失敗を共通処理へ通知するAction
import {
  activeLoader,                                                                                        // 指定Actionに対応するローディングを開始
  addMessage,                                                                                          // 画面メッセージを表示
  deactivateLoader,                                                                                    // 指定Actionに対応するローディングを終了
  setBackdrop,                                                                                         // 編集中の背面操作を防ぐ覆いを制御
  setServerError                                                                                       // サーバーエラーを画面へ渡す
} from '../../core/actions/layout.actions';
import {selectAppVisible} from '../../core/reducers/view.reducer';                                     // アプリ画面が表示中かを判定するセレクタ
import * as commonInfoActions from '../actions/common-experiments-info.actions';                       // 実験詳細に関するActionを名前空間付きで取り込む
import {
  cancelExperimentEdit,                                                                                // 編集取り消しAction
  deactivateEdit,                                                                                      // 編集モード解除Action
  deleteHyperParamsSection,                                                                            // ハイパーパラメータ節の削除Action
  experimentDetailsUpdated,                                                                            // 名前・コメント・タグ等の変更Action
  getExperimentConfigurationNames,                                                                     // 設定オブジェクト名の取得Action
  getExperimentConfigurationObj,                                                                       // 選択中の設定オブジェクト取得Action
  getPipelineConfigurationObj,                                                                         // Pipeline設定オブジェクト取得Action
  getSelectedPipelineStep,                                                                             // パイプライン内の選択ステップ取得Action
  navigateToDataset,                                                                                   // 関連データセットへの移動Action
  saveExperiment,                                                                                      // 実験フォーム全体の保存Action
  saveExperimentConfigObj,                                                                             // 設定オブジェクト単位の保存Action
  saveExperimentSection,                                                                               // 実験の一部セクション保存Action
  saveHyperParamsSection,                                                                              // ハイパーパラメータ節の保存Action
  setExperimentSaving, setLastTasksTab,                                                                // 保存中フラグとタスク詳細タブ設定Action
  TreeStep                                                                                             // Pipeline設定JSON内のステップ型
} from '../actions/common-experiments-info.actions';
import {getTags, updateExperiment} from '../actions/common-experiments-view.actions';                  // 一覧の実験更新とタグ再取得Action
import {
  selectExperimentConfiguration,                                                                       // Store上の実験設定一覧
  selectExperimentHyperParamsSelectedSectionFromRoute,                                                 // URLで選択したハイパーパラメータ節
  selectExperimentSelectedConfigObjectFromRoute,                                                       // URLで選択した設定オブジェクト名
  selectPipelineSelectedStep,                                                                          // 選択中のPipelineステップ
  selectSelectedExperimentFromRouter,                                                                  // URL上で選択した実験ID
  selectSelectedFromTable,                                                                             // 表から選んだ実験データ
  selectSelectedTableExperiment                                                                        // 表の現在選択行
} from '../reducers';
import {convertStopToComplete} from '../shared/common-experiments.utils';                              // 表示用にStoppedをCompletedとして扱う変換
import {ExperimentConverterService} from '@features/experiments/shared/services/experiment-converter.service'; // 編集データをAPI向けに変換するサービス
import {forkJoin, from, of} from 'rxjs';                                                               // forkJoinは複数API完了待ち、from/ofは値をObservable化
import {emptyAction} from '~/app.constants';                                                           // 分岐でActionを出す必要がないときの空Action
import {ReplaceHyperparamsEnum} from '~/business-logic/model/tasks/replaceHyperparamsEnum';            // ハイパーパラメータの置換範囲を指定する列挙型
import {Router} from '@angular/router';                                                                // 画面遷移と現在URLの取得に使用
import {selectRouterConfig, selectRouterParams} from '../../core/reducers/router-reducer';             // ルート設定名とURLパラメータを読むセレクタ
import {cloneDeep, get} from 'lodash-es';                                                              // 設定の深いコピーとStateのネスト値取得に使用
import {CommonExperimentReverterService} from '../shared/services/common-experiment-reverter.service'; // 読み取り専用実験の表示用補正サービス
import {resetOutput} from '../actions/common-experiment-output.actions';                               // 実験再開時にログ出力を消すAction
import {HttpErrorResponse} from '@angular/common/http';                                                // HTTPエラーの型
import {selectHasDataFeature} from '~/core/reducers/users.reducer';                                    // データセット機能の有無を示すセレクタ
import {selectSelectedProject} from '../../core/reducers/projects.reducer';                            // 現在のプロジェクトが選ばれているかを確認
import {PIPELINE_INFO_ONLY_FIELDS} from '@common/pipelines-controller/controllers.consts';             // Pipeline画面で取得するフィールド一覧
import {TasksGetByIdExResponse} from '~/business-logic/model/tasks/tasksGetByIdExResponse';            // ID指定のタスク取得APIの応答型
import {ARTIFACTS_ONLY_FIELDS} from '@common/experiments/experiment.consts';                           // Artifacts表示に必要なフィールド一覧
import {ITask} from '~/business-logic/model/al-task';                                                  // Artifacts整形処理に渡すタスク型
import {RefreshService} from '@common/core/services/refresh.service';                                  // 自動更新の発生を通知するサービス
import {downloadObjectAsJson} from '@common/experiments/shared/common-experiments.utils';              // JavaScriptオブジェクトをJSONファイルとして保存
import {buildTaskExportData, generateTaskExportFilename} from '@common/experiments/shared/task-export.utils'; // タスク書き出し用データとファイル名を生成
import {selectActiveWorkspace} from '@common/core/reducers/users-reducer';                             // 認証ヘッダー用のアクティブWorkspace
import {fromFetch} from 'rxjs/fetch';                                                                  // Fetch APIをObservableとして使う
import {isFileserverUrl} from '~/shared/utils/url';                                                    // URLがClearMLファイルサーバーか判定
import {getExtraHeaders} from '@features/experiments/shared/experiments.utils';                        // Workspaceに応じたリクエストヘッダーを生成
import {MESSAGES_SEVERITY} from '@common/constants';                                                   // 警告メッセージの重要度を指定
import {Task} from '~/business-logic/model/tasks/task';                                                // Pipeline本体と各ステップのタスク型
import {TasksGetAllExResponse} from '~/business-logic/model/tasks/tasksGetAllExResponse';              // 複数タスク取得APIの応答型
import {TaskStatusEnum} from '~/business-logic/model/tasks/taskStatusEnum';                            // Stopped状態の判定に使用
import {UserPreferences} from '@common/user-preferences';                                              // 利用者の設定を永続化するサービス
import {TaskTypeEnum} from '~/business-logic/model/tasks/taskTypeEnum';                                // データ処理タスクかどうかの判定に使用


@Injectable()                                                                                          // このクラスをAngularのDIで生成可能にする
export class CommonExperimentsInfoEffects {                                                            // 実験詳細の取得・更新・ダウンロードをActionから実行するEffect群
  private previousSelectedLastUpdate: Date = null;                                                     // 前回取得した選択実験の最終変更時刻。自動更新判定に使用
  private previousSelectedId: string;                                                                  // 実験の選択切替を検出するため前回IDを保持
  private userPreferences = inject(UserPreferences);                                                   // タブ位置などの利用者設定を書き込むサービス


  constructor(                                                                                         // 各Effectから使う依存をコンストラクタで受け取る
    private actions$: Actions,                                                                         // すべてのActionを流すObservable
    private store: Store,                                                                              // 選択中実験やフォーム値を参照するStore
    private apiTasks: ApiTasksService,                                                                 // タスク取得・編集APIを呼び出す
    private reverter: ExperimentReverterService,                                                       // 取得した実験をフォーム用データへ変換
    private converter: ExperimentConverterService,                                                     // フォーム値をAPI用データへ変換
    private router: Router,                                                                            // 取得対象が見つからない場合などに画面遷移
    private commonExperimentReverterService: CommonExperimentReverterService,                          // 読み取り専用実験の表示用補正を担当
    private refreshService: RefreshService                                                             // 自動更新をほかの画面処理へ通知
  ) {
  }

  activeLoader = createEffect(() => this.actions$.pipe(                                                // 取得系Actionの実行中表示を開始するEffect
    ofType(commonInfoActions.getExperimentInfo, commonInfoActions.getSelectedPipelineStep, getExperimentConfigurationNames, // 詳細・ステップ・設定名の取得開始を監視
      commonInfoActions.getExperiment, getPipelineConfigurationObj, commonInfoActions.getExperimentUncommittedChanges), // 実験本体・Pipeline設定・差分取得も監視
    filter(action => !action?.['autoRefresh']),                                                        // 自動更新ならローディング表示を省く
    map(action => activeLoader(action.type))                                                           // Action種別をキーにしてローダー開始Actionへ変換
  ));


  private getPathsFromAction(action): string[] {                                                       // Actionに応じて保存先の設定パスを返す
    switch (action.type) {                                                                             // Action種別で設定パスを選ぶ
      case setLastTasksTab.type:                                                                       // 最後に開いたタブの変更Action
        return [`experiments.info.lastTab.${action.projectId}`];                                       // プロジェクトごとに最後のタブを分けて保存
    }
    return [];                                                                                         // 対応しないActionなら保存先なし
  }

  setUserPreferences = createEffect(() => this.actions$.pipe(                                          // タブ変更を利用者設定へ反映するEffect
    ofType(setLastTasksTab),                                                                           // 最後に開いたタブが更新されたときだけ動く
    concatLatestFrom(() => this.store.select(experimentInfo)),                                         // Action処理時の実験情報Stateを読む
    map(([action, state]) => {                                                                         // ActionとStateから保存値を組み立てる
      const paths = this.getPathsFromAction(action);                                                   // 保存すべき設定パスを取得
      paths.forEach(path => this.userPreferences.setPreferences(path, get(state, path.split('.').slice(2).join('.')))); // パス先のState値を取り出して設定へ保存。先頭2階層はState内の経路から除く
    })), {dispatch: false});                                                                           // 設定保存だけを行いActionはdispatchしない


  getExperimentConfigurationNames$ = createEffect(() => this.actions$.pipe(                            // サーバー上の設定名一覧と手元の設定を同期するEffect
    ofType(getExperimentConfigurationNames),                                                           // 設定名取得Actionを監視
    concatLatestFrom(() => [                                                                           // 関連するStore値をAction時点で取得
      this.store.select(selectSelectedExperimentFromRouter),                                           // URLから対象実験IDを取得
      this.store.select(selectExperimentConfiguration),                                                // 現在Storeにある設定一覧を取得
      this.store.select(selectExperimentSelectedConfigObjectFromRoute)                                 // URL上で選択中の設定名を取得
    ]),
    filter(([, experimentId]) => !!experimentId),                                                      // 実験IDがない間はAPIを呼ばない
    switchMap(([action, experimentId, configuration, selectedConfiguration]) => this.apiTasks.tasksGetConfigurationNames({ // 新しい要求では以前の取得を取り消して設定名APIを呼ぶ
        tasks: [experimentId],                                                                         // 対象タスクを1件指定
        skip_empty: false                                                                              // 値が空の設定も名前一覧に含める
      })
        .pipe(
          mergeMap(res => {                                                                            // API結果を複数Actionに展開
            let configurations = cloneDeep(configuration);                                             // 元の設定Stateを直接変えないよう深くコピー
            if (configurations) {                                                                      // 既存の設定一覧がある場合
              Object.keys(configurations).forEach(name => {                                            // 保持中の各設定名を確認
                if (!res.configurations[0]?.names.includes(name)) {                                    // サーバーの名前一覧に存在しない項目を検出
                  delete configurations.name;                                                          // 実装上は固定のnameプロパティを削除。ループ変数の項目は削除されない
                }
              });
            } else {                                                                                   // 設定Stateがない場合は空の一覧を作る
              configurations = {};                                                                     // 新しい設定一覧の入れ物
            }
            res.configurations[0]?.names.forEach(name => {                                             // サーバーにある各設定名を確認
              if (!(name in configurations)) {                                                         // Storeにまだない名前だけ追加
                configurations[name] = null;                                                           // 本体は後で取得するため、まずnullで場所を確保
              }
            });
            return [                                                                                   // State更新などのActionを順に出す
              commonInfoActions.updateExperimentInfoData({                                             // 実験情報の設定一覧を更新
                id: experimentId,                                                                      // 更新対象の実験ID
                changes: {configuration: configurations}                                               // 同期後の設定一覧をStateへ渡す
              }),
              selectedConfiguration ? getExperimentConfigurationObj() : emptyAction(),                 // 設定が選択済みならその本体を取得する。未選択なら空Action
              deactivateLoader(action.type)                                                            // 設定名取得のローディングを終了
            ];
          }),
          catchError(error => [                                                                        // API失敗を画面用Action群に変換
            requestFailed(error),                                                                      // 共通のHTTP失敗処理へ渡す
            deactivateLoader(action.type),                                                             // 失敗してもローディングは終了
            addMessage('warn', 'Fetch configuration names failed', [{                                  // 警告を表示し、詳細を開く操作を付ける
              name: 'More info',                                                                       // 詳細操作の表示名
              actions: [setServerError(error, null, 'Fetch configuration names failed')]               // 詳細操作から同じエラーを開けるようにする
            }])
          ])
        )
    )
  ));

  getExperimentConfigurationObj$ = createEffect(() => this.actions$.pipe(                              // 選択した設定オブジェクトの中身を取得するEffect
    ofType(getExperimentConfigurationObj, getPipelineConfigurationObj),                                // 通常の設定取得とPipeline設定取得の両方を監視
    concatLatestFrom(() => [                                                                           // APIに必要なStore値をAction時点で取得
      this.store.select(selectSelectedExperimentFromRouter),                                           // 対象実験ID
      this.store.select(selectExperimentConfiguration),                                                // 既存の設定一覧
      this.store.select(selectExperimentSelectedConfigObjectFromRoute)                                 // URLで選択中の設定名
    ]),
    filter(([action, , configuration, configObj]) => (configuration && configObj && (configObj in configuration)) || action.type === getPipelineConfigurationObj.type), // 既存一覧に選択名があるか、Pipeline取得なら続行
    switchMap(([action, experimentId, configuration, configObj]) => this.apiTasks.tasksGetConfigurations({ // 要求切替時に前の取得を止めて設定本体APIを呼ぶ
        tasks: [experimentId],                                                                         // 対象タスクID
        names: [action.type === getPipelineConfigurationObj.type ? 'Pipeline' : configObj]             // Pipeline取得なら固定名、通常取得ならURL上の設定名
      })
        .pipe(
          mergeMap(res => {                                                                            // API結果を更新Action群へ変換
            const configurationObj = {                                                                 // 変更する設定オブジェクトを作る
              ...configuration,                                                                        // それ以外の設定を維持
              [action.type === getPipelineConfigurationObj.type ? 'Pipeline' : configObj]: res.configurations[0].configuration[0] // 取得した1件を選択名の場所へ上書き
            };
            return [                                                                                   // 取得完了後に出すAction群
              commonInfoActions.updateExperimentInfoData({                                             // 実験情報の設定本体を更新
                id: experimentId,                                                                      // 更新対象の実験ID
                changes: {configuration: configurationObj}                                             // 既存設定に取得結果を合成した値
              }),
              deactivateLoader(getExperimentConfigurationObj.type),                                    // 通常設定取得のローダーを終了
              deactivateLoader(getPipelineConfigurationObj.type),                                      // Pipeline設定取得のローダーも終了
              setBackdrop({active: false}),                                                            // 編集用Backdropを閉じる
              deactivateEdit(),                                                                        // 編集モードを解除
              setExperimentSaving({saving: false})                                                     // 保存中フラグを下げる
            ];
          }),
          catchError(error => [                                                                        // 取得失敗時も画面状態を戻すAction群
            requestFailed(error),                                                                      // HTTP失敗を通知
            deactivateLoader(action.type),                                                             // 起点Actionのローダーを終了
            setBackdrop({active: false}),                                                              // Backdropを閉じる
            deactivateEdit(),                                                                          // 編集モードを解除
            setExperimentSaving({saving: false}),                                                      // 保存中フラグを下げる
            addMessage('warn', 'Fetch configuration failed', [{                                        // 設定取得失敗の警告と詳細操作を表示
              name: 'More info',                                                                       // 詳細操作の表示名
              actions: [setServerError(error, null, 'Fetch configuration failed')]                     // 詳細操作にサーバーエラー表示Actionを設定
            }])
          ])
        )
    )
  ));

  getPipelineStep$ = createEffect(() => this.actions$.pipe(                                            // 選択したPipelineステップを取得するEffect
    ofType(commonInfoActions.getSelectedPipelineStep),                                                 // ステップ取得Actionを監視
    concatLatestFrom(() => [                                                                           // 現在の画面種別を読む
      this.store.select(selectRouterConfig).pipe(map(config => !!config?.includes('pipelines')))       // ルート名にpipelinesを含むときPipeline画面と判定
    ]),
    switchMap(([action, pipeline]) => this.apiTasks.tasksGetByIdEx({                                   // ステップIDを指定して取得を開始。新要求で旧要求を切り替える
      id: [action.id],                                                                                 // Actionで指定されたステップID
      only_fields: pipeline ? PIPELINE_INFO_ONLY_FIELDS : ['name', 'comment', 'parent.name', 'parent.project.id', 'runtime', 'configuration', 'status'] // 画面種別に応じて必要なフィールドだけ取得
    }).pipe(
      mergeMap(res =>                                                                                  // 応答からステップ設定とローダー終了のActionを出す
        [commonInfoActions.setSelectedPipelineStep({step: res?.tasks[0]}), deactivateLoader(action.type)] // 取得した先頭タスクを選択ステップとして保存
      ),
      catchError(error => [                                                                            // 取得失敗時のAction群
        requestFailed(error),                                                                          // HTTP失敗を通知
        deactivateLoader(action.type)                                                                  // ステップ取得のローダーを終了
      ])
    ))
  ));

  getExperimentInfo$ = createEffect(() => this.actions$.pipe(                                          // 実験詳細の再取得が必要か判定するEffect
    ofType(commonInfoActions.getExperimentInfo, commonInfoActions.autoRefreshExperimentInfo, commonInfoActions.experimentUpdatedSuccessfully), // 初回取得・自動更新・保存成功を入口にする
    concatLatestFrom(() => [                                                                           // 再取得判定に使うStore値を合わせて読む
      this.store.select(selectSelectedTableExperiment),                                                // 表で現在選ばれている実験
      this.store.select(selectSelectedExperiment),                                                     // 詳細表示中の実験
      this.store.select(selectSelectedFromTable),                                                      // 表から選んだ実験のデータ
      this.store.select(selectExperimentInfoData),                                                     // すでに表示中の詳細データ
      this.store.select(selectAppVisible),                                                             // 画面が表示中かどうか
      this.store.select(selectRouterConfig).pipe(map(config => !!config?.includes('pipelines') || !!config?.includes('datasets'))) // PipelineかDatasetの専用画面か判定
    ]),
    switchMap(([action, tableSelected, selected, selectedExperimentFromTable, infoData, visible, customView]) => { // 実験選択と更新時刻の判定を開始。新Actionなら前処理を切り替える
      const currentSelected = tableSelected || selected;                                               // 表の選択を優先し、なければ詳細の選択を使う
      if (this.previousSelectedId && currentSelected?.id != this.previousSelectedId) {                 // 前回とは異なる実験に切り替わったか調べる
        this.previousSelectedLastUpdate = null;                                                        // 別実験の最終更新時刻を流用しないよう破棄
      }
      this.previousSelectedId = currentSelected?.id;                                                   // 今回の実験IDを次回比較用に保存
      if (!infoData || !currentSelected || !visible) {                                                 // 詳細データ・選択実験・画面表示のいずれかがない場合
        return of([action, null, tableSelected, selected, customView]);                                // 更新時刻なしとして後段へ渡し、ローダー終了経路を残す
      }

      return (selectedExperimentFromTable ?                                                            // 表由来の実験データがあればそれを使用
          of(selectedExperimentFromTable) :                                                            // すでにStoreにある実験データをObservable化
          this.apiTasks.tasksGetByIdEx({id: [selected.id], only_fields: ['last_change']})              // 表データがなければAPIから最終変更時刻だけ取得
            .pipe(map(res => res.tasks[0]))                                                            // API応答の先頭タスクを取り出す
      ).pipe(map(task => [action, task?.last_change ?? task?.last_update, task, selected, customView])); // last_changeを優先し、なければlast_updateを比較時刻に使う
    }),
    filter(([action, , tableSelected, selected]) => (action.type !== commonInfoActions.autoRefreshExperimentInfo.type || (!tableSelected) || (tableSelected?.id === selected?.id))), // 自動更新時に表の選択と詳細の選択が食い違う場合だけ除外
    // Can't have filter here because we need to deactivate loader
    // filter(([action, selected, updateTime]) => !selected || new Date(selected.last_change) < new Date(updateTime)),
    switchMap(([action, updateTime, tableSelected, selected, customView]) => {                         // 更新時刻を見て再取得Actionを出すか決める
      // else will deactivate loader
      if (                                                                                             // 再取得が必要になる条件を列挙
        !updateTime ||                                                                                 // 更新時刻が取れない場合は取得を試みる
        (new Date(this.previousSelectedLastUpdate) < new Date(updateTime)) ||                          // 前回取得よりサーバー側の変更が新しい場合
        action.type === commonInfoActions.experimentUpdatedSuccessfully.type                           // 保存成功なら時刻にかかわらず再取得
      ) {
        const autoRefresh = action.type === commonInfoActions.autoRefreshExperimentInfo.type || action['autoRefresh']; // Action種別またはフラグから自動更新かを判断
        if (action.type === commonInfoActions.autoRefreshExperimentInfo.type) {                        // 自動更新Actionの場合
          this.refreshService.trigger(true);                                                           // RefreshServiceにも更新発生を伝える
        }
        return [                                                                                       // 再取得が必要なときのAction群
          deactivateLoader(action.type),                                                               // 起点Actionのローダーを先に終了
          commonInfoActions.getExperiment({experimentId: action.id, autoRefresh}),                     // 実験本体の取得を要求。自動更新フラグも引き継ぐ
          ...(customView ? [] : [commonInfoActions.getExperimentUncommittedChanges({                   // Pipeline・Datasetの専用画面でなければ差分も取得
            experimentId: action.id,                                                                   // 差分取得の対象ID
            autoRefresh                                                                                // 差分取得側にも自動更新フラグを渡す
          })]),
          // clear log data if experiment was restarted
          ...(selected?.started && tableSelected?.started && selected.started !== tableSelected?.started ? [resetOutput()] : []) // 実験開始時刻が変わったら再実行とみなしログを消す
        ];
      } else {                                                                                         // 再取得不要の場合
        return [deactivateLoader(action.type)];                                                        // ローダー終了Actionだけは必ず出す
      }
    })
  ));


  fetchExperiment$ = createEffect(() => this.actions$.pipe(                                            // 実験本体をAPIから取得してStoreへ反映するEffect
    ofType(commonInfoActions.getExperiment),                                                           // 実験取得Actionを監視
    switchMap(action => this.store.select(selectSelectedProject).pipe(                                 // プロジェクト選択の確定を待つ
      filter(project => !!project),                                                                    // 未選択の間は先へ進まない
      take(1),                                                                                         // 選択された最初の1件だけを使う
      map(() => action))),                                                                             // 待機後に元のActionを後段へ戻す
    concatLatestFrom(() => [                                                                           // 取得フィールド選択に使うStore値を読む
      this.store.select(selectHasDataFeature),                                                         // データセット機能が使えるか
      this.store.select(selectRouterConfig).pipe(map(config => !!config?.includes('pipelines') || !!config?.includes('datasets'))) // Pipeline・Datasetの専用画面か
    ]),
    switchMap(([action, hasDataFeature, graphView]) => this.apiTasks.tasksGetByIdEx({                  // 新しい取得Actionで前回のAPI要求を切り替える
        id: [action.experimentId],                                                                     // 取得対象の実験ID

        only_fields: graphView ? PIPELINE_INFO_ONLY_FIELDS : getExperimentInfoOnlyFields(hasDataFeature) // 画面種別と機能に応じたフィールドだけ要求
      })
        .pipe(
          switchMap((res: TasksGetByIdExResponse) => {                                                 // API応答を後続処理に渡す前にPipelineステップを補正
            // fetch steps real status
            const task = res.tasks[0];                                                                 // 取得したタスク本体
            const ids = this.getPipelineStepsIds(task);                                                // 設定JSONに含まれるステップのジョブIDを抽出
            return graphView && task.status === TaskStatusEnum.Stopped && ids.length ?                 // 停止済みPipelineの専用画面でステップIDがある場合のみ追加取得
              this.apiTasks.tasksGetAllEx({                                                            // 各ステップの実際の状態をまとめて問い合わせる
                id: ids,                                                                               // 設定JSONから抽出したステップのID群
                only_fields: ['status'],                                                               // 状態だけ取得して通信量を抑える
                search_hidden: true                                                                    // 非表示ステップも検索対象にする
              }).pipe(
                map((steps: TasksGetAllExResponse) => steps?.tasks.length ?                            // ステップ取得結果が1件以上あるか判定
                  this.updateStepsStatus(task, steps.tasks) :                                          // 実際の状態をPipeline設定JSONへ反映
                  task)                                                                                // 取得結果が空なら元のタスクをそのまま使う
              ) :
              of(res.tasks[0]);                                                                        // 追加取得が不要なら元のタスクを返す
          }),
          concatLatestFrom(() => this.store.select(selectPipelineSelectedStep)),                       // 現在選択中のPipelineステップも取得
          mergeMap(([task, selectedStep]) => {                                                         // タスク取得結果を画面更新Actionへ展開
            if (task) {                                                                                // タスクが見つかった場合
              this.previousSelectedLastUpdate = task.last_change;                                      // 今回の最終変更時刻を次回の自動更新比較に保存
              let experiment = convertStopToComplete([task])[0];                                       // 表示用の完了状態へ変換
              experiment = this.commonExperimentReverterService.revertReadOnly(experiment);            // 読み取り専用実験を表示できる形へ補正
              return [                                                                                 // 詳細・一覧・画面状態を同期するAction群
                commonInfoActions.setExperimentInfoData({experiment: this.reverter.revertExperiment(experiment)}), // 編集フォームに使う実験データを保存
                commonInfoActions.setExperiment({experiment}),                                         // 選択中実験の表示用データを保存
                updateExperiment({id: action.experimentId, changes: experiment}),                      // 一覧側の同じ実験にも変更を反映
                deactivateLoader(action.type),                                                         // 実験取得ローダーを終了
                deactivateLoader(commonInfoActions.getExperimentInfo.type),                            // 詳細取得ローダーも終了
                setBackdrop({active: false}),                                                          // Backdropを閉じる
                deactivateEdit(),                                                                      // 編集モードを解除
                setExperimentSaving({saving: false}),                                                  // 保存中フラグを下げる
                graphView && selectedStep?.id ? getSelectedPipelineStep({id: selectedStep.id}) : emptyAction() // 専用画面でステップ選択中ならそのステップを再取得
              ];
            } else {                                                                                   // 対象タスクが見つからなかった場合
              this.router.navigate(['']);                                                              // トップへ戻る
              return [deactivateLoader(action.type)];                                                  // 起点Actionのローダーを終了
            }
          }),
          catchError(error => [                                                                        // 実験本体の取得に失敗した場合
            requestFailed(error),                                                                      // HTTP失敗を通知
            deactivateLoader(action.type),                                                             // 実験取得ローダーを終了
            deactivateLoader(commonInfoActions.getExperimentInfo.type),                                // 詳細取得ローダーも終了
            ...(action.autoRefresh ? [] : [setServerError(error, null, 'Fetch task failed')])          // 自動更新時はエラー表示を省き、手動取得時のみ通知
          ])
        )
    )
  ));

  fetchDiff$ = createEffect(() => this.actions$.pipe(                                                  // 未コミットのコード差分だけを取得するEffect
    ofType(commonInfoActions.getExperimentUncommittedChanges),                                         // 差分取得Actionを監視
    switchMap((action) =>                                                                              // 新Actionが来たら前回の取得から切り替える

      this.apiTasks.tasksGetByIdEx({id: [action.experimentId], only_fields: ['script.diff']})          // script.diffだけを対象実験から取得
        .pipe(
          mergeMap(res => {                                                                            // 応答をActionに変換
            const experiment = res.tasks[0];                                                           // 取得した先頭の実験
            return [                                                                                   // 差分保存とローダー終了のAction群
              commonInfoActions.setExperimentUncommittedChanges({diff: experiment?.script?.diff}),     // script.diffをStoreへ保存
              deactivateLoader(action.type)                                                            // 差分取得ローダーを終了
            ];
          }),
          catchError(() => [                                                                           // 失敗時は差分を空文字へ戻す
            commonInfoActions.setExperimentUncommittedChanges({diff: ''}),                             // 前回の差分を画面に残さない
            deactivateLoader(action.type)                                                              // 失敗してもローダーを終了
          ])
        )
    )
  ));

  fetchArtifacts$ = createEffect(() => this.actions$.pipe(                                             // Artifactsの表示データを取得するEffect
    ofType(commonInfoActions.getExperimentArtifacts),                                                  // Artifacts取得Actionを監視
    switchMap((action) =>                                                                              // 新Actionが来たら前回の取得から切り替える

      this.apiTasks.tasksGetByIdEx({id: [action.experimentId], only_fields: ARTIFACTS_ONLY_FIELDS})    // Artifactsに必要なフィールドだけ取得
        .pipe(
          mergeMap((res: TasksGetByIdExResponse) => {                                                  // 応答からStore更新Actionを作る
            const experiment = res.tasks[0] as unknown as ITask;                                       // 先頭のタスクをモデル整形用の型として扱う
            return [commonInfoActions.setExperimentArtifacts({                                         // 整形済みArtifactsをStoreへ渡す
              model: this.reverter.commonExperimentReverterService.revertModel(experiment),            // タスク内のモデル情報を表示向けに変換
              experimentId: action.experimentId                                                        // 取得した実験のIDを添える
            })];
          }),
          catchError(e => [addMessage('error', e.toString())])                                         // 失敗内容をエラーメッセージとして表示
        )
    )
  ));

  downloadArtifact = createEffect(() => this.actions$.pipe(                                            // Artifactダウンロードを実行するEffect
    ofType(commonInfoActions.downloadArtifacts),                                                       // ダウンロードActionを監視
    filter(action => !!action.url),                                                                    // URLが空のActionは処理しない
    concatLatestFrom(() => this.store.select(selectActiveWorkspace)),                                  // 認証用ヘッダーに使うWorkspaceを取得
    switchMap(([action, workspace]) => action.inMemory ?                                               // メモリ上に取得する方式か、URLを直接開く方式か分岐
      fromFetch(action.url,                                                                            // 指定URLをFetchで取得
        {
          ...getExtraHeaders(workspace?.id),                                                           // Workspaceに応じた認証ヘッダーを追加
          method: 'GET',                                                                               // HTTP GETでファイルを取得
          credentials: 'include',                                                                      // Cookieなどの認証情報を送る
          mode: 'cors'                                                                                 // クロスオリジン要求として実行
        })
        .pipe(
          switchMap(res => from(res.blob()).pipe(                                                      // Fetch応答をBlobへ変換
            map(fileBlob => {                                                                          // Blobごとにダウンロード処理を実行
              const url = window.URL.createObjectURL(fileBlob);                                        // Blobをブラウザー内の一時URLにする
              const a = document.createElement('a');                                                   // ダウンロードに使うリンク要素を作成
              a.href = url;                                                                            // リンク先にBlobの一時URLを設定
              a.target = '_blank';                                                                     // 新しいタブを対象にする
              const header = res.headers.get('Content-Disposition');                                   // 応答ヘッダーからファイル名を取得
              const parts = header!.split(';');                                                        // Content-Dispositionをセミコロンで分割
              a.download = parts[1].split('=')[1];                                                     // 2番目の要素の=以降をファイル名に使う
              a.click();                                                                               // リンクをクリックして保存を開始
            })
          )),
          catchError(() => of(action.url))                                                             // Fetch失敗時は元URLを流し、後段で再試行Actionにする
        ) :
      of(null)                                                                                         // メモリ取得しない場合は同期処理をObservable化
        .pipe(map(() => {                                                                              // URLを開く処理をmap内で実行
          const src = new URL(action.url);                                                             // 指定URLをURLオブジェクトへ変換
          if (isFileserverUrl(action.url)) {                                                           // ClearMLファイルサーバーのURLか判定
            src.searchParams.set('download', '');                                                      // downloadクエリを付けて添付ファイルとして要求
          }
          const a = document.createElement('a') as HTMLAnchorElement;                                  // 直接開くためのリンクを作成
          a.target = '_blank';                                                                         // リンクを新しいタブで開く
          a.href = src.toString();                                                                     // クエリ加工後のURLを設定
          a.click();                                                                                   // クリックしてダウンロードを開始
        }))
    ),
    catchError(() => of(commonInfoActions.downloadFailed())),                                          // ここまでで投げられたエラーを失敗Actionへ変換
    map((status: string) => status ?                                                                   // 戻り値の真偽で分岐。Actionオブジェクトも真値になる
      commonInfoActions.downloadArtifacts({url: status}) :                                             // 真値をurlへ入れてダウンロードActionを再発行
      commonInfoActions.downloadSuccess())                                                             // 正常終了なら成功Actionを出す
  ));


  // Changes fields which can be applied regardless of experiment draft state i.e name, comments, tags
  updateExperimentDetails$ = createEffect(() => this.actions$.pipe(                                    // 下書き状態に関係なく変更可能な詳細項目を保存するEffect
    ofType(experimentDetailsUpdated),                                                                  // 名前・コメント・タグ等の変更Actionを監視
    concatLatestFrom(() => [                                                                           // 保存可否と選択状態を取得
      this.store.select(selectExperimentInfoData),                                                     // 編集中の実験情報を取得。後段では参照していない
      this.store.select(selectSelectedExperiment),                                                     // 詳細表示中の実験を取得
      this.store.select(selectExperimentFormValidity)                                                  // フォームの妥当性を取得
    ]),
    filter(([, , , valid]) => valid),                                                                  // 入力が不正なら保存しない
    mergeMap(([action, , selectedExperiment]) =>                                                       // 変更ActionごとにAPI更新を並行実行できる演算子
      this.apiTasks.tasksUpdate({task: action.id, ...action.changes})                                  // ActionのIDと変更項目をtasks.updateへ送る
        .pipe(
          mergeMap((res) => {                                                                          // API応答をStore反映Actionへ展開
            const changes = res?.fields || action.changes;                                             // APIが返した更新済みフィールドを優先
            return [                                                                                   // 成功後に発行するAction群
              commonInfoActions.experimentUpdatedSuccessfully({id: action.id}),                        // 詳細を再取得する成功通知
              updateExperiment({id: action.id, changes}),                                              // 一覧側の実験にも変更を反映
              ...(selectedExperiment?.id === action.id ?                                               // 変更対象が現在の詳細表示中実験なら
                  [commonInfoActions.updateExperimentInfoData({id: action.id, changes})] :             // 詳細フォームの値も同時に更新
                  []
              ),
              ...(changes.tags ? [getTags({})] : [])                                                   // タグが変わった場合だけ候補一覧を再取得
            ];
          }),
          catchError((err: HttpErrorResponse) => [                                                     // HTTP失敗を処理
            requestFailed(err),                                                                        // 共通の失敗通知
            setServerError(err, null, 'Update task failed'),                                           // 更新失敗を画面へ表示
            commonInfoActions.getExperimentInfo({id: action.id})                                       // 元データを取得し直して表示を戻す
          ])
        )
    )
  ));

  saveExperimentData$ = createEffect(() => this.actions$.pipe(                                         // 下書き実験の編集フォーム全体を保存するEffect
    ofType(saveExperiment),                                                                            // 実験全体の保存Actionを監視
    // Changes fields which can be applied Only on draft mode experiment
    concatLatestFrom(() => [                                                                           // 保存用データと妥当性をAction時点で取得
      this.store.select(selectExperimentInfoData),                                                     // 編集フォームの実験データ
      this.store.select(selectSelectedExperiment),                                                     // 保存対象の実験
      this.store.select(selectExperimentInfoDataFreeze),                                               // 編集開始時に固定したデータ
      this.store.select(selectExperimentFormValidity)                                                  // フォームの妥当性
    ]),
    filter(([, , , , valid]) => valid),                                                                // フォームが有効な場合だけAPIを呼ぶ
    switchMap(([, infoData, selectedExperiment, infoFreeze]) =>                                        // 新しい保存要求で前の要求から購読を切り替える
      this.apiTasks.tasksEdit(this.converter.convertExperiment(infoData, selectedExperiment, infoFreeze)) // フォーム値をAPI形式に変換してtasks.editへ送る
        .pipe(
          mergeMap(() => [                                                                             // 保存成功後にActionを出す
            commonInfoActions.experimentUpdatedSuccessfully({id: selectedExperiment.id})               // 実験を再取得する成功通知
          ]),
          catchError(err => [                                                                          // 保存失敗時のAction群
            requestFailed(err),                                                                        // 共通のHTTP失敗通知
            setServerError(err),                                                                       // サーバーエラーを表示
            commonInfoActions.experimentUpdatedSuccessfully({id: selectedExperiment.id}),              // 失敗後も再取得を要求して表示をサーバーに合わせる
            cancelExperimentEdit(),                                                                    // 編集を取り消す
            setBackdrop({active: false})                                                               // Backdropを閉じる
          ])
        )
    ),
    shareReplay(1)                                                                                     // 最後の発行値を後からの購読へ再送する
  ));

  saveExperimentSectionData$ = createEffect(() => this.actions$.pipe(                                  // 実験の一部分だけを保存するEffect
    ofType(saveExperimentSection),                                                                     // セクション保存Actionを監視
    concatLatestFrom(() => [this.store.select(selectSelectedExperiment)]),                             // 保存対象の実験をStoreから取得
    switchMap(([action, selectedExperiment]) => {                                                      // Actionと選択実験からAPI要求を組み立てる
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const {type, parent, ...changes} = action;                                                       // Action型と親オブジェクトを分離し、残りを編集項目とする
      return this.apiTasks.tasksEdit({task: selectedExperiment.id, ...changes, ...(parent && {parent: parent.id})}) // 親があればIDに変換してtasks.editへ送る
        .pipe(
          mergeMap(() => 'models' in changes ?                                                         // modelsを変更した場合だけ後処理を分岐
            [
              commonInfoActions.getExperimentArtifacts({experimentId: selectedExperiment.id}),         // モデル更新後はArtifactsを取り直す
              deactivateEdit(),                                                                        // 編集モードを解除
              setBackdrop({active: false})                                                             // Backdropを閉じる
            ] :
            [commonInfoActions.experimentUpdatedSuccessfully({id: selectedExperiment.id})]             // models以外なら実験全体の再取得を通知
          ),
          catchError(err => [                                                                          // API失敗時の後処理
            requestFailed(err),                                                                        // HTTP失敗を通知
            setServerError(err),                                                                       // エラーを画面へ表示
            commonInfoActions.experimentUpdatedSuccessfully({id: selectedExperiment.id}),              // 失敗後も実験再取得を要求
            cancelExperimentEdit(),                                                                    // 編集を取り消す
            setBackdrop({active: false})                                                               // Backdropを閉じる
          ])
        );
    })
  ));

  saveExperimentHyperParams$ = createEffect(() => this.actions$.pipe(                                  // ハイパーパラメータの節を保存するEffect
    ofType(saveHyperParamsSection),                                                                    // 節保存Actionを監視
    concatLatestFrom(() => [                                                                           // 対象・妥当性・節名を取得
      this.store.select(selectSelectedExperiment),                                                     // 詳細表示中の実験
      this.store.select(selectExperimentFormValidity),                                                 // フォームの妥当性
      this.store.select(selectExperimentHyperParamsSelectedSectionFromRoute)                           // URLで選択中のハイパーパラメータ節
    ]),
    filter(([, , valid]) => valid),                                                                    // フォームが有効な場合だけ続行
    switchMap(([action, selectedExperiment1, , section]) => {                                          // 保存対象と追加更新の要否を決める
        const selectedExperiment = action.task ?? selectedExperiment1;                                 // Actionにtaskがあればそれを優先
        const shouldUpdateRuntimeVersion = selectedExperiment.type === TaskTypeEnum.DataProcessing &&  // データ処理タスクでruntimeのversionが存在するか確認
          selectedExperiment.runtime?.version && action.hyperparams.length === 1 && action.hyperparams[0].name === 'version'; // 変更がversionパラメータ1件だけならruntimeも同期対象
        return forkJoin([                                                                              // 必要なAPI処理がすべて終わるまでforkJoinで待つ
          this.apiTasks.tasksEditHyperParams({                                                         // ハイパーパラメータ節を編集
            task: selectedExperiment.id,                                                               // 対象タスクID
            hyperparams: action.hyperparams.length > 0 ? action.hyperparams : [{section}],             // 入力が空なら選択節だけを指定して置き換える
            replace_hyperparams: ReplaceHyperparamsEnum.Section                                        // 置換範囲を節単位に限定
          }),
          ...(shouldUpdateRuntimeVersion ? [this.apiTasks.tasksEdit({                                  // version変更時だけruntime更新APIも追加
            force: true,                                                                               // 停止状態でも更新できるようforceを指定
            task: selectedExperiment.id,                                                               // runtimeを更新するタスクID
            runtime: {...selectedExperiment.runtime, version: action.hyperparams[0].value}             // 既存runtimeを保ちつつversionだけ新値に変更
          })] : [])                                                                                    // 追加APIが不要なら空配列を展開
        ])
          .pipe(
            mergeMap(() => [                                                                           // 両APIの完了後に成功Actionを出す
              commonInfoActions.experimentUpdatedSuccessfully({id: selectedExperiment.id})             // 保存後の実験を再取得
            ]),
            catchError(err => [                                                                        // いずれかのAPIが失敗した場合
              requestFailed(err),                                                                      // HTTP失敗を通知
              setServerError(err),                                                                     // エラーを画面へ表示
              commonInfoActions.experimentUpdatedSuccessfully({id: selectedExperiment.id}),            // 失敗後も実験を再取得
              cancelExperimentEdit(),                                                                  // 編集を取り消す
              setBackdrop({active: false})                                                             // Backdropを閉じる
            ])
          );
      }
    )
  ));

  saveExperimentConfigObj$ = createEffect(() => this.actions$.pipe(                                    // 設定オブジェクトを保存するEffect
    ofType(saveExperimentConfigObj),                                                                   // 設定保存Actionを監視
    concatLatestFrom(() => [                                                                           // URL上の対象実験IDを取得
      this.store.select(selectSelectedExperimentFromRouter)                                            // 編集対象の実験ID
    ]),
    switchMap(([action, selectedExperiment]) =>                                                        // 新しい保存要求で旧要求から切り替える
      this.apiTasks.tasksEditConfiguration({task: selectedExperiment, configuration: action.configuration}) // 設定内容をtasks.edit_configurationへ送る
        .pipe(
          mergeMap(() => [                                                                             // 保存完了後のAction群
            commonInfoActions.getExperimentConfigurationObj()                                          // 設定本体を再取得して表示へ反映
            // commonInfoActions.setExperimentSaving({saving: false}),
          ]),
          catchError(err => [                                                                          // 保存失敗時のAction群
            requestFailed(err),                                                                        // HTTP失敗を通知
            setServerError(err),                                                                       // エラーを画面へ表示
            commonInfoActions.getExperimentConfigurationObj(),                                         // 失敗後も設定本体を取り直す
            commonInfoActions.setExperimentSaving({saving: false}),                                    // 保存中フラグを下げる
            cancelExperimentEdit(),                                                                    // 編集を取り消す
            setBackdrop({active: false})                                                               // Backdropを閉じる
          ])
        )
    )
  ));

  deleteExperimentHyperParamsSection$ = createEffect(() => this.actions$.pipe(                         // ハイパーパラメータ節を削除するEffect
    ofType(deleteHyperParamsSection),                                                                  // 節削除Actionを監視
    concatLatestFrom(() => [                                                                           // 削除条件とURL上の節名を取得
      this.store.select(selectExperimentInfoData),                                                     // 実験情報データ。後段では参照していない
      this.store.select(selectSelectedExperiment),                                                     // 削除対象の実験
      this.store.select(selectExperimentInfoDataFreeze),                                               // 固定した編集元データ。後段では参照していない
      this.store.select(selectExperimentFormValidity),                                                 // フォームの妥当性
      this.store.select(selectRouterParams).pipe(map(params => params?.projectId)),                    // URL上のprojectId。後段では参照していない
      this.store.select(selectExperimentHyperParamsSelectedSectionFromRoute)                           // URLで選択中の節名
    ]),
    filter(([, , , , valid]) => valid),                                                                // フォームが有効な場合だけ削除
    switchMap(([action, , selectedExperiment, , , , section]) =>                                       // Actionの節を選択中実験から削除
      this.apiTasks.tasksDeleteHyperParams({task: selectedExperiment.id, hyperparams: [{section: action.section}]}) // taskと節名を指定して削除APIを呼ぶ
        .pipe(
          tap(() => this.router.navigateByUrl(this.router.url.replace('/hyper-param/' + section, ''))), // 削除後にURLから選択中の節部分を外す
          mergeMap(() => [                                                                             // 削除成功を受けてActionを出す
            commonInfoActions.experimentUpdatedSuccessfully({id: selectedExperiment.id})               // 実験を再取得して削除結果を表示へ反映
          ]),
          catchError(err => [                                                                          // 削除失敗時のAction群
            requestFailed(err),                                                                        // HTTP失敗を通知
            setServerError(err),                                                                       // エラーを画面へ表示
            commonInfoActions.experimentUpdatedSuccessfully({id: selectedExperiment.id}),              // 失敗後も実験を再取得
            cancelExperimentEdit(),                                                                    // 編集を取り消す
            setBackdrop({active: false})                                                               // Backdropを閉じる
          ])
        )
    )
  ));

  navigateToDataset = createEffect(() => this.actions$.pipe(                                           // 関連データセットの画面を開くEffect
    ofType(navigateToDataset),                                                                         // データセットへ移動するActionを監視
    switchMap(action => this.apiTasks.tasksGetByIdEx({                                                 // データセットタスクの情報を取得
      id: [action.datasetId],                                                                          // Actionで指定されたデータセットID
      only_fields: ['project.id']                                                                      // 遷移URLに必要なプロジェクトIDだけ要求
    })),
    map(res => {                                                                                       // 取得結果から遷移先を組み立てる
      if (res.tasks?.length > 0) {                                                                     // 対象データセットが見つかった場合
        const task = res.tasks[0];                                                                     // 取得した先頭タスクを使う
        const a = document.createElement('a');                                                         // 新規タブ用のリンク要素を作成
        a.href = `/datasets/simple/${task.project.id}/tasks/${task.id}`;                               // プロジェクトIDとタスクIDを含むURL
        a.target = '_blank';                                                                           // 新しいタブで開く
        a.click();                                                                                     // リンクをクリックして遷移
        return {type: 'none'};                                                                         // Effectに必要な空相当のActionを返す
      } else {                                                                                         // 対象が存在しない場合
        return addMessage(MESSAGES_SEVERITY.WARN, 'Dataset not found');                                // 見つからない旨の警告を表示
      }
    }),
    catchError(() => of(addMessage(MESSAGES_SEVERITY.WARN, 'Dataset not found')))                      // 取得エラーも同じ警告へ変換
  ));

  exportTaskInfo$ = createEffect(() => this.actions$.pipe(                                             // タスク情報をJSONで書き出すEffect
    ofType(commonInfoActions.exportTaskInfo),                                                          // エクスポートActionを監視
    concatLatestFrom(() => this.store.select(selectHasDataFeature)),                                   // データセット機能の有無を取得
    switchMap(([action, hasDataFeature]) =>                                                            // Actionごとに対象タスクの取得を開始
      this.apiTasks.tasksGetByIdEx({                                                                   // 指定IDのタスクをAPIから取得
        id: [action.taskId],                                                                           // Actionで指定されたタスクID
        only_fields: getTaskExportOnlyFields(hasDataFeature)                                           // 機能に応じた書き出し用フィールドだけ要求
      }).pipe(
        mergeMap((res: TasksGetByIdExResponse) => {                                                    // 応答をダウンロード処理へ渡す
          const task = res.tasks[0];                                                                   // 取得した先頭タスク
          if (!task) {                                                                                 // 対象タスクがない場合
            return [addMessage('error', 'Task not found')];                                            // 見つからないエラーを表示
          }

          try {                                                                                        // 変換・保存時の例外を捕捉
            const exportData = buildTaskExportData(task);                                              // API応答からエクスポート用データを作る
            const filename = generateTaskExportFilename(task.id);                                      // タスクIDからダウンロード名を生成
            downloadObjectAsJson(exportData, filename, true);                                          // JSONファイルをブラウザーへ保存

            return [addMessage('success', `${action.exportType ?? 'Task'} exported successfully`)];    // 成功メッセージ。種別未指定時はTaskと表示
          } catch (error) {                                                                            // 変換・保存処理が失敗した場合
            console.error('Export failed:', error);                                                    // 失敗内容を開発者コンソールへ記録
            return [addMessage('error', 'Failed to export task. Please try again.')];                  // 利用者に書き出し失敗を表示
          }
        }),
        catchError(error => [                                                                          // タスク取得API自体の失敗を捕捉
          requestFailed(error),                                                                        // 共通のHTTP失敗通知
          addMessage('error', 'Failed to export task. Please try again.')                              // 利用者にも書き出し失敗を表示
        ])
      )
    )
  ));

  private getPipelineStepsIds(task: Task) {                                                            // Pipeline設定からステップのジョブID一覧を返す補助メソッド
    if (!task.runtime._pipeline_hash) {                                                                // Pipelineハッシュがないタスクを除外
      return [];                                                                                       // Pipeline構成なしならID一覧は空
    }
    const pipelineStr = task?.configuration?.Pipeline?.value;                                          // 設定内のPipeline JSON文字列を取得
    try {                                                                                              // JSON解析失敗に備える
      const pipelineObj: Record<string, TreeStep> = JSON.parse(pipelineStr);                           // 文字列をステップIDからTreeStepへの辞書へ変換
      return Object.values(pipelineObj).map(step => step.job_id);                                      // 各ステップのjob_idを追加API用に抽出
    } catch {                                                                                          // 構成JSONを解析できなかった場合
      return [];                                                                                       // 追加取得せず空配列を返す
    }
  }

  private updateStepsStatus(task: Task, steps: Task[]) {                                               // APIで取得した実ステータスをPipeline設定へ反映する補助メソッド
    const pipelineStr = task?.configuration?.Pipeline?.value;                                          // 元のPipeline構成JSONを取得
    let pipelineObj: Record<string, TreeStep>;                                                         // 解析後のステップ辞書を入れる変数
    try {                                                                                              // JSON解析失敗に備える
      pipelineObj = JSON.parse(pipelineStr);                                                           // Pipeline構成を辞書に戻す
    } catch {                                                                                          // 解析に失敗した場合
      return task;                                                                                     // タスクをそのまま返す
    }
    const stepStatus = steps.reduce((acc, step) => {                                                   // 取得済みステップをIDから状態への辞書にまとめる
      acc[step.id] = step.status;                                                                      // タスクIDをキーに状態を保存
      return acc;                                                                                      // 次のreduceへ集計結果を返す
    }, {});                                                                                             // タスクIDから状態への辞書の初期値は空オブジェクト
    pipelineObj = Object.entries(pipelineObj).reduce((acc, [id, step]: [string, TreeStep]) => {        // 設定内の全ステップを順に更新
      acc[id] = {...step, status: stepStatus[step.job_id] ?? step.status};                             // 取得した状態があれば優先し、なければ設定内の元状態を保つ
      return acc;                                                                                      // 更新済み辞書を次の反復へ渡す
    }, {});                                                                                             // 更新済みステップ辞書の初期値は空オブジェクト
    task.configuration.Pipeline.value = JSON.stringify(pipelineObj);                                   // 更新済みステップ辞書をJSONに戻してタスクへ書き込む
    return task;                                                                                       // ステップ状態を反映したタスクを返す
  }
}
````

## このファイルの役割

`CommonExperimentsInfoEffects` は、実験詳細画面に関する NgRx Action を受け、API 呼び出しやブラウザー操作を行って、結果を再び Action として Store に戻す。主な経路は次のとおり。

- **取得**: `getExperimentInfo$` が更新の必要性を判定し、`fetchExperiment$` が実験本体を取得する。設定名・設定本体・差分・Artifacts・Pipeline ステップは専用の Effect が別途取得する。
- **保存**: 更新できる項目は `updateExperimentDetails$` の `tasksUpdate`、下書きの編集内容は `saveExperimentData$` などの `tasksEdit` 系 API で保存する。保存後は再取得 Action を出して表示をサーバーに合わせる。
- **ブラウザー操作**: Artifact のダウンロード、データセット画面の新規タブ表示、タスク情報の JSON 書き出しもここで行う。

## RxJS の読み方

`ofType` は入口となる Action を選び、`concatLatestFrom` はその時点の Store 値を添える。`switchMap` は新しい要求が来ると前の購読を切り替える。`mergeMap` は応答から複数の Action を流す場面で使われる。`catchError` は通信失敗を Action に変え、Effect の流れがそこで終わらないようにする。

## 読むときに注意する箇所

- 147行の `delete configurations.name` は、ループ中の `name` をキーにしていない。サーバーから消えた設定名を削除したい意図に見えるが、実際には固定の `name` プロパティだけを削除する。
- 442〜445行では `catchError` が `downloadFailed()` の Action オブジェクトを返した場合も、次の `map` は真値として扱う。その値を `downloadArtifacts` の `url` に入れる経路になるため、期待する失敗 Action にならない可能性がある。
- 保存失敗時にも `experimentUpdatedSuccessfully` を出す箇所がある。ここでは「保存成功」そのものではなく、サーバーの値を再取得して表示を戻す起点にも使われている。

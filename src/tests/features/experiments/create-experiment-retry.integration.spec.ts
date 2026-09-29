import {provideHttpClient} from '@angular/common/http'; //:: 実際の API サービスが使う HttpClient を登録
import {HttpTestingController, provideHttpClientTesting} from '@angular/common/http/testing'; //:: HTTP 通信を捕捉して応答を制御
import {TestBed} from '@angular/core/testing'; //:: Angular の依存関係をテスト用に構成
import {ActivatedRoute, Router} from '@angular/router'; //:: Effect が依存するルーター関連のトークン
import {provideMockActions} from '@ngrx/effects/testing'; //:: Effect に流すアクションをテストから指定
import {Action} from '@ngrx/store'; //:: 入出力アクションの型
import {MockStore, provideMockStore} from '@ngrx/store/testing'; //:: プロジェクト選択状態をテスト用に固定
import {Subject} from 'rxjs'; //:: 作成アクションを任意のタイミングで発行
import {describe, expect, it} from 'vitest'; //:: テストの定義と検証
import {ApiEventsService} from '~/business-logic/api-services/events.service'; //:: Effect の依存サービス
import {ApiOrganizationService} from '~/business-logic/api-services/organization.service'; //:: Effect の依存サービス
import {ApiProjectsService} from '~/business-logic/api-services/projects.service'; //:: Effect の依存サービス
import {ApiTasksService} from '~/business-logic/api-services/tasks.service'; //:: tasks.create を呼ぶ実サービス
import {MESSAGES_SEVERITY} from '~/app.constants'; //:: 失敗通知の重要度
import {addMessage} from '@common/core/actions/layout.actions'; //:: 失敗時に出る通知アクション
import {selectSelectedProjectId} from '@common/core/reducers/projects.reducer'; //:: 作成先プロジェクトのセレクタ
import * as exActions from '@common/experiments/actions/common-experiments-view.actions'; //:: 作成要求と成功のアクション
import {createExperimentDialogResult} from '@common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component'; //:: 作成フォームの入力型
import {CommonExperimentsViewEffects} from '@common/experiments/effects/common-experiments-view.effects'; //:: 検証対象の実際の Effect
import {UserPreferences} from '@common/user-preferences'; //:: Effect の依存サービス

describe('experiment creation retry with ApiTasksService', () => { //:: Effect と API サービスをつないだ再試行の検証
  it('HTTP 失敗後も同じ Effect から再送し、成功アクションを出す', () => { //:: 失敗で購読が終わらないことを確認
    const actions$ = new Subject<Action>(); //:: 同じ購読へ作成要求を2回流す

    TestBed.configureTestingModule({ //:: 実サービスとテスト用の入力・通信を組み合わせる
      providers: [ //:: Effect の依存を DI コンテナへ登録
        provideHttpClient(), //:: 実 ApiTasksService に HttpClient を供給
        provideHttpClientTesting(), //:: ネットワークへ出さず HTTP 応答を制御
        provideMockActions(() => actions$), //:: Effect の actions$ を手動発行する Subject に接続
        provideMockStore(), //:: Store の選択結果を後で固定
        CommonExperimentsViewEffects, //:: 実際の Effect を生成
        ApiTasksService, //:: tasksCreate の実装を差し替えずに使う
        {provide: ApiProjectsService, useValue: {}}, //:: このテストで使わない依存を代替
        {provide: ApiEventsService, useValue: {}}, //:: このテストで使わない依存を代替
        {provide: ApiOrganizationService, useValue: {}}, //:: このテストで使わない依存を代替
        {provide: Router, useValue: {}}, //:: このテストで使わない遷移機能を代替
        {provide: ActivatedRoute, useValue: {}}, //:: このテストで使わないルート情報を代替
        {provide: UserPreferences, useValue: {}} //:: このテストで使わない設定保存を代替
      ]
    });

    TestBed.inject(MockStore).overrideSelector(selectSelectedProjectId, 'project-id'); //:: 作成先を固定
    const http = TestBed.inject(HttpTestingController); //:: 実サービスが送る HTTP を検査
    const effects = TestBed.inject(CommonExperimentsViewEffects); //:: DI で構成した Effect を取得
    const output: Action[] = []; //:: Effect が発行したアクションを記録
    let completed = false; //:: Effect の購読終了を検知
    const subscription = effects.createExperiment.subscribe({ //:: 失敗と再試行を同じ購読で監視
      next: action => output.push(action), //:: 発行されたアクションを順に保存
      complete: () => completed = true //:: 外側のストリームが終わったか記録
    });
    const data: createExperimentDialogResult = { //:: 2回の作成要求に使うフォーム入力
      action: 'save', //:: 保存操作として送信
      name: 'retry task', //:: リクエスト本文の検証にも使うタスク名
      taskType: 'training', //:: 作成するタスクの種類
      repo: '', //:: リポジトリ指定なし
      type: 'branch', //:: コードの参照方法をブランチに指定
      branch: 'master', //:: 参照するブランチ
      commit: '', //:: コミット指定は使わない
      tag: '', //:: タグ指定は使わない
      directory: '', //:: 作業ディレクトリ指定なし
      script: '', //:: 起動スクリプト指定なし
      taskInit: false, //:: タスク初期化の強制なし
      args: [], //:: ハイパーパラメータなし
      poetry: false, //:: Poetry を使わない
      binary: 'python3', //:: 実行バイナリ
      venvType: 'discover', //:: 仮想環境は自動検出
      venv: '', //:: 手動の仮想環境指定なし
      requirements: 'skip', //:: 依存関係のインストールを省略
      pip: '', //:: 手動の pip 指定なし
      vars: [], //:: 追加の環境変数なし
      docker: {args: ''} //:: Docker の追加引数なし
    };

    actions$.next(exActions.createExperiment({data})); //:: 1回目の作成要求を発行
    const firstRequest = http.expectOne(request => request.method === 'POST' && request.url.endsWith('/tasks.create')); //:: 実サービスからの POST を捕捉
    expect(firstRequest.request.body).toMatchObject({project: 'project-id', name: 'retry task'}); //:: 作成先と名前が HTTP 本文に入ることを確認
    firstRequest.flush({meta: {result_msg: 'create failed'}}, {status: 500, statusText: 'Server Error'}); //:: 1回目だけ HTTP 500 を返す

    expect(output).toEqual([addMessage(MESSAGES_SEVERITY.ERROR, 'Failed to create tasks.\ncreate failed')]); //:: 失敗通知だけが発行されることを確認
    expect(completed).toBe(false); //:: 失敗後も Effect の購読が続くことを確認

    actions$.next(exActions.createExperiment({data})); //:: 同じ購読へ2回目の作成要求を発行
    const secondRequest = http.expectOne(request => request.method === 'POST' && request.url.endsWith('/tasks.create')); //:: 再送された POST を捕捉
    expect(secondRequest.request.body).toMatchObject({project: 'project-id', name: 'retry task'}); //:: 再送でも作成先と名前が正しいことを確認
    secondRequest.flush({data: {id: 'created-task'}, meta: {result_code: 200}}); //:: サーバー応答の data に採番 ID を入れて成功させる

    expect(output[1]).toEqual(exActions.createExperimentSuccess({ //:: 2回目の結果が成功アクションになることを検証
      data: {...data, id: 'created-task'}, //:: 入力にサーバー採番の ID が追加される
      project: 'project-id' //:: 作成先プロジェクトが引き継がれる
    }));
    expect(completed).toBe(false); //:: 成功後も Effect の購読が続くことを確認
    http.verify(); //:: 処理されていない HTTP リクエストがないことを確認
    subscription.unsubscribe(); //:: テストで開始した購読を解除
  });
});

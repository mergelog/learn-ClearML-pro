import {provideHttpClient} from '@angular/common/http';
import {HttpTestingController, provideHttpClientTesting} from '@angular/common/http/testing';
import {TestBed} from '@angular/core/testing';
import {ActivatedRoute, Router} from '@angular/router';
import {provideMockActions} from '@ngrx/effects/testing';
import {Action} from '@ngrx/store';
import {MockStore, provideMockStore} from '@ngrx/store/testing';
import {Subject} from 'rxjs';
import {describe, expect, it} from 'vitest';
import {ApiEventsService} from '~/business-logic/api-services/events.service';
import {ApiOrganizationService} from '~/business-logic/api-services/organization.service';
import {ApiProjectsService} from '~/business-logic/api-services/projects.service';
import {ApiTasksService} from '~/business-logic/api-services/tasks.service';
import {MESSAGES_SEVERITY} from '~/app.constants';
import {addMessage} from '@common/core/actions/layout.actions';
import {selectSelectedProjectId} from '@common/core/reducers/projects.reducer';
import * as exActions from '@common/experiments/actions/common-experiments-view.actions';
import {createExperimentDialogResult} from '@common/experiments/containers/create-experiment-dialog/create-experiment-dialog.component';
import {CommonExperimentsViewEffects} from '@common/experiments/effects/common-experiments-view.effects';
import {UserPreferences} from '@common/user-preferences';

describe('experiment creation retry with ApiTasksService', () => {
  it('HTTP 失敗後も同じ Effect から再送し、成功アクションを出す', () => {
    const actions$ = new Subject<Action>();

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideMockActions(() => actions$),
        provideMockStore(),
        CommonExperimentsViewEffects,
        ApiTasksService,
        {provide: ApiProjectsService, useValue: {}},
        {provide: ApiEventsService, useValue: {}},
        {provide: ApiOrganizationService, useValue: {}},
        {provide: Router, useValue: {}},
        {provide: ActivatedRoute, useValue: {}},
        {provide: UserPreferences, useValue: {}}
      ]
    });

    TestBed.inject(MockStore).overrideSelector(selectSelectedProjectId, 'project-id');
    const http = TestBed.inject(HttpTestingController);
    const effects = TestBed.inject(CommonExperimentsViewEffects);
    const output: Action[] = [];
    let completed = false;
    const subscription = effects.createExperiment.subscribe({
      next: action => output.push(action),
      complete: () => completed = true
    });
    const data: createExperimentDialogResult = {
      action: 'save',
      name: 'retry task',
      taskType: 'training',
      repo: '',
      type: 'branch',
      branch: 'master',
      commit: '',
      tag: '',
      directory: '',
      script: '',
      taskInit: false,
      args: [],
      poetry: false,
      binary: 'python3',
      venvType: 'discover',
      venv: '',
      requirements: 'skip',
      pip: '',
      vars: [],
      docker: {args: ''}
    };

    actions$.next(exActions.createExperiment({data}));
    const firstRequest = http.expectOne(request => request.method === 'POST' && request.url.endsWith('/tasks.create'));
    expect(firstRequest.request.body).toMatchObject({project: 'project-id', name: 'retry task'});
    firstRequest.flush({meta: {result_msg: 'create failed'}}, {status: 500, statusText: 'Server Error'});

    expect(output).toEqual([addMessage(MESSAGES_SEVERITY.ERROR, 'Failed to create tasks.\ncreate failed')]);
    expect(completed).toBe(false);

    actions$.next(exActions.createExperiment({data}));
    const secondRequest = http.expectOne(request => request.method === 'POST' && request.url.endsWith('/tasks.create'));
    expect(secondRequest.request.body).toMatchObject({project: 'project-id', name: 'retry task'});
    secondRequest.flush({data: {id: 'created-task'}, meta: {result_code: 200}});

    expect(output[1]).toEqual(exActions.createExperimentSuccess({
      data: {...data, id: 'created-task'},
      project: 'project-id'
    }));
    expect(completed).toBe(false);
    http.verify();
    subscription.unsubscribe();
  });
});

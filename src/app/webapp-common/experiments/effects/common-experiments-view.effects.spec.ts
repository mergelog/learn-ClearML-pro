import {TestBed} from '@angular/core/testing';
import {ActivatedRoute, Router} from '@angular/router';
import {provideMockActions} from '@ngrx/effects/testing';
import {Action} from '@ngrx/store';
import {MockStore, provideMockStore} from '@ngrx/store/testing';
import {of, Subject, throwError} from 'rxjs';
import {describe, expect, it, vi} from 'vitest';
import {ApiEventsService} from '~/business-logic/api-services/events.service';
import {ApiOrganizationService} from '~/business-logic/api-services/organization.service';
import {ApiProjectsService} from '~/business-logic/api-services/projects.service';
import {ApiTasksService} from '~/business-logic/api-services/tasks.service';
import {UserPreferences} from '@common/user-preferences';
import {ErrorService} from '@common/shared/services/error.service';
import {selectSelectedProjectId} from '../../core/reducers/projects.reducer';
import * as exActions from '../actions/common-experiments-view.actions';
import {createExperimentDialogResult} from '../containers/create-experiment-dialog/create-experiment-dialog.component';
import {CommonExperimentsViewEffects} from './common-experiments-view.effects';

describe('CommonExperimentsViewEffects.createExperiment', () => {
  it('API の失敗後も次の作成アクションを処理する', () => {
    const actions$ = new Subject<Action>();
    const tasksCreate = vi.fn()
      .mockReturnValueOnce(throwError(() => ({error: 'create failed'})))
      .mockReturnValueOnce(of({id: 'created-task'}));

    TestBed.configureTestingModule({
      providers: [
        CommonExperimentsViewEffects,
        provideMockActions(() => actions$),
        provideMockStore(),
        {provide: ApiTasksService, useValue: {tasksCreate}},
        {provide: ApiProjectsService, useValue: {}},
        {provide: ApiEventsService, useValue: {}},
        {provide: ApiOrganizationService, useValue: {}},
        {provide: Router, useValue: {}},
        {provide: ActivatedRoute, useValue: {}},
        {provide: ErrorService, useValue: {getErrorMsg: () => 'create failed'}},
        {provide: UserPreferences, useValue: {}}
      ]
    });

    TestBed.inject(MockStore).overrideSelector(selectSelectedProjectId, 'project-id');
    const effects = TestBed.inject(CommonExperimentsViewEffects);
    const output: Action[] = [];
    let completed = false;
    const subscription = effects.createExperiment.subscribe({
      next: action => output.push(action),
      complete: () => completed = true
    });
    const data: createExperimentDialogResult = {
      action: 'save',
      name: 'test task',
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
    expect(output).toHaveLength(1);
    expect(completed).toBe(false);

    actions$.next(exActions.createExperiment({data}));
    expect(tasksCreate).toHaveBeenCalledTimes(2);
    expect(output[1]).toEqual(exActions.createExperimentSuccess({
      data: {...data, id: 'created-task'},
      project: 'project-id'
    }));

    subscription.unsubscribe();
  });
});

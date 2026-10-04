"""Read-only recovery of stopped merge workers, including after source adoption."""
from __future__ import annotations

import copy

from .article_merge import _effect_name, _observed_merge
from .github import GitHubError
from .identity import SlotIdentity
from .jules import JulesError
from .policy import record_incident, seconds
from .state import StateInvalid


def observe_merge_effects(state, github, repo, main_sha):
    observations = []
    cache = {}
    for command in state['commands'].values():
        # Active workers retain ownership of their receipts. Once they stop,
        # reconciliation is independent of whether the slot adopted a source.
        if command['operation'] != 'merge_article' or command['outcome'] == 'pending':
            continue
        for name, effect in command['effects'].items():
            request = effect['request']
            if not request.get('validation') or name != _effect_name(request) or effect['receipt'] is not None:
                continue
            key = effect['request_sha256']
            if key not in cache:
                try:
                    result = _observed_merge(github, repo, request, main_sha=main_sha)
                    cache[key] = {'status': 'merged', 'evidence': result} if result else {'status': 'pending'}
                except JulesError as exc:
                    cache[key] = {'status': {'CODE_CHANGED': 'superseded', 'MERGE_RECORD_PENDING': 'pending'}.get(exc.failure_class, 'unknown')}
                except (GitHubError, OSError, ValueError, TypeError, KeyError, AttributeError):
                    cache[key] = {'status': 'unknown'}
            observations.append({'command_id': command['id'], 'effect_name': name,
                                 'request_sha256': key, **copy.deepcopy(cache[key])})
    return observations


def reconcile_merge_effects(state, observations, *, main_sha, now):
    if not isinstance(observations, list):
        raise StateInvalid('Malformed independent merge observation')
    for observed in observations:
        command = state['commands'].get(observed.get('command_id'))
        effect = (command or {}).get('effects', {}).get(observed.get('effect_name'))
        if (not command or command['operation'] != 'merge_article' or command['outcome'] == 'pending'
                or not effect or effect['request_sha256'] != observed.get('request_sha256')
                or observed['effect_name'] != _effect_name(effect['request'])):
            raise StateInvalid('Merge observation does not bind the exact stopped worker intent')
        request = effect['request']
        status = observed.get('status')
        if status == 'merged':
            receipt = {'status': 'merged', 'pr_number': int(request['pr_number']),
                       'merge_sha': request['head_sha'], 'tree_sha': request['tree_sha'],
                       'base_sha': request['base_sha'], 'validation': request['validation']}
            if observed.get('evidence') != receipt:
                raise StateInvalid('Independent merge evidence differs from saved validated intent')
        elif status == 'superseded':
            if main_sha in {request['base_sha'], request['head_sha']}:
                raise StateInvalid('Unchanged/merged main cannot supersede an intent')
            receipt = {'status': 'superseded', 'observed_main_sha': main_sha}
        elif status in {'pending', 'unknown'}:
            if seconds(now, effect['created_at']) >= 43200:
                record_incident(state, SlotIdentity(command['target']['slot']), 'merge_article',
                                'MERGE_OBSERVATION_STALLED', now=now,
                                evidence={'command_id': command['id'], 'effect_name': observed['effect_name']})
            continue
        else:
            raise StateInvalid('Unknown independent merge result')
        if effect['receipt'] is not None:
            if effect['receipt'] != receipt:
                raise StateInvalid('Conflicting independent merge receipt')
            continue
        effect['receipt'] = copy.deepcopy(receipt)
        # Keep the worker's actual failure/outcome. This later observation is a
        # separate audit event, not a fabricated successful workflow or public proof.
        state['audit'].append({'at': now, 'event': 'merge_intent_reconciled',
                               'command_id': command['id'], 'effect_name': observed['effect_name'], 'status': status})

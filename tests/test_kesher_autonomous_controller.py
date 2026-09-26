"""Controller-level regressions for overlapping schedulers and bounded exact recovery."""
import copy
import unittest
from datetime import datetime, timedelta

from scripts.kesher_runtime.controller import Observation, reconcile, run_tick
from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.identity import MediaIdentity, SlotIdentity, SourceIdentity
from scripts.kesher_runtime.state import StateConflict, StateInvalid, bind_source, new_state, plan_command
from tests.test_kesher_canonical_state import CODE, NOW, SOURCE, ContentsServer


def later(seconds):
    return (datetime.fromisoformat(NOW) + timedelta(seconds=seconds)).isoformat()


def publication(source=SOURCE, *, article='verified', overview='absent', short='absent'):
    def verdict(status, identity):
        if status == 'verified':
            return {'status': status, 'evidence': {'identity': identity.to_dict(), 'verifier_version': 2 if isinstance(identity, SourceIdentity) else 1,
                    'verified_at': NOW, 'public_url': 'https://example.test/exact', 'deploy_sha': CODE}}
        if status == 'absent':
            return {'status': status}
        return {'status': 'failed', 'failure_class': status}
    return {'source': source.to_dict(), 'main_sha': CODE, 'article': verdict(article, source),
            'media': {kind: verdict(value, MediaIdentity(source, kind))
                      for kind, value in [('overview', overview), ('short', short)]}}


def observed(*publications, now=NOW, current_slot=SOURCE.slot, runs=(), prs=()):
    publications = copy.deepcopy(publications)
    for publication in publications:
        for row in [publication['article'], *publication['media'].values()]:
            if row['status'] == 'verified':
                row['evidence']['verified_at'] = now
    return Observation({'observed_at': now, 'main_sha': CODE, 'current_slot': current_slot,
                        'publications': list(publications), 'runs': list(runs), 'article_prs': list(prs)})


class AutonomousControllerTests(unittest.TestCase):
    def test_new_main_deployment_does_not_inherit_old_revision_budget_or_stall_clock(self):
        state = bind_source(new_state(), SOURCE, now=NOW)
        for ordinal in (1, 2):
            state, key = plan_command(state, SOURCE, 'deploy_article', ordinal, {'deploy_sha': CODE}, code_sha=CODE, now=NOW)
            state['commands'][key]['outcome'] = 'failed'
            state['commands'][key]['failure'] = {'class': 'DEPLOY_FAILED'}
        state['sources'][SOURCE.key]['recovery'] = {'last_meaningful_progress_at': NOW}
        current = 'e'*40
        when = later(50000)
        entry = publication(article='ARTICLE_NOT_PUBLIC', overview='verified', short='verified')
        entry['main_sha'] = current
        observation = observed(entry, now=when).value
        observation['main_sha'] = current
        result = reconcile(state, Observation(observation), now=when)
        self.assertIsNotNone(result.command_id)
        command = result.state['commands'][result.command_id]
        self.assertEqual(command['operation'], 'deploy_article')
        self.assertEqual(command['inputs']['deploy_sha'], current)

    def test_merge_binds_body_and_validation_base_for_recovery(self):
        from scripts.kesher_runtime.worker import WorkerContext
        pr = {'slot': SOURCE.slot, 'number': 854, 'head_sha': CODE, 'status': 'ready_to_merge', 'body_sha256': '1'*64}
        first = reconcile(new_state(), observed(prs=[pr]), now=NOW)
        store = GitHubStateStore(ContentsServer(first.state), 'owner/repo')
        worker = WorkerContext(store, first.command_id, '1/1', SlotIdentity(SOURCE.slot), code_sha=CODE, now=lambda: NOW)
        worker.claim()
        worker.checkpoint('article_pr_settled', {'number': 854, 'head_sha': CODE, 'slot': SOURCE.slot, 'sessions': []}, phase='OUTPUT_CREATED')
        worker.finish()
        result = reconcile(store.load().state, observed(prs=[pr]), now=NOW)
        command = result.state['commands'][result.command_id]
        self.assertEqual(command['operation'], 'merge_article')
        self.assertEqual(command['inputs'].get('pr_body_sha256'), '1'*64)
        self.assertEqual(command['inputs'].get('validation_base_sha'), CODE)

    def test_article_mutation_requires_exact_head_jules_quiescence(self):
        for status in ('normalize_required', 'image_required', 'ci_required', 'ready_to_merge', 'ci_failed'):
            with self.subTest(status=status):
                pr = {'slot': SOURCE.slot, 'number': 854, 'head_sha': CODE, 'status': status}
                result = reconcile(new_state(), observed(prs=[pr]), now=NOW)
                self.assertEqual(result.state['commands'][result.command_id]['operation'], 'settle_article')

    def test_settled_article_moves_to_next_stage_without_previous_poll_backoff(self):
        from scripts.kesher_runtime.worker import WorkerContext
        pr = {'slot': SOURCE.slot, 'number': 854, 'head_sha': CODE, 'status': 'image_required'}
        first = reconcile(new_state(), observed(prs=[pr]), now=NOW)
        server = ContentsServer(first.state); store = GitHubStateStore(server, 'owner/repo')
        worker = WorkerContext(store, first.command_id, '1/1', SlotIdentity(SOURCE.slot), code_sha=CODE, now=lambda: NOW)
        worker.claim()
        worker.checkpoint('article_pr_settled', {'number': 854, 'head_sha': CODE, 'slot': SOURCE.slot, 'sessions': []}, phase='OUTPUT_CREATED')
        worker.checkpoint('execution_result', {'status': 'pr_ready'}, phase='OUTPUT_CREATED')
        worker.finish()
        result = reconcile(server.document, observed(prs=[pr]), now=NOW)
        self.assertEqual(result.state['commands'][result.command_id]['operation'], 'attach_image')
        changed = {**pr, 'head_sha': 'e'*40}
        server.document['commands'][result.command_id] = result.state['commands'][result.command_id]
        server.document['commands'][result.command_id]['outcome'] = 'succeeded'
        result = reconcile(server.document, observed(prs=[changed]), now=NOW)
        self.assertEqual(result.state['commands'][result.command_id]['operation'], 'settle_article')
        self.assertEqual(result.state['commands'][result.command_id]['inputs']['pr_head_sha'], changed['head_sha'])

    def test_observation_of_an_older_canonical_revision_cannot_drive_new_state(self):
        obs = observed(publication()).value
        obs['state_revision'] = 0
        state = new_state(); state['revision'] = 1
        with self.assertRaises(StateConflict):
            reconcile(state, Observation(obs), now=NOW)

    def test_article_validation_budget_is_bound_to_body_and_trusted_code_revision(self):
        from scripts.kesher_runtime.worker import WorkerContext
        pr = {'slot': SOURCE.slot, 'number': 854, 'head_sha': CODE, 'status': 'ci_required', 'body_sha256': '0'*64}
        first = reconcile(new_state(), observed(prs=[pr]), now=NOW)
        server = ContentsServer(first.state); store = GitHubStateStore(server, 'owner/repo')
        worker = WorkerContext(store, first.command_id, '1/1', SlotIdentity(SOURCE.slot), code_sha=CODE, now=lambda: NOW)
        worker.claim()
        worker.checkpoint('article_pr_settled', {'number': 854, 'head_sha': CODE, 'slot': SOURCE.slot, 'sessions': []}, phase='OUTPUT_CREATED')
        worker.finish()
        first = reconcile(store.load().state, observed(prs=[pr]), now=NOW)
        server.document = first.state
        worker = WorkerContext(store, first.command_id, '2/1', SlotIdentity(SOURCE.slot), code_sha=CODE, now=lambda: NOW)
        worker.claim(); worker.finish(failure={'class': 'CI_INPUT_CHANGED'})
        for changed in ('body', 'main'):
            with self.subTest(changed=changed):
                obs = observed(prs=[pr]).value
                if changed == 'body': obs['article_prs'][0]['body_sha256'] = '1'*64
                else: obs['main_sha'] = 'f'*40
                result = reconcile(store.load().state, Observation(obs), now=NOW)
                self.assertIsNotNone(result.command_id, 'A new immutable validation input needs its own budget')
                command = result.state['commands'][result.command_id]
                self.assertEqual(command['operation'], 'validate_article')
                self.assertEqual(command['inputs']['pr_body_sha256'], obs['article_prs'][0]['body_sha256'])
                self.assertEqual(command['code_sha'], obs['main_sha'])

    def test_creation_respects_publication_window_without_stopping_reconciliation(self):
        obs = observed().value; obs['article_creation_allowed'] = False
        result = reconcile(new_state(), Observation(obs), now=NOW)
        self.assertIsNone(result.command_id)

    def test_observed_slot_rotates_backlog_and_missing_adopted_source_is_incident(self):
        old = SourceIdentity('2026-09-16', 'old', 'b'*64)
        state = bind_source(new_state(), old, now=NOW)
        obs = observed(publication()).value; obs['missing_slots'] = [old.slot]
        result = reconcile(state, Observation(obs), now=NOW)
        self.assertEqual(result.state['slots'][SOURCE.slot]['observed_at'], NOW)
        self.assertEqual(result.state['slots'][old.slot]['observed_at'], NOW)
        self.assertTrue(any(row['failure_class'] == 'SOURCE_MISSING' for row in result.state['incidents'].values()))

    def test_independent_technical_receipt_is_saved_separately_from_worker_claims(self):
        from tests.test_kesher_media_publication import fixture
        from scripts.kesher_runtime.identity import digest
        args = fixture(); source = args['identity'].source
        pub = publication(source, overview='verified', short='PUBLIC_METADATA_INVALID')
        pub['media']['short']['technical_evidence'] = args['technical']
        result = reconcile(new_state(), observed(pub, current_slot=source.slot), now=NOW)
        saved = result.state['items'][args['identity'].key]['receipts']
        self.assertEqual(saved['technical:' + digest(args['technical'])], args['technical'])
        self.assertFalse(result.state['slots'][source.slot]['complete'])

    def test_transient_article_recovery_counts_actual_deploy_commands(self):
        state = new_state()
        for index in range(6):
            now = later(index * 4000)
            result = reconcile(state, observed(publication(article='TRANSIENT_API'), now=now), now=now)
            state = result.state
            if result.command_id:
                state['commands'][result.command_id]['outcome'] = 'failed'
                state['commands'][result.command_id]['failure'] = {'class': 'TRANSIENT_API'}
        self.assertEqual(len(state['commands']), 3)
        self.assertEqual(next(iter(state['incidents'].values()))['failure_class'], 'TRANSIENT_API')

    def test_two_schedulers_produce_same_exact_intent(self):
        obs = observed(publication())
        a = reconcile(new_state(), obs, now=NOW)
        b = reconcile(new_state(), obs, now=NOW)
        self.assertEqual(a.command_id, b.command_id)
        self.assertEqual(len(a.state['commands']), 1)
        command = a.state['commands'][a.command_id]
        self.assertEqual(command['target'], MediaIdentity(SOURCE, 'overview').to_dict())
        self.assertEqual(command['operation'], 'publish')
        self.assertEqual(command['inputs']['generation_attempt'], '1')
        self.assertIsNone(a.state['items'][MediaIdentity(SOURCE, 'overview').key]['phase'])

    def test_cas_conflict_never_dispatches_stale_plan(self):
        server = ContentsServer()
        store = GitHubStateStore(server, 'owner/repo')
        saved = store.save
        dispatched = []
        def conflict(loaded, proposed):
            server.sha = 'f' * 40
            return saved(loaded, proposed)
        store.save = conflict
        with self.assertRaises(StateConflict):
            run_tick(store, observed(publication()), now=NOW, dispatch=dispatched.append)
        self.assertEqual(dispatched, [])

    def test_current_pending_allows_exact_backlog_without_global_fifo(self):
        old = SourceIdentity('2026-09-16', 'older-exact', 'b' * 64)
        state = bind_source(new_state(), SOURCE, now=NOW)
        state, pending = plan_command(state, MediaIdentity(SOURCE, 'overview'), 'publish', 1, {}, code_sha=CODE, now=NOW)
        # The other current product has already been verified; only old work is eligible.
        result = reconcile(state, observed(publication(old), publication(short='verified')), now=NOW)
        self.assertNotEqual(result.command_id, pending)
        self.assertEqual(result.state['commands'][result.command_id]['target'], MediaIdentity(old, 'overview').to_dict())

    def test_alternating_fairness_preserves_current_priority_without_starving_backlog(self):
        old = SourceIdentity('2026-09-16', 'older', 'b' * 64)
        first = reconcile(new_state(), observed(publication(old), publication()), now=NOW)
        self.assertEqual(first.state['commands'][first.command_id]['target']['slot'], SOURCE.slot)
        second = reconcile(first.state, observed(publication(old), publication()), now=NOW)
        self.assertEqual(second.state['commands'][second.command_id]['target']['slot'], old.slot)
        third = reconcile(second.state, observed(publication(old), publication()), now=NOW)
        self.assertEqual(third.state['commands'][third.command_id]['target']['slot'], SOURCE.slot)

    def test_duplicate_daily_sources_are_quarantined_not_chosen_by_position(self):
        other = SourceIdentity(SOURCE.slot, 'other-article', 'b' * 64)
        result = reconcile(new_state(), observed(publication(), publication(other)), now=NOW)
        self.assertIsNone(result.command_id)
        self.assertNotIn(SOURCE.slot, result.state['slots'])
        self.assertEqual(len(result.state['incidents']), 1)
        self.assertEqual(next(iter(result.state['incidents'].values()))['failure_class'], 'SOURCE_AMBIGUOUS')

    def test_source_edit_does_not_adopt_old_upload_or_spend_new_budget(self):
        changed = SourceIdentity(SOURCE.slot, SOURCE.slug, 'd' * 64)
        state = bind_source(new_state(), SOURCE, now=NOW)
        result = reconcile(state, observed(publication(changed)), now=NOW)
        self.assertEqual(result.state['slots'][SOURCE.slot]['source_key'], changed.key)
        self.assertEqual(result.state['commands'][result.command_id]['target'], MediaIdentity(changed, 'overview').to_dict())
        self.assertEqual(result.state['commands'][result.command_id]['ordinal'], 1)
        self.assertIn(SOURCE.key, result.state['sources'])

    def test_workflow_green_is_never_public_delivery(self):
        state = bind_source(new_state(), SOURCE, now=NOW)
        state, command_id = plan_command(state, MediaIdentity(SOURCE, 'overview'), 'publish', 1, {}, code_sha=CODE, now=NOW)
        result = reconcile(state, observed(publication(), runs=[{'command_id': command_id, 'run_id': '123/1',
                           'code_sha': CODE, 'status': 'completed', 'conclusion': 'success'}]), now=NOW)
        self.assertFalse(result.state['slots'][SOURCE.slot].get('complete'))
        self.assertIsNone(result.state['items'][MediaIdentity(SOURCE, 'overview').key]['phase'])

    def test_only_fresh_matching_independent_abc_can_complete_and_revoke(self):
        result = reconcile(new_state(), observed(publication(overview='verified', short='verified')), now=NOW)
        self.assertTrue(result.state['slots'][SOURCE.slot]['complete'])
        self.assertIsNone(result.command_id)
        broken = reconcile(result.state, observed(publication(overview='verified', short='PUBLIC_METADATA_INVALID')), now=NOW)
        self.assertFalse(broken.state['slots'][SOURCE.slot]['complete'])
        self.assertEqual(broken.state['commands'][broken.command_id]['operation'], 'repair_metadata')
        self.assertEqual(broken.state['commands'][broken.command_id]['target']['kind'], 'short')
        wrong = publication(overview='verified', short='verified')
        wrong['media']['short']['evidence']['identity']['kind'] = 'overview'
        with self.assertRaises(StateInvalid):
            reconcile(new_state(), observed(wrong), now=NOW)
        with self.assertRaises(StateInvalid):
            reconcile(new_state(), observed(publication(), now=NOW), now=later(601))

    def test_duplicate_pr_and_existing_pr_adoption_do_not_start_jules_again(self):
        pr = {'slot': SOURCE.slot, 'number': 854, 'head_sha': CODE, 'status': 'pending'}
        result = reconcile(new_state(), observed(prs=[pr]), now=NOW)
        self.assertIsNone(result.command_id)
        self.assertEqual(result.state['slots'][SOURCE.slot]['article_pr']['number'], 854)
        duplicate = reconcile(new_state(), observed(prs=[pr, {**pr, 'number': 855}]), now=NOW)
        self.assertIsNone(duplicate.command_id)
        self.assertEqual(next(iter(duplicate.state['incidents'].values()))['failure_class'], 'DUPLICATE_PR')

    def test_empty_today_plans_one_article_command_and_duplicate_tick_reuses_it(self):
        first = reconcile(new_state(), observed(), now=NOW)
        command = first.state['commands'][first.command_id]
        self.assertEqual(command['target'], SlotIdentity(SOURCE.slot).to_dict())
        self.assertEqual(command['operation'], 'create_article')
        again = reconcile(first.state, observed(), now=NOW)
        self.assertEqual(len(again.state['commands']), 1)
        self.assertEqual(again.command_id, first.command_id)

    def test_metadata_recovery_has_finite_budget_and_one_software_incident(self):
        state = new_state()
        for index in range(8):
            now = later(index * 4000)
            obs = observed(publication(short='PUBLIC_METADATA_INVALID', overview='verified'), now=now)
            result = reconcile(state, obs, now=now)
            state = result.state
            if result.command_id:
                state['commands'][result.command_id]['outcome'] = 'failed'
                state['commands'][result.command_id]['failure'] = {'class': 'PUBLIC_METADATA_INVALID'}
        commands = list(state['commands'].values())
        self.assertEqual(len(commands), 3)
        incidents = list(state['incidents'].values())
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]['status'], 'repair_required')
        self.assertNotEqual(incidents[0]['status'], 'external_action_required')

    def test_external_auth_proof_circuit_breaks_without_generation_spend(self):
        entry = publication(overview='AUTH_EXPIRED', short='AUTH_EXPIRED')
        for row in entry['media'].values():
            row['external_blocker'] = {'confirmed': True, 'action': 'interactive_reauthentication', 'provider': 'notebooklm'}
        result = reconcile(new_state(), observed(entry), now=NOW)
        self.assertIsNone(result.command_id)
        self.assertEqual(len(result.state['commands']), 0)
        self.assertTrue(all(row['status'] == 'external_action_required' for row in result.state['incidents'].values()))

    def test_ambiguous_source_revokes_completion_and_stops_previously_pending_intent(self):
        state = bind_source(new_state(), SOURCE, now=NOW)
        state, command_id = plan_command(state, MediaIdentity(SOURCE, 'overview'), 'publish', 1, {}, code_sha=CODE, now=NOW)
        state['slots'][SOURCE.slot]['complete'] = True
        other = SourceIdentity(SOURCE.slot, 'different', 'e' * 64)
        result = reconcile(state, observed(publication(), publication(other)), now=NOW)
        self.assertIsNone(result.command_id)
        self.assertFalse(result.state['slots'][SOURCE.slot]['complete'])
        self.assertEqual(result.state['commands'][command_id]['outcome'], 'cancelled')

    def test_unknown_observation_has_finite_semantic_deadline_without_new_work(self):
        entry = publication(short='verified')
        entry['media']['overview'] = {'status': 'unknown'}
        first = reconcile(new_state(), observed(entry), now=NOW)
        self.assertIsNone(first.command_id)
        last = reconcile(first.state, observed(entry, now=later(43201)), now=later(43201))
        self.assertIsNone(last.command_id)
        self.assertEqual(next(iter(last.state['incidents'].values()))['failure_class'], 'OBSERVATION_UNAVAILABLE')

    def test_existing_pr_timestamp_only_progress_cannot_wait_forever(self):
        pr = {'slot': SOURCE.slot, 'number': 854, 'head_sha': CODE, 'status': 'pending', 'updated_at': NOW}
        first = reconcile(new_state(), observed(prs=[pr]), now=NOW)
        last = reconcile(first.state, observed(prs=[{**pr, 'updated_at': later(86400)}], now=later(86400)), now=later(86400))
        self.assertIsNone(last.command_id)
        self.assertEqual(next(iter(last.state['incidents'].values()))['failure_class'], 'ARTICLE_PR_STALLED')

    def test_unclaimed_dispatch_cannot_loop_without_a_persistent_incident(self):
        first = reconcile(new_state(), observed(), now=NOW)
        command = first.state['commands'][first.command_id]
        for offset in (0, 600, 1200):
            command['dispatch']['attempts'].append({'requested_at': later(offset), 'workflow': 'kesher-article-generation.yml',
                                                   'inputs': {'command_id': first.command_id}, 'receipt': {'status': 'uncertain'}})
        final = reconcile(first.state, observed(now=later(1801)), now=later(1801))
        self.assertIsNone(final.command_id)
        self.assertEqual(next(iter(final.state['incidents'].values()))['failure_class'], 'WORKER_ACCEPTANCE_STALLED')


if __name__ == '__main__':
    unittest.main()

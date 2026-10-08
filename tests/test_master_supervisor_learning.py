import copy
import unittest
from scripts import kesher_master_supervisor_live as master

NOW='2026-10-07T00:00:00+00:00'
def report(slug='one', noise='time=123'):
    return dict(incident_id=f'v5|{slug}|hash-{slug}|image',
                failure_signature='IMAGE_CATALOG_EXHAUSTED: '+noise,
                proposed_action='repair_trusted_image_same_pr', evidence_hash=slug,
                exact=dict(slug=slug,content_sha256='hash-'+slug,pr_number=1083))

class LearningTests(unittest.TestCase):
    def test_fingerprint_survives_slug_hash_and_log_changes(self):
        self.assertEqual(master.incident_fingerprint(report()),master.incident_fingerprint(report('two','time=999')))
        changed=report();changed['failure_signature']='VOICE_PITCH_REJECTION_LOOP'
        self.assertNotEqual(master.incident_fingerprint(report()),master.incident_fingerprint(changed))

    def test_delivery_does_not_reset_learning_or_close_defect(self):
        state,d=master.prepare_escalation(master.new_supervisor_state(),report(),now=NOW,prior_action_terminal=False)
        state=master.record_resolution(state,report(),at=NOW)
        self.assertEqual(state['incidents'][master.incident_fingerprint(report())]['status'],'awaiting_durable_fix')
        state,d=master.prepare_escalation(state,report('two'),now=NOW,prior_action_terminal=True)
        self.assertEqual(d['stage'],'S2')
        packet=master.build_incident_packet(report('two'),strike=2,command_id=d['command_id'])
        for key in ('generic_correction_required','deterministic_regression_required','no_oneoff_recovery_workflows'):
            self.assertTrue(packet['constraints'][key])
        self.assertEqual(packet['component_owner'],'canonical_image_worker')

    def test_no_third_symptom_rescue(self):
        state=master.new_supervisor_state()
        for i in range(2):
            state,d=master.prepare_escalation(state,report(),now=NOW,prior_action_terminal=True)
            state=master.mark_command_failed(state,d['command_id'],'failed',at=NOW)
        state,d=master.prepare_escalation(state,report(),now=NOW,prior_action_terminal=True)
        self.assertEqual(d['stage'],'HUMAN_BLOCKER');self.assertFalse(d['execute_now'])

    def test_active_old_fingerprint_migrates_without_reissuing(self):
        state,d=master.prepare_escalation(master.new_supervisor_state(),report(),now=NOW,prior_action_terminal=False)
        old=state['incidents'].pop(master.incident_fingerprint(report()));state['incidents']['legacy-fp']=old
        state['commands'][d['command_id']]['fingerprint']='legacy-fp'
        state,next_d=master.prepare_escalation(state,report('two'),now=NOW,prior_action_terminal=False)
        self.assertEqual(next_d['stage'],'WAIT');self.assertEqual(next_d['command_id'],d['command_id'])

    def test_shadow_comparison_is_recorded(self):
        r=report();r['v6_shadow']={'v6_recommended_decision':'wait_for_maintainer','active_v5_decision':'dispatch_image','agreement':False}
        state,d=master.prepare_escalation(master.new_supervisor_state(),r,now=NOW,prior_action_terminal=False)
        incident=state['incidents'][master.incident_fingerprint(r)]
        self.assertFalse(incident['v6_shadow_comparison']['agreement'])
        self.assertEqual(incident['learning_window_days'],7)

    def test_absent_incident_is_delivery_recovery_only(self):
        state,d=master.prepare_escalation(master.new_supervisor_state(),report(),now=NOW,prior_action_terminal=False)
        healthy=report();healthy['status']='healthy'
        state,changed=master.resolve_absent_incidents(state,healthy,at=NOW)
        self.assertTrue(changed)
        self.assertEqual(state['incidents'][master.incident_fingerprint(report())]['status'],'awaiting_durable_fix')

    def test_learning_window_does_not_reset_unmerged_defect(self):
        state,d=master.prepare_escalation(master.new_supervisor_state(),report(),now=NOW,prior_action_terminal=False)
        state=master.record_resolution(state,report(),at=NOW)
        state,d=master.prepare_escalation(state,report('two'),now='2026-11-07T00:00:00+00:00',prior_action_terminal=True)
        self.assertEqual(d['stage'],'S2')
        self.assertFalse(state['incidents'][master.incident_fingerprint(report())]['recurrence_in_learning_window'])

    def test_legacy_active_alias_cannot_be_hidden_by_new_inactive_fingerprint(self):
        state,d=master.prepare_escalation(master.new_supervisor_state(),report(),now=NOW,prior_action_terminal=False)
        fp=master.incident_fingerprint(report());old=copy.deepcopy(state['incidents'][fp])
        state['incidents']['legacy-fp']=old;state['incidents'][fp]['active_command_id']=None
        state['commands'][d['command_id']]['fingerprint']='legacy-fp'
        state,next_d=master.prepare_escalation(state,report('two'),now=NOW,prior_action_terminal=False)
        self.assertEqual(next_d['stage'],'WAIT');self.assertEqual(next_d['command_id'],d['command_id'])
        self.assertEqual(len(state['commands']),1)

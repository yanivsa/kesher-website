import unittest
from unittest.mock import Mock

from scripts.kesher_runtime.controller_entry import execute_tick
from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.state import StateConflict, StateInvalid
from tests.test_kesher_autonomous_controller import observed, publication
from tests.test_kesher_canonical_state import CODE, NOW, ContentsServer


class ControllerEntryTests(unittest.TestCase):
    def setUp(self):
        self.server = ContentsServer()
        self.store = GitHubStateStore(self.server, 'owner/repo')
        self.obs = observed(publication()).value
        self.obs['state_revision'] = 0
        from scripts.kesher_runtime.controller import Observation
        self.observer = Mock(); self.observer.read.return_value = Observation(self.obs)

    def test_shadow_proposes_exact_work_without_writing_or_dispatching(self):
        saved, dispatched = Mock(side_effect=AssertionError('shadow write')), Mock(side_effect=AssertionError('shadow dispatch'))
        self.store.save = saved
        result = execute_tick(self.store, self.observer, mode='shadow', dispatch=dispatched, clock=lambda: NOW)
        self.assertEqual(result['mode'], 'shadow')
        self.assertEqual(result['action']['target']['kind'], 'overview')
        saved.assert_not_called(); dispatched.assert_not_called()

    def test_live_requires_completed_cutover_before_any_observation_or_mutation(self):
        with self.assertRaises(StateInvalid):
            execute_tick(self.store, self.observer, mode='live', dispatch=Mock(), clock=lambda: NOW)
        self.observer.read.assert_not_called()

    def test_conflict_during_live_observation_cannot_dispatch_or_rebind(self):
        self.server.document['migration'] = {'status': 'complete', 'runtime_owner': 'kesher-canonical-controller'}
        def read(state):
            self.server.sha = 'f'*40
            return self.observer.read.return_value
        self.observer.read.side_effect = read
        dispatch = Mock()
        with self.assertRaises(StateConflict):
            execute_tick(self.store, self.observer, mode='live', dispatch=dispatch, clock=lambda: NOW)
        dispatch.assert_not_called()


if __name__ == '__main__': unittest.main()

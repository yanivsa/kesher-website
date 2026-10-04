import copy
import unittest
from unittest.mock import patch
from scripts.kesher_runtime.handover import require_legacy_writable
from scripts.kesher_runtime.legacy_retirement import retired_entrypoint, validate_legacy_write
from scripts.kesher_runtime.state import StateInvalid, validate_transition
from tests import test_kesher_handover as fixtures


class LegacyRetirementTests(unittest.TestCase):
    def test_production_legacy_github_transports_refuse_without_network(self):
        from scripts.kesher_content_controller import GitHubClient
        from scripts.kesher_master_supervisor_live import GitHubApi
        for method in ('POST','PUT','PATCH','DELETE'):
            with patch('urllib.request.urlopen',side_effect=AssertionError('network')):
                with self.assertRaises(StateInvalid):
                    GitHubClient('yanivsa/kesher-website','synthetic').request(method,'https://api.github.com/repos/yanivsa/kesher-website/contents/state')
                with self.assertRaises(StateInvalid):
                    GitHubApi('yanivsa/kesher-website','synthetic')._request(method,'https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/1/dispatches')

    def test_legacy_provider_creation_and_raw_upload_are_retired(self):
        from scripts import kesher_daily_pipeline as core, kesher_short_pipeline_v4 as short
        from pathlib import Path
        operations = [lambda:core.add_source({},{}),lambda:core.start_generation({},{}),
            lambda:short.start_generation({},{}),lambda:core.start_resumable_upload({}, {}, 'synthetic',Path('unused')),
            lambda:core.upload_bytes('synthetic','synthetic',Path('unused'),0)]
        with patch.object(core,'run_notebooklm',side_effect=AssertionError('provider')), patch.object(core.requests,'post',side_effect=AssertionError('network')):
            for operation in operations:
                with self.assertRaises(StateInvalid):operation()

    def test_retired_entrypoint_allows_only_exact_manual_media_bridge(self):
        base = {
            'KESHER_MANUAL_EMERGENCY_BRIDGE': 'true',
            'GITHUB_EVENT_NAME': 'workflow_dispatch',
            'GITHUB_REPOSITORY': 'yanivsa/kesher-website',
            'GITHUB_REF': 'refs/heads/main',
            'GITHUB_WORKFLOW_REF': 'yanivsa/kesher-website/.github/workflows/kesher-daily-video.yml@refs/heads/main',
        }
        with patch.dict('os.environ', base, clear=True):
            self.assertIsNone(retired_entrypoint())
        for key, value in (
            ('GITHUB_EVENT_NAME', 'schedule'),
            ('GITHUB_REF', 'refs/heads/other'),
            ('GITHUB_REPOSITORY', 'other/repo'),
            ('GITHUB_WORKFLOW_REF', 'yanivsa/kesher-website/.github/workflows/ci.yml@refs/heads/main'),
        ):
            env = dict(base)
            env[key] = value
            with patch.dict('os.environ', env, clear=True):
                with self.assertRaises(StateInvalid):
                    retired_entrypoint()

    def test_every_durable_phase_fences_legacy_state_writes(self):
        case=fixtures.HandoverTests();case.setUp()
        require_legacy_writable(case.backend.document)
        c=case.coordinator()
        for _ in range(50):
            phase=c.tick()
            with self.assertRaises(StateInvalid):require_legacy_writable(case.backend.document)
            with self.assertRaises(StateInvalid):
                validate_legacy_write(case.backend.document, {'schema_version':5},
                                      before_sha=case.backend.sha, current_sha=case.backend.sha)
            if phase=='VERIFIED':break
        else:self.fail('Incomplete handover')

    def test_normal_canonical_store_cannot_grant_authority_or_remove_history(self):
        case=fixtures.HandoverTests();case.setUp();before=case.finish()
        for mutation in ('handover','migration','quarantine'):
            after=copy.deepcopy(before)
            if mutation=='handover':after.pop('handover')
            elif mutation=='migration':after['migration']['input_sha256']='forged'
            else:
                before['quarantine'].append({'retained':'claim'})
                after=copy.deepcopy(before);after['quarantine']=[]
            with self.assertRaises(StateInvalid):validate_transition(before,after)


if __name__=='__main__':unittest.main()

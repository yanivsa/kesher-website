from pathlib import Path
import unittest


class OpenClawRecoveryContractTest(unittest.TestCase):
    def test_local_proof_replaces_stuck_helper_once_without_repatching(self):
        workflow = Path('.github/workflows/openclaw-offline-boot-repair.yml').read_text()

        self.assertIn('Retry local proof with fresh helper', workflow)
        self.assertIn('OPENCLAW_LOCAL_PROOF_HELPER_REPLACED=true', workflow)
        self.assertGreaterEqual(
            workflow.count('scripts/oci_openclaw_helper_local_proof.py'),
            2,
            'local proof must get one bounded retry on a fresh disposable helper',
        )
        retry_block = workflow.split('Retry local proof with fresh helper', 1)[1]
        self.assertIn('scripts/oci_openclaw_offline_repair_v3.py', retry_block)
        self.assertNotIn('openclaw_offline_mount_repair_cloudflare.sh', retry_block)

    def test_local_proof_script_self_heals_stuck_plugin_for_old_reruns(self):
        script = Path('scripts/oci_openclaw_helper_local_proof.py').read_text()

        self.assertIn('OPENCLAW_LOCAL_PROOF_PLUGIN_STALLED=true', script)
        self.assertIn('OPENCLAW_LOCAL_PROOF_HELPER_REPLACED=true', script)
        self.assertIn('oci_openclaw_offline_repair_v3', script)
        self.assertIn('replace_stuck_helper', script)

    def test_prepare_waits_for_preserved_boot_to_fully_detach_before_helper_attach(self):
        script = Path('scripts/oci_openclaw_offline_repair_v3.py').read_text()
        prepare = script.split('def prepare(args) -> int:', 1)[1]

        self.assertIn('def wait_boot_volume_detached(', script)
        self.assertIn('OFFLINE_REPAIR_BOOT_DETACHED_AFTER_TARGET_TERMINATION=true', script)
        wait_call = prepare.index('wait_boot_volume_detached(')
        launch_call = prepare.index('compute.launch_instance(')
        attach_call = prepare.index('compute.attach_volume(')
        self.assertLess(wait_call, launch_call)
        self.assertLess(wait_call, attach_call)


if __name__ == '__main__':
    unittest.main()

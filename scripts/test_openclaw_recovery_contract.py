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


if __name__ == '__main__':
    unittest.main()

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OpenClawGatewayFailFastContractTest(unittest.TestCase):
    def test_finalizer_fails_fast_and_persists_gateway_diagnostics(self):
        text = (ROOT / "scripts/openclaw_offline_mount_repair_cloudflare.sh").read_text(encoding="utf-8")
        self.assertIn('OPENCLAW_FINALIZE_FAILED=GATEWAY_UNIT_NOT_ACTIVE', text)
        self.assertIn('journalctl -u openclaw-gateway.service', text)
        self.assertIn('OPENCLAW_GATEWAY_JOURNAL_BEGIN=true', text)
        self.assertIn('OPENCLAW_GATEWAY_JOURNAL_END=true', text)
        self.assertIn('if [ "$gateway_unit_state" != active ]; then', text)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OpenClawGatewayJournalDiagnosticsTest(unittest.TestCase):
    def test_missing_ready_file_captures_persistent_gateway_journal(self):
        text = (ROOT / "scripts/openclaw_local_proof.sh").read_text(encoding="utf-8")
        self.assertIn("OPENCLAW_LOCAL_PROOF_GATEWAY_JOURNAL_BEGIN=true", text)
        self.assertIn('journalctl --directory="$MNT/var/log/journal" -u openclaw-gateway.service', text)
        self.assertIn("OPENCLAW_LOCAL_PROOF_GATEWAY_JOURNAL_END=true", text)

    def test_finalizer_fails_fast_and_persists_live_gateway_failure(self):
        text = (ROOT / "scripts/openclaw_offline_mount_repair_cloudflare.sh").read_text(encoding="utf-8")
        self.assertIn('gateway_unit_state="$(systemctl is-active openclaw-gateway.service', text)
        self.assertIn('if [ "$gateway_unit_state" != active ]; then', text)
        self.assertIn("OPENCLAW_FINALIZE_FAILED=GATEWAY_UNIT_NOT_ACTIVE", text)
        self.assertIn("OPENCLAW_GATEWAY_JOURNAL_BEGIN=true", text)
        self.assertIn("journalctl -u openclaw-gateway.service -n 160 --no-pager", text)
        self.assertIn("OPENCLAW_GATEWAY_JOURNAL_END=true", text)

    def test_gateway_failure_is_exported_as_safe_markers_for_ci(self):
        text = (ROOT / "scripts/openclaw_offline_mount_repair_cloudflare.sh").read_text(encoding="utf-8")
        self.assertIn("OPENCLAW_GATEWAY_RESULT=", text)
        self.assertIn("OPENCLAW_GATEWAY_EXEC_MAIN_CODE=", text)
        self.assertIn("OPENCLAW_GATEWAY_EXEC_MAIN_STATUS=", text)
        self.assertIn("OPENCLAW_GATEWAY_JOURNAL_LINE=", text)
        self.assertIn("systemctl show openclaw-gateway.service", text)


if __name__ == "__main__":
    unittest.main()

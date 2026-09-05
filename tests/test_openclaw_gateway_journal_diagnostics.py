from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OpenClawGatewayJournalDiagnosticsTest(unittest.TestCase):
    def test_missing_ready_file_captures_persistent_gateway_journal(self):
        text = (ROOT / "scripts/openclaw_local_proof.sh").read_text(encoding="utf-8")
        self.assertIn("OPENCLAW_LOCAL_PROOF_GATEWAY_JOURNAL_BEGIN=true", text)
        self.assertIn('journalctl --directory="$MNT/var/log/journal" -u openclaw-gateway.service', text)
        self.assertIn("OPENCLAW_LOCAL_PROOF_GATEWAY_JOURNAL_END=true", text)


if __name__ == "__main__":
    unittest.main()

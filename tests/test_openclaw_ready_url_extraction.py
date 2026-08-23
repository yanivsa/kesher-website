import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = ROOT / "scripts/openclaw_extract_ready_url.sh"


class OpenClawReadyUrlExtractionTests(unittest.TestCase):
    def test_repeated_proof_records_return_one_latest_url(self):
        logs = "\n".join(
            [
                "repair proof 2026-08-22 OPENCLAW_READY_URL=https://openclaw.tail3b2afe.ts.net/",
                "repair summary 2026-08-22 OPENCLAW_READY_URL=https://openclaw.tail3b2afe.ts.net/",
            ]
        )
        result = subprocess.run(
            ["bash", str(EXTRACTOR)],
            input=logs,
            text=True,
            check=True,
            capture_output=True,
        )
        self.assertEqual(result.stdout.strip(), "https://openclaw.tail3b2afe.ts.net/")

    def test_echoed_source_is_not_accepted_as_proof(self):
        logs = "echo OPENCLAW_READY_URL=https://fake.ts.net/ && exit 0\n"
        result = subprocess.run(
            ["bash", str(EXTRACTOR)],
            input=logs,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()

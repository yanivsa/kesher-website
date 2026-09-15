from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / ".github/workflows/kesher-daily-video.yml"
SHORT = ROOT / ".github/workflows/kesher-short-v4.yml"


class NotebookLMAuthPrecedenceTests(unittest.TestCase):
    def test_github_secret_precedes_durable_state(self):
        guard = 'if [ -z "${NOTEBOOKLM_STORAGE_STATE_SECRET:-}" ] && [ -s "$sealed_path" ]; then'
        for path in (DAILY, SHORT):
            text = path.read_text(encoding="utf-8")
            self.assertIn(guard, text, path)
            self.assertNotIn('if [ -s "$sealed_path" ]; then', text, path)

    def test_provider_paths_run_read_only_preflight(self):
        daily = DAILY.read_text(encoding="utf-8")
        short = SHORT.read_text(encoding="utf-8")
        self.assertIn("inputs.operation == 'preflight' || inputs.operation == 'full' || inputs.operation == 'generate'", daily)
        self.assertIn('scripts/kesher_daily_pipeline.py --preflight', daily)
        self.assertIn("inputs.operation == 'preflight' || inputs.operation == 'full' || inputs.operation == 'generate'", short)
        self.assertIn("inputs.operation == 'derive' || inputs.operation == 'historical'", short)
        self.assertIn('scripts/kesher_short_pipeline_v4.py --preflight', short)


if __name__ == "__main__":
    unittest.main()

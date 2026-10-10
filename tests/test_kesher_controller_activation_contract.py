from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/kesher-content-controller.yml"


class CanonicalControllerActivationContractTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_controller_is_manual_only(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("schedule:", self.text)

    def test_controller_is_exact_repo_main_gated(self):
        self.assertIn("github.repository == 'yanivsa/kesher-website'", self.text)
        self.assertIn("github.ref == 'refs/heads/main'", self.text)
        self.assertNotIn("__KESHER_RETIRED__", self.text)

    def test_controller_enters_only_canonical_live_runtime(self):
        self.assertIn(
            "python -m scripts.kesher_runtime.controller_entry --mode live",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()

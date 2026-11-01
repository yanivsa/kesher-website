import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MasterIntentLiveContractTests(unittest.TestCase):
    def test_registered_controller_workflow_has_explicit_master_live_path(self):
        text = (ROOT / '.github/workflows/kesher-content-controller.yml').read_text(encoding='utf-8')
        self.assertIn('request_json:', text)
        self.assertIn('request_id:', text)
        self.assertIn('scripts.kesher_runtime.master_intent_entry --mode live', text)
        self.assertIn('id-token: write', text)
        self.assertIn('scripts.kesher_runtime.bridge_admission --controller', text)
        self.assertIn('scripts/kesher_content_controller_stabilized.py', text)

    def test_master_live_entry_is_explicit_and_never_calls_controller_decision_entry(self):
        text = (ROOT / 'scripts/kesher_runtime/master_intent_entry.py').read_text(encoding='utf-8')
        self.assertIn("choices=('shadow', 'live')", text)
        self.assertIn('require_live', text)
        self.assertIn('store.save', text)
        self.assertIn('deliver_command', text)
        self.assertNotIn('controller_entry', text)
        self.assertNotIn('reconcile(', text)


if __name__ == '__main__':
    unittest.main()

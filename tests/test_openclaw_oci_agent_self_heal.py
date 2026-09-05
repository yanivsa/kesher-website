from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OpenClawOciAgentSelfHealContractTest(unittest.TestCase):
    def test_stuck_accepted_command_triggers_one_softreset_and_plugin_diagnostics(self):
        text = (ROOT / "scripts/oci_openclaw_agent_command.py").read_text(encoding="utf-8")
        self.assertIn("PluginClient", text)
        self.assertIn("OCI_RUN_COMMAND_PLUGIN_STATUS=", text)
        self.assertIn("OCI_AGENT_STUCK_ACCEPTED=true", text)
        self.assertIn('instance_action(inst.id, "SOFTRESET")', text)
        self.assertIn("OCI_AGENT_SOFTRESET_REQUESTED=true", text)
        self.assertIn("reboot_attempted", text)
        self.assertIn("accepted_since", text)


if __name__ == "__main__":
    unittest.main()

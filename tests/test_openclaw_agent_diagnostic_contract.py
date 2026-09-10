from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "scripts/oci_openclaw_agent_diagnostic.py"
SH = ROOT / "scripts/openclaw_readonly_diagnostic.sh"
WF = ROOT / ".github/workflows/openclaw-agent-diagnostic.yml"

def test_readonly_agent_diagnostic_contract():
    py = PY.read_text()
    sh = SH.read_text()
    wf = WF.read_text()
    for forbidden in ("update_instance(", "instance_action(", "SOFTRESET", "terminate_instance("):
        assert forbidden not in py
    for forbidden in ("systemctl restart", "systemctl enable", "apt ", "apt-get ", "reboot", "shutdown", "rm -rf"):
        assert forbidden not in sh
    assert "CreateInstanceAgentCommandDetails" in py
    assert "OCI_AGENT_DIAG_OUTPUT_BEGIN" in py
    assert "cloud-init status --long" in sh
    assert "systemctl is-active ssh" in sh
    assert "ss -lnt" in sh
    assert "openclaw-clean-bootstrap.log" in sh
    assert "--instance-name openclaw-e2-tailscale" in wf

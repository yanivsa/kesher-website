from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/openclaw-inspect-tailnet-console.yml"

def test_console_inspection_surfaces_clean_boot_and_ssh_failures_without_mutation():
    text = WORKFLOW.read_text()
    for marker in ("OPENCLAW_CLEAN_BOOTSTRAP", "cloud-init", "sshd", "error|failed|failure"):
        assert marker in text
    for forbidden in ("terminate_instance", "reboot_instance", "update_instance"):
        assert forbidden not in text

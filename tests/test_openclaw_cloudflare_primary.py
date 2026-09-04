from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read_repo(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class OpenClawCloudflarePrimaryContractTest(unittest.TestCase):
    def test_controller_requires_cloudflare_not_tailscale(self):
        text = read_repo("scripts/openclaw_recovery_controller.sh")
        self.assertIn("CLOUDFLARED_SERVICE_ACTIVE=true", text)
        self.assertIn("CLOUDFLARE_ACCESS_PROTECTED=true", text)
        self.assertNotIn('&& "$serve" == true', text)
        self.assertNotIn("missing+=(TAILSCALE_SERVE_ACTIVE)", text)

    def test_controller_auto_dispatches_recovery_after_recovery_code_merge(self):
        workflow = read_repo(".github/workflows/openclaw-recovery-controller.yml")
        controller = read_repo("scripts/openclaw_recovery_controller.sh")
        self.assertIn("push:", workflow)
        self.assertIn("scripts/openclaw_recovery_controller.sh", workflow)
        self.assertIn(".github/workflows/openclaw-offline-boot-repair.yml", workflow)
        self.assertIn("OPENCLAW_CONTROLLER_FORCE_DISPATCH", workflow)
        self.assertIn('OPENCLAW_CONTROLLER_FORCE_DISPATCH:-0', controller)
        self.assertIn("controller_forced_dispatch", controller)

    def test_status_strict_success_requires_cloudflare_not_tailscale(self):
        text = read_repo("scripts/openclaw_publish_status.sh")
        self.assertIn("CLOUDFLARED_SERVICE_ACTIVE_VALUE", text)
        self.assertIn("CLOUDFLARE_ACCESS_PROTECTED_VALUE", text)
        self.assertNotIn('&& "$SERVE_OK" == "true"', text)

    def test_local_proof_has_no_tailscale_requirement(self):
        text = read_repo("scripts/openclaw_local_proof.sh")
        self.assertIn("OPENCLAW_LOCAL_READY=true", text)
        self.assertIn("OPENCLAW_GATEWAY_RPC_OK=true", text)
        self.assertNotIn("TAILSCALE_NOT_RUNNING", text)
        self.assertNotIn("SERVE_PROOF_MISSING", text)

    def test_local_helper_proof_does_not_require_public_url(self):
        text = read_repo("scripts/oci_openclaw_helper_local_proof.py")
        self.assertIn('"OPENCLAW_LOCAL_READY=true"', text)
        self.assertNotIn('"TAILSCALE_SERVE_ACTIVE=true"', text)
        self.assertNotIn("URL_RE", text)

    def test_cloudflare_repair_wrapper_disables_managed_tailscale(self):
        text = read_repo("scripts/openclaw_offline_mount_repair_cloudflare.sh")
        self.assertIn("gateway.setdefault('tailscale', {})['mode'] = 'off'", text)
        self.assertIn("gateway.setdefault('auth', {})['allowTailscale'] = False", text)
        self.assertIn("OPENCLAW_TAILSCALE_REQUIRED=false", text)
        self.assertIn("After=network-online.target", text)
        self.assertNotIn("After=network-online.target tailscaled.service", text)

    def test_recovery_workflow_uses_local_proof_then_cloudflare(self):
        text = read_repo(".github/workflows/openclaw-offline-boot-repair.yml")
        self.assertIn("actions: write", text)
        self.assertIn("openclaw_offline_mount_repair_cloudflare.sh", text)
        self.assertIn("oci_openclaw_helper_local_proof.py", text)
        self.assertIn("openclaw_local_proof.sh", text)
        self.assertIn("openclaw-cloudflare-tunnel.yml", text)
        self.assertIn("CLOUDFLARED_SERVICE_ACTIVE=true", text)
        self.assertIn("CLOUDFLARE_ACCESS_PROTECTED=true", text)
        self.assertIn("OPENCLAW_READY_URL=https://openclaw.saharoni.com/", text)

    def test_recovery_target_discovery_tries_both_known_openclaw_names(self):
        text = read_repo("scripts/oci_openclaw_offline_repair_v2.py")
        self.assertIn("for name in (TARGET_NAME, FALLBACK_NAME):", text)
        self.assertIn("OPENCLAW_TARGET_SELECTED", text)
        self.assertIn("OPENCLAW_TARGET_DISCOVERY_FAILED", text)

    def test_target_discovery_changes_trigger_fresh_recovery(self):
        workflow = read_repo(".github/workflows/openclaw-recovery-controller.yml")
        self.assertIn("scripts/oci_openclaw_offline_repair_v2.py", workflow)
        self.assertIn("scripts/oci_openclaw_offline_repair_v3.py", workflow)


if __name__ == "__main__":
    unittest.main()

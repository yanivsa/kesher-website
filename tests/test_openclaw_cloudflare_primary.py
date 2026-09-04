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

    def test_status_strict_success_requires_cloudflare_not_tailscale(self):
        text = read_repo("scripts/openclaw_publish_status.sh")
        self.assertIn("CLOUDFLARED_SERVICE_ACTIVE_VALUE", text)
        self.assertIn("CLOUDFLARE_ACCESS_PROTECTED_VALUE", text)
        self.assertNotIn('&& "$SERVE_OK" == "true"', text)

    def test_offline_proof_is_local_gateway_proof(self):
        text = read_repo("scripts/openclaw_offline_proof.sh")
        self.assertIn("OPENCLAW_LOCAL_READY=true", text)
        self.assertNotIn("OPENCLAW_OFFLINE_PROOF_FAILED=TAILSCALE_NOT_RUNNING", text)
        self.assertNotIn("OPENCLAW_OFFLINE_PROOF_FAILED=SERVE_PROOF_MISSING", text)

    def test_helper_proof_does_not_require_tailscale_or_public_url(self):
        text = read_repo("scripts/oci_openclaw_helper_proof.py")
        self.assertIn('"OPENCLAW_LOCAL_READY=true"', text)
        self.assertNotIn('"TAILSCALE_SERVE_ACTIVE=true"', text)
        self.assertNotIn("or not urls", text)

    def test_repair_disables_openclaw_managed_tailscale(self):
        text = read_repo("scripts/openclaw_offline_mount_repair_early.sh")
        self.assertIn("gateway.setdefault('tailscale', {})['mode'] = 'off'", text)
        self.assertIn("gateway.setdefault('auth', {})['allowTailscale'] = False", text)
        self.assertIn("OPENCLAW_TAILSCALE_REQUIRED=false", text)

    def test_recovery_workflow_dispatches_and_verifies_cloudflare(self):
        text = read_repo(".github/workflows/openclaw-offline-boot-repair.yml")
        self.assertIn("actions: write", text)
        self.assertIn("openclaw-cloudflare-tunnel.yml", text)
        self.assertIn("CLOUDFLARED_SERVICE_ACTIVE=true", text)
        self.assertIn("CLOUDFLARE_ACCESS_PROTECTED=true", text)
        self.assertIn("OPENCLAW_READY_URL=https://openclaw.saharoni.com/", text)


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

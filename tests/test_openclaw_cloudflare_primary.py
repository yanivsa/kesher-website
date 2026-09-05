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

    def test_finalizer_owns_gateway_restart_without_hard_dependency_cycle(self):
        text = read_repo("scripts/openclaw_offline_mount_repair_cloudflare.sh")
        self.assertIn("systemctl restart openclaw-gateway.service", text)
        self.assertNotIn("Requires=openclaw-gateway.service", text)
        self.assertNotIn(
            "After=local-fs.target swap.target network-online.target openclaw-gateway.service",
            text,
        )

    def test_gateway_failure_diagnostics_survive_ci_marker_filter(self):
        text = read_repo("scripts/openclaw_offline_mount_repair_cloudflare.sh")
        self.assertIn("OPENCLAW_GATEWAY_RESULT=", text)
        self.assertIn("OPENCLAW_GATEWAY_EXEC_MAIN_CODE=", text)
        self.assertIn("OPENCLAW_GATEWAY_EXEC_MAIN_STATUS=", text)
        self.assertIn("OPENCLAW_GATEWAY_JOURNAL_LINE=", text)
        self.assertIn("systemctl show openclaw-gateway.service", text)

    def test_live_cloudflare_deploy_repairs_gateway_unit_with_discovered_binary(self):
        text = read_repo("scripts/openclaw_enable_cloudflare_tunnel.sh")
        self.assertIn("OPENCLAW_LIVE_GATEWAY_REPAIR=true", text)
        self.assertIn("ExecStart=$B gateway --port 18789", text)
        self.assertIn("systemctl reset-failed openclaw-gateway.service", text)
        self.assertIn("systemctl is-active --quiet openclaw-gateway.service", text)
        self.assertIn("gateway.bind loopback", text)
        self.assertIn("PUBLIC_GATEWAY_LISTENER_DETECTED", text)

    def test_live_cloudflare_deploy_reuses_existing_service_without_api_control_plane(self):
        workflow = read_repo(".github/workflows/openclaw-cloudflare-tunnel.yml")
        script = read_repo("scripts/openclaw_enable_cloudflare_tunnel.sh")
        self.assertNotIn("/zones?name=", workflow)
        self.assertNotIn("/access/apps/", workflow)
        self.assertNotIn("/cfd_tunnel/$TUNNEL_ID/token", workflow)
        self.assertIn("CLOUDFLARED_REUSED_EXISTING_SERVICE=true", script)
        self.assertIn("systemctl restart cloudflared.service", script)
        self.assertIn("Verify Access protects public hostname", workflow)
        self.assertIn("CLOUDFLARE_ACCESS_PROTECTED=true", workflow)

    def test_live_cloudflare_uses_bounded_verified_oci_bootstrap(self):
        workflow = read_repo(".github/workflows/openclaw-cloudflare-tunnel.yml")
        self.assertIn("OPENCLAW_OCI_BOOTSTRAP_BYTES", workflow)
        self.assertIn("raw.githubusercontent.com/yanivsa/kesher-website/${GITHUB_SHA}/scripts/openclaw_enable_cloudflare_tunnel.sh", workflow)
        self.assertIn("sha256sum -c", workflow)
        self.assertIn("/tmp/openclaw-cloudflare-bootstrap.sh", workflow)
        self.assertIn("--script-file /tmp/openclaw-cloudflare-bootstrap.sh", workflow)

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

    def test_run_command_wrapper_fetches_cloudflare_transitive_dependencies(self):
        text = read_repo("scripts/oci_openclaw_helper_run_command_v2.py")
        self.assertIn('"openclaw_offline_mount_repair_cloudflare.sh"', text)
        self.assertIn('"openclaw_offline_mount_repair_early.sh"', text)
        self.assertIn('"openclaw_offline_mount_repair_base.sh"', text)
        self.assertIn("files.extend", text)

    def test_helper_wrapper_changes_trigger_fresh_recovery(self):
        workflow = read_repo(".github/workflows/openclaw-recovery-controller.yml")
        self.assertIn("scripts/oci_openclaw_helper_run_command_v2.py", workflow)


if __name__ == "__main__":
    unittest.main()

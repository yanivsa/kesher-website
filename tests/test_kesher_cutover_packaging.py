"""Static deployment-package guards for the external cutover service."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops" / "kesher-cutover"


class CutoverPackagingTests(unittest.TestCase):
    def test_systemd_unit_is_loopback_service_only_and_never_bootstraps_ledger(self):
        text = (OPS / "kesher-cutover.service").read_text(encoding="utf-8")
        self.assertIn("User=kesher-cutover", text)
        self.assertIn("ConditionPathExists=/var/lib/kesher-cutover/invocations.sqlite", text)
        self.assertIn("--factory trusted_kesher_cutover:build --port 8789", text)
        self.assertIn("Restart=on-failure", text)
        self.assertIn("ReadWritePaths=/var/lib/kesher-cutover", text)
        self.assertNotIn("InvocationJournal.initialize", text)
        self.assertNotIn("kesher-production-cutover.yml", text)
        self.assertNotIn("gh workflow run", text)

    def test_environment_template_contains_only_names_paths_and_placeholders(self):
        text = (OPS / "kesher-cutover.env.example").read_text(encoding="utf-8")
        required = (
            "KESHER_CUTOVER_REVIEW_FILE",
            "KESHER_CUTOVER_MATERIAL_FILE",
            "KESHER_CUTOVER_CLOSURE_FILE",
            "KESHER_CUTOVER_BINDINGS_FILE",
            "KESHER_CUTOVER_REGISTRATIONS_FILE",
            "KESHER_CUTOVER_KEY_BINDING_FILE",
            "KESHER_CUTOVER_NATIVE_FACTORY",
            "KESHER_CUTOVER_OIDC_AUDIENCE",
            "KESHER_CUTOVER_JOURNAL",
            "KESHER_CUTOVER_EPOCH",
            "KESHER_CUTOVER_OWNER",
            "KESHER_GITHUB_REPOSITORY",
            "KESHER_GITHUB_REPOSITORY_ID",
            "KESHER_CUTOVER_ROOT",
        )
        for name in required:
            self.assertIn(name + "=", text)
        for forbidden in ("GITHUB_TOKEN=", "YOUTUBE_REFRESH_TOKEN=", "NOTEBOOKLM_AUTH_JSON=", "CLOUDFLARE_API_TOKEN="):
            self.assertNotIn(forbidden, text)
        self.assertIn("REPLACE_WITH_EXACT_GATEWAY_ORIGIN", text)
        self.assertIn("/var/lib/kesher-cutover/invocations.sqlite", text)

    def test_runbook_requires_one_time_manual_ledger_and_explicit_tls_audience(self):
        text = (OPS / "README.md").read_text(encoding="utf-8")
        self.assertIn("Initialize the replay-denial ledger exactly once", text)
        self.assertIn("Never recreate a lost ledger", text)
        self.assertIn("127.0.0.1:8789", text)
        self.assertIn("TLS reverse proxy", text)
        self.assertIn("OIDC audience", text)
        self.assertIn("startup performs no cutover step", text)
        self.assertIn("controller retirement sentinel remains in place", text)


if __name__ == "__main__":
    unittest.main()

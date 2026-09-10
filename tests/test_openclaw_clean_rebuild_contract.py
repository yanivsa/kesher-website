from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_clean_rebuild_uses_fresh_image_and_preserves_rollback():
    text = (ROOT / "scripts/oci_openclaw_clean_rebuild.py").read_text()
    assert 'source="image"' not in text  # SDK uses source_type below.
    assert 'source_type="image"' in text
    assert "preserve_boot_volume=True" in text
    assert "openclaw-cloudflared-source" in text
    assert "openclaw-clean-rollback" in text
    assert "is_read_only=True" in text
    assert '"source": "fresh-image"' in text


def test_clean_finalize_only_migrates_tunnel_credential():
    text = (ROOT / "scripts/openclaw_clean_finalize.sh").read_text()
    assert "OPENCLAW_CLEAN_ONLY_TUNNEL_CREDENTIAL_MIGRATED=true" in text
    assert "cert.pem" in text
    assert "Never copy cert.pem" in text
    assert "tunnel-token" in text
    assert "openclaw-migrated-credential.json" in text
    assert "cp -a" not in text
    assert "rsync" not in text


def test_gateway_follows_cloudflare_access_topology():
    text = (ROOT / "scripts/openclaw_clean_finalize.sh").read_text()
    assert "gateway.bind loopback" in text
    assert "gateway.auth.mode trusted-proxy" in text
    assert "cf-access-authenticated-user-email" in text
    assert "cf-access-jwt-assertion" in text
    assert "gateway.auth.trustedProxy.allowLoopback true" in text
    assert 'gateway.trustedProxies \'["127.0.0.1","::1"]\'' in text
    assert "PUBLIC_GATEWAY_LISTENER_DETECTED" in text


def test_workflow_requires_local_and_public_proofs_and_always_closes_ssh():
    text = (ROOT / ".github/workflows/openclaw-clean-rebuild.yml").read_text()
    assert "workflow_dispatch" in text
    assert "concurrency:" in text
    assert "OPENCLAW_CLEAN_LOCAL_RUNTIME_PROOF=true" in text
    assert "CLOUDFLARE_ACCESS_PROTECTED=true" in text
    assert "OPENCLAW_PUBLIC_ROUTE_OK=true" in text
    assert "Close temporary SSH" in text
    assert "if: always()" in text

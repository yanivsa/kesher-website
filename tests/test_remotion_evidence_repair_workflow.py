from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "kesher-remotion-evidence-repair.yml"


def test_remotion_evidence_repair_is_fail_closed_and_reuses_exact_raw_media():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "group: kesher-daily-notebooklm-video" in text
    assert 'item.get("status") != "downloaded"' in text
    assert 'item.get("uploaded") is True' in text
    assert 'source_slug != target_slug' in text
    assert 'digest != item["raw_sha256"]' in text
    assert 'item.get("visual_pipeline") != "remotion-v1-notebooklm-audio"' in text
    assert 'evidence_complete' in text
    assert 'Remotion evidence is already complete; refusing destructive repair' in text
    assert 'remotion_evidence_repair_applied' in text


def test_remotion_evidence_repair_never_generates_provider_media_directly():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "notebooklm generate" not in text
    assert "generate video" not in text
    assert "GITHUB_TOKEN" not in text
    assert "gh workflow run kesher-daily-video.yml" in text
    assert "-f operation=generate" in text
    assert '-f target_slug="$TARGET_SLUG"' in text

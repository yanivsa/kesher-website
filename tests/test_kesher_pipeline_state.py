import pytest
import os
import json
import fcntl
import hashlib
from pathlib import Path
from scripts.pipeline_state import (
    ManifestSchema, StateError, SchemaError, is_duplicate,
    check_review_transition, is_upload_eligible, quarantine_legacy_items,
    reconcile_state, PipelineLock, build_manifest_id, atomic_save
)

@pytest.fixture
def tmp_files(tmp_path):
    f_raw = tmp_path / "raw.mp4"
    f_raw.write_bytes(b"raw")
    h_raw = hashlib.sha256(b"raw").hexdigest()

    f_ren = tmp_path / "ren.mp4"
    f_ren.write_bytes(b"ren")
    h_ren = hashlib.sha256(b"ren").hexdigest()

    f_rev = tmp_path / "rev.jpg"
    f_rev.write_bytes(b"rev")
    h_rev = hashlib.sha256(b"rev").hexdigest()

    return {
        "raw_path": str(f_raw), "raw_sha256": h_raw,
        "render_path": str(f_ren), "render_sha256": h_ren,
        "visual_review_path": str(f_rev), "visual_review_sha256": h_rev
    }

@pytest.fixture
def base_manifest():
    gen_date = "2023-10-27"
    url = "http://example.com/video"
    sha = "abc123sha"
    man_id = build_manifest_id(gen_date, url, sha)
    return {
        "schema_version": "1.0",
        "type": "normal",
        "generation_date": gen_date,
        "source_url": url,
        "source_evidence_sha256": sha,
        "manifest_id": man_id,
        "state": "discovered"
    }

def test_manifest_schema_validation(base_manifest):
    ManifestSchema.validate(base_manifest)

    base_manifest["schema_version"] = "2.0"
    with pytest.raises(SchemaError, match="schema version"):
        ManifestSchema.validate(base_manifest)

    base_manifest["schema_version"] = "1.0"
    base_manifest["type"] = "short"
    with pytest.raises(SchemaError, match="'normal' type"):
        ManifestSchema.validate(base_manifest)

def test_state_transitions(base_manifest):
    ManifestSchema.transition(base_manifest, "source_verified_unique")
    assert base_manifest["state"] == "source_verified_unique"

    ManifestSchema.transition(base_manifest, "source_verified_unique") # idempotent
    assert base_manifest["state"] == "source_verified_unique"

    with pytest.raises(StateError, match="Backward"):
        ManifestSchema.transition(base_manifest, "discovered")

    with pytest.raises(StateError, match="Skipping forward states"):
        ManifestSchema.transition(base_manifest, "generating")

def test_generating_requires_ids(base_manifest):
    ManifestSchema.transition(base_manifest, "source_verified_unique")
    ManifestSchema.transition(base_manifest, "source_added")
    with pytest.raises(SchemaError, match="real notebook_id"):
        ManifestSchema.transition(base_manifest, "generating")

    base_manifest["notebook_id"] = "nb123"
    base_manifest["generation_job_id"] = "job123"
    ManifestSchema.transition(base_manifest, "generating")
    assert base_manifest["state"] == "generating"

def test_artifact_ready_requires_id(base_manifest):
    ManifestSchema.transition(base_manifest, "source_verified_unique")
    ManifestSchema.transition(base_manifest, "source_added")
    base_manifest["notebook_id"] = "nb123"
    base_manifest["generation_job_id"] = "job123"
    ManifestSchema.transition(base_manifest, "generating")
    with pytest.raises(SchemaError, match="real artifact_id"):
        ManifestSchema.transition(base_manifest, "artifact_ready")
    base_manifest["artifact_id"] = "art123"
    ManifestSchema.transition(base_manifest, "artifact_ready")

    with pytest.raises(SchemaError, match="raw_path required and must exist"):
        ManifestSchema.transition(base_manifest, "downloaded")

    base_manifest["artifact_id"] = "art123"
    base_manifest["raw_path"] = "/tmp/fake"
    base_manifest["raw_sha256"] = "fake"
    base_manifest["render_path"] = "/tmp/fake"
    base_manifest["render_sha256"] = "fake"
    with pytest.raises(SchemaError, match="must exist"):
        ManifestSchema.transition(base_manifest, "downloaded")

def test_downloaded_requires_files(base_manifest, tmp_files):
    ManifestSchema.transition(base_manifest, "source_verified_unique")
    ManifestSchema.transition(base_manifest, "source_added")
    base_manifest.update({"notebook_id": "1", "generation_job_id": "2", "artifact_id": "3"})
    ManifestSchema.transition(base_manifest, "generating")
    ManifestSchema.transition(base_manifest, "artifact_ready")

    with pytest.raises(SchemaError, match="raw_path"):
        ManifestSchema.transition(base_manifest, "downloaded")

    base_manifest.update({
        "raw_path": tmp_files["raw_path"], "raw_sha256": tmp_files["raw_sha256"],
        "render_path": tmp_files["render_path"], "render_sha256": tmp_files["render_sha256"]
    })
    ManifestSchema.transition(base_manifest, "downloaded")

def test_technically_verified_requires_meta(base_manifest, tmp_files):
    ManifestSchema.transition(base_manifest, "source_verified_unique")
    ManifestSchema.transition(base_manifest, "source_added")
    base_manifest.update({
        "notebook_id": "1", "generation_job_id": "2", "artifact_id": "3",
        "raw_path": tmp_files["raw_path"], "raw_sha256": tmp_files["raw_sha256"],
        "render_path": tmp_files["render_path"], "render_sha256": tmp_files["render_sha256"]
    })
    ManifestSchema.transition(base_manifest, "generating")
    ManifestSchema.transition(base_manifest, "artifact_ready")
    ManifestSchema.transition(base_manifest, "downloaded")

    with pytest.raises(SchemaError, match="width"):
        ManifestSchema.transition(base_manifest, "technically_verified")

    base_manifest.update({
        "width": 1000, "height": 1080, "duration": 120, "audio_evidence": {"has_audio": True},
        "machine_gate_results": {"g1": "pass", "g2": "pass", "g3": "pass", "g4": "pass"}
    })
    # No need to reset state, the rollback fix handles it.
    with pytest.raises(SchemaError, match="16:9 geometry required"):
        ManifestSchema.transition(base_manifest, "technically_verified")

    base_manifest["width"] = 1920
    ManifestSchema.transition(base_manifest, "technically_verified")

def test_review_pending_requires_review_meta(base_manifest, tmp_files):
    ManifestSchema.transition(base_manifest, "source_verified_unique")
    ManifestSchema.transition(base_manifest, "source_added")
    base_manifest.update({
        "notebook_id": "1", "generation_job_id": "2", "artifact_id": "3",
        "raw_path": tmp_files["raw_path"], "raw_sha256": tmp_files["raw_sha256"],
        "render_path": tmp_files["render_path"], "render_sha256": tmp_files["render_sha256"],
        "width": 1920, "height": 1080, "duration": 120, "audio_evidence": {"has_audio": True},
        "machine_gate_results": {"g1": "pass", "g2": "pass", "g3": "pass", "g4": "pass"}
    })
    ManifestSchema.transition(base_manifest, "generating")
    ManifestSchema.transition(base_manifest, "artifact_ready")
    ManifestSchema.transition(base_manifest, "downloaded")
    ManifestSchema.transition(base_manifest, "technically_verified")

    with pytest.raises(SchemaError, match="visual_review"):
        ManifestSchema.transition(base_manifest, "review_pending")

    base_manifest.update({
        "visual_review_path": tmp_files["visual_review_path"], "visual_review_sha256": tmp_files["visual_review_sha256"],
        "exact_youtube_metadata": {"title": "כותרת", "description": "תיאור", "tags": ["tag"]}
    })
    ManifestSchema.transition(base_manifest, "review_pending")

def test_is_duplicate(base_manifest):
    history = [base_manifest]
    new_item = {"source_url": base_manifest["source_url"]}
    assert is_duplicate(new_item, history)

    new_item2 = {"source_evidence_sha256": base_manifest["source_evidence_sha256"]}
    assert is_duplicate(new_item2, history)

def test_check_review_transition(base_manifest, tmp_files):
    ManifestSchema.transition(base_manifest, "source_verified_unique")
    ManifestSchema.transition(base_manifest, "source_added")
    base_manifest.update({
        "notebook_id": "1", "generation_job_id": "2", "artifact_id": "3",
        "raw_path": tmp_files["raw_path"], "raw_sha256": tmp_files["raw_sha256"],
        "render_path": tmp_files["render_path"], "render_sha256": tmp_files["render_sha256"],
        "width": 1920, "height": 1080, "duration": 120, "audio_evidence": {"has_audio": True},
        "machine_gate_results": {"g1": "pass", "g2": "pass", "g3": "pass", "g4": "pass"},
        "visual_review_path": tmp_files["visual_review_path"], "visual_review_sha256": tmp_files["visual_review_sha256"],
        "exact_youtube_metadata": {"title": "כותרת", "description": "תיאור", "tags": ["tag"]}
    })
    ManifestSchema.transition(base_manifest, "generating")
    ManifestSchema.transition(base_manifest, "artifact_ready")
    ManifestSchema.transition(base_manifest, "downloaded")
    ManifestSchema.transition(base_manifest, "technically_verified")
    ManifestSchema.transition(base_manifest, "review_pending")

    with pytest.raises(StateError, match="Separate nonempty Hebrew notes required"):
        check_review_transition(base_manifest, "good video", True, True, True)

    check_review_transition(base_manifest, "סרטון טוב", True, True, True)
    assert base_manifest["state"] == "reviewed"

def test_is_upload_eligible(base_manifest, tmp_files):
    assert not is_upload_eligible(base_manifest)

    ManifestSchema.transition(base_manifest, "source_verified_unique")
    ManifestSchema.transition(base_manifest, "source_added")
    base_manifest.update({
        "notebook_id": "1", "generation_job_id": "2", "artifact_id": "3",
        "raw_path": tmp_files["raw_path"], "raw_sha256": tmp_files["raw_sha256"],
        "render_path": tmp_files["render_path"], "render_sha256": tmp_files["render_sha256"],
        "width": 1920, "height": 1080, "duration": 120, "audio_evidence": {"has_audio": True},
        "machine_gate_results": {"g1": "pass", "g2": "pass", "g3": "pass", "g4": "pass"},
        "visual_review_path": tmp_files["visual_review_path"], "visual_review_sha256": tmp_files["visual_review_sha256"],
        "exact_youtube_metadata": {"title": "כותרת", "description": "תיאור", "tags": ["tag"]},
        "technical_verified": True,
        "verified": True
    })
    ManifestSchema.transition(base_manifest, "generating")
    ManifestSchema.transition(base_manifest, "artifact_ready")
    ManifestSchema.transition(base_manifest, "downloaded")
    ManifestSchema.transition(base_manifest, "technically_verified")
    ManifestSchema.transition(base_manifest, "review_pending")

    check_review_transition(base_manifest, "סרטון טוב", True, True, True)

    assert is_upload_eligible(base_manifest)

def test_quarantine_legacy_items(base_manifest):
    queue = {"queue": [{"type": "short", "state": "discovered"}, {"type": "normal"}]}
    quarantine_legacy_items(queue)
    assert queue["queue"][0]["state"] == "quarantined"
    assert queue["queue"][1]["state"] == "quarantined"

def test_reconcile_state():
    queue = {"queue": [
        {"state": "public_verified", "exact_youtube_metadata": {"video_id": "v1"}},
        {"state": "public_verified", "exact_youtube_metadata": {"video_id": "v2"}}
    ]}
    reconcile_state(queue, ["v1"])
    assert queue["queue"][0]["state"] == "public_verified"
    assert queue["queue"][1]["state"] == "quarantined"

def test_lock(tmp_path):
    l1 = PipelineLock(tmp_path / "lock.txt")
    l1.acquire()
    l2 = PipelineLock(tmp_path / "lock.txt")
    with pytest.raises(StateError):
        l2.acquire()
    l1.release()

def test_atomic_save(tmp_path):
    target = tmp_path / "queue.json"
    data = {"a": 1}
    atomic_save(target, data)
    assert json.loads(target.read_text()) == data

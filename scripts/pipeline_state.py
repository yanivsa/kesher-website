import json
import os
import fcntl
import hashlib
from datetime import datetime
import re
from pathlib import Path

SCHEMA_VERSION = "1.0"
STATES = [
    "discovered",
    "source_verified_unique",
    "source_added",
    "generating",
    "artifact_ready",
    "downloaded",
    "technically_verified",
    "review_pending",
    "reviewed",
    "upload_session_created",
    "uploaded_unverified",
    "public_verified",
]
TERMINAL_STATES = ["rejected", "quarantined"]

class StateError(Exception): pass
class SchemaError(Exception): pass
class ConfigurationError(Exception): pass

class PipelineLock:
    def __init__(self, lock_path, test_mode=False):
        self.lock_path = Path(lock_path)
        self.test_mode = test_mode
        self.file_obj = None

    def acquire(self):
        if self.test_mode:
            return

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_obj = open(self.lock_path, 'a+')
        try:
            fcntl.flock(self.file_obj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.file_obj.seek(0)
            data = self.file_obj.read()
            pid_match = re.search(r"pid=(\d+)", data)
            if pid_match:
                pid = int(pid_match.group(1))
                try:
                    os.kill(pid, 0)
                    self.file_obj.close()
                    raise StateError(f"Lock held by live process {pid}")
                except ProcessLookupError:
                    pass # Dead owner
            else:
                self.file_obj.close()
                raise StateError("Lock held by live process")

            self.file_obj.close()
            self.file_obj = open(self.lock_path, 'a+')
            try:
                fcntl.flock(self.file_obj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.file_obj.close()
                raise StateError("Lock held by live process")

        self.file_obj.seek(0)
        self.file_obj.truncate()
        self.file_obj.write(f"pid={os.getpid()} started_at={datetime.now().isoformat()}\n")
        self.file_obj.flush()
        os.fsync(self.file_obj.fileno())

    def release(self):
        if self.test_mode or not self.file_obj:
            return
        try:
            fcntl.flock(self.file_obj.fileno(), fcntl.LOCK_UN)
        finally:
            self.file_obj.close()
            self.file_obj = None
            try:
                if self.lock_path.exists():
                    self.lock_path.unlink()
            except OSError:
                pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

def atomic_save(path, data, test_mode=False):
    if test_mode:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix('.tmp')
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)

def load_queue(path):
    path = Path(path)
    if not path.exists():
        return {"queue": []}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"queue": []}

def normalize_url(url):
    if not url: return ""
    return url.split('&')[0].split('#')[0]

def build_manifest_id(date_str, url, sha):
    norm_url = normalize_url(url)
    raw = f"{date_str}_{norm_url}_{sha}"
    return hashlib.sha256(raw.encode()).hexdigest()

class ManifestSchema:
    @staticmethod
    def validate(data):
        if data.get("schema_version") != SCHEMA_VERSION:
            raise SchemaError("Invalid schema version")
        if data.get("type") != "normal":
            raise SchemaError("Only 'normal' type is supported")

        gen_date = data.get("generation_date", "")
        url = data.get("source_url", "")
        sha = data.get("source_evidence_sha256", "")
        if not gen_date or not url or not sha:
            raise SchemaError("generation_date, source_url, source_evidence_sha256 required")

        expected_id = build_manifest_id(gen_date, url, sha)
        if data.get("manifest_id") != expected_id:
            raise SchemaError(f"manifest_id mismatch: expected {expected_id}")

        state = data.get("state")
        if state not in STATES and state not in TERMINAL_STATES:
            raise SchemaError(f"Invalid state: {state}")

        idx = STATES.index(state) if state in STATES else -1

        nb_id = data.get("notebook_id", "")
        job_id = data.get("generation_job_id", "")
        art_id = data.get("artifact_id", "")

        if idx >= STATES.index("generating"):
            if not nb_id or "placeholder" in nb_id: raise SchemaError("real notebook_id required")
            if not job_id or "placeholder" in job_id: raise SchemaError("real generation_job_id required")

        if idx >= STATES.index("artifact_ready"):
            if not art_id or "placeholder" in art_id: raise SchemaError("real artifact_id required")

        if idx >= STATES.index("downloaded"):
            if not data.get("raw_path") or not data.get("raw_sha256"): raise SchemaError("raw_path and raw_sha256 required")
            if not data.get("render_path") or not data.get("render_sha256"): raise SchemaError("render_path and render_sha256 required")

        if idx >= STATES.index("technically_verified"):
            if not data.get("width") or not data.get("height") or not data.get("duration"):
                raise SchemaError("width/height/duration required")
            if not data.get("audio_evidence"): raise SchemaError("audio_evidence required")

            gates = data.get("machine_gate_results")
            if not gates or not isinstance(gates, dict): raise SchemaError("machine_gate_results dictionary required")
            if len(gates) < 4: raise SchemaError("at least four machine gate results required")

        if idx >= STATES.index("review_pending"):
            if not data.get("visual_review_path") or not data.get("visual_review_sha256"):
                raise SchemaError("visual_review_path and sha256 required")
            meta = data.get("exact_youtube_metadata")
            if not meta or not isinstance(meta, dict):
                raise SchemaError("exact_youtube_metadata required")
            if not meta.get("title") or not meta.get("description") or not meta.get("tags"):
                raise SchemaError("empty or default metadata not allowed")

    @staticmethod
    def transition(data, to_state):
        if data.get("state") in TERMINAL_STATES:
            raise StateError("Cannot transition from terminal state")
        if to_state in TERMINAL_STATES:
            data["state"] = to_state
            return

        current = data.get("state")
        curr_idx = STATES.index(current) if current in STATES else -1
        target_idx = STATES.index(to_state)

        if target_idx < curr_idx:
            raise StateError("Backward transitions not allowed")

        data["state"] = to_state
        ManifestSchema.validate(data)

def is_duplicate(new_item, history):
    n_url = normalize_url(new_item.get("source_url", ""))
    n_sha = new_item.get("source_evidence_sha256", "")
    n_man = new_item.get("manifest_id", "")
    n_job = new_item.get("generation_job_id", "")
    n_art = new_item.get("artifact_id", "")
    n_raw = new_item.get("raw_sha256", "")
    n_ren = new_item.get("render_sha256", "")

    for item in history:
        if item is new_item: continue
        i_url = normalize_url(item.get("source_url", ""))
        i_sha = item.get("source_evidence_sha256", "")
        if n_url and i_url and n_url == i_url: return True
        if n_sha and i_sha and n_sha == i_sha: return True
        if n_man and n_man == item.get("manifest_id"): return True
        if n_job and n_job != "placeholder" and n_job == item.get("generation_job_id"): return True
        if n_art and n_art != "placeholder" and n_art == item.get("artifact_id"): return True
        if n_raw and n_raw == item.get("raw_sha256"): return True
        if n_ren and n_ren == item.get("render_sha256"): return True
    return False

def check_review_transition(item_data, review_notes, is_approved, file_hashes_match=True):
    if item_data.get("state") != "review_pending":
        raise StateError("Must be in review_pending state")

    if not file_hashes_match:
        raise StateError("Manifest/file hash match required")

    if not review_notes or not re.search(r'[\u0590-\u05FF]', review_notes):
        raise StateError("Separate nonempty Hebrew notes required")

    src_type = item_data.get("source_type", "")
    meta = item_data.get("exact_youtube_metadata", {})
    desc = meta.get("description", "")

    if "הדרכת הורים" in src_type and "זוגיות" in desc:
        raise StateError("Parenting source with couples metadata fixture rejected")

    if is_approved:
        gates = item_data.get("machine_gate_results", {})
        if gates.get("semantic") == "auto-approved":
            raise StateError("Machine gates may reject but never auto-approve semantics")

        item_data["visual_status"] = "approved"
        item_data["semantic_status"] = "approved"
        item_data["metadata_status"] = "approved"
        item_data["technical_verified"] = True
        ManifestSchema.transition(item_data, "reviewed")
    else:
        ManifestSchema.transition(item_data, "rejected")

def is_upload_eligible(item):
    if item.get("type") != "normal": return False
    if item.get("state") not in ["reviewed", "upload_session_created"]: return False
    if not item.get("technical_verified"): return False
    if not item.get("verified"): return False

    gates = item.get("machine_gate_results", {})
    if len(gates) < 4 or not all(v == "pass" for v in gates.values()): return False

    try:
        ManifestSchema.validate(item)
    except SchemaError:
        return False

    return True

def quarantine_legacy_items(queue_data):
    for item in queue_data.get("queue", []):
        if item.get("state") in TERMINAL_STATES:
            continue
        if item.get("type") == "short" or "schema_version" not in item:
            item["state"] = "quarantined"
            continue

        try:
            ManifestSchema.validate(item)
        except SchemaError:
            item["state"] = "quarantined"

def reconcile_state(queue_data, external_history):
    for item in queue_data.get("queue", []):
        if item.get("state") in ["public_verified", "uploaded_unverified"]:
            vid = item.get("exact_youtube_metadata", {}).get("video_id")
            if vid and vid not in external_history:
                item["state"] = "quarantined"
                item["reconciliation_note"] = "Unavailable external video history"

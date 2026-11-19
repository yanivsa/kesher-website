"""One-source GH-only protected NotebookLM Long production through durable Git CAS.

This worker may execute ONLY in an authentic, reviewed kesher-cutover job of
the EXISTING kesher-media-worker.yml, for its one exact article/command ID.
It is NOT a general-purpose dispatcher or a legacy Schema6 gateway bypass.

Write-ahead source / generation intents are CAS persisted BEFORE every provider
POST. Existing or uncertain intents NEVER cause a repeat POST. Original provider
outputs get QA evidence without upload. Native Short and YouTube are explicitly
held until separately reviewed long/short QA and public release authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from .github import GitHub
from .github_only_effects import GitHubOnlyEffectJournal
from .github_only_live_activation import _reviewed_run
from .github_only_live_inventory import (
    NOTEBOOK, _provider_json, _rows, inspect_live_inventory,
)
from .github_only_owner_policy import command_identity, OwnerLedgerBlocked
from .github_only_owner_store import REPOSITORY, GitHubOnlyLedgerStore
from .github_owner_readiness import inventory
from .identity import canonical_json, digest
from .state import StateInvalid

SLOT = "2026-11-18"
SLUG = "couple-conversation-stuck-pursue-withdraw-cycle"
SOURCE_SHA256 = "e5a57c64f85a2e56d355c73b4abe052c5052aa1addb074fcea677262c8b77616"
OPERATION = "article"
EPOCH = "kesher-ghonly-20261117-prepare1"
COMMAND_ID = command_identity(slot=SLOT, source_sha256=SOURCE_SHA256, operation=OPERATION)
WORKFLOW = REPOSITORY + "/.github/workflows/kesher-media-worker.yml@refs/heads/main"
LIVENESS = REPOSITORY + "/.github/workflows/kesher-controller-liveness.yml@refs/heads/main"
SOURCE_TITLE = "kesher-ghonly:" + SLUG + ":" + SOURCE_SHA256[:12]
_HASH = re.compile(r"[a-f0-9]{64}")
_UUID = re.compile(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}")
_TERMINAL = {"completed", "rejected", "cancelled", "failed"}


def trusted_article():
    from scripts import kesher_daily_pipeline as core
    source = core.article_by_slug(SLUG)
    if (source.get("slug") != SLUG or source.get("date") != SLOT
            or source.get("content_sha256") != SOURCE_SHA256
            or hashlib.sha256(source.get("body", "").encode()).hexdigest() != SOURCE_SHA256
            or source.get("canonical_url") !=
               "https://kesher.saharoni.com/blog/" + SLUG):
        raise StateInvalid("GHONLY_PRODUCTION_IMMUTABLE_SOURCE_MISMATCH")
    return source


def _verify_review_chain(github, document, main):
    owner = document.get("protected_live") or {}
    if (document.get("owner") != "github-only"
            or document.get("activation") != "PROTECTED_VERIFIED"
            or document.get("inventory_complete") is not True
            or document.get("epoch") != EPOCH
            or document.get("reviewed_main_sha") != main
            or owner.get("single_writer") != "github-only"
            or owner.get("media_qa_required") is not True
            or owner.get("source_publication_authorized") is not False
            or not isinstance(document.get("commands"), dict)):
        raise StateInvalid("GHONLY_PRODUCTION_ACTIVATION_NOT_VERIFIED")
    revs = owner.get("code_revision_reviews")
    if not isinstance(revs, list) or not revs:
        raise StateInvalid("GHONLY_PRODUCTION_MISSING_REAL_CODE_REVIEW")
    prior = revs[0].get("previous_main")
    if not isinstance(prior, str) or not re.fullmatch(r"[a-f0-9]{40}", prior):
        raise StateInvalid("GHONLY_PRODUCTION_INVALID_INITIAL_REVIEW_MAIN")
    _reviewed_run(github, owner.get("approved_review_run"), prior)
    for step in revs:
        if (not isinstance(step, dict) or step.get("previous_main") != prior
                or not isinstance(step.get("reviewed_main"), str)
                or not re.fullmatch(r"[a-f0-9]{40}", step["reviewed_main"])):
            raise StateInvalid("GHONLY_PRODUCTION_REVIEW_CHAIN_BROKEN")
        _reviewed_run(github, step.get("approved_review_run"), step["reviewed_main"])
        prior = step["reviewed_main"]
    if prior != main:
        raise StateInvalid("GHONLY_PRODUCTION_REVIEWED_CODE_STALE")


def _exact_run(github, *, environment, expected_main, command_id):
    if (command_id != COMMAND_ID
            or environment.get("GITHUB_REPOSITORY") != REPOSITORY
            or environment.get("GITHUB_WORKFLOW_REF") != WORKFLOW
            or environment.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or environment.get("GITHUB_REF") != "refs/heads/main"
            or environment.get("GITHUB_JOB") != "github_only_production"
            or environment.get("GITHUB_SHA") != expected_main
            or environment.get("GITHUB_WORKFLOW_SHA") != expected_main
            or not re.fullmatch(r"[a-f0-9]{40}", expected_main)):
        raise StateInvalid("GHONLY_PRODUCTION_EXACT_JOB_SHA_COMMAND_REQUIRED")
    rid, attempt = environment.get("GITHUB_RUN_ID", ""), environment.get("GITHUB_RUN_ATTEMPT", "")
    if not re.fullmatch(r"[1-9][0-9]*", rid) or not re.fullmatch(r"[1-9][0-9]*", attempt):
        raise StateInvalid("GHONLY_PRODUCTION_EXACT_RUN_ATTEMPT_REQUIRED")
    row = github.request("GET", "/repos/" + REPOSITORY + "/actions/runs/" + rid)
    if (str(row.get("id")) != rid or row.get("path") != ".github/workflows/kesher-media-worker.yml"
            or row.get("head_sha") != expected_main
            or row.get("event") != "workflow_dispatch"
            or row.get("head_branch") != "main"
            or str(row.get("run_attempt")) != attempt):
        raise StateInvalid("GHONLY_PRODUCTION_UNTRUSTED_WORKFLOW_RUN")
    _reviewed_run(github, rid + ":" + attempt, expected_main)
    return rid + ":" + attempt


def _observed_terminal_tasks():
    """One authenticated complete catalog; any active/unknown task blocks claim."""
    records = _rows(_provider_json([
        "artifact", "list", "--type", "video", "--notebook", NOTEBOOK,
    ]), "artifacts")
    statuses = {}
    for row in records:
        task_id = row.get("id", row.get("task_id", row.get("artifact_id")))
        status = str(row.get("status", row.get("state", ""))).lower().strip()
        if not isinstance(task_id, str) or not _UUID.fullmatch(task_id):
            raise StateInvalid("GHONLY_PRODUCTION_UNTRUSTED_PROVIDER_TASK_ID")
        if status not in _TERMINAL or task_id in statuses:
            raise StateInvalid("GHONLY_PRODUCTION_UNSETTLED_OR_DUPLICATE_TASK")
        # plan_dispatch only supports the three terminal policy categories.
        statuses[task_id] = "rejected" if status == "failed" else status
    if len(statuses) < 8:
        raise StateInvalid("GHONLY_PRODUCTION_INCOMPLETE_PROVIDER_TASK_CATALOG")
    return statuses


def acquire(github, *, env, expected_main, command_id):
    """One reviewed run claims exactly one source-bound creation command."""
    run_id = _exact_run(
        github, environment=env, expected_main=expected_main,
        command_id=command_id,
    )
    source = trusted_article()
    store = GitHubOnlyLedgerStore(github)
    before = store.load(reviewed_main_sha=expected_main)
    _verify_review_chain(github, before.document, expected_main)
    # Reobserve *all* external tasks/YouTube before the first write. Never
    # infer 'not created' merely because a legacy state file has no task.
    report = inspect_live_inventory()
    if (report.get("no_active_notebooklm_tasks") is not True
            or report.get("youtube_scan_complete") is not True
            or report.get("provider_mutations") is not False):
        raise StateInvalid("GHONLY_PRODUCTION_PROVIDER_INVENTORY_NOT_CLEAR")
    observed = _observed_terminal_tasks()
    check = inventory(
        github, expected_main=expected_main, workflow_ref=LIVENESS,
        event_name="workflow_dispatch", repo=REPOSITORY,
    )
    if (check.get("status") not in (
            "READY_FOR_REVIEWED_MIGRATION_ONLY", "BLOCKED_EXISTING_OWNER_OR_TASK")
            or check.get("legacy_blob_sha")
                    != before.document.get("migration_basis", {}).get("legacy_blob_sha")):
        raise StateInvalid("GHONLY_PRODUCTION_LEGACY_FENCE_CHANGED")
    pending = check.get("pending")
    if not isinstance(pending, list):
        raise StateInvalid("GHONLY_PRODUCTION_ACTIVE_RUNS_UNTRUSTED")
    # The one approved current media-worker run is not a competing owner.
    # EVERY other active media/legacy run is an unconditional blocker.
    self_rows = [r for r in pending
                 if isinstance(r, dict)
                 and r.get("workflow") == "kesher-media-worker.yml"
                 and r.get("run") == int(env["GITHUB_RUN_ID"])
                 and r.get("status") == "in_progress"]
    if len(self_rows) != 1 or len(pending) != 1:
        raise StateInvalid("GHONLY_PRODUCTION_COMPETING_GITHUB_RUN")
    decision, loaded = store.claim(
        before, epoch=EPOCH, command_id=COMMAND_ID,
        workflow_run=run_id, observed_provider_tasks=observed,
        pending_github_runs=[],
    )
    if decision != "CLAIMED":
        return decision, loaded, source, run_id
    return "CLAIMED", loaded, source, run_id


def _source_observer(request):
    """SDK verifies original fulltext and exact stable title, not just a list."""
    payload = json.dumps({"name": "provider_source", "request": request})
    result = subprocess.run(
        [sys.executable, "-m", "scripts.kesher_runtime.provider"],
        input=payload, capture_output=True, text=True, timeout=180,
        check=False,
    )
    if result.returncode:
        raise StateInvalid("GHONLY_PRODUCTION_SOURCE_READBACK_FAILED")
    row = json.loads(result.stdout)
    if set(row) != {"receipt"}:
        raise StateInvalid("GHONLY_PRODUCTION_SOURCE_OBSERVER_UNTRUSTED")
    return row["receipt"]


def _generation_observer(request):
    payload = json.dumps({"name": "provider_generation", "request": request})
    result = subprocess.run(
        [sys.executable, "-m", "scripts.kesher_runtime.provider"],
        input=payload, capture_output=True, text=True, timeout=180,
        check=False,
    )
    if result.returncode:
        raise StateInvalid("GHONLY_PRODUCTION_GENERATION_READBACK_FAILED")
    row = json.loads(result.stdout)
    if set(row) != {"receipt"}:
        raise StateInvalid("GHONLY_PRODUCTION_GENERATION_OBSERVER_UNTRUSTED")
    return row["receipt"]


def _external_post_once(args):
    """The only mutation transport. Caller must hold a fresh CAS INTENT."""
    try:
        result = subprocess.run(
            ["notebooklm", *args, "--json"],
            capture_output=True, text=True, timeout=180, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StateInvalid("GHONLY_PRODUCTION_POST_OUTCOME_UNKNOWN") from exc
    if result.returncode:
        # Failed/timeout API may have accepted the request. DO NOT RETRY.
        raise StateInvalid("GHONLY_PRODUCTION_POST_UNCERTAIN_NO_RETRY")
    try:
        row = json.loads(result.stdout)
        if not isinstance(row, dict):
            raise ValueError("not dict")
        return row
    except ValueError as exc:
        raise StateInvalid("GHONLY_PRODUCTION_POST_ACK_UNTRUSTED_NO_RETRY") from exc


def _identity_params(run_id):
    return dict(epoch=EPOCH, command_id=COMMAND_ID, run_id=run_id,
                slot=SLOT, slug=SLUG, source_sha256=SOURCE_SHA256,
                operation=OPERATION)


def source_once(journal, loaded, *, run_id, source):
    params = _identity_params(run_id)
    request = {
        "notebook_id": NOTEBOOK, "title": SOURCE_TITLE,
        "body_sha256": SOURCE_SHA256,
        "body_normalized_sha256": hashlib.sha256(
            " ".join(source["body"].split()).encode()
        ).hexdigest(),
    }
    action, state = journal.begin(
        loaded, **params, effect_kind="notebooklm_source",
        request_sha256=digest(request),
    )
    if action != "INTENT_RECORDED":
        # Existing intent might already have touched the provider. Read-only
        # reconciliation can resume later; no automatic second POST.
        return "NO_REPEAT_POST", state, None
    receipt = _source_observer(request)
    if receipt is None:
        _external_post_once([
            "source", "add", source["body"], "--type", "text",
            "--title", SOURCE_TITLE, "--notebook", NOTEBOOK,
        ])
    # Independent fulltext readback after the provider create response.
    receipt = _source_observer(request)
    source_id = receipt.get("source_id") if isinstance(receipt, dict) else None
    if not isinstance(source_id, str) or not _UUID.fullmatch(source_id):
        raise StateInvalid("GHONLY_PRODUCTION_SOURCE_ACK_UNKNOWN_NO_RETRY")
    _, state = journal.observe(
        state, **params, effect_kind="notebooklm_source",
        request_sha256=digest(request),
        provider_id=source_id, receipt_sha256=digest(receipt),
    )
    _, state = journal.verify_output(
        state, **params, effect_kind="notebooklm_source",
        request_sha256=digest(request), provider_id=source_id,
        receipt_sha256=digest(receipt), qa_sha256=SOURCE_SHA256,
        evidence_kind="source_fulltext",
    )
    return "SOURCE_VERIFIED", state, source_id


def long_once(journal, loaded, *, run_id, source, source_id, folder):
    from scripts import kesher_daily_pipeline as core
    params = _identity_params(run_id)
    # Immutable internal marker makes the approved source, provider item and
    # attempt recoverable by READ-ONLY exact generation_prompt comparison.
    marker = digest({
        "slot": SLOT, "slug": SLUG, "source_sha256": SOURCE_SHA256,
        "source_id": source_id, "format": "explainer", "epoch": EPOCH,
        "attempt": 1,
    })
    prompt = (core.generation_prompt(source)
              + "\n\nמזהה בקרה פנימי, אין להציג או להקריא: " + marker)
    request = {
        "notebook_id": NOTEBOOK, "source_id": source_id,
        "format": "explainer", "style": "auto", "language": "he",
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    }
    action, state = journal.begin(
        loaded, **params, effect_kind="notebooklm_long",
        request_sha256=digest(request),
    )
    if action != "INTENT_RECORDED":
        return "NO_REPEAT_POST", state, None
    observed = _generation_observer(request)
    if observed is None:
        folder.mkdir(parents=True, exist_ok=True)
        promptfile = folder / "long-prompt-he.txt"
        promptfile.write_text(prompt, encoding="utf-8")
        _external_post_once([
            "generate", "video", "--prompt-file", str(promptfile),
            "--notebook", NOTEBOOK, "--source", source_id,
            "--format", "explainer", "--style", "auto",
            "--language", "he", "--no-wait",
        ])
    observed = _generation_observer(request)
    task_id = (observed.get("task_id") if isinstance(observed, dict) else None)
    if not isinstance(task_id, str) or not _UUID.fullmatch(task_id):
        raise StateInvalid("GHONLY_PRODUCTION_LONG_ACK_UNKNOWN_NO_RETRY")
    _, state = journal.observe(
        state, **params, effect_kind="notebooklm_long",
        request_sha256=digest(request),
        provider_id=task_id, receipt_sha256=digest(observed),
    )
    return "LONG_ID_RECORDED", state, task_id


def wait_existing_task(task_id, *, max_minutes=27):
    from scripts import kesher_daily_pipeline as core
    until = time.monotonic() + max_minutes * 60
    while time.monotonic() < until:
        response = _provider_json([
            "artifact", "poll", task_id, "--notebook", NOTEBOOK,
        ])
        status = core.artifact_status(response)
        if status in ("completed", "complete", "ready", "success", "succeeded"):
            return "COMPLETED"
        if status in ("failed", "error", "cancelled", "canceled", "rejected"):
            raise StateInvalid("GHONLY_PRODUCTION_LONG_PROVIDER_REJECTED")
        if status not in ("generating", "pending", "queued", "processing", "running", "in_progress"):
            raise StateInvalid("GHONLY_PRODUCTION_LONG_UNTRUSTED_PROVIDER_STATE")
        time.sleep(25)
    return "WAITING_PROVIDER"


def long_qa(task_id, *, folder, source):
    from scripts import kesher_daily_pipeline as core
    folder.mkdir(parents=True, exist_ok=True)
    mp4 = folder / "original-notebooklm-long.mp4"
    response = subprocess.run([
        "notebooklm", "download", "video", str(mp4),
        "--notebook", NOTEBOOK, "--artifact", task_id, "--force", "--json",
    ], capture_output=True, text=True, timeout=900, check=False)
    if response.returncode or not mp4.is_file() or mp4.stat().st_size < 1024:
        raise StateInvalid("GHONLY_PRODUCTION_LONG_DOWNLOAD_NOT_VERIFIED")
    media = core.ffprobe(mp4)
    if (media.get("codec") != "h264" or not media.get("audio_codec")
            or media.get("width", 0) < 960
            or media.get("height", 0) < 540
            or not 1.70 <= media["width"] / media["height"] <= 1.82
            or not 90 <= media.get("duration", 0) <= 180):
        raise StateInvalid("GHONLY_PRODUCTION_LONG_TECHNICAL_QA_HOLD")
    original_item = {"id": "ghonly-" + SOURCE_SHA256[:14]}
    contact = core.create_contact_sheet(mp4, original_item, media["duration"])
    transcript = core.transcribe_hebrew(mp4, original_item)
    count = len(re.findall(r"[\u0590-\u05ff]",
                           transcript.read_text(encoding="utf-8")))
    pitch = core.estimate_voice_pitch(mp4)
    qa = {
        "source_slug": SLUG, "source_sha256": SOURCE_SHA256,
        "provider_task_id": task_id,
        "media_sha256": core.sha256_file(mp4),
        "contact_sheet_sha256": core.sha256_file(contact),
        "transcript_sha256": core.sha256_file(transcript),
        "hebrew_transcript_characters": count,
        "pitch_hz": round(pitch, 2) if pitch is not None else None,
        "media": media, "native_long": True,
        "visual_editorial_approved": False,
        "audio_editorial_approved": False,
        "semantic_source_review_approved": False,
        "new_short_generation_authorized": False,
        "youtube_upload_authorized": False,
        "qa_status": "VOICE_QA_HOLD" if (
            pitch is None or pitch < core.FEMALE_PITCH_MIN_HZ or count < 40
        ) else "TECHNICAL_ACCEPTED_EDITORIAL_HOLD",
    }
    (folder / "qa.json").write_text(canonical_json(qa) + "\n", encoding="utf-8")
    mp4.unlink()  # Never upload the raw MP4 in an Actions artifact.
    return qa


def run(github, *, env, command_id, output):
    """One bounded action; no Short or YouTube until Long passes QA/release."""
    main = env.get("GITHUB_SHA", "")
    decision, loaded, source, run_id = acquire(
        github, env=env, expected_main=main, command_id=command_id,
    )
    if decision == "NOOP":
        print("KESHER_GHONLY_DUPLICATE_COMMAND_NOOP")
        return {"status": "DUPLICATE_NOOP", "publication": False}
    if decision != "CLAIMED":
        raise StateInvalid("GHONLY_PRODUCTION_INVALID_CLAIM_RESULT")
    journal = GitHubOnlyEffectJournal(GitHubOnlyLedgerStore(github))
    action, loaded, source_id = source_once(
        journal, loaded, run_id=run_id, source=source,
    )
    if action != "SOURCE_VERIFIED":
        return {"status": "WAITING_EXACT_SOURCE_RECONCILIATION",
                "publication": False}
    action, loaded, task_id = long_once(
        journal, loaded, run_id=run_id, source=source,
        source_id=source_id, folder=output,
    )
    if action != "LONG_ID_RECORDED":
        return {"status": "WAITING_EXACT_VIDEO_RECONCILIATION",
                "publication": False}
    status = wait_existing_task(task_id)
    if status != "COMPLETED":
        return {"status": "WAITING_PROVIDER",
                "task_id": task_id, "publication": False}
    qa = long_qa(task_id, folder=output, source=source)
    print("KESHER_GHONLY_GENERATION_QA " + canonical_json(qa))
    return {"status": qa["qa_status"], "task_id": task_id,
            "publication": False}


def main(argv=None):
    if len(sys.argv) != 2:
        print("GHONLY_PRODUCTION_EXACT_COMMAND_INPUT_REQUIRED", file=sys.stderr)
        return 2
    try:
        result = run(
            GitHub(os.environ.get("GH_TOKEN", "")),
            env=os.environ, command_id=sys.argv[1],
            output=Path(os.environ.get("KESHER_GHONLY_OUTPUT", "/tmp/kesher-ghonly-new")),
        )
        print("KESHER_GHONLY_PRODUCTION " + canonical_json(result))
        return 0
    except (RuntimeError, ValueError, OSError, KeyError, TypeError,
            subprocess.TimeoutExpired):
        print("GHONLY_PRODUCTION_SAFELY_BLOCKED_NO_RETRY", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

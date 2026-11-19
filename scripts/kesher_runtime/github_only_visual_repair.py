"""Read-only source-bound remaster of the original NotebookLM Long.

This NEVER creates a NotebookLM task, uploads to YouTube, mutates the GH-only
owner ledger, retargets a scheduler or authorizes public publication.

Visuals are ORIGINAL animated Remotion scenes, without external stock URLs.
The authentic original NotebookLM audio is *stream-copied* (not regenerated).
The rendered MP4 and proof may be held in a short-lived private GitHub artifact
for an independent full visual+audio+source QA, NOT a YouTube public video.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .github import GitHub
from .github_only_qa_hold import (
    COMMAND_ID, SOURCE_SHA, SOURCE_SLUG, ORIGINAL_TASK_ID, MEDIA_SHA,
    SEALED_EVIDENCE, hold_basis, verified_qa_hold,
)
from .github_only_media_production import _verify_review_chain
from .github_only_live_inventory import NOTEBOOK, inspect_live_inventory
from .github_only_owner_store import GitHubOnlyLedgerStore, REPOSITORY
from .identity import canonical_json
from .state import StateInvalid

WORKFLOW = REPOSITORY + "/.github/workflows/kesher-controller-liveness.yml@refs/heads/main"
ARTIFACT_ROOT = Path("/tmp/kesher-ghonly-visual-repair")
REVIEW_FRAMES = 8
_ORIGINAL_SIZE_MAX = 1024 * 1024 * 1024


def exact_admission(github, *, env):
    sha = env.get("GITHUB_SHA", "")
    if (env.get("GITHUB_REPOSITORY") != REPOSITORY
            or env.get("GITHUB_WORKFLOW_REF") != WORKFLOW
            or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("GITHUB_JOB") != "github_only_visual_repair"
            or env.get("REVIEWED_REVISION") != sha
            or not isinstance(sha, str)
            or re.fullmatch(r"[0-9a-f]{40}", sha) is None):
        raise StateInvalid("GHONLY_VISUAL_REPAIR_EXACT_REVIEWED_RUN_REQUIRED")
    store = GitHubOnlyLedgerStore(github)
    snapshot = store.load(reviewed_main_sha=sha)
    doc = snapshot.document
    _verify_review_chain(github, doc, sha)
    if (doc.get("activation") != "PROTECTED_VERIFIED"
            or doc.get("reviewed_main_sha") != sha
            or doc.get("owner") != "github-only"
            or doc.get("protected_live", {}).get("source_publication_authorized") is not False
            or hold_basis(doc) != SEALED_EVIDENCE
            or doc["commands"][COMMAND_ID].get("phase") != "QA_HOLD"):
        raise StateInvalid("GHONLY_VISUAL_REPAIR_SEALED_SOURCE_REQUIRED")
    # Independently check ALL external tasks before handling provider bytes.
    inventory = inspect_live_inventory()
    if (inventory.get("notebooklm_authenticated") is not True
            or inventory.get("youtube_authenticated") is not True
            or inventory.get("no_active_notebooklm_tasks") is not True
            or inventory.get("youtube_scan_complete") is not True
            or inventory.get("provider_mutations") is not False):
        raise StateInvalid("GHONLY_VISUAL_REPAIR_UNSAFE_PROVIDER_INVENTORY")
    verified_qa_hold(github, doc)
    from scripts import kesher_daily_pipeline as core
    article = core.article_by_slug(SOURCE_SLUG)
    if (article.get("slug") != SOURCE_SLUG
            or article.get("content_sha256") != SOURCE_SHA
            or article.get("date") != "2026-11-18"
            or hashlib.sha256(article.get("body", "").encode("utf-8")).hexdigest() != SOURCE_SHA):
        raise StateInvalid("GHONLY_VISUAL_REPAIR_SOURCE_DRIFT")
    return article, snapshot


def _call(args, *, timeout):
    result = subprocess.run(args, check=False, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise StateInvalid("GHONLY_VISUAL_REPAIR_SUBPROCESS_FAILED:" + str(args[0]))
    return result


def _audio_hash(path):
    """Hash decoded authentic speech, independent of the MP4 container."""
    r = _call([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", "-f", "hash", "-hash", "sha256", "-",
    ], timeout=180)
    value = r.stdout.strip().removeprefix("SHA256=").lower()
    if re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise StateInvalid("GHONLY_VISUAL_REPAIR_AUDIO_FINGERPRINT_INVALID")
    return value


def _source_mp4(output: Path):
    raw = output / "exact-original-notebooklm.mp4"
    _call([
        "notebooklm", "download", "video", str(raw),
        "--notebook", NOTEBOOK, "--artifact", ORIGINAL_TASK_ID, "--force",
    ], timeout=900)
    if (not raw.is_file() or raw.is_symlink() or raw.stat().st_size > _ORIGINAL_SIZE_MAX
            or raw.stat().st_size < 1024):
        raise StateInvalid("GHONLY_VISUAL_REPAIR_PROVIDER_FILE_INVALID")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    if digest != MEDIA_SHA:
        raise StateInvalid("GHONLY_VISUAL_REPAIR_ORIGINAL_MEDIA_HASH_MISMATCH")
    return raw


def render_exact_story(raw: Path, output: Path, article: dict):
    from scripts import kesher_daily_pipeline as core
    meta = core.ffprobe(raw)
    if (meta.get("codec") != "h264" or not meta.get("audio_codec")
            or not 90 <= meta.get("duration", 0) <= 180
            or meta.get("width") != 1280 or meta.get("height") != 720):
        raise StateInvalid("GHONLY_VISUAL_REPAIR_ORIGINAL_TECHNICAL_MISMATCH")

    frames = round(float(meta["duration"]) * 30)
    props = {
        "durationInFrames": frames,
        "articleTitle": article["title"],
        "signatureImageSrc": "signature-mask.svg",
    }
    props_path = output / "visual-props.json"
    props_path.write_text(canonical_json(props) + "\n", encoding="utf-8")
    signature = Path(__file__).resolve().parents[2] / "public/images/signature/signature-mask.svg"
    if not signature.is_file() or signature.stat().st_size < 50:
        raise StateInvalid("GHONLY_VISUAL_REPAIR_SIGNATURE_ASSET_MISSING")
    shutil.copyfile(signature, output / "signature-mask.svg")
    project = Path(__file__).resolve().parents[2]
    remotion = project / "node_modules/.bin/remotion"
    if not remotion.is_file():
        raise StateInvalid("GHONLY_VISUAL_REPAIR_REMOTION_NOT_INSTALLED")
    visual_only = output / "animated-original-scenes-no-audio.mp4"
    result = subprocess.run([
        str(remotion), "render", "src/remotion/index.ts", "KesherCinematicRepair",
        str(visual_only), "--props=" + str(props_path),
        "--public-dir=" + str(output), "--codec=h264", "--concurrency=2",
        "--timeout=120000",
    ], cwd=project, capture_output=True, text=True, check=False, timeout=2700)
    if (result.returncode != 0 or not visual_only.is_file()
            or visual_only.stat().st_size < 1024):
        raise StateInvalid("GHONLY_VISUAL_REPAIR_RENDER_FAILED")
    final = output / "kesher-remastered-cinematic-review.mp4"
    # Hard preserve original NotebookLM audio stream. No voice model or TTS.
    _call([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(visual_only), "-i", str(raw),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "copy", "-shortest", str(final),
    ], timeout=600)
    visual_only.unlink()
    final_meta = core.ffprobe(final)
    if (final_meta.get("codec") != "h264"
            or not final_meta.get("audio_codec")
            or final_meta.get("width") != 1280
            or final_meta.get("height") != 720
            or abs(float(final_meta.get("duration", 0)) - float(meta["duration"])) > 0.20):
        raise StateInvalid("GHONLY_VISUAL_REPAIR_FINAL_TECHNICAL_MISMATCH")
    raw_audio = _audio_hash(raw)
    final_audio = _audio_hash(final)
    if raw_audio != final_audio:
        raise StateInvalid("GHONLY_VISUAL_REPAIR_NOTEBOOKLM_AUDIO_CHANGED")
    item = {"id": "ghonly-cinematic-e5a57c64f85a2e", "visual_pipeline": "remotion-v1-notebooklm-audio"}
    sheet = core.create_contact_sheet(final, item, float(final_meta["duration"]))
    # Varying scenes must be inspected; frame-to-frame movement alone cannot
    # attest quality. The original source audio remains unmodified.
    raw_pitch = core.estimate_voice_pitch(raw)
    report = {
        "status": "VISUAL_REPAIR_RENDERED_EDITORIAL_QA_HOLD",
        "source_slug": SOURCE_SLUG, "source_sha256": SOURCE_SHA,
        "original_notebooklm_task_id": ORIGINAL_TASK_ID,
        "original_notebooklm_media_sha256": MEDIA_SHA,
        "final_sha256": core.sha256_file(final),
        "original_audio_decoded_sha256": raw_audio,
        "repaired_audio_decoded_sha256": final_audio,
        "audio_bitstream_preserved": True,
        "final_media": final_meta,
        "storyboard": "original_animated_couple_narrative_no_stock_slideshow",
        "storyboard_scenes": 9,
        "visual_contact_sheet_sha256": core.sha256_file(sheet),
        "estimated_voice_pitch_hz": round(raw_pitch, 2) if raw_pitch is not None else None,
        "human_visual_review_passed": False,
        "human_hebrew_audio_review_passed": False,
        "human_source_semantics_review_passed": False,
        "youtube_upload_authorized": False,
        "new_notebooklm_short_authorized": False,
        "github_state_mutations": False,
        "new_provider_tasks_created": False,
    }
    (output / "visual-repair-qa.json").write_text(
        canonical_json(report) + "\n", encoding="utf-8",
    )
    # Original provider MP4 stays ephemeral. Only altered version retained
    # for private QA, with GitHub artifact short retention and no public URL.
    raw.unlink()
    return report


def run(github, *, env, output):
    article, _ = exact_admission(github, env=env)
    output.mkdir(parents=True, exist_ok=True)
    raw = _source_mp4(output)
    report = render_exact_story(raw, output, article)
    print("GHONLY_VISUAL_REPAIR " + canonical_json(report))
    return report


def main():
    try:
        result = run(GitHub(os.environ.get("GH_TOKEN", "")), env=os.environ,
                     output=ARTIFACT_ROOT)
        return 0 if result.get("status") == "VISUAL_REPAIR_RENDERED_EDITORIAL_QA_HOLD" else 2
    except (RuntimeError, ValueError, TypeError, OSError, KeyError, subprocess.TimeoutExpired):
        print("GHONLY_VISUAL_REPAIR_BLOCKED_NO_PUBLICATION", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

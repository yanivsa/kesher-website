#!/usr/bin/env python3
"""V4 adapter that turns the proven NotebookLM pipeline into one YouTube Short.

The legacy module remains the provider/upload engine. V4 replaces only the
creative contract, Remotion render, and technical validation:

* NotebookLM remains the narration/source master;
* the prompt requests one concise, complete idea with a natural ending;
* provider output keeps its full natural duration instead of being hard-trimmed;
* Remotion renders the exact source/audio into a 1080x1920 composition;
* technical publication requires H.264 + audio + 9:16; duration is preserved unchanged.

No second TTS engine, generic captions, or second semantic video is introduced.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__:
    from . import kesher_daily_pipeline as core
    from . import kesher_e2e_delivery_guard as delivery_guard
    from .kesher_short_motion_plan import build_motion_plan
    from .kesher_video_enhancement import build_enhancement_manifest, execute_enhancement
else:
    import kesher_daily_pipeline as core
    import kesher_e2e_delivery_guard as delivery_guard
    from kesher_short_motion_plan import build_motion_plan
    from kesher_video_enhancement import build_enhancement_manifest, execute_enhancement

SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920
SHORT_FPS = 30
SIGNATURE_DURATION_SECONDS = 3.0
NATIVE_SHORT_FALLBACK_ATTEMPT = 3
VISUAL_PIPELINE = "remotion-v4-notebooklm-short-motion-plan-v1"
SIGNATURE_SOURCE = Path("public/images/signature/signature-mask.svg")
SIGNATURE_RUNTIME_NAME = "signature-mask.svg"
OPTIONAL_TARGET_ASSET_FIELDS = (
    "assetRef",
    "assetType",
    "assetStartFrame",
    "assetEndFrame",
    "assetIntent",
    "assetProvenance",
)

_base_new_item = core.new_item


def generation_prompt(source: dict[str, Any]) -> str:
    short_metadata = source.get("short_youtube_metadata") or {}
    short_topic = str(short_metadata.get("title") or source.get("short_title") or source["title"]).strip()
    short_hook = str(source.get("short_hook") or "").strip()
    hook_instruction = f'פתח במשפט הבא: "{short_hook}" ' if short_hook else ""
    prompt = (
        "חובה: כל הקריינות, מתחילת הסרטון ועד סופו, בקול נשי בלבד. אין להשתמש בקול גברי, "
        "אין להחליף בין דוברים, ואין להשתמש בקול ניטרלי או דו-קולי. "
        "הקול צריך להישמע כאישה ישראלית בוגרת, טבעית, חמה, ברורה ומקצועית. "
        "אם אין אפשרות להבטיח קול נשי — אל תפיק תוצר. "
        "צור סרטון קצר מקורי שנוצר מלכתחילה כסרטון אנכי ביחס 9:16 בעברית טבעית בלבד, המבוסס אך ורק על המקור שנבחר. "
        "אין ליצור סקירת וידאו אופקית, אין ליצור יחס 16:9, ואין להסתמך על חיתוך, מסגור מחדש או המרה מאוחרת של וידאו ארוך לסרטון קצר. "
        "אין מגבלת משך: העדף קיצור, אך תן לרעיון להסתיים במלואו ובאופן טבעי. "
        "תזכורת מחייבת: הקריינות כולה בקול נשי ישראלי בלבד. "
        "הרעיון השלם חייב לעמוד בפני עצמו: פתח במשפט שמציג בעיה או שאלה ברורה, "
        "המשך בתובנה אחת בלבד ובדוגמה אחת קצרה, וסיים בפעולה מעשית אחת ובסיום טבעי ומלא. "
        "לעולם אל תקטע משפט, מחשבה או מסקנה כדי לעמוד במשך מסוים. "
        "אין לערבב בין הורות לזוגיות כאשר המקור עוסק רק באחד מהם. "
        "אין להוסיף אבחנות, תארים מקצועיים או הבטחות שאינם במקור. "
        "כל קריינות או טקסט חזותי יהיו בעברית תקינה. אין להשתמש באנגלית, בג׳יבריש, "
        "בטבלאות או בתרשימים. אין ליצור מטא־דאטה ליוטיוב בתוך הווידאו. "
        f"{hook_instruction}"
        f"הנושא המדויק הוא: {short_topic}"
    )
    core.require_hebrew(prompt, "Short generation prompt")
    return prompt


def repair_youtube_metadata(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("source") or {}
    try:
        metadata = core.publication_metadata(source, "short")
    except core.VerificationError as exc:
        raise core.PipelineError(str(exc)) from exc
    item["youtube_metadata"] = metadata
    return core.apply_enhancement_media_credits(item)


def new_item(source: dict[str, Any]) -> dict[str, Any]:
    item = _base_new_item(source)
    item["type"] = "article_short"
    item["source_mode"] = "direct-short"
    item["provider_video_format"] = "short"
    item["provider_native_short"] = True
    item["provider_short_fallback_used"] = False
    item["fresh_generation_attempt"] = int(item.get("technical_retry_count") or 0) + 1
    repair_youtube_metadata(item)
    return item


def start_generation(state: dict[str, Any], item: dict[str, Any]) -> None:
    """Prefer a provider-native Short; use an independent landscape fallback only on the bounded final attempt."""
    from scripts.kesher_runtime.media_state import CanonicalMediaState
    from scripts.kesher_runtime.legacy_retirement import media_mutation
    media_mutation(state)
    from scripts.kesher_runtime.provider import bind_generation_prompt
    prompt_path = core.STATE_DIR / f"{item['id']}-prompt-he.txt"
    prompt = generation_prompt(item["source"])
    attempt = int(item.get("fresh_generation_attempt") or 1)
    provider_format = "short" if attempt < NATIVE_SHORT_FALLBACK_ATTEMPT else "explainer"
    if not 1 <= attempt <= NATIVE_SHORT_FALLBACK_ATTEMPT:
        raise core.PipelineError("Short generation attempt is outside its bounded contract")
    prompt = bind_generation_prompt(state, item, prompt, provider_format)
    prompt_path.write_text(prompt, encoding="utf-8")

    def create_generation():
        payload = core.run_notebooklm(
            [
                "generate", "video", "--prompt-file", str(prompt_path), "--notebook", core.NOTEBOOK_ID,
                "--source", item["source_id"], "--format", provider_format, "--language", "he", "--no-wait",
            ],
            timeout=180,
        )
        task_id = core.nested_identifier(payload, ("task_id", "taskId", "artifact_id", "id"))
        if not task_id:
            raise core.PipelineError("NotebookLM native Short generation returned no task ID")
        return {"task_id": task_id, "artifact_id": task_id}

    request = {"notebook_id": core.NOTEBOOK_ID, "source_id": item["source_id"], "format": provider_format,
               "language": "he", "prompt_sha256": core.sha256_text(prompt), "prompt": prompt}
    receipt = state.external('provider_generation', request, create_generation) if isinstance(state, CanonicalMediaState) else create_generation()
    task_id = receipt["task_id"]
    item["task_id"] = task_id
    item["artifact_id"] = task_id
    item["generation_prompt"] = prompt
    item["generation_prompt_sha256"] = core.sha256_text(prompt)
    item["provider_video_format"] = provider_format
    item["provider_native_short"] = provider_format == "short"
    item["provider_short_fallback_used"] = provider_format != "short"
    item["status"] = "generating"
    item["generation_started_at"] = core.utc_now()
    item["updated_at"] = core.utc_now()
    core.save_state(state)
    print(f"SHORT_GENERATION_STARTED item={item['id']} task_id={task_id} format={provider_format} attempt={attempt}")


def native_provider_short_failures(media: dict[str, Any], item: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    width = int(media.get("width") or 0)
    height = int(media.get("height") or 0)
    ratio = (width / height) if height else 0
    attempt = int(item.get("fresh_generation_attempt") or 1)
    native_portrait = height > width and 0.53 <= ratio <= 0.60
    fallback_allowed = attempt == NATIVE_SHORT_FALLBACK_ATTEMPT
    if attempt < 1 or attempt > NATIVE_SHORT_FALLBACK_ATTEMPT:
        failures.append("Short generation attempt is outside the bounded native-first policy")
    if item.get("provider_video_format") not in {"short", "explainer"}:
        failures.append("Unknown NotebookLM provider format for Short")
    if not native_portrait and not fallback_allowed:
        failures.append(f"NotebookLM source is not a native portrait Short ({width}x{height}); retry native Short before fallback")
    if item.get("provider_video_format") != "short" and not fallback_allowed:
        failures.append("NotebookLM provider format is not the native Short format before the fallback attempt")
    if item.get("shared_provider_identity") is True or item.get("adopted_from_long_item_id"):
        failures.append("Short reuses Video Overview provider identity; an independent Short generation is required")
    return failures


def short_window(raw_duration: float) -> tuple[float, float]:
    return 0.0, round(float(raw_duration), 3)


def short_technical_failures(
    media: dict[str, Any],
    video_path: Path | None = None,
    item: dict[str, Any] | None = None,
) -> list[str]:
    failures: list[str] = []
    if str(media.get("codec") or "") != "h264":
        failures.append(f"קודק הווידאו הוא {media.get('codec')} ולא H.264")
    if not str(media.get("audio_codec") or ""):
        failures.append("לקובץ אין ערוץ אודיו תקין")
    width = int(media.get("width") or 0)
    height = int(media.get("height") or 0)
    ratio = (width / height) if height else 0
    if width != SHORT_WIDTH or height != SHORT_HEIGHT or not 0.55 <= ratio <= 0.58:
        failures.append(
            f"יחס התמונה {width}x{height} אינו Short אנכי 1080x1920"
        )
    if video_path and video_path.exists():
        female_ok, pitch_hz, pitch_msg = core.validate_female_voice(video_path, item)
        if not female_ok:
            failures.append(pitch_msg)

    if item is not None:
        if item.get("source_mode") == "overview-segment":
            failures.append("נפסל: גזירת Short מסגמנט של סרטון ארוך (overview-segment) אסורה תחת חוזה Short עצמאי")
        if not delivery_guard._signature_verified(dict(item, media=media)):
            failures.append("ראיית החתימה אינה קשורה לקובץ הנוכחי ולציר הזמן המקורי (signature_provenance)")
        try:
            sig_duration = float(item.get("signature_duration_seconds") or 0)
        except (TypeError, ValueError):
            sig_duration = 0.0
        expected_signature = min(SIGNATURE_DURATION_SECONDS, float(media.get("duration") or 0))
        if abs(sig_duration - expected_signature) >= 0.001:
            failures.append(f"משך סגיר החתימה הוא {sig_duration} שניות במקום {SIGNATURE_DURATION_SECONDS}")
        if not str(item.get("signature_video_sha256") or "").strip():
            failures.append("חסר גיבוב וידאו תקין של מקטע החתימה (signature_video_sha256)")
        if item.get("signature_verified") is not True:
            failures.append("חתימת הווידאו לא אומתה (signature_verified)")

    return failures


def extract_signature_video_segment(output_path: Path, item_id: str, *, duration_seconds: float = 3.0) -> tuple[Path, str]:
    from scripts.kesher_runtime.render_provenance import extract_signature_segment
    return extract_signature_segment(core, output_path, item_id, duration_seconds=duration_seconds)


def prepare_signature_asset() -> str:
    source = core.PROJECT_DIR / SIGNATURE_SOURCE
    if not source.is_file() or source.stat().st_size <= 0:
        raise core.PipelineError(f"Approved Short signature asset is missing: {source}")
    svg = source.read_text(encoding="utf-8")
    if "<svg" not in svg or "</svg>" not in svg:
        raise core.PipelineError(f"Approved Short signature asset is not a valid SVG: {source}")

    core.STATE_DIR.mkdir(parents=True, exist_ok=True)
    target = core.STATE_DIR / SIGNATURE_RUNTIME_NAME
    shutil.copyfile(source, target)
    return target.name


def _short_targets_for_plan(edit_plan: dict[str, Any]) -> list[dict[str, Any]]:
    targets = copy.deepcopy(edit_plan.get("targets") or [])
    if edit_plan.get("render_mode") == "full" and edit_plan.get("assets_used"):
        return targets
    for target in targets:
        for field in OPTIONAL_TARGET_ASSET_FIELDS:
            target.pop(field, None)
    return targets


def _render_input_sha256(raw_path: Path, item: dict[str, Any], signature_sha256: str) -> str:
    from scripts.kesher_runtime.render_provenance import render_input_digest
    return render_input_digest(core, raw_path, item, signature_sha256, 'short')


def _short_render_cache_reusable(raw_path: Path, output_path: Path, item: dict[str, Any],
                                 signature_sha256: str) -> bool:
    """Require actual current bytes for every persisted render and signature receipt."""
    try:
        if item.get("render_input_sha256") != _render_input_sha256(raw_path, item, signature_sha256):
            return False
        if item.get("enhancement_status") not in {"enhancement_complete", "enhancement_partial", "enhancement_skipped"}:
            return False
        if item.get("raw_sha256") != core.sha256_file(raw_path) or item.get("signature_sha256") != signature_sha256:
            return False
        files = [(output_path, item.get("final_sha256"))]
        for path_key, hash_key in (("motion_plan_path", "motion_plan_sha256"),
                                   ("remotion_props_path", "remotion_props_sha256"),
                                   ("signature_video_path", "signature_video_sha256")):
            relative = item.get(path_key)
            if not isinstance(relative, str) or not relative:
                return False
            files.append((core.STATE_DIR / relative, item.get(hash_key)))
        if any(not path.is_file() or path.stat().st_size <= 0 or
               core.sha256_file(path) != expected for path, expected in files):
            return False
        media = core.ffprobe(output_path)
        if not delivery_guard._signature_verified(dict(item, media=media)):
            return False
        props = json.loads((core.STATE_DIR / item["remotion_props_path"]).read_text(encoding="utf-8"))
        plan = json.loads((core.STATE_DIR / item["motion_plan_path"]).read_text(encoding="utf-8"))
        return bool(props.get("videoSrc") == raw_path.name
                    and props.get("sourceStartFrame") == 0
                    and props.get("durationInFrames") == round(float(item["short_duration_seconds"]) * SHORT_FPS)
                    and props.get("signatureImageSrc") == item.get("signature_asset")
                    and props.get("motionPlan") == _short_targets_for_plan(plan))
    except (OSError, ValueError, TypeError, KeyError, core.PipelineError):
        return False


def render_remotion_video(raw_path: Path, item: dict[str, Any]) -> Path:
    output_path = core.STATE_DIR / f"{item['id']}-short-final.mp4"
    motion_plan_path = core.STATE_DIR / f"{item['id']}-short-motion-plan.json"
    props_path = core.STATE_DIR / f"{item['id']}-short-remotion-props.json"
    signature_image_src = prepare_signature_asset()
    signature_path = core.STATE_DIR / signature_image_src
    signature_sha256 = core.sha256_file(signature_path)

    raw_media = core.ffprobe(raw_path)
    native_failures = native_provider_short_failures(raw_media, item)
    if native_failures:
        raise core.PipelineError("; ".join(native_failures))
    raw_width = int(raw_media.get("width") or 0)
    raw_height = int(raw_media.get("height") or 0)
    raw_ratio = (raw_width / raw_height) if raw_height else 0
    item["provider_native_short_verified"] = raw_height > raw_width and 0.53 <= raw_ratio <= 0.60
    if not item["provider_native_short_verified"]:
        item["provider_short_fallback_used"] = True
        item["provider_short_fallback_reason"] = "native_short_unavailable_after_bounded_attempts"
    item["provider_raw_media"] = {key: raw_media.get(key) for key in ("width", "height", "duration", "codec", "audio_codec")}
    start_seconds, duration_seconds = short_window(float(raw_media["duration"]))
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise core.PipelineError("Short source duration must be positive and finite")
    duration_frames = max(1, round(duration_seconds * SHORT_FPS))
    start_frame = max(0, round(start_seconds * SHORT_FPS))

    if _short_render_cache_reusable(raw_path, output_path, item, signature_sha256):
        return output_path
    # A failed rebuild must never leave the old completion receipt usable.
    for field in ("render_input_sha256", "signature_provenance", "signature_verified", "technical_verified"):
        item.pop(field, None)
    render_input_sha256 = _render_input_sha256(raw_path, item, signature_sha256)

    remotion = core.PROJECT_DIR / "node_modules" / ".bin" / "remotion"
    if not remotion.is_file():
        raise core.PipelineError("Remotion dependencies are not installed")

    motion_plan = build_motion_plan(raw_path, duration_seconds, SHORT_FPS)

    def renderer(candidate_plan: dict[str, Any], candidate_output: Path) -> None:
        core.atomic_json_write(
            props_path,
            {
                "videoSrc": raw_path.name,
                "sourceStartFrame": start_frame,
                "durationInFrames": duration_frames,
                "title": item["source"]["title"],
                "category": item["source"]["category"],
                "url": core.DISPLAY_URL,
                "signatureImageSrc": signature_image_src,
                "motionPlan": _short_targets_for_plan(candidate_plan),
                "preserveSourceSharpness": bool(item.get("provider_native_short_verified")),
            },
        )
        command = [
            str(remotion),
            "render",
            "src/remotion/index.ts",
            "ArticleShort",
            str(candidate_output),
            f"--props={props_path}",
            f"--public-dir={core.STATE_DIR}",
            "--pixel-format=yuv420p",
            "--codec=h264",
            "--audio-codec=aac",
            "--concurrency=2",
            "--timeout=120000",
        ]
        result = subprocess.run(
            command,
            cwd=core.PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
        if result.returncode != 0 or not candidate_output.exists() or candidate_output.stat().st_size < 1024:
            detail = (result.stderr or result.stdout)[-700:]
            raise RuntimeError(f"Remotion Short render failed: {detail}")

    enhancement = execute_enhancement(
        source_path=raw_path,
        output_path=output_path,
        edit_plan=motion_plan,
        renderer=renderer,
        source_publishable=False,
    )
    effective_plan = enhancement["effective_plan"]
    core.atomic_json_write(motion_plan_path, effective_plan)

    item["visual_pipeline"] = VISUAL_PIPELINE
    item["source_mode"] = "direct-short"
    item["short_start_seconds"] = start_seconds
    item["short_duration_seconds"] = duration_seconds
    item["enhancement_status"] = enhancement["enhancement_status"]
    item["enhancement_render_mode"] = enhancement["render_mode"]
    item["enhancement_assets_used"] = enhancement["assets_used"]
    item["enhancement_assets_dropped"] = enhancement["assets_dropped"]
    item["enhancement_fallback_reason"] = enhancement["fallback_reason"]
    item["motion_plan_path"] = motion_plan_path.name
    item["motion_plan_sha256"] = core.sha256_file(motion_plan_path)
    item["signature_asset"] = signature_image_src
    item["signature_sha256"] = signature_sha256
    item["remotion_props_path"] = props_path.name
    item["remotion_props_sha256"] = core.sha256_file(props_path)

    from scripts.kesher_runtime.render_provenance import record_signature
    media = core.ffprobe(output_path)
    record_signature(core, raw_path, output_path, item, signature_path, raw_media, media)
    if render_input_sha256 != _render_input_sha256(raw_path, item, signature_sha256):
        raise core.PipelineError("Short render inputs changed during rendering")
    item["render_input_sha256"] = render_input_sha256
    return output_path


def validate_and_manifest(
    state: dict[str, Any],
    item: dict[str, Any],
    raw_path: Path,
) -> None:
    final_path = render_remotion_video(raw_path, item)
    media = core.ffprobe(final_path)
    sheet = core.create_contact_sheet(final_path, item, media["duration"])
    item["final_mp4"] = final_path.name
    item["final_sha256"] = core.sha256_file(final_path)
    item["media"] = media
    item["visual_review_path"] = sheet.name
    item["visual_review_sha256"] = core.sha256_file(sheet)

    frame_dir = core.STATE_DIR / f"{item['id']}-frames"
    item["frame_paths"] = [
        str(path.relative_to(core.STATE_DIR))
        for path in sorted(frame_dir.glob("frame-*.png"))
    ]
    if len(item["frame_paths"]) != core.REVIEW_FRAME_COUNT:
        raise core.PipelineError(
            f"Exactly {core.REVIEW_FRAME_COUNT} review frames are required"
        )
    item["frame_sha256"] = {
        relative: core.sha256_file(core.STATE_DIR / relative)
        for relative in item["frame_paths"]
    }

    technical_failures = short_technical_failures(media, final_path, item)
    metadata = repair_youtube_metadata(item)
    metadata_failure = ""
    try:
        core.require_hebrew(metadata["title"], "YouTube title")
        core.require_hebrew(metadata["description"], "YouTube description", allow_url=True)
        for tag in metadata["tags"]:
            core.require_hebrew(tag, "YouTube tag")
        description_lines = [line.strip() for line in metadata["description"].splitlines() if line.strip()]
        canonical_url = str((item.get("source") or {}).get("canonical_url") or "").strip()
        if not canonical_url or canonical_url not in description_lines:
            raise core.PipelineError("YouTube description is missing the exact article URL")
        if core.SITE_URL not in description_lines:
            raise core.PipelineError("YouTube description is missing the standalone Kesher site URL")
        if core.APPOINTMENT_URL not in description_lines:
            raise core.PipelineError("YouTube description is missing the appointment URL")
    except (KeyError, core.PipelineError) as exc:
        metadata_failure = f"המטא־דאטה אינו עומד בשער העברית והמקור: {exc}"
        technical_failures.append(metadata_failure)

    manifest: dict[str, Any] = {
        "schema_version": 2,
        "type": "article_short",
        "item_id": item["id"],
        "created_at": core.utc_now(),
        "source": item["source"],
        "source_mode": item.get("source_mode"),
        "provider_video_format": item.get("provider_video_format"),
        "provider_native_short": item.get("provider_native_short"),
        "provider_native_short_verified": item.get("provider_native_short_verified"),
        "notebook_id": item["notebook_id"],
        "source_id": item["source_id"],
        "task_id": item["task_id"],
        "artifact_id": item["artifact_id"],
        "generation_prompt": item.get("generation_prompt"),
        "generation_prompt_sha256": item.get("generation_prompt_sha256"),
        "raw_mp4": item["raw_mp4"],
        "raw_sha256": item["raw_sha256"],
        "final_mp4": item["final_mp4"],
        "final_sha256": item["final_sha256"],
        "visual_pipeline": item.get("visual_pipeline"),
        "short_start_seconds": item.get("short_start_seconds"),
        "short_duration_seconds": item.get("short_duration_seconds"),
        "motion_plan_path": item.get("motion_plan_path"),
        "motion_plan_sha256": item.get("motion_plan_sha256"),
        "signature_asset": item.get("signature_asset"),
        "signature_sha256": item.get("signature_sha256"),
        "signature_video_path": item.get("signature_video_path"),
        "signature_video_sha256": item.get("signature_video_sha256"),
        "signature_duration_seconds": item.get("signature_duration_seconds"),
        "signature_fullscreen": item.get("signature_fullscreen"),
        "signature_verified": item.get("signature_verified"),
        "signature_overlay": item.get("signature_overlay"),
        "signature_provenance": item.get("signature_provenance"),
        "audio_provenance": item.get("audio_provenance"),
        "render_input_sha256": item.get("render_input_sha256"),
        "overview_provider_identity": item.get("overview_provider_identity"),
        "provider_raw_media": item.get("provider_raw_media"),
        "provider_short_fallback_used": item.get("provider_short_fallback_used"),
        "fresh_generation_attempt": item.get("fresh_generation_attempt"),
        "remotion_props_path": item.get("remotion_props_path"),
        "remotion_props_sha256": item.get("remotion_props_sha256"),
        "media": media,
        "youtube_metadata": metadata,
        "frame_paths": item["frame_paths"],
        "frame_sha256": item["frame_sha256"],
        "visual_review_path": item["visual_review_path"],
        "visual_review_sha256": item["visual_review_sha256"],
    }
    manifest["enhancement"] = build_enhancement_manifest(
        source_path=raw_path,
        final_path=final_path,
        edit_plan_path=core.STATE_DIR / item["motion_plan_path"],
        enhancement_status=item["enhancement_status"],
        assets_used=item.get("enhancement_assets_used") or [],
        assets_dropped=item.get("enhancement_assets_dropped") or [],
        fallback_reason=item.get("enhancement_fallback_reason"),
    )

    if technical_failures:
        item["technical_verified"] = False
        item["review_notes"]["technical"] = "נפסל טכנית: " + "; ".join(technical_failures)
        if metadata_failure:
            item["metadata_review_status"] = "rejected"
            item["review_notes"]["metadata"] = metadata_failure
        item["status"] = "rejected"
        item["rejected_at"] = core.utc_now()
        manifest["technical_verified"] = False
        manifest["rejection_reasons"] = technical_failures
        manifest_path = core.STATE_DIR / f"{item['id']}-short-manifest.json"
        core.atomic_json_write(manifest_path, manifest)
        item["manifest_path"] = manifest_path.name
        item["manifest_sha256"] = core.sha256_file(manifest_path)
        reasons_text = "; ".join(technical_failures)
        print(f"SHORT_TECHNICAL_REJECTED item={item['id']} count={len(technical_failures)} reasons={reasons_text}")
        core.save_state(state)
        return

    item["technical_verified"] = True
    item["review_notes"]["technical"] = (
        f"אומת Short תקין H.264 עם אודיו, {media['width']}x{media['height']}, "
        f"משך {media['duration']} שניות ו־SHA-256"
    )
    transcript_path = core.transcribe_hebrew(final_path, item)
    item["transcript_path"] = transcript_path.name
    item["transcript_sha256"] = core.sha256_file(transcript_path)
    source_path = core.STATE_DIR / f"{item['id']}-source-he.txt"
    source_path.write_text(core.article_body_for_item(item) + "\n", encoding="utf-8")
    item["source_path"] = source_path.name
    item["source_file_sha256"] = core.sha256_file(source_path)
    manifest.update({
        "technical_verified": True,
        "transcript_path": item["transcript_path"],
        "transcript_sha256": item["transcript_sha256"],
        "source_path": item["source_path"],
        "source_file_sha256": item["source_file_sha256"],
    })
    manifest_path = core.STATE_DIR / f"{item['id']}-short-manifest.json"
    core.atomic_json_write(manifest_path, manifest)
    item["manifest_path"] = manifest_path.name
    item["manifest_sha256"] = core.sha256_file(manifest_path)
    item["status"] = "pending_review"
    item["updated_at"] = core.utc_now()
    core.save_state(state)
    print(f"SHORT_PENDING_REVIEW item={item['id']} review={sheet} manifest={manifest_path}")


def install() -> None:
    core.generation_prompt = generation_prompt
    core.new_item = new_item
    core.start_generation = start_generation
    core.render_remotion_video = render_remotion_video
    core.validate_and_manifest = validate_and_manifest


def main() -> int:
    from scripts.kesher_runtime.legacy_retirement import retired_entrypoint
    retired_entrypoint()
    install()
    return core.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (core.PipelineError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"SHORT_PIPELINE_V4_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

#!/usr/bin/env python3
"""V4 adapter that turns the proven NotebookLM pipeline into one YouTube Short.

The legacy module remains the provider/upload engine. V4 replaces only the
creative contract, Remotion render, and technical validation:

* NotebookLM remains the narration/source master;
* the prompt requests one concise, complete idea with a natural ending;
* provider output keeps its full natural duration instead of being hard-trimmed;
* Remotion renders the exact source/audio into a 1080x1920 composition;
* technical publication requires H.264 + audio + a usable minimum duration + 9:16.

No second TTS engine, generic captions, or second semantic video is introduced.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__:
    from . import kesher_daily_pipeline as core
    from .kesher_short_motion_plan import build_motion_plan
else:
    import kesher_daily_pipeline as core
    from kesher_short_motion_plan import build_motion_plan

SHORT_MIN_SECONDS = 30.0
SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920
SHORT_FPS = 30
SIGNATURE_DURATION_SECONDS = 3.0
VISUAL_PIPELINE = "remotion-v4-notebooklm-short-motion-plan-v1"
SIGNATURE_SOURCE = Path("public/images/signature/signature-mask.svg")
SIGNATURE_RUNTIME_NAME = "signature-mask.svg"

_base_new_item = core.new_item


def generation_prompt(source: dict[str, Any]) -> str:
    prompt = (
        "צור וידאו קצר ותמציתי בעברית טבעית בלבד, המבוסס אך ורק על המקור שנבחר. "
        "אין מגבלת משך קשיחה: העדף קיצור, אך תן לרעיון להסתיים במלואו ובאופן טבעי. "
        "חובה: השתמש אך ורק בקול של אישה ישראלית (קריינית נקבה), חם, טבעי, ברור ומקצועי לכל אורך הקריינות, ללא קול גברי כלל. "
        "הרעיון השלם חייב לעמוד בפני עצמו: פתח במשפט שמציג בעיה או שאלה ברורה, "
        "המשך בתובנה אחת בלבד ובדוגמה אחת קצרה, וסיים בפעולה מעשית אחת ובסיום טבעי ומלא. "
        "לעולם אל תקטע משפט, מחשבה או מסקנה כדי לעמוד במשך מסוים. "
        "אין לערבב בין הורות לזוגיות כאשר המקור עוסק רק באחד מהם. "
        "אין להוסיף אבחנות, תארים מקצועיים או הבטחות שאינם במקור. "
        "כל קריינות או טקסט חזותי יהיו בעברית תקינה. אין להשתמש באנגלית, בג׳יבריש, "
        "בטבלאות או בתרשימים. אין ליצור מטא־דאטה ליוטיוב בתוך הווידאו. "
        f"הנושא המדויק הוא: {source['title']}"
    )
    core.require_hebrew(prompt, "Short generation prompt")
    return prompt


def new_item(source: dict[str, Any]) -> dict[str, Any]:
    item = _base_new_item(source)
    item["type"] = "article_short"
    item["source_mode"] = "direct-short"
    item["fresh_generation_attempt"] = int(item.get("technical_retry_count") or 0) + 1
    return item


def short_window(raw_duration: float) -> tuple[float, float]:
    duration = float(raw_duration)
    if duration < SHORT_MIN_SECONDS:
        raise core.PipelineError(
            f"NotebookLM source is too short for a usable Short: {duration:.3f}s"
        )
    return 0.0, round(duration, 3)


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
    duration = float(media.get("duration") or 0)
    if duration < SHORT_MIN_SECONDS:
        failures.append(
            f"משך ה־Short הוא {duration} שניות וקצר מהמינימום {int(SHORT_MIN_SECONDS)} שניות"
        )
    width = int(media.get("width") or 0)
    height = int(media.get("height") or 0)
    ratio = (width / height) if height else 0
    if width != SHORT_WIDTH or height != SHORT_HEIGHT or not 0.55 <= ratio <= 0.58:
        failures.append(
            f"יחס התמונה {width}x{height} אינו Short אנכי 1080x1920"
        )
    if video_path and video_path.exists():
        female_ok, pitch_hz, pitch_msg = core.validate_female_voice(video_path)
        if not female_ok:
            failures.append(pitch_msg)

    if item is not None:
        if item.get("source_mode") == "overview-segment":
            failures.append("נפסל: גזירת Short מסגמנט של סרטון ארוך (overview-segment) אסורה תחת חוזה Short עצמאי")
        if item.get("signature_fullscreen") is not True:
            failures.append("סגיר החתימה אינו מוגדר כמסך מלא (signature_fullscreen)")
        try:
            sig_duration = float(item.get("signature_duration_seconds") or 0)
        except (TypeError, ValueError):
            sig_duration = 0.0
        if abs(sig_duration - SIGNATURE_DURATION_SECONDS) >= 0.001:
            failures.append(f"משך סגיר החתימה הוא {sig_duration} שניות במקום {SIGNATURE_DURATION_SECONDS}")
        if not str(item.get("signature_video_sha256") or "").strip():
            failures.append("חסר גיבוב וידאו תקין של מקטע החתימה (signature_video_sha256)")
        if item.get("signature_verified") is not True:
            failures.append("חתימת הווידאו לא אומתה (signature_verified)")

    return failures


def extract_signature_video_segment(output_path: Path, item_id: str) -> tuple[Path, str]:
    core.STATE_DIR.mkdir(parents=True, exist_ok=True)
    signature_video_path = core.STATE_DIR / f"{item_id}-signature-segment.mp4"
    if signature_video_path.exists() and signature_video_path.stat().st_size > 0:
        return signature_video_path, core.sha256_file(signature_video_path)

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise core.PipelineError("ffmpeg is required to extract the signature video segment")

    command = [
        ffmpeg,
        "-y",
        "-sseof", f"-{SIGNATURE_DURATION_SECONDS}",
        "-i", str(output_path),
        "-t", f"{SIGNATURE_DURATION_SECONDS}",
        "-c:v", "libx264",
        "-c:a", "aac",
        str(signature_video_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not signature_video_path.exists() or signature_video_path.stat().st_size <= 0:
        detail = (result.stderr or result.stdout)[-500:]
        raise core.PipelineError(f"Failed to extract signature video segment: {detail}")

    return signature_video_path, core.sha256_file(signature_video_path)


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


def render_remotion_video(raw_path: Path, item: dict[str, Any]) -> Path:
    output_path = core.STATE_DIR / f"{item['id']}-short-final.mp4"
    motion_plan_path = core.STATE_DIR / f"{item['id']}-short-motion-plan.json"
    props_path = core.STATE_DIR / f"{item['id']}-short-remotion-props.json"
    signature_image_src = prepare_signature_asset()
    signature_path = core.STATE_DIR / signature_image_src
    signature_sha256 = core.sha256_file(signature_path)

    raw_media = core.ffprobe(raw_path)
    start_seconds, duration_seconds = short_window(float(raw_media["duration"]))
    duration_frames = max(1, round(duration_seconds * SHORT_FPS))
    start_frame = max(0, round(start_seconds * SHORT_FPS))

    if not (output_path.exists() and output_path.stat().st_size > 0):
        remotion = core.PROJECT_DIR / "node_modules" / ".bin" / "remotion"
        if not remotion.is_file():
            raise core.PipelineError("Remotion dependencies are not installed")

        motion_plan = build_motion_plan(raw_path, duration_seconds, SHORT_FPS)
        core.atomic_json_write(motion_plan_path, motion_plan)

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
                "motionPlan": motion_plan["targets"],
            },
        )
        command = [
            str(remotion),
            "render",
            "src/remotion/index.ts",
            "ArticleShort",
            str(output_path),
            f"--props={props_path}",
            f"--public-dir={core.STATE_DIR}",
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
        if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size < 1024:
            detail = (result.stderr or result.stdout)[-700:]
            raise core.PipelineError(f"Remotion Short render failed: {detail}")

    item["visual_pipeline"] = VISUAL_PIPELINE
    item["source_mode"] = "direct-short"
    item["short_start_seconds"] = start_seconds
    item["short_duration_seconds"] = duration_seconds
    if motion_plan_path.exists():
        item["motion_plan_path"] = motion_plan_path.name
        item["motion_plan_sha256"] = core.sha256_file(motion_plan_path)
    item["signature_asset"] = signature_image_src
    item["signature_sha256"] = signature_sha256
    if props_path.exists():
        item["remotion_props_path"] = props_path.name
        item["remotion_props_sha256"] = core.sha256_file(props_path)

    sig_video_path, sig_video_sha256 = extract_signature_video_segment(output_path, item["id"])
    item["signature_video_path"] = sig_video_path.name
    item["signature_video_sha256"] = sig_video_sha256
    item["signature_duration_seconds"] = SIGNATURE_DURATION_SECONDS
    item["signature_fullscreen"] = True
    item["signature_verified"] = True
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
    metadata = item["youtube_metadata"]
    metadata_failure = ""
    try:
        core.require_hebrew(metadata["title"], "YouTube title")
        core.require_hebrew(metadata["description"], "YouTube description", allow_url=True)
        for tag in metadata["tags"]:
            core.require_hebrew(tag, "YouTube tag")
        if core.SITE_URL not in metadata["description"]:
            raise core.PipelineError("YouTube description is missing the Kesher URL")
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
        "remotion_props_path": item.get("remotion_props_path"),
        "remotion_props_sha256": item.get("remotion_props_sha256"),
        "media": media,
        "youtube_metadata": metadata,
        "frame_paths": item["frame_paths"],
        "frame_sha256": item["frame_sha256"],
        "visual_review_path": item["visual_review_path"],
        "visual_review_sha256": item["visual_review_sha256"],
    }

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
    core.render_remotion_video = render_remotion_video
    core.validate_and_manifest = validate_and_manifest


def main() -> int:
    install()
    return core.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (core.PipelineError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"SHORT_PIPELINE_V4_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

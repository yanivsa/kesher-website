#!/usr/bin/env python3
"""Fail-closed cloud pipeline for Kesher NotebookLM Video Overviews.

This file is the only supported entrypoint for generation, review and upload.
It deliberately creates one Hebrew 16:9 Explainer Video Overview at a time.
Shorts, alternate generators, alternate uploaders and default metadata are not
part of this pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests


PROJECT_DIR = Path(__file__).resolve().parents[1]
POSTS_FILE = PROJECT_DIR / "src" / "data" / "posts.json"
STATE_DIR = Path(os.environ.get("KESHER_STATE_DIR", PROJECT_DIR / "notebooklm-output" / "cloud"))
STATE_FILE = STATE_DIR / "state.json"
NOTEBOOK_ID = os.environ.get("KESHER_NOTEBOOK_ID", "e101e7d7-5305-45b3-a611-21a5475ceb63")
NOTEBOOKLM_BIN = os.environ.get("NOTEBOOKLM_BIN", "notebooklm")
NOTEBOOKLM_REQUIRED_VERSION = "0.8.0"
YOUTUBE_CHANNEL_ID = "UCx5fEFvdVf28HLAR2dFW64Q"
SITE_URL = "https://kesher.saharoni.com"
DISPLAY_URL = "kesher.saharoni.com"
STATE_VERSION = 1
POLL_INTERVAL_SECONDS = 30
ALLOWED_REVIEW = {"approved", "rejected"}


class PipelineError(RuntimeError):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.parts.append(value)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def israel_now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Jerusalem"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"version": STATE_VERSION, "items": [], "updated_at": utc_now()}
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"State file is unreadable: {type(exc).__name__}") from exc
    if state.get("version") != STATE_VERSION or not isinstance(state.get("items"), list):
        raise PipelineError("State schema is unsupported")
    return state


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    atomic_json_write(STATE_FILE, state)


def clean_article_html(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    return html.unescape("\n\n".join(parser.parts))


def require_hebrew(value: str, field: str, allow_url: bool = False) -> None:
    checked = value
    if allow_url:
        checked = re.sub(
            rf"{re.escape(SITE_URL)}(?:/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*)?",
            "",
            checked,
        )
    if re.search(r"[A-Za-z]", checked):
        raise PipelineError(f"{field} contains unsupported Latin text")
    if not re.search(r"[\u0590-\u05ff]", checked):
        raise PipelineError(f"{field} contains no Hebrew")


def source_metadata(post: dict[str, Any]) -> dict[str, Any]:
    required = ("id", "slug", "title", "date", "category", "excerpt", "content")
    missing = [field for field in required if not str(post.get(field, "")).strip()]
    if missing:
        raise PipelineError(f"Article is missing authoritative fields: {', '.join(missing)}")
    title = str(post["title"]).strip()
    excerpt = clean_article_html(str(post["excerpt"]))
    article_text = clean_article_html(str(post["content"]))
    category = str(post["category"]).strip()
    subcategory = str(post.get("subcategory", "")).strip()
    canonical_url = f"{SITE_URL}/blog/{post['slug']}"
    for field, value in (("title", title), ("excerpt", excerpt), ("article", article_text), ("category", category)):
        require_hebrew(value, field)
    if subcategory:
        require_hebrew(subcategory, "subcategory")
    body = "\n\n".join(
        part
        for part in (
            title,
            excerpt,
            article_text,
            f"מקור: {canonical_url}",
        )
        if part
    )
    content_hash = sha256_text(body)
    tags = [category]
    if subcategory and subcategory not in tags:
        tags.append(subcategory)
    for tag in tags:
        require_hebrew(tag, "tag")
    description = f"{excerpt}\n\nלקריאת המאמר המלא:\n{canonical_url}"
    require_hebrew(description, "description", allow_url=True)
    return {
        "id": str(post["id"]),
        "slug": str(post["slug"]),
        "title": title,
        "date": str(post["date"]),
        "category": category,
        "subcategory": subcategory,
        "excerpt": excerpt,
        "canonical_url": canonical_url,
        "body": body,
        "content_sha256": content_hash,
        "youtube_metadata": {
            "title": title[:100],
            "description": description,
            "tags": tags,
        },
    }


def select_newest_unused_article(state: dict[str, Any]) -> dict[str, Any]:
    if not POSTS_FILE.exists():
        raise PipelineError(f"Article source does not exist: {POSTS_FILE}")
    posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
    if not isinstance(posts, list):
        raise PipelineError("posts.json must contain a list")
    used_hashes = {item.get("source", {}).get("content_sha256") for item in state["items"]}
    used_slugs = {item.get("source", {}).get("slug") for item in state["items"]}
    today = israel_now().date()
    eligible: list[tuple[date, int, dict[str, Any]]] = []
    for index, post in enumerate(posts):
        try:
            metadata = source_metadata(post)
            published = date.fromisoformat(metadata["date"])
        except (PipelineError, ValueError, TypeError):
            continue
        if published <= today and metadata["content_sha256"] not in used_hashes and metadata["slug"] not in used_slugs:
            eligible.append((published, -index, metadata))
    if not eligible:
        raise PipelineError("No unused published Hebrew article is available")
    eligible.sort(reverse=True, key=lambda row: (row[0], row[1]))
    return eligible[0][2]


def notebooklm_env() -> dict[str, str]:
    auth_json = os.environ.get("NOTEBOOKLM_AUTH_JSON", "").strip()
    env = os.environ.copy()
    if auth_json:
        try:
            parsed = json.loads(auth_json)
        except json.JSONDecodeError as exc:
            raise PipelineError("NOTEBOOKLM_AUTH_JSON is invalid JSON") from exc
        if not isinstance(parsed, dict) or not isinstance(parsed.get("cookies"), list) or not parsed["cookies"]:
            raise PipelineError("NOTEBOOKLM_AUTH_JSON is not a nonempty storage-state object")
        env["NOTEBOOKLM_AUTH_JSON"] = auth_json
    else:
        notebooklm_home = Path(env.get("NOTEBOOKLM_HOME", Path.home() / ".notebooklm"))
        storage_path = notebooklm_home / "profiles" / "default" / "storage_state.json"
        if not storage_path.is_file():
            raise PipelineError("NotebookLM auth storage is missing")
        try:
            parsed = json.loads(storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PipelineError("NotebookLM auth storage is invalid JSON") from exc
        if not isinstance(parsed, dict) or not isinstance(parsed.get("cookies"), list) or not parsed["cookies"]:
            raise PipelineError("NotebookLM auth storage is not a nonempty storage-state object")
    env["NOTEBOOKLM_NOTEBOOK"] = NOTEBOOK_ID
    return env


def run_notebooklm(arguments: list[str], timeout: int = 180) -> dict[str, Any]:
    command = [NOTEBOOKLM_BIN, *arguments, "--json"]
    try:
        result = subprocess.run(
            command,
            env=notebooklm_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise PipelineError("notebooklm CLI is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise PipelineError(f"NotebookLM command timed out: {' '.join(arguments[:2])}") from exc
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    if result.returncode != 0:
        error_type = nested_identifier(payload, ("error_type", "type")) or "NotebookLMCommandError"
        message = nested_identifier(payload, ("error", "message")) or "command failed"
        message = re.sub(r"https://accounts\.google\.com/\S+", "Google sign-in redirect", str(message))
        raise PipelineError(f"{error_type}: {message[:300]}")
    if not isinstance(payload, dict):
        raise PipelineError("NotebookLM returned non-object JSON")
    return payload


def nested_identifier(payload: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in payload.values():
            found = nested_identifier(value, keys)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = nested_identifier(value, keys)
            if found:
                return found
    return None


def auth_preflight() -> dict[str, Any]:
    try:
        version = importlib.metadata.version("notebooklm-py")
    except importlib.metadata.PackageNotFoundError as exc:
        raise PipelineError("notebooklm-py is not installed") from exc
    if version != NOTEBOOKLM_REQUIRED_VERSION:
        raise PipelineError(f"notebooklm-py must be {NOTEBOOKLM_REQUIRED_VERSION}, got {version}")
    payload = run_notebooklm(["auth", "check", "--test"], timeout=120)
    checks = payload.get("checks") or {}
    if payload.get("status") != "ok" or checks.get("token_fetch") is not True:
        raise PipelineError("NotebookLM authentication network test failed")
    return {"package_version": version, "auth_status": "ok", "token_fetch": True}


def generation_prompt(source: dict[str, Any]) -> str:
    prompt = (
        "צור סקירת וידאו מסוג הסבר, בעברית טבעית בלבד, המבוססת אך ורק על המקור שנבחר. "
        "אורך היעד הוא בין תשעים למאה ושמונים שניות, ביחס אופקי טבעי של שש עשרה לתשע. "
        "השתמש בקול של אישה ישראלית, חם, טבעי, ברור ומקצועי לכל אורך הקריינות. "
        "הקריינות כולה תהיה תמציתית ותכיל לכל היותר מאתיים ושישים מילים. "
        "הצג רעיון מרכזי אחד, דוגמה ביתית מוחשית ופעולה אחת שאפשר לנסות. "
        "אל תערבב בין הורות לזוגיות אם המקור עוסק רק באחד מהם. "
        "אין להוסיף טענות, תארים מקצועיים, אבחנות או הבטחות שאינם כתובים במקור. "
        "כל קריינות או טקסט חזותי יהיו בעברית תקינה. אין להשתמש באנגלית, בג׳יבריש, "
        "בשקופיות, בכרטיסיות מידע, בטבלאות או בתרשימים. העדף סיפור חזותי רציף וברור. "
        "אין ליצור כותרת ליוטיוב, תיאור ליוטיוב או תגיות בתוך הסרטון. "
        f"הנושא המדויק הוא: {source['title']}"
    )
    require_hebrew(prompt, "generation prompt")
    return prompt


def new_item(source: dict[str, Any]) -> dict[str, Any]:
    stamp = israel_now().strftime("%Y%m%d-%H%M%S")
    return {
        "id": f"video-{stamp}-{source['content_sha256'][:10]}",
        "type": "video_overview",
        "israel_date": israel_now().date().isoformat(),
        "status": "source_selected",
        "source": {key: value for key, value in source.items() if key not in {"body", "youtube_metadata"}},
        "youtube_metadata": source["youtube_metadata"],
        "notebook_id": NOTEBOOK_ID,
        "source_id": None,
        "task_id": None,
        "artifact_id": None,
        "raw_mp4": None,
        "final_mp4": None,
        "visual_review_path": None,
        "manifest_path": None,
        "technical_verified": False,
        "visual_review_status": "pending",
        "semantic_review_status": "pending",
        "metadata_review_status": "pending",
        "review_notes": {
            "technical": "",
            "visual": "ממתין לבדיקת ארבעת הפריימים בפועל",
            "semantic": "ממתין להשוואת הווידאו והמקור למטא־דאטה",
            "metadata": "ממתין לאימות עברית ותמיכה מלאה במקור",
        },
        "uploaded": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }


def active_item(state: dict[str, Any]) -> dict[str, Any] | None:
    active_statuses = {"source_selected", "source_added", "generating", "downloaded", "pending_review", "approved", "uploading"}
    matches = [item for item in state["items"] if item.get("status") in active_statuses and not item.get("uploaded")]
    if len(matches) > 1:
        raise PipelineError("More than one active video exists; refusing duplicate work")
    return matches[0] if matches else None


def article_body_for_item(item: dict[str, Any]) -> str:
    posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
    for post in posts:
        if post.get("slug") == item["source"]["slug"]:
            source = source_metadata(post)
            if source["content_sha256"] != item["source"]["content_sha256"]:
                raise PipelineError("Article content changed after selection")
            return source["body"]
    raise PipelineError("Selected article no longer exists")


def add_source(state: dict[str, Any], item: dict[str, Any]) -> None:
    body = article_body_for_item(item)
    payload = run_notebooklm(
        ["source", "add", body, "--type", "text", "--title", item["source"]["title"], "--notebook", NOTEBOOK_ID],
        timeout=180,
    )
    source_id = nested_identifier(payload, ("source_id", "sourceId", "id"))
    if not source_id:
        raise PipelineError("NotebookLM source add returned no source ID")
    item["source_id"] = source_id
    item["status"] = "source_added"
    item["updated_at"] = utc_now()
    save_state(state)
    print(f"SOURCE_ADDED item={item['id']} source_id={source_id}")


def start_generation(state: dict[str, Any], item: dict[str, Any]) -> None:
    prompt_path = STATE_DIR / f"{item['id']}-prompt-he.txt"
    prompt = generation_prompt(item["source"])
    prompt_path.write_text(prompt, encoding="utf-8")
    payload = run_notebooklm(
        [
            "generate", "video", "--prompt-file", str(prompt_path), "--notebook", NOTEBOOK_ID,
            "--source", item["source_id"], "--format", "explainer", "--style", "auto",
            "--language", "he", "--no-wait",
        ],
        timeout=180,
    )
    task_id = nested_identifier(payload, ("task_id", "taskId", "artifact_id", "id"))
    if not task_id:
        raise PipelineError("NotebookLM generation returned no task ID")
    item["task_id"] = task_id
    item["artifact_id"] = task_id
    item["generation_prompt"] = prompt
    item["generation_prompt_sha256"] = sha256_text(prompt)
    item["status"] = "generating"
    item["generation_started_at"] = utc_now()
    item["updated_at"] = utc_now()
    save_state(state)
    print(f"GENERATION_STARTED item={item['id']} task_id={task_id}")


def artifact_status(payload: dict[str, Any]) -> str:
    value = nested_identifier(payload, ("status", "state", "generation_status"))
    return (value or "unknown").lower().replace(" ", "_")


def wait_for_generation(state: dict[str, Any], item: dict[str, Any], max_wait_seconds: int) -> bool:
    deadline = time.monotonic() + max(0, max_wait_seconds)
    while True:
        payload = run_notebooklm(["artifact", "poll", item["task_id"], "--notebook", NOTEBOOK_ID], timeout=120)
        status = artifact_status(payload)
        item["last_provider_status"] = status
        item["last_polled_at"] = utc_now()
        item["updated_at"] = utc_now()
        save_state(state)
        if status in {"completed", "complete", "ready", "succeeded", "success"}:
            return True
        if status in {"failed", "error", "cancelled", "canceled", "rejected"}:
            item["status"] = "rejected"
            item["rejection_reason"] = f"NotebookLM generation ended with {status}"
            save_state(state)
            raise PipelineError(item["rejection_reason"])
        if time.monotonic() >= deadline:
            print(f"GENERATION_PENDING item={item['id']} provider_status={status}")
            return False
        time.sleep(min(POLL_INTERVAL_SECONDS, max(1, int(deadline - time.monotonic()))))


def download_artifact(state: dict[str, Any], item: dict[str, Any]) -> Path:
    raw_path = STATE_DIR / f"{item['id']}-notebooklm.mp4"
    if raw_path.exists() and raw_path.stat().st_size > 0:
        return raw_path
    run_notebooklm(
        ["download", "video", str(raw_path), "--notebook", NOTEBOOK_ID, "--artifact", item["artifact_id"], "--force"],
        timeout=900,
    )
    if not raw_path.exists() or raw_path.stat().st_size < 1024:
        raise PipelineError("NotebookLM download did not produce a usable MP4")
    item["raw_mp4"] = raw_path.name
    item["raw_sha256"] = sha256_file(raw_path)
    item["status"] = "downloaded"
    item["downloaded_at"] = utc_now()
    item["updated_at"] = utc_now()
    save_state(state)
    return raw_path


def ffprobe(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type,codec_name,width,height,duration:format=duration,format_name",
        "-of", "json", str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode != 0:
        raise PipelineError("ffprobe could not inspect the MP4")
    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not video_streams:
        raise PipelineError("MP4 has no video stream")
    if not audio_streams:
        raise PipelineError("MP4 has no audio stream")
    stream = video_streams[0]
    duration = float(stream.get("duration") or payload.get("format", {}).get("duration") or 0)
    return {
        "codec": stream.get("codec_name"),
        "audio_codec": audio_streams[0].get("codec_name"),
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "duration": round(duration, 3),
        "format": payload.get("format", {}).get("format_name"),
    }


def transcribe_hebrew(video_path: Path, item: dict[str, Any]) -> Path:
    transcript_path = STATE_DIR / f"{item['id']}-transcript-he.txt"
    if transcript_path.exists() and transcript_path.stat().st_size > 0:
        return transcript_path
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise PipelineError("faster-whisper is required for semantic review evidence") from exc
    model_name = os.environ.get("KESHER_WHISPER_MODEL", "small")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(video_path), language="he", vad_filter=True, beam_size=5)
    lines = [segment.text.strip() for segment in segments if segment.text.strip()]
    transcript = "\n".join(lines).strip()
    if not transcript or len(re.findall(r"[\u0590-\u05ff]", transcript)) < 40:
        raise PipelineError("Hebrew transcript is empty or too weak for semantic review")
    if getattr(info, "language", "he") not in {"he", "iw"}:
        raise PipelineError("Transcription did not identify Hebrew narration")
    transcript_path.write_text(transcript + "\n", encoding="utf-8")
    return transcript_path


def render_remotion_video(raw_path: Path, item: dict[str, Any]) -> Path:
    output_path = STATE_DIR / f"{item['id']}-remotion-final.mp4"
    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path
    remotion = PROJECT_DIR / "node_modules" / ".bin" / "remotion"
    if not remotion.is_file():
        raise PipelineError("Remotion dependencies are not installed")
    raw_media = ffprobe(raw_path)
    duration_frames = round(float(raw_media["duration"]) * 30)
    if duration_frames <= 0:
        raise PipelineError("NotebookLM audio duration is invalid for Remotion")
    props_path = STATE_DIR / f"{item['id']}-remotion-props.json"
    atomic_json_write(
        props_path,
        {
            "audioSrc": raw_path.name,
            "durationInFrames": duration_frames,
            "title": item["source"]["title"],
            "category": item["source"]["category"],
            "url": DISPLAY_URL,
        },
    )
    command = [
        str(remotion), "render", "src/remotion/index.ts", "KesherOverview", str(output_path),
        f"--props={props_path}", f"--public-dir={STATE_DIR}", "--codec=h264",
        "--audio-codec=aac", "--concurrency=2", "--timeout=120000",
    ]
    result = subprocess.run(
        command,
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=3600,
        check=False,
    )
    if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size < 1024:
        detail = (result.stderr or result.stdout)[-500:]
        raise PipelineError(f"Remotion visual rebuild failed: {detail}")
    item["visual_pipeline"] = "remotion-v1-notebooklm-audio"
    item["remotion_props_path"] = props_path.name
    item["remotion_props_sha256"] = sha256_file(props_path)
    return output_path


def create_contact_sheet(video_path: Path, item: dict[str, Any], duration: float) -> Path:
    suffix = "-remotion" if item.get("visual_pipeline") == "remotion-v1-notebooklm-audio" else ""
    frame_dir = STATE_DIR / f"{item['id']}{suffix}-frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    timestamps = [duration * fraction for fraction in (0.08, 0.35, 0.65, 0.92)]
    frames: list[Path] = []
    for index, timestamp in enumerate(timestamps, start=1):
        frame = frame_dir / f"frame-{index}.png"
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{timestamp:.3f}",
            "-i", str(video_path), "-frames:v", "1", "-vf", "scale=960:-2", str(frame),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        if result.returncode != 0 or not frame.exists() or frame.stat().st_size == 0:
            raise PipelineError(f"Frame extraction failed for frame {index}")
        frames.append(frame)
    sheet = STATE_DIR / f"{item['id']}{suffix}-visual-review.png"
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        *sum((["-i", str(frame)] for frame in frames), []),
        "-filter_complex", "[0:v][1:v]hstack=inputs=2[top];[2:v][3:v]hstack=inputs=2[bottom];[top][bottom]vstack=inputs=2[out]",
        "-map", "[out]", "-frames:v", "1", str(sheet),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    if result.returncode != 0 or not sheet.exists() or sheet.stat().st_size == 0:
        raise PipelineError("Contact-sheet creation failed")
    return sheet


def validate_and_manifest(state: dict[str, Any], item: dict[str, Any], raw_path: Path) -> None:
    final_path = render_remotion_video(raw_path, item)
    media = ffprobe(final_path)
    sheet = create_contact_sheet(final_path, item, media["duration"])
    item["final_mp4"] = final_path.name
    item["final_sha256"] = sha256_file(final_path)
    item["media"] = media
    item["visual_review_path"] = sheet.name
    item["visual_review_sha256"] = sha256_file(sheet)
    item["frame_paths"] = [
        str(path.relative_to(STATE_DIR))
        for path in sorted(
            (
                STATE_DIR
                / f"{item['id']}{'-remotion' if item.get('visual_pipeline') == 'remotion-v1-notebooklm-audio' else ''}-frames"
            ).glob("frame-*.png")
        )
    ]
    if len(item["frame_paths"]) != 4:
        raise PipelineError("Exactly four review frames are required")
    item["frame_sha256"] = {
        relative: sha256_file(STATE_DIR / relative) for relative in item["frame_paths"]
    }

    technical_failures: list[str] = []
    if media["codec"] != "h264":
        technical_failures.append(f"קודק הווידאו הוא {media['codec']} ולא H.264")
    if not 90 <= media["duration"] <= 180:
        technical_failures.append(
            f"משך הווידאו הוא {media['duration']} שניות ואינו בטווח 90–180 שניות"
        )
    if media["width"] <= media["height"] or not 1.70 <= media["width"] / media["height"] <= 1.82:
        technical_failures.append(
            f"יחס התמונה {media['width']}x{media['height']} אינו יחס אופקי טבעי 16:9"
        )
    metadata = item["youtube_metadata"]
    metadata_failure = ""
    try:
        require_hebrew(metadata["title"], "YouTube title")
        require_hebrew(metadata["description"], "YouTube description", allow_url=True)
        for tag in metadata["tags"]:
            require_hebrew(tag, "YouTube tag")
        if SITE_URL not in metadata["description"]:
            raise PipelineError("YouTube description is missing the Kesher URL")
    except (KeyError, PipelineError) as exc:
        metadata_failure = f"המטא־דאטה אינו עומד בשער העברית והמקור: {exc}"
        technical_failures.append(metadata_failure)

    manifest = {
        "schema_version": 1,
        "item_id": item["id"],
        "created_at": utc_now(),
        "source": item["source"],
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
        item["rejected_at"] = utc_now()
        manifest["technical_verified"] = False
        manifest["rejection_reasons"] = technical_failures
        manifest_path = STATE_DIR / f"{item['id']}-remotion-manifest.json"
        atomic_json_write(manifest_path, manifest)
        item["manifest_path"] = manifest_path.name
        item["manifest_sha256"] = sha256_file(manifest_path)
        save_state(state)
        print(f"TECHNICAL_REJECTED item={item['id']} reasons={len(technical_failures)}")
        return

    item["technical_verified"] = True
    item["review_notes"]["technical"] = (
        f"אומת קובץ MP4 תקין, H.264, יחס {media['width']}x{media['height']}, "
        f"משך {media['duration']} שניות וחותמת SHA-256"
    )
    transcript_path = transcribe_hebrew(final_path, item)
    item["transcript_path"] = transcript_path.name
    item["transcript_sha256"] = sha256_file(transcript_path)
    source_path = STATE_DIR / f"{item['id']}-source-he.txt"
    source_path.write_text(article_body_for_item(item) + "\n", encoding="utf-8")
    item["source_path"] = source_path.name
    item["source_file_sha256"] = sha256_file(source_path)
    manifest["transcript_path"] = item["transcript_path"]
    manifest["transcript_sha256"] = item["transcript_sha256"]
    manifest["source_path"] = item["source_path"]
    manifest["source_file_sha256"] = item["source_file_sha256"]
    manifest["frame_paths"] = item["frame_paths"]
    manifest["frame_sha256"] = item["frame_sha256"]
    manifest["visual_review_path"] = item["visual_review_path"]
    manifest["visual_review_sha256"] = item["visual_review_sha256"]
    manifest_path = STATE_DIR / f"{item['id']}-remotion-manifest.json"
    atomic_json_write(manifest_path, manifest)
    item["manifest_path"] = manifest_path.name
    item["manifest_sha256"] = sha256_file(manifest_path)
    item["status"] = "pending_review"
    item["updated_at"] = utc_now()
    save_state(state)
    print(f"PENDING_REVIEW item={item['id']} review={sheet} manifest={manifest_path}")


def run_generation(
    max_wait_seconds: int,
    require_israel_hour: int | None,
    allow_additional_canary: bool = False,
) -> int:
    if require_israel_hour is not None and israel_now().hour != require_israel_hour:
        print(f"SCHEDULE_SKIPPED israel_hour={israel_now().hour}")
        return 0
    auth_preflight()
    state = load_state()
    item = active_item(state)
    if item and item["status"] in {"pending_review", "approved", "uploading"}:
        print(f"NO_GENERATION active_item={item['id']} status={item['status']}")
        return 0
    if not item:
        today = israel_now().date().isoformat()
        attempted_today = any(
            candidate.get("israel_date") == today
            or str(candidate.get("created_at", "")).startswith(today)
            for candidate in state["items"]
        )
        if attempted_today and not allow_additional_canary:
            print(f"DAILY_ATTEMPT_ALREADY_RECORDED israel_date={today}")
            return 0
        if attempted_today:
            print(f"MANUAL_ADDITIONAL_CANARY israel_date={today}")
        source = select_newest_unused_article(state)
        item = new_item(source)
        state["items"].append(item)
        save_state(state)
        print(f"SOURCE_SELECTED item={item['id']} slug={source['slug']}")
    if item["status"] == "source_selected":
        add_source(state, item)
    if item["status"] == "source_added":
        start_generation(state, item)
    if item["status"] == "generating":
        if not wait_for_generation(state, item, max_wait_seconds):
            return 0
        raw_path = download_artifact(state, item)
    elif item["status"] == "downloaded":
        raw_path = STATE_DIR / item["raw_mp4"]
    else:
        return 0
    validate_and_manifest(state, item, raw_path)
    return 0


def rebuild_rejected_with_remotion(item_id: str) -> int:
    state = load_state()
    matches = [item for item in state["items"] if item.get("id") == item_id]
    if len(matches) != 1:
        raise PipelineError("Remotion rebuild item was not found uniquely")
    item = matches[0]
    if item.get("status") != "rejected" or item.get("visual_review_status") != "rejected":
        raise PipelineError("Remotion rebuild is allowed only for a visually rejected item")
    if item.get("uploaded") is True or item.get("youtube_id"):
        raise PipelineError("Uploaded media cannot be rebuilt")
    raw_path = STATE_DIR / item.get("raw_mp4", "")
    if not raw_path.is_file() or sha256_file(raw_path) != item.get("raw_sha256"):
        raise PipelineError("Original NotebookLM MP4 is missing or changed")
    required_identity = ("notebook_id", "source_id", "task_id", "artifact_id", "source", "youtube_metadata")
    if any(not item.get(field) for field in required_identity):
        raise PipelineError("Provider identity or metadata is incomplete")

    item.setdefault("evidence_history", []).append(
        {
            "recorded_at": utc_now(),
            "status": item.get("status"),
            "final_mp4": item.get("final_mp4"),
            "final_sha256": item.get("final_sha256"),
            "manifest_path": item.get("manifest_path"),
            "manifest_sha256": item.get("manifest_sha256"),
            "visual_review_path": item.get("visual_review_path"),
            "visual_review_sha256": item.get("visual_review_sha256"),
            "frame_paths": item.get("frame_paths"),
            "frame_sha256": item.get("frame_sha256"),
            "review_notes": item.get("review_notes"),
        }
    )
    for field in (
        "final_mp4", "final_sha256", "manifest_path", "manifest_sha256",
        "visual_review_path", "visual_review_sha256", "frame_paths", "frame_sha256",
        "remotion_props_path", "remotion_props_sha256", "rejected_at",
    ):
        item.pop(field, None)
    item["status"] = "downloaded"
    item["technical_verified"] = False
    item["visual_review_status"] = "pending"
    item["semantic_review_status"] = "pending"
    item["metadata_review_status"] = "pending"
    item["review_notes"] = {"technical": "", "visual": "", "semantic": "", "metadata": ""}
    item["remotion_rebuild_started_at"] = utc_now()
    save_state(state)
    validate_and_manifest(state, item, raw_path)
    print(f"REMOTION_REBUILT item={item_id} status={item['status']}")
    return 0


def prune_uploaded_media() -> int:
    state = load_state()
    removed = 0
    for item in state["items"]:
        if item.get("uploaded") is not True or not item.get("youtube_verification"):
            continue
        candidates = [item.get("raw_mp4"), item.get("final_mp4"), item.get("remotion_props_path")]
        for relative in candidates:
            if not isinstance(relative, str) or not relative:
                continue
            path = (STATE_DIR / relative).resolve()
            if STATE_DIR.resolve() not in path.parents or not path.is_file():
                continue
            path.unlink()
            removed += 1
        item["large_media_pruned_at"] = utc_now()
    save_state(state)
    print(f"UPLOADED_MEDIA_PRUNED files={removed}")
    return 0


def update_review(args: argparse.Namespace) -> int:
    state = load_state()
    matches = [item for item in state["items"] if item.get("id") == args.review_item]
    if len(matches) != 1:
        raise PipelineError("Review item was not found uniquely")
    item = matches[0]
    if item.get("status") != "pending_review" or item.get("technical_verified") is not True:
        raise PipelineError("Only technically verified pending items may be reviewed")
    for field in ("visual", "semantic", "metadata"):
        status = getattr(args, f"{field}_status")
        note = getattr(args, f"{field}_note").strip()
        if status not in ALLOWED_REVIEW or not re.search(r"[\u0590-\u05ff]", note):
            raise PipelineError(f"{field} review requires approved/rejected and a Hebrew note")
    final_path = STATE_DIR / item["final_mp4"]
    manifest_path = STATE_DIR / item["manifest_path"]
    review_path = STATE_DIR / item["visual_review_path"]
    transcript_path = STATE_DIR / item.get("transcript_path", "")
    source_path = STATE_DIR / item.get("source_path", "")
    frame_paths = [STATE_DIR / relative for relative in item.get("frame_paths") or []]
    if not final_path.exists() or not manifest_path.exists() or not review_path.exists():
        raise PipelineError("Review evidence is incomplete")
    if sha256_file(final_path) != item["final_sha256"] or sha256_file(manifest_path) != item["manifest_sha256"]:
        raise PipelineError("Review evidence hash mismatch")
    if sha256_file(review_path) != item.get("visual_review_sha256"):
        raise PipelineError("Visual review sheet hash mismatch")
    if not transcript_path.is_file() or sha256_file(transcript_path) != item.get("transcript_sha256"):
        raise PipelineError("Transcript evidence hash mismatch")
    if not source_path.is_file() or sha256_file(source_path) != item.get("source_file_sha256"):
        raise PipelineError("Source evidence hash mismatch")
    if len(frame_paths) != 4 or any(not path.is_file() for path in frame_paths):
        raise PipelineError("Four frame evidence files are required")
    for relative, expected in (item.get("frame_sha256") or {}).items():
        if sha256_file(STATE_DIR / relative) != expected:
            raise PipelineError("Frame evidence hash mismatch")
    for field in ("visual", "semantic", "metadata"):
        item[f"{field}_review_status"] = getattr(args, f"{field}_status")
        item["review_notes"][field] = getattr(args, f"{field}_note").strip()
    statuses = [item[f"{field}_review_status"] for field in ("visual", "semantic", "metadata")]
    item["status"] = "approved" if statuses == ["approved", "approved", "approved"] else "rejected"
    item["reviewed_at"] = utc_now()
    reviewer_session = getattr(args, "reviewer_session", None)
    if reviewer_session:
        item["reviewer"] = {"type": "jules", "session": reviewer_session}
    item["updated_at"] = utc_now()
    save_state(state)
    print(f"REVIEW_RECORDED item={item['id']} status={item['status']}")
    return 0


def youtube_access_token() -> str:
    required = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
    missing = [key for key in required if not os.environ.get(key, "").strip()]
    if missing:
        raise PipelineError(f"YouTube OAuth secrets are missing: {', '.join(missing)}")
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": os.environ["YOUTUBE_CLIENT_ID"],
            "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
            "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if response.status_code != 200 or not response.json().get("access_token"):
        raise PipelineError(f"YouTube OAuth refresh failed with HTTP {response.status_code}")
    return str(response.json()["access_token"])


def youtube_get(path: str, token: str, params: dict[str, str]) -> dict[str, Any]:
    response = requests.get(
        f"https://www.googleapis.com/youtube/v3/{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=30,
    )
    if response.status_code != 200:
        raise PipelineError(f"YouTube {path} failed with HTTP {response.status_code}")
    return response.json()


def verify_authenticated_channel(token: str) -> None:
    payload = youtube_get("channels", token, {"part": "id", "mine": "true"})
    ids = [row.get("id") for row in payload.get("items", [])]
    if ids != [YOUTUBE_CHANNEL_ID]:
        raise PipelineError("Authenticated YouTube channel does not match the Kesher channel")


def start_resumable_upload(state: dict[str, Any], item: dict[str, Any], token: str, video_path: Path) -> str:
    metadata = item["youtube_metadata"]
    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": "22",
            "defaultLanguage": "he",
            "defaultAudioLanguage": "he",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }
    response = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(video_path.stat().st_size),
            "X-Upload-Content-Type": "video/mp4",
        },
        json=body,
        timeout=60,
    )
    location = response.headers.get("Location")
    if response.status_code not in {200, 201} or not location:
        raise PipelineError(f"YouTube resumable session creation failed with HTTP {response.status_code}")
    item["upload_session_uri"] = location
    item["upload_session_created_at"] = utc_now()
    item["status"] = "uploading"
    save_state(state)
    return location


def resume_offset(session_uri: str, token: str, total: int) -> int:
    response = requests.put(
        session_uri,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Length": "0",
            "Content-Range": f"bytes */{total}",
        },
        timeout=60,
    )
    if response.status_code in {200, 201}:
        return total
    if response.status_code == 308:
        match = re.search(r"bytes=0-(\d+)", response.headers.get("Range", ""))
        return int(match.group(1)) + 1 if match else 0
    if response.status_code in {404, 410}:
        raise PipelineError("Saved YouTube upload session expired; refusing a second insert automatically")
    raise PipelineError(f"YouTube upload status query failed with HTTP {response.status_code}")


def upload_bytes(session_uri: str, token: str, video_path: Path, offset: int) -> str:
    total = video_path.stat().st_size
    if offset >= total:
        raise PipelineError("Upload session reports complete but no video ID is persisted")
    with video_path.open("rb") as handle:
        handle.seek(offset)
        data = handle.read()
    response = requests.put(
        session_uri,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "video/mp4",
            "Content-Length": str(len(data)),
            "Content-Range": f"bytes {offset}-{total - 1}/{total}",
        },
        data=data,
        timeout=1200,
    )
    if response.status_code not in {200, 201}:
        raise PipelineError(f"YouTube media upload failed with HTTP {response.status_code}")
    video_id = response.json().get("id")
    if not video_id:
        raise PipelineError("YouTube upload response contained no video ID")
    return str(video_id)


def verify_public_upload(item: dict[str, Any], token: str, timeout_seconds: int = 900) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        payload = youtube_get(
            "videos", token,
            {"part": "snippet,status,processingDetails", "id": item["youtube_id"]},
        )
        rows = payload.get("items") or []
        if len(rows) != 1:
            raise PipelineError("Uploaded YouTube video is not uniquely visible")
        row = rows[0]
        snippet = row.get("snippet") or {}
        status = row.get("status") or {}
        processing = row.get("processingDetails") or {}
        if snippet.get("channelId") != YOUTUBE_CHANNEL_ID:
            raise PipelineError("Uploaded video belongs to the wrong YouTube channel")
        if snippet.get("title") != item["youtube_metadata"]["title"]:
            raise PipelineError("Uploaded title differs from the approved metadata")
        if SITE_URL not in str(snippet.get("description", "")):
            raise PipelineError("Uploaded description is missing the Kesher URL")
        require_hebrew(str(snippet.get("title", "")), "uploaded title")
        require_hebrew(str(snippet.get("description", "")), "uploaded description", allow_url=True)
        process_status = processing.get("processingStatus")
        if status.get("privacyStatus") == "public" and process_status == "succeeded":
            return {
                "video_id": item["youtube_id"],
                "channel_id": snippet.get("channelId"),
                "privacy_status": status.get("privacyStatus"),
                "processing_status": process_status,
                "default_language": snippet.get("defaultLanguage"),
                "default_audio_language": snippet.get("defaultAudioLanguage"),
            }
        if process_status in {"failed", "terminated"}:
            raise PipelineError(f"YouTube processing ended with {process_status}")
        if time.monotonic() >= deadline:
            raise PipelineError("YouTube processing did not become public and complete in time")
        time.sleep(20)


def upload_only() -> int:
    state = load_state()
    approved = [
        item for item in state["items"]
        if item.get("status") in {"approved", "uploading"} and not item.get("uploaded")
    ]
    if not approved:
        print("NO_APPROVED_UPLOAD")
        return 0
    if len(approved) != 1:
        raise PipelineError("More than one approved item exists")
    item = approved[0]
    required_gates = {
        "technical_verified": True,
        "visual_review_status": "approved",
        "semantic_review_status": "approved",
        "metadata_review_status": "approved",
    }
    for field, expected in required_gates.items():
        if item.get(field) != expected:
            raise PipelineError(f"Upload gate failed: {field}")
    for field in ("technical", "visual", "semantic", "metadata"):
        if not re.search(r"[\u0590-\u05ff]", str(item.get("review_notes", {}).get(field, ""))):
            raise PipelineError(f"Upload gate is missing a Hebrew {field} review note")
    video_path = STATE_DIR / item["final_mp4"]
    manifest_path = STATE_DIR / item["manifest_path"]
    review_path = STATE_DIR / item["visual_review_path"]
    if not all(path.exists() for path in (video_path, manifest_path, review_path)):
        raise PipelineError("Approved item is missing MP4, manifest or review path")
    if sha256_file(video_path) != item["final_sha256"] or sha256_file(manifest_path) != item["manifest_sha256"]:
        raise PipelineError("Approved evidence hash mismatch")
    if sha256_file(review_path) != item.get("visual_review_sha256"):
        raise PipelineError("Approved visual review sheet hash mismatch")
    transcript_path = STATE_DIR / item.get("transcript_path", "")
    source_path = STATE_DIR / item.get("source_path", "")
    if not transcript_path.is_file() or sha256_file(transcript_path) != item.get("transcript_sha256"):
        raise PipelineError("Approved transcript hash mismatch")
    if not source_path.is_file() or sha256_file(source_path) != item.get("source_file_sha256"):
        raise PipelineError("Approved source hash mismatch")
    frame_hashes = item.get("frame_sha256") or {}
    if len(frame_hashes) != 4:
        raise PipelineError("Approved item must retain exactly four frame hashes")
    for relative, expected in frame_hashes.items():
        frame_path = STATE_DIR / relative
        if not frame_path.is_file() or sha256_file(frame_path) != expected:
            raise PipelineError("Approved frame hash mismatch")
    token = youtube_access_token()
    verify_authenticated_channel(token)
    session_uri = item.get("upload_session_uri")
    if not session_uri:
        session_uri = start_resumable_upload(state, item, token, video_path)
        offset = 0
    else:
        offset = resume_offset(session_uri, token, video_path.stat().st_size)
    video_id = upload_bytes(session_uri, token, video_path, offset)
    item["youtube_id"] = video_id
    item["youtube_url"] = f"https://youtu.be/{video_id}"
    item["upload_response_at"] = utc_now()
    save_state(state)
    verification = verify_public_upload(item, token)
    item["youtube_verification"] = verification
    item["uploaded"] = True
    item["status"] = "uploaded"
    item["uploaded_at"] = utc_now()
    item.pop("upload_session_uri", None)
    save_state(state)
    print(f"UPLOADED item={item['id']} url={item['youtube_url']}")
    return 0


def report() -> int:
    state = load_state()
    counts: dict[str, int] = {}
    for item in state["items"]:
        counts[item.get("status", "unknown")] = counts.get(item.get("status", "unknown"), 0) + 1
    print(json.dumps({"state_file": str(STATE_FILE), "counts": counts, "items": state["items"]}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kesher cloud NotebookLM Video Overview pipeline")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--upload-only", action="store_true")
    mode.add_argument("--review-item")
    mode.add_argument("--remotion-rebuild-item")
    mode.add_argument("--prune-uploaded-media", action="store_true")
    mode.add_argument("--report-json", action="store_true")
    parser.add_argument("--max-wait-seconds", type=int, default=3600)
    parser.add_argument("--require-israel-hour", type=int, choices=range(24))
    parser.add_argument("--allow-additional-canary", action="store_true")
    parser.add_argument("--visual-status", choices=sorted(ALLOWED_REVIEW))
    parser.add_argument("--semantic-status", choices=sorted(ALLOWED_REVIEW))
    parser.add_argument("--metadata-status", choices=sorted(ALLOWED_REVIEW))
    parser.add_argument("--visual-note")
    parser.add_argument("--semantic-note")
    parser.add_argument("--metadata-note")
    parser.add_argument("--reviewer-session")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.preflight:
        print(json.dumps({"preflight": "passed", **auth_preflight()}, ensure_ascii=False))
        return 0
    if args.upload_only:
        return upload_only()
    if args.review_item:
        required = (
            args.visual_status, args.semantic_status, args.metadata_status,
            args.visual_note, args.semantic_note, args.metadata_note,
        )
        if any(value is None for value in required):
            raise PipelineError("Atomic review requires all three statuses and Hebrew notes")
        return update_review(args)
    if args.remotion_rebuild_item:
        return rebuild_rejected_with_remotion(args.remotion_rebuild_item)
    if args.prune_uploaded_media:
        return prune_uploaded_media()
    if args.report_json:
        return report()
    return run_generation(
        args.max_wait_seconds,
        args.require_israel_hour,
        allow_additional_canary=args.allow_additional_canary,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PipelineError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"PIPELINE_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

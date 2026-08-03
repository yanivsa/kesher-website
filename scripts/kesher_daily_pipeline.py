#!/usr/bin/env python3
import os
import sys
import re
import json
import time
import shutil
import hashlib
import argparse
import subprocess
import urllib.request
import urllib.parse
import contextlib
import select
import socket
import fcntl
from datetime import datetime
from pathlib import Path
import requests

sys.path.append("scripts")
from notebooklm_client import NotebookLMClient

# Configuration constants
NOTEBOOK_ID = "e101e7d7-5305-45b3-a611-21a5475ceb63"
NOTEBOOK_URL = f"https://notebooklm.google.com/notebook/{NOTEBOOK_ID}?hl=en"
YOUTUBE_CHANNEL_ID = "UCx5fEFvdVf28HLAR2dFW64Q"
COMPOSIO_CONNECTED_ACCOUNT = "youtube_ransom-winish"
SITE_URL = "https://kesher.saharoni.com"
MAX_GENERATION_SOURCE_ATTEMPTS = 3
NOTEBOOKLM_SOURCE_ADD_TIMEOUT_SECONDS = 180

# Directories
PROJECT_DIR = Path("/Users/ninja/Documents/Kesher")
OUTPUT_DIR = PROJECT_DIR / "notebooklm-output"
REMOTION_DIR = PROJECT_DIR / "remotion-kesher"
REMOTION_OUTPUT_DIR = PROJECT_DIR / "remotion-output"
QUEUE_FILE = OUTPUT_DIR / "video_queue.json"
RUN_LOCK_FILE = OUTPUT_DIR / "kesher_daily_pipeline.lock"

# Content Prompt
CONTENT_PROMPT_TEMPLATE = (
    "אתה במאי, תסריטאי ועורך וידאו ויראלי לערוץ 'קשר' לייעוץ זוגי ומשפחתי. "
    "צור Video Overview מקורי לחלוטין שנכתב, מוקלט ונערך בעברית מלכתחילה. "
    "כל הדיבור, הטקסט המוטמע, הכותרת, התיאור והתגיות חייבים להיות בעברית; "
    "החריגים היחידים הם https://kesher.saharoni.com והמונח Shorts. "
    "אל תתרגם תסריט אנגלי ואל תחזיר כותרת או תיאור באנגלית. "
    "איסור מוחלט: אל תציג בפריימים מילים באנגלית, אותיות לטיניות, טקסט דמה או ג'יבריש. "
    "אם אינך בטוח שתוכל לכתוב עברית תקינה בתוך תמונה, אל תציג טקסט בתמונה בכלל; העדף סיפור חזותי ללא מילים. "
    "צור סרטון faceless קולנועי, חם, רגשי, ברור, מקצועי ומכבד. "
    "אסור מראה של מצגת: אין שקופיות, כרטיסיות מידע, תרשימי חצים, רשימות, טבלאות, מסגרות טקסט או מסכים סטטיים עם כותרת גדולה. "
    "בחר רעיון אחד בלבד שהצופה מזהה מיד מחיי הבית. השתמש בשמות עבריים חדשים ואל תעתיק שמות, דמויות, מבנה או ניסוחים מהמקור. "
    "מבנה חובה: בתוך 0-3 שניות משפט מסקרן שמציג מחיר רגשי או סתירה; מיד אחריו סיטואציה ביתית קונקרטית; "
    "לאחר מכן הסבר מפתיע אחד; נקודת מפנה עם פעולה אחת שאפשר לבצע היום; וסיום קצר שסוגר את ההבטחה מהפתיחה. "
    "אל תפתח בהקדמה, לוגו, ברכה, הגדרה כללית או 'בסרטון הזה'. אל תחזור על אותו רעיון בניסוחים שונים. "
    "הקריינות תהיה טבעית, במשפטים קצרים ובקצב אנושי. הימנע מאבחון, הבטחות טיפוליות, הפחדה או טון מטיף. "
    "תכנון חזותי חובה: ספר סיפור באמצעות סצנות ולא באמצעות הסברים כתובים. התאם כל סצנה למשפט הנאמר; "
    "החלף סוג פריים, זווית, מרחק או תנועה כל 3-6 שניות; "
    "שלב שלושה pattern interrupts עדינים בנקודות מפתח; השתמש ב-B-roll ביתי אמין, מחוות ידיים, מרחק בין בני זוג, דלת, שולחן או טלפון רק כשהם משרתים את הסיפור. "
    "אין להציג פנים מדברות למצלמה ואין להשתמש באותו שוט שוב ושוב. "
    "טקסט מוטמע הוא מוצא אחרון בלבד, לא כתוביות: עברית תקינה בלבד, עד 4 מילים בשורה, עד 2 שורות, ניגודיות גבוהה ובאזור הבטוח. "
    "לפני סיום בדוק בעצמך: אין אף מילה באנגלית, אין ג'יבריש, אין שקופיות, אין טקסט חתוך, והסיום משלים את המשפט והסיפור בלי קטיעה. "
    "בסוף התשובה החזר בדיוק: "
    "YT_TITLE: כותרת עברית מסקרנת וספציפית עד 70 תווים, בלי clickbait מטעה; "
    "YT_DESCRIPTION: 2-4 משפטים בעברית שמסבירים את הערך בלי לגלות הכול; "
    "YT_TAGS: 6-12 תגיות עבריות מופרדות בפסיקים; "
    "REMOTION_THEME: אחת מהאפשרויות mind-reading, listening, boundaries, connection; "
    "REMOTION_BEATS: שלושה שלבים קצרים בעברית, 2-5 מילים כל אחד, מופרדים בסימן |. "
)

DEFAULT_TAGS = [
    "ייעוץ זוגי", "הדרכת הורים", "הנחיית הורים", "הורות", "זוגיות",
    "תקשורת זוגית", "גבולות", "ויסות רגשי", "משפחה", "אשדוד", "שירה סהרוני",
]

def search_youtube_candidates(query, max_results=5):
    print(f"Searching YouTube for candidates: '{query}'...")
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching YouTube: {e}")
        return []

    # Regex fallback extraction of video IDs
    video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
    seen = set()
    unique_ids = [x for x in video_ids if not (x in seen or seen.add(x))]
    
    candidates = []
    for vid in unique_ids[:max_results]:
        candidates.append({
            "url": f"https://www.youtube.com/watch?v={vid}",
            "topic": f"YouTube video {vid}"
        })
    return candidates

def add_source_to_notebooklm(client, candidate_url):
    print(f"Adding source to NotebookLM: {candidate_url}")
    try:
        result = client.call_tool(
            "source_add",
            {
                "source_type": "youtube",
                "url": candidate_url,
                "notebook_url": NOTEBOOK_URL,
            },
            timeout=180
        )
        raw = json.dumps(result, ensure_ascii=False).lower()
        if "success" in raw or "source" in raw or "title" in raw:
            return True, result
        return False, result
    except Exception as e:
        return False, str(e)


def notebooklm_artifact_count():
    cmd = [
        "node",
        str(PROJECT_DIR / "scripts/notebooklm_direct_video_download.mjs"),
        "/tmp/kesher-notebooklm-count-only.mp4",
        "--count-only",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f"Unable to count NotebookLM artifacts: {result.stderr}")
    for line in reversed(result.stdout.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("success") and isinstance(payload.get("artifactCount"), int):
            return payload["artifactCount"]
    raise RuntimeError("NotebookLM artifact count was missing from browser output")


def generation_text(result):
    if isinstance(result, dict):
        data = result.get("structuredContent", {}).get("data", {})
        if isinstance(data.get("textContent"), str):
            return data["textContent"]
    for payload in decode_mcp_payloads(result):
        if isinstance(payload, dict):
            text_content = payload.get("textContent")
            if isinstance(text_content, str):
                return text_content
    return ""


def metadata_from_generation(result, format_type):
    text = generation_text(result)
    title_match = re.search(r"YT_TITLE:\s*(.+)", text)
    description_match = re.search(
        r"YT_DESCRIPTION:\s*(.*?)(?=\n\s*YT_TAGS:|$)", text, re.DOTALL
    )
    tags_match = re.search(r"YT_TAGS:\s*(.+)", text)
    theme_match = re.search(r"REMOTION_THEME:\s*(mind-reading|listening|boundaries|connection)", text, re.I)
    beats_match = re.search(r"REMOTION_BEATS:\s*(.+)", text)

    if not title_match:
        title_match = re.search(r"כותרות[^\n]*\n([^\n]+)", text)
    if not description_match:
        description_match = re.search(
            r"תיאור הסרטון[^:]*:\s*(.*?)(?=\n\s*תגיות|\n\s*רעיונות|$)",
            text,
            re.DOTALL,
        )
    if not tags_match:
        tags_match = re.search(r"תגיות[^:]*:\s*([^\n]+)", text)

    title = title_match.group(1).strip() if title_match else "כלי קטן שמשנה את השיחה בבית"
    title = re.sub(r"\s*\(מומלצת[^)]*\)\s*$", "", title).strip(' "')[:100]
    if format_type == "short" and "#shorts" not in title.lower():
        title = f"{title[:90]} #Shorts"

    description_body = (
        description_match.group(1).strip()
        if description_match
        else "סיפור קצר וכלי מעשי לתקשורת טובה יותר בבית ובזוגיות."
    )
    required_footer = (
        "למידע נוסף ותיאום פגישה:\n"
        f"{SITE_URL}\n\n"
        "קשר - ייעוץ זוגי ומשפחתי"
    )
    if SITE_URL not in description_body:
        description_body = f"{description_body}\n\n{required_footer}"
    if format_type == "short" and "#shorts" not in description_body.lower():
        description_body = f"{description_body}\n\n#Shorts"

    tags = DEFAULT_TAGS.copy()
    if tags_match:
        parsed_tags = [tag.strip().lstrip("#") for tag in tags_match.group(1).split(",")]
        tags = [tag for tag in parsed_tags if tag][:20] or tags
    if format_type == "short" and "shorts" not in [tag.lower() for tag in tags]:
        tags.append("shorts")

    metadata = {"title": title, "description": description_body, "tags": tags}
    if theme_match:
        metadata["contentTheme"] = theme_match.group(1).lower()
    if beats_match:
        beats = [part.strip() for part in beats_match.group(1).split("|") if part.strip()]
        if len(beats) == 3 and all(re.search(r"[\u0590-\u05ff]", beat) for beat in beats):
            metadata["beatLabels"] = beats
    ok, reason = validate_hebrew_metadata(metadata)
    if not ok:
        raise RuntimeError(f"NotebookLM returned invalid non-Hebrew metadata: {reason}")
    return metadata


def validate_hebrew_metadata(metadata):
    for field in ("title", "description"):
        value = metadata.get(field, "")
        letters = re.findall(r"[A-Za-z\u0590-\u05ff]", value.replace(SITE_URL, ""))
        hebrew = re.findall(r"[\u0590-\u05ff]", value)
        if not hebrew:
            return False, f"{field} contains no Hebrew"
        if letters and len(hebrew) / len(letters) < 0.72:
            return False, f"{field} is not predominantly Hebrew"
    tags_text = " ".join(metadata.get("tags") or []).replace("shorts", "")
    if not re.search(r"[\u0590-\u05ff]", tags_text):
        return False, "tags contain no Hebrew"
    return True, ""


def remotion_content_plan(metadata):
    if metadata.get("contentTheme") and len(metadata.get("beatLabels") or []) == 3:
        return {
            "contentTheme": metadata["contentTheme"],
            "beatLabels": metadata["beatLabels"],
        }
    text = f"{metadata.get('title', '')} {metadata.get('description', '')}"
    plans = [
        (("מחשב", "מנחש", "ציפ"), "mind-reading", ["מה ציפיתי שיבינו?", "לבקש במקום לנחש", "לנסח צורך ברור"]),
        (("גבול", "מאבק", "ילד"), "boundaries", ["לזהות את הגבול", "להישאר רגועים", "לפעול באותו צד"]),
        (("הקשב", "עצה", "ביקורת"), "listening", ["לעצור לפני עצה", "להקשיב לרגש", "לשאול מה נחוץ"]),
    ]
    for keywords, motif, beats in plans:
        if any(keyword in text for keyword in keywords):
            return {"contentTheme": motif, "beatLabels": beats}
    return {"contentTheme": "connection", "beatLabels": ["לזהות את הרגע", "לומר את הצורך", "לבנות חיבור"]}


def generate_and_download_notebooklm(client, format_type, custom_prompt, output_path):
    print(f"Generating {format_type} video in NotebookLM...")
    try:
        baseline_count = notebooklm_artifact_count()
        print(f"NotebookLM artifact baseline: {baseline_count}")
        gen_result = client.call_tool(
            "content_generate",
            {
                "content_type": "video",
                "video_style": "cinematic",
                "custom_instructions": custom_prompt,
                "language": "Hebrew",
                "notebook_url": NOTEBOOK_URL,
            },
            timeout=900,
        )
        print(f"Generation started/ready: {gen_result}")

        print("Waiting for a new completed Studio artifact before downloading...")
        output_path.unlink(missing_ok=True)
        cmd = [
            "node",
            str(PROJECT_DIR / "scripts/notebooklm_direct_video_download.mjs"),
            str(output_path),
            f"--min-artifact-count={baseline_count + 1}",
            "--wait-seconds=3600",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=4200)
        print("Playwright script output:", res.stdout)
        if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            print("New NotebookLM artifact downloaded successfully.")
            return True, {
                "method": "playwright-new-artifact",
                "baseline_count": baseline_count,
                "new_count": baseline_count + 1,
                "youtube_metadata": metadata_from_generation(gen_result, format_type),
            }
            
        return False, f"Download empty. Playwright err: {res.stderr}"
    except Exception as e:
        return False, str(e)

def run_remotion_render(input_mp4, output_mp4, metadata, format_type):
    print(f"Running Remotion Render: {input_mp4} -> {output_mp4}")
    # Copy input to remotion public folder
    public_input = REMOTION_DIR / "public" / "kesher-input.mp4"
    shutil.copy2(input_mp4, public_input)
    
    # Run Remotion CLI render
    source = media_metadata(input_mp4)
    if not source:
        return False, "Unable to read source video metadata."
    if format_type == "short" and not 35 <= source["duration"] <= 55:
        return False, f"Short source is {source['duration']:.2f}s; refusing to cut it arbitrarily to 35-55s. Regeneration required."
    if format_type == "short" and source["height"] <= source["width"]:
        return False, f"Short source is {source['width']}x{source['height']}; it must be generated vertically in 9:16. Regeneration required."
    if format_type == "normal" and not 90 <= source["duration"] <= 180:
        return False, f"Normal source is outside 90-180s: {source['duration']:.2f}s."
    fps = 24 if format_type == "short" else 30
    props = json.dumps({
        "videoSrc": "kesher-input.mp4",
        "title": "",  # No subtitles/text overlays as requested
        "hook": "",
        "sourceDurationInFrames": round(source["duration"] * fps),
        **remotion_content_plan(metadata),
    })
    
    composition_id = "KesherShort" if format_type == "short" else "KesherVideo"
    cmd = [
        "npx", "remotion", "render", "src/index.ts", composition_id,
        str(output_mp4),
        "--props", props,
        "--concurrency=4",
    ]
    
    try:
        res = subprocess.run(cmd, cwd=str(REMOTION_DIR), capture_output=True, text=True, timeout=3600)
        if res.returncode == 0 and output_mp4.exists() and output_mp4.stat().st_size > 0:
            print("Remotion rendering completed successfully.")
            return True, ""
        return False, f"Remotion failed: {res.stderr}\nStdout: {res.stdout}"
    except Exception as e:
        return False, str(e)

def media_metadata(video_path):
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(video_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stderr
        duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
        size_match = re.search(r"\b(\d{3,5})x(\d{3,5})\b", output)
        if not duration_match or not size_match:
            return None
        hours, minutes, seconds = duration_match.groups()
        return {
            "duration": int(hours) * 3600 + int(minutes) * 60 + float(seconds),
            "width": int(size_match.group(1)),
            "height": int(size_match.group(2)),
        }
    except Exception:
        return None

def verify_rendered_video(video_path, format_type):
    metadata = media_metadata(video_path)
    if not metadata:
        return False, "Unable to read rendered video metadata."
    if format_type == "short":
        if metadata["height"] <= metadata["width"]:
            return False, f"Short must be vertical, got {metadata['width']}x{metadata['height']}."
        if not 35 <= metadata["duration"] <= 55:
            return False, f"Short must be 35-55 seconds, got {metadata['duration']:.2f}."
    elif not 90 <= metadata["duration"] <= 180:
        return False, f"Normal video must be 90-180 seconds, got {metadata['duration']:.2f}."
    return True, metadata


def create_visual_contact_sheet(video_path, format_type):
    """Create four evenly spaced frames for the automation's mandatory visual review."""
    metadata = media_metadata(video_path)
    if not metadata or metadata["duration"] <= 0:
        return None, "Unable to read video for visual review."
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        frame_rate = 4 / metadata["duration"]
        scale = "360:640" if format_type == "short" else "640:360"
        sheet_path = video_path.with_name(f"{video_path.stem}-visual-review.png")
        command = [
            ffmpeg, "-y", "-i", str(video_path),
            "-vf", f"fps={frame_rate:.8f},scale={scale},tile=2x2",
            "-frames:v", "1", "-update", "1", str(sheet_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if result.returncode != 0 or not sheet_path.exists() or sheet_path.stat().st_size == 0:
            return None, f"Contact-sheet creation failed: {result.stderr[-500:]}"
        return sheet_path, ""
    except Exception as exc:
        return None, str(exc)


def iter_nested_values(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from iter_nested_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_nested_values(child)
    else:
        yield value


def decode_mcp_payloads(result):
    payloads = []
    pending = [result]
    decoded_strings = set()
    while pending:
        payload = pending.pop(0)
        payloads.append(payload)
        for value in iter_nested_values(payload):
            if not isinstance(value, str):
                continue
            stripped = value.strip()
            if not stripped or stripped[0] not in "[{" or stripped in decoded_strings:
                continue
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            decoded_strings.add(stripped)
            pending.append(decoded)
    return payloads


def find_video_record(value, video_id):
    if isinstance(value, dict):
        if value.get("id") == video_id and ("snippet" in value or "status" in value):
            return value
        for child in value.values():
            found = find_video_record(child, video_id)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_video_record(child, video_id)
            if found:
                return found
    return None


def get_youtube_video_record(mcp_client, video_id):
    result = mcp_client.call_tool(
        "COMPOSIO_MULTI_EXECUTE_TOOL",
        {
            "sync_response_to_workbench": False,
            "current_step": "VERIFYING_PUBLIC_VIDEO",
            "memory": {},
            "tools": [
                {
                    "tool_slug": "YOUTUBE_GET_VIDEO_DETAILS_BATCH",
                    "connected_account_id": COMPOSIO_CONNECTED_ACCOUNT,
                    "arguments": {
                        "id": [video_id],
                        "parts": ["snippet", "status"],
                    },
                }
            ],
        },
        timeout=120,
    )
    for payload in decode_mcp_payloads(result):
        record = find_video_record(payload, video_id)
        if record:
            return record
    return None


def verify_public_youtube_video(mcp_client, video_id):
    record = get_youtube_video_record(mcp_client, video_id)
    if not record:
        return False, "video is missing, private, or deleted"

    snippet = record.get("snippet") or {}
    status = record.get("status") or {}
    channel_id = snippet.get("channelId")
    privacy = status.get("privacyStatus")
    description = snippet.get("description") or ""
    title = snippet.get("title") or ""

    if channel_id != YOUTUBE_CHANNEL_ID:
        return False, f"wrong channel: {channel_id!r}"
    if privacy != "public":
        return False, f"privacy status is {privacy!r}, not 'public'"
    if SITE_URL not in description:
        return False, "Kesher site URL is missing from the description"
    if not re.search(r"[\u0590-\u05ff]", title):
        return False, "YouTube title is not in Hebrew"
    valid_metadata, reason = validate_hebrew_metadata({
        "title": title,
        "description": description,
        "tags": ["עברית"],
    })
    if not valid_metadata:
        return False, f"YouTube metadata language check failed: {reason}"

    return True, {
        "video_id": video_id,
        "channel_id": channel_id,
        "privacy_status": privacy,
        "upload_status": status.get("uploadStatus"),
        "title": title,
    }


def extract_uploaded_video_candidates(result):
    candidates = []
    for payload in decode_mcp_payloads(result):
        texts = [value for value in iter_nested_values(payload) if isinstance(value, str)]
        for text in texts:
            if "YouTube Upload Success:" not in text:
                continue
            success_text = text.split("YouTube Upload Success:", 1)[1]
            for candidate in re.findall(r'"id"\s*:\s*"([a-zA-Z0-9_-]{11})"', success_text):
                if candidate not in candidates:
                    candidates.append(candidate)
    return candidates


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextlib.contextmanager
def serve_video_through_localtunnel(video_path):
    expected_size = video_path.stat().st_size
    port = find_free_port()
    http_process = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(video_path.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    tunnel_process = subprocess.Popen(
        [
            "npx",
            "--yes",
            "localtunnel",
            "--port",
            str(port),
            "--local-host",
            "127.0.0.1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        tunnel_url = None
        deadline = time.time() + 45
        while time.time() < deadline:
            ready, _, _ = select.select([tunnel_process.stdout], [], [], 1)
            if ready:
                line = tunnel_process.stdout.readline().strip()
                if "your url is:" in line:
                    tunnel_url = line.split("your url is:", 1)[1].strip()
                    break
            if tunnel_process.poll() is not None:
                stderr = tunnel_process.stderr.read().strip()
                raise RuntimeError(f"localtunnel exited early: {stderr}")
        if not tunnel_url:
            raise RuntimeError("localtunnel did not provide a public URL")

        public_url = f"{tunnel_url}/{urllib.parse.quote(video_path.name)}"
        probe = requests.get(
            public_url,
            headers={
                "User-Agent": "KesherVideoPipeline/1.0",
                "bypass-tunnel-reminder": "true",
            },
            stream=True,
            timeout=45,
        )
        probe.raise_for_status()
        content_length = int(probe.headers.get("Content-Length") or 0)
        first_chunk = next(probe.iter_content(chunk_size=32), b"")
        probe.close()
        if content_length != expected_size:
            raise RuntimeError(
                f"Tunnel size mismatch: expected {expected_size}, got {content_length}"
            )
        if len(first_chunk) < 12 or first_chunk[4:8] != b"ftyp":
            raise RuntimeError("Tunnel response is not an MP4 file")
        yield public_url, expected_size
    finally:
        tunnel_process.terminate()
        http_process.terminate()
        for process in (tunnel_process, http_process):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def reconcile_uploaded_queue(queue_data):
    uploaded_items = [item for item in queue_data.get("queue", []) if item.get("uploaded")]
    if not uploaded_items:
        return False

    changed = False
    from composio_mcp_client import ComposioMCPClient
    mcp_client = ComposioMCPClient()
    mcp_client.connect()
    try:
        for item in uploaded_items:
            video_id = item.get("youtube_id")
            if not video_id:
                ok, verification = False, "queue item has no YouTube ID"
            else:
                ok, verification = verify_public_youtube_video(mcp_client, video_id)
            if ok:
                item["youtube_verification"] = verification
                item["last_verified_at"] = datetime.now().isoformat()
                item["upload_status"] = "public_verified"
                item.pop("last_upload_error", None)
                continue

            item.setdefault("upload_history", []).append(
                {
                    "youtube_id": video_id,
                    "youtube_url": item.get("youtube_url"),
                    "uploaded_at": item.get("uploaded_at"),
                    "invalidated_at": datetime.now().isoformat(),
                    "reason": verification,
                }
            )
            item["uploaded"] = False
            item["upload_status"] = "deleted_or_unavailable"
            item["last_upload_error"] = verification
            item.pop("youtube_id", None)
            item.pop("youtube_url", None)
            item.pop("youtube_verification", None)
            changed = True
    finally:
        mcp_client.disconnect()
    return changed

def verify_channel_and_upload(video_path, title, description, tags, is_test=False):
    print(f"Uploading {video_path} via a verified local tunnel and Composio Remote Workbench...")
    if is_test:
        print("[TEST MODE] Skipped upload.")
        return True, "test_video_id", "https://youtube.com/watch?v=test_video_id"
        
    try:
        file_name = video_path.name
        with serve_video_through_localtunnel(video_path) as (direct_url, expected_size):
            print(f"Verified tunnel URL for {expected_size} bytes.")

            # Prepare workbench code
            workbench_code = f'''
import urllib.request
import json
import sys
import os

download_url = "{direct_url}"
local_path = "/tmp/{file_name}"
expected_size = {expected_size}

print("Step 1: Downloading verified video inside sandbox...")
req = urllib.request.Request(download_url, headers={{
    "User-Agent": "KesherVideoPipeline/1.0",
    "bypass-tunnel-reminder": "true",
}})
with urllib.request.urlopen(req, timeout=300) as response:
    with open(local_path, "wb") as f:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

actual_size = os.path.getsize(local_path)
with open(local_path, "rb") as f:
    header = f.read(12)
if actual_size != expected_size:
    print(f"Downloaded size mismatch: expected {{expected_size}}, got {{actual_size}}")
    sys.exit(1)
if len(header) < 12 or header[4:8] != b"ftyp":
    print("Downloaded file is not an MP4")
    sys.exit(1)
print("Downloaded and verified MP4, size:", actual_size)

print("Step 2: Uploading to S3...")
uploaded, err = upload_local_file(local_path)
if err:
    print("S3 Upload error:", err)
    sys.exit(1)
    
s3key = uploaded["s3key"]
print("Uploaded to S3. Key:", s3key)

print("Step 3: Running YouTube Multipart Upload...")
title = {repr(title)}
description = {repr(description)}
tags = {repr(tags)}

result, yt_err = run_composio_tool("YOUTUBE_MULTIPART_UPLOAD_VIDEO", {{
    "title": title,
    "description": description,
    "tags": tags,
    "categoryId": "22",
    "privacyStatus": "public",
    "videoFile": {{
        "name": "{file_name}",
        "mimetype": "video/mp4",
        "s3key": s3key
    }}
}}, account="kesher")

if yt_err:
    print("YouTube Upload error:", yt_err)
    sys.exit(1)
    
print("YouTube Upload Success:", json.dumps(result, ensure_ascii=False))
'''

            # Run via ComposioMCPClient while the tunnel stays open.
            from composio_mcp_client import ComposioMCPClient
            mcp_client = ComposioMCPClient()
            mcp_client.connect()
            try:
                result = mcp_client.call_tool(
                    "COMPOSIO_REMOTE_WORKBENCH",
                    {
                        "code_to_execute": workbench_code,
                        "sync_response_to_workbench": False,
                    },
                    timeout=600
                )
                print("Workbench result:", result)

                candidate_ids = extract_uploaded_video_candidates(result)
                if not candidate_ids:
                    return False, "Upload response did not contain a YouTube video ID", ""

                verification_errors = []
                for yt_id in candidate_ids:
                    for attempt in range(6):
                        ok, verification = verify_public_youtube_video(mcp_client, yt_id)
                        if ok:
                            return True, yt_id, f"https://youtu.be/{yt_id}"
                        verification_errors.append(f"{yt_id}: {verification}")
                        if attempt < 5:
                            time.sleep(10)

                return False, "; ".join(verification_errors[-3:]), ""
            finally:
                mcp_client.disconnect()
            
    except Exception as e:
        return False, str(e), ""

def load_queue():
    if not QUEUE_FILE.exists():
        return {"queue": []}
    try:
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"queue": []}


def upload_eligible(item):
    """Only a fully evidenced, content-bound item may reach YouTube."""
    metadata = item.get("youtube_metadata") or {}
    required_metadata = ("title", "description", "tags")
    required_statuses = {
        "technical_verified": True,
        "verified": True,
        "visual_review_status": "approved",
        "semantic_review_status": "approved",
        "metadata_review_status": "approved",
    }
    for field, expected in required_statuses.items():
        if item.get(field) != expected:
            return False, f"{field} is not {expected!r}"
    if not all(metadata.get(field) for field in required_metadata):
        return False, "content-bound Hebrew metadata is missing"
    if not item.get("content_manifest"):
        return False, "content manifest is missing"
    return True, ""


def quarantine_ineligible_unuploaded_items(queue_data):
    changed = False
    for item in queue_data.get("queue", []):
        if item.get("uploaded") or item.get("remotion_status") != "done":
            continue
        eligible, reason = upload_eligible(item)
        if not eligible:
            item["upload_status"] = "quarantined_missing_content_evidence"
            item["last_upload_error"] = reason
            item["verified"] = False
            changed = True
    return changed

def save_queue(q_data):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temporary_file = QUEUE_FILE.with_suffix(".json.tmp")
    temporary_file.write_text(
        json.dumps(q_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary_file, QUEUE_FILE)


def acquire_pipeline_lock():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    handle = RUN_LOCK_FILE.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError("Another Kesher daily pipeline run is already active")
    handle.seek(0)
    handle.truncate()
    handle.write(f"pid={os.getpid()} started_at={datetime.now().isoformat()}\n")
    handle.flush()
    return handle

def main():
    os.environ["PATH"] = "/Users/ninja/.nvm/versions/node/v22.21.1/bin:" + os.environ.get("PATH", "")
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-mode", action="store_true", help="Run in dry run test mode without real generation/upload")
    parser.add_argument("--upload-only", action="store_true", help="Reconcile and upload ready queue items without generating new videos")
    parser.add_argument("--skip-reconcile", action="store_true", help="Skip live YouTube reconciliation before processing the queue")
    args = parser.parse_args()
    pipeline_lock = acquire_pipeline_lock()
    
    print(f"=== Daily YouTube Video Pipeline - {datetime.now().isoformat()} ===")
    
    # 1. Load Queue
    queue_data = load_queue()
    if quarantine_ineligible_unuploaded_items(queue_data):
        print("Quarantined queue items without complete visual, semantic, and metadata evidence.")
        save_queue(queue_data)
    if not args.test_mode and not args.skip_reconcile:
        if reconcile_uploaded_queue(queue_data):
            print("Reconciled deleted or unavailable YouTube items back into the upload queue.")
            save_queue(queue_data)
    
    # 2. Upload Phase: Find ready-to-upload items
    ready_normal = [item for item in queue_data["queue"] if item["type"] == "normal" and not item["uploaded"] and upload_eligible(item)[0]]
    ready_short = [item for item in queue_data["queue"] if item["type"] == "short" and not item["uploaded"] and upload_eligible(item)[0]]
    
    uploaded_items = []
    
    # Upload Normal
    if ready_normal:
        item = ready_normal[0]
        metadata = item.get("youtube_metadata") or {}
        title, description, tags = metadata["title"], metadata["description"], metadata["tags"]
        success, yt_id, yt_url = verify_channel_and_upload(
            Path(item["remotion_mp4_path"]), title, description, tags, is_test=args.test_mode
        )
        if success:
            item["uploaded"] = True
            item["youtube_id"] = yt_id
            item["youtube_url"] = yt_url
            item["uploaded_at"] = datetime.now().isoformat()
            item["upload_status"] = "public_verified"
            item["last_verified_at"] = datetime.now().isoformat()
            item.pop("last_upload_error", None)
            uploaded_items.append(item)
            print(f"Normal video uploaded: {yt_url}")
        else:
            print(f"Failed to upload Normal video: {yt_id}")
            
    # Upload Short
    if ready_short:
        item = ready_short[0]
        metadata = item.get("youtube_metadata") or {}
        title, description, tags = metadata["title"], metadata["description"], metadata["tags"]
        success, yt_id, yt_url = verify_channel_and_upload(
            Path(item["remotion_mp4_path"]), title, description, tags, is_test=args.test_mode
        )
        if success:
            item["uploaded"] = True
            item["youtube_id"] = yt_id
            item["youtube_url"] = yt_url
            item["uploaded_at"] = datetime.now().isoformat()
            item["upload_status"] = "public_verified"
            item["last_verified_at"] = datetime.now().isoformat()
            item.pop("last_upload_error", None)
            uploaded_items.append(item)
            print(f"Short video uploaded: {yt_url}")
        else:
            print(f"Failed to upload Short video: {yt_id}")
            
    save_queue(queue_data)

    if args.upload_only:
        print("Upload-only pipeline execution complete.")
        return
    
    # 3. Generation Phase: If we don't have enough ready items for next run, generate them
    needed_types = []
    # Rejected media is retained for auditability, but must never suppress a
    # replacement generation for its format.
    def is_active_unuploaded(item):
        return (
            not item.get("uploaded", False)
            and not str(item.get("remotion_status", "")).startswith("rejected")
            and item.get("visual_review_status") != "rejected"
        )

    active_normal = [item for item in queue_data["queue"] if item["type"] == "normal" and is_active_unuploaded(item)]
    active_short = [item for item in queue_data["queue"] if item["type"] == "short" and is_active_unuploaded(item)]
    
    if len(active_normal) < 1:
        needed_types.append("normal")
    if len(active_short) < 1:
        needed_types.append("short")
        
    if needed_types:
        print(f"Generating new content. Needed types: {needed_types}")
        
        # Search YouTube for source topics
        queries = ["טיפים לזוגיות", "הדרכת הורים גבולות", "תקשורת זוגית בבית"]
        selected_source = None
        candidates = []
        for q in queries:
            candidates.extend(search_youtube_candidates(q, max_results=3))
            
        client = NotebookLMClient()
        try:
            client.connect()
            
            # Now generate for each needed type
            for t in needed_types:
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                raw_path = OUTPUT_DIR / f"kesher-raw-{t}-{stamp}.mp4"
                remotion_path = REMOTION_OUTPUT_DIR / f"kesher-upgraded-{t}-{stamp}.mp4"
                REMOTION_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                
                duration_prompt = (
                    "זהו סרטון YouTube רגיל ביחס 16:9. אורך הסרטון חייב להיות בין 90 ל-180 שניות."
                    if t == "normal" else
                    "צור מלכתחילה YouTube Short עצמאי ואנכי ביחס 9:16 וברזולוציה אנכית. "
                    "אל תיצור סרטון 16:9 ואל תיצור גרסה ארוכה שאמורה להיחתך לאחר מכן. "
                    "האורך הסופי המלא חייב להיות 35-55 שניות, וכל הקריינות, הסצנות והטקסט המוטמע חייבים להסתיים בתוך משך זה. "
                    "מקם כל טקסט באזור הבטוח המרכזי של מסך 9:16, בשורות קצרות, בלי טקסט שנוגע בשוליים. "
                    "התוכן צריך להיות ממוקד ומהיר: הוק, רעיון אחד, דוגמה אחת וסיום אחד."
                )
                custom_instructions = CONTENT_PROMPT_TEMPLATE + f"\n{duration_prompt}"
                
                if args.test_mode:
                    selected_source = candidates[0] if candidates else {"url": "", "topic": "נושא בדיקה"}
                    print(f"[TEST MODE] Skipping generation/download/remotion steps for {t}.")
                    # Create mock entry
                    queue_data["queue"].append({
                        "id": f"mock-{stamp}-{t}",
                        "type": t,
                        "topic": "נושא בדיקה",
                        "source_url": selected_source["url"],
                        "notebooklm_id": NOTEBOOK_ID,
                        "raw_mp4_path": str(raw_path),
                        "remotion_mp4_path": str(remotion_path),
                        "creation_status": "done",
                        "remotion_status": "done",
                        "verified": True,
                        "uploaded": False,
                        "created_at": datetime.now().isoformat()
                    })
                    continue
                    
                # Real generation
                success = False
                details = ""
                selected_source = None
                attempted_generation_sources = 0
                attempted_urls = set()

                for candidate in candidates:
                    if candidate["url"] in attempted_urls:
                        continue
                    attempted_urls.add(candidate["url"])

                    source_success, source_details = add_source_to_notebooklm(client, candidate["url"])
                    if not source_success:
                        print(f"Failed to add source {candidate['url']}: {source_details}")
                        continue

                    selected_source = candidate
                    attempted_generation_sources += 1
                    print(
                        f"Added source successfully for {t} attempt "
                        f"{attempted_generation_sources}/{MAX_GENERATION_SOURCE_ATTEMPTS}: {candidate['url']}"
                    )

                    success, details = generate_and_download_notebooklm(
                        client, t, custom_instructions, raw_path
                    )
                    if success:
                        break

                    print(
                        f"NotebookLM generation attempt failed for {t} "
                        f"with source {candidate['url']}: {details}"
                    )
                    raw_path.unlink(missing_ok=True)

                    if attempted_generation_sources >= MAX_GENERATION_SOURCE_ATTEMPTS:
                        break

                if attempted_generation_sources == 0:
                    details = "Failed to add any YouTube candidates to NotebookLM."
                
                if success:
                    print(f"NotebookLM generation complete for {t}.")
                    # Run Remotion Upgrade
                    youtube_metadata = details.get("youtube_metadata") or {}
                    rem_success, rem_err = run_remotion_render(raw_path, remotion_path, youtube_metadata, t)
                    if rem_success:
                        verified, verification = verify_rendered_video(remotion_path, t)
                        if not verified:
                            print(f"Rendered {t} video failed verification: {verification}")
                            continue
                        review_path, review_error = create_visual_contact_sheet(remotion_path, t)
                        if not review_path:
                            print(f"Rendered {t} video could not enter visual review: {review_error}")
                            continue
                        queue_data["queue"].append({
                            "id": f"{t}-{stamp}",
                            "type": t,
                            "topic": selected_source["topic"],
                            "source_url": selected_source["url"],
                            "notebooklm_id": NOTEBOOK_ID,
                            "raw_mp4_path": str(raw_path),
                            "remotion_mp4_path": str(remotion_path),
                            "creation_status": "done",
                            "remotion_status": "done",
                            "technical_verified": True,
                            "verified": False,
                            "visual_review_status": "pending",
                            "semantic_review_status": "pending",
                            "metadata_review_status": "pending",
                            "visual_review_path": str(review_path),
                            "visual_review_rules": [
                                "Hebrew visual text only; URL and Shorts are the only Latin exceptions",
                                "No gibberish, presentation slides, information cards, tables, or arrow diagrams",
                                "No cropped text, overlay collisions, black frames, or repeated static layouts",
                                "Normal must feel cinematic; Short must be native 9:16 with all content in the safe area",
                            ],
                            "media": verification,
                            "youtube_metadata": details.get("youtube_metadata"),
                            "content_manifest": {
                                "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                                "rendered_sha256": hashlib.sha256(remotion_path.read_bytes()).hexdigest(),
                                "source_url": selected_source["url"],
                                "topic": selected_source["topic"],
                            },
                            "uploaded": False,
                            "created_at": datetime.now().isoformat()
                        })
                        save_queue(queue_data)
                        print(f"Successfully processed and queue'd {t} video.")
                    else:
                        print(f"Remotion render failed: {rem_err}")
                else:
                    print(f"NotebookLM generation failed for {t}: {details}")
                    
        finally:
            client.disconnect()
            
    save_queue(queue_data)
    print("Pipeline execution complete.")
    
    # 4. Report in Hebrew
    for item in uploaded_items:
        print(f"\n--- סרטון הועלה בהצלחה! ---")
        print(f"כותרת: {item.get('topic')}")
        print(f"קישור: {item.get('youtube_url')}")
        print(f"סוג: {item.get('type')}")
        print(f"סטטוס: Public")
        print(f"נוצר בעברית מלכתחילה: כן")

if __name__ == "__main__":
    main()

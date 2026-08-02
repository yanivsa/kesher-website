import os
import re
import json
import time
import shutil
import subprocess
import urllib.request
import urllib.parse
import contextlib
import select
import socket
import requests
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path('/Users/ninja/Documents/Kesher')
REMOTION_DIR = PROJECT_DIR / 'remotion-kesher'
SITE_URL = 'https://kesher.saharoni.com'
YOUTUBE_CHANNEL_ID = 'UCx5fEFvdVf28HLAR2dFW64Q'
COMPOSIO_CONNECTED_ACCOUNT = 'youtube_ransom-winish'

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




def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]




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




def iter_nested_values(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from iter_nested_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_nested_values(child)
    else:
        yield value




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




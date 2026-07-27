#!/usr/bin/env python3
import os
import sys
import time
import json
import subprocess
import socket
from pathlib import Path

# We can import requests or use urllib

REMOTION_OUTPUT_DIR = Path("/Users/ninja/Documents/Kesher/remotion-output")

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def main():
    if len(sys.argv) < 5:
        print("Usage: upload_via_localtunnel.py <file_name> <title> <description_file> <tags_json>")
        sys.exit(1)
        
    file_name = sys.argv[1]
    title = sys.argv[2]
    desc_file = sys.argv[3]
    tags_json = sys.argv[4]
    
    video_path = REMOTION_OUTPUT_DIR / file_name
    if not video_path.exists():
        print(f"Error: {video_path} does not exist.")
        sys.exit(1)
        
    description = Path(desc_file).read_text(encoding="utf-8")
    tags = json.loads(tags_json)
    
    port = find_free_port()
    print(f"Starting local HTTP server on port {port}...")
    
    # Start HTTP server serving the remotion-output folder
    http_proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port)],
        cwd=str(REMOTION_OUTPUT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    lt_proc = None
    try:
        print("Starting localtunnel...")
        lt_proc = subprocess.Popen(
            ["npx", "localtunnel", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Read localtunnel URL from stdout
        url = None
        start_time = time.time()
        while time.time() - start_time < 30:
            line = lt_proc.stdout.readline()
            if "your url is" in line:
                url = line.split("your url is:")[-1].strip()
                break
            time.sleep(0.5)
            
        if not url:
            raise RuntimeError("Failed to get localtunnel URL.")
            
        print(f"Localtunnel is live at: {url}")
        download_url = f"{url}/{file_name}"
        print(f"Sandbox download URL: {download_url}")
        
        # Now prepare python code to run in Composio Workbench
        workbench_code = f'''
import urllib.request
import json
import sys

download_url = "{download_url}"
local_path = "/tmp/{file_name}"

print("Step 1: Downloading video inside sandbox...")
req = urllib.request.Request(download_url, headers={{"User-Agent": "Mozilla/5.0"}})
with urllib.request.urlopen(req, timeout=180) as response:
    with open(local_path, "wb") as f:
        f.write(response.read())

print("Downloaded successfully, size:", os.path.getsize(local_path))

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
        
        # Save workbench code to a temp file in the scratch dir
        scratch_dir = Path("/Users/ninja/.gemini/antigravity/brain/3bc5ffd9-8a55-4da4-8580-1762b8abeb20/scratch")
        scratch_dir.mkdir(parents=True, exist_ok=True)
        code_file = scratch_dir / "workbench_upload_code.py"
        code_file.write_text(workbench_code, encoding="utf-8")
        print(f"Workbench code staged. Exiting to let parent execute via MCP.")
        
    finally:
        # We don't terminate yet, the parent needs the tunnel to stay open.
        # We'll print the PID and port, and the parent can kill them after executing the MCP tool.
        print(f"PIDS: {http_proc.pid},{lt_proc.pid if lt_proc else 0}")
        
if __name__ == "__main__":
    main()

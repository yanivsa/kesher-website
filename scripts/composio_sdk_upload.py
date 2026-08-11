import sys
import json
import os
import traceback

# Bypass cache refresh that hits deprecated v1 endpoints
os.environ["COMPOSIO_NO_CACHE_REFRESH"] = "true"

from composio import ComposioToolSet, Action, App

api_key = os.environ.get("COMPOSIO_API_KEY")
if not api_key:
    print("Error: COMPOSIO_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)
video_path = "/Users/ninja/Documents/Kesher/output/test_video.mp4"
metadata_path = "/Users/ninja/Documents/Kesher/output/metadata_06r1-_wBFDo_איך_מגיעים_לשיח_רגשי_בזוגיות.json"

# Load metadata
with open(metadata_path, 'r', encoding='utf-8') as f:
    meta = json.load(f)

yt_meta = meta.get("youtube_metadata", {})
title = yt_meta.get("titles", ["שיח רגשי בזוגיות"])[0]
description = yt_meta.get("description", "סרטון בדיקה")
tags = yt_meta.get("tags", ["זוגיות", "ייעוץ זוגי"])

print("Initializing ComposioToolSet...")
toolset = ComposioToolSet(api_key=api_key)

print(f"Uploading video: {video_path}")
print(f"Title: {title}")

try:
    # Execute action
    result = toolset.execute_action(
        action=Action.YOUTUBE_UPLOAD_VIDEO,
        params={
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22",
            "privacyStatus": "private",
            "videoFilePath": video_path
        }
    )
    print("\nSUCCESS!")
    print(json.dumps(result, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"\n[ERROR] Upload failed: {e}")
    traceback.print_exc()

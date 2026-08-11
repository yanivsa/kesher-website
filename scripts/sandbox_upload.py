import sys
import os
import hashlib
import requests
import json
from composio import Composio

# 1. Initialize Composio client with the user's ck_ key
api_key = os.environ.get("COMPOSIO_API_KEY")
if not api_key:
    print("Error: COMPOSIO_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)
print("Initializing Composio Client with user key...")
c = Composio(api_key=api_key)

# 2. Get file details
file_path = "/tmp/test_video.mp4"
filename = "test_video.mp4"
mimetype = "video/mp4"

print(f"Reading file: {file_path}")
with open(file_path, "rb") as f:
    file_bytes = f.read()

md5_hash = hashlib.md5(file_bytes).hexdigest()
print(f"File MD5: {md5_hash}")

# 3. Create presigned upload URL
print("Creating presigned S3 upload URL...")
try:
    resp = c.client.files.create_presigned_url(
        filename=filename,
        md5=md5_hash,
        mimetype=mimetype,
        tool_slug="YOUTUBE_UPLOAD_VIDEO",
        toolkit_slug="YOUTUBE"
    )
except Exception as e:
    print(f"Failed to create presigned URL: {e}")
    # Let's also try to print request/response headers or details if we can
    raise e

# 4. Upload file to S3 if not exists
if not resp.exists:
    print(f"Uploading file to S3: {resp.url[:100]}...")
    upload_resp = requests.put(resp.url, data=file_bytes)
    print("S3 Upload status:", upload_resp.status_code)
else:
    print("File already exists in S3, skipping upload.")

print("S3 Key:", resp.key)

# 5. Define upload metadata
title = "למה בעלך לא משתף אותך? (הטעות שנשים עושות בלי לשים לב)"
description = """האם את מרגישה שבעלך נעול כמו קיר ולא משתף אותך ברגשות שלו? 
בסרטון זה נחשוף את שורש הבעיה לפי מחקריה של ברנה בראון, נציג מקרה קלאסי של התנגשות תקשורתית בין בני זוג, ונלמד אתכם 3 כלים מעשיים ליצירת מרחב בטוח שיאפשר לבן הזוג להיפתח ולשתף מבלי לפחד מביקורת.

לתיאום שיחת ייעוץ אישית/זוגית ומאמרים נוספים:
בקרו באתר של 'קשר - ייעוץ זוגי ומשפחתי': https://kesher.saharoni.com

אם מצאתם ערך בסרטון, אל תשכחו לעשות לייק, להירשם לערוץ ולשתף אותו!"""

tags = [
    "תקשורת בזוגיות",
    "שיח רגשי",
    "ייעוץ זוגי",
    "טיפול זוגי",
    "למה הוא לא מדבר",
    "איך לגרום לגבר להיפתח",
    "ברנה בראון",
    "שלום בית",
    "קשר ייעוץ זוגי",
    "פגיעות בזוגיות",
    "הקשבה ללא שיפוטיות",
    "בעיות זוגיות",
    "חיבור רגשי",
    "ייעוץ משפחתי",
    "תקשורת מקרבת"
]

print("Executing YouTube Video Upload Action...")
# We use the specific connected account for 'kesher'
execute_resp = c.client.tools.execute(
    tool_slug="YOUTUBE_UPLOAD_VIDEO",
    connected_account_id="youtube_ransom-winish",  # from tool search connection status
    arguments={
        "title": title,
        "description": description,
        "tags": tags,
        "categoryId": "22",
        "privacyStatus": "public",  # the user requested to upload it to youtube
        "videoFilePath": {
            "name": filename,
            "mimetype": mimetype,
            "s3key": resp.key
        }
    }
)

print("\n--- EXECUTION RESPONSE ---")
print(json.dumps(execute_resp, indent=2, default=str))

# Print YouTube URL
video_id = None
if isinstance(execute_resp, dict):
    video_id = execute_resp.get("video", {}).get("id") or execute_resp.get("data", {}).get("video", {}).get("id")
elif hasattr(execute_resp, "video"):
    video_id = getattr(execute_resp.video, "id", None)
elif hasattr(execute_resp, "data"):
    data = getattr(execute_resp, "data", {})
    if isinstance(data, dict):
        video_id = data.get("video", {}).get("id")

if video_id:
    print(f"\nSUCCESS! Video URL: https://www.youtube.com/watch?v={video_id}")
else:
    print("Could not parse video ID programmatically.")

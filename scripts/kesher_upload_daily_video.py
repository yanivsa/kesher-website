#!/usr/bin/env python3
import os
import sys
import hashlib
import json
from pathlib import Path

import requests
from composio import Action, App, Composio


API_KEY = os.environ.get("COMPOSIO_API_KEY")
if not API_KEY:
    print("Error: COMPOSIO_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)
CONNECTED_ACCOUNT_ID = "youtube_ransom-winish"
VIDEO_PATH = Path("/Users/ninja/Documents/Kesher/dub-output/kesher-daily-20260706-hebrew-dubbed.mp4")
RESULT_PATH = Path("/Users/ninja/Documents/Kesher/notebooklm-output/kesher-daily-20260706-youtube-upload.json")

TITLE = "מלכודת המתקן: למה עזרה פוגעת בזוגיות?"
DESCRIPTION = """לפעמים אנחנו מנסים לעזור לבן או בת הזוג מהר מדי, ודווקא שם הקשר נסגר.

בסרטון הזה נראה דרך סיפור קצר איך עצות טובות יכולות להישמע כמו ביקורת, למה הקשבה רגועה חשובה לפני פתרונות, ואיך אפשר ליצור בבית מרחב רגשי בטוח יותר.

למידע נוסף ותיאום פגישה:
https://kesher.saharoni.com

קשר - ייעוץ זוגי ומשפחתי

#ייעוץזוגי #הדרכתהורים #הנחייתהורים #הורות #זוגיות #תקשורתזוגית #גבולות #ויסותרגשי #משפחה #אשדוד #שירהסהרוני"""

TAGS = [
    "ייעוץ זוגי",
    "הדרכת הורים",
    "הנחיית הורים",
    "הורות",
    "זוגיות",
    "תקשורת זוגית",
    "גבולות",
    "ויסות רגשי",
    "משפחה",
    "אשדוד",
    "שירה סהרוני",
    "קשר ייעוץ זוגי ומשפחתי",
    "הקשבה בזוגיות",
    "מרחב רגשי",
    "תקשורת מקרבת",
]


def as_jsonable(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [as_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: as_jsonable(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return as_jsonable(value.model_dump())
    if hasattr(value, "__dict__"):
        return as_jsonable(value.__dict__)
    return str(value)


def main():
    client = Composio(api_key=API_KEY)
    video_bytes = VIDEO_PATH.read_bytes()
    md5_hash = hashlib.md5(video_bytes).hexdigest()

    presigned = client.actions.create_file_upload(
        app="YOUTUBE",
        action="YOUTUBE_UPLOAD_VIDEO",
        filename=VIDEO_PATH.name,
        md5=md5_hash,
        mimetype="video/mp4",
    )
    if not presigned.exists:
        upload_response = requests.put(presigned.url, data=video_bytes, timeout=300)
        upload_response.raise_for_status()

    result = client.actions.execute(
        action=Action.YOUTUBE_UPLOAD_VIDEO,
        connected_account=CONNECTED_ACCOUNT_ID,
        params={
            "title": TITLE,
            "description": DESCRIPTION,
            "tags": TAGS,
            "categoryId": "22",
            "privacyStatus": "public",
            "videoFilePath": {
                "name": VIDEO_PATH.name,
                "mimetype": "video/mp4",
                "s3key": presigned.s3key,
            },
        },
    )
    payload = {
        "video_path": str(VIDEO_PATH),
        "title": TITLE,
        "description": DESCRIPTION,
        "tags": TAGS,
        "privacyStatus": "public",
        "connected_account_id": CONNECTED_ACCOUNT_ID,
        "presigned_key": presigned.s3key,
        "result": as_jsonable(result),
    }
    RESULT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

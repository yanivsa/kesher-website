#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

import requests


API_KEY = "ck_-hh6vYTdFqm5Mt_vvIDp"
BASE_URLS = [
    "https://backend.composio.dev",
    "https://api.composio.dev",
]
CONNECTED_ACCOUNT_ID = "youtube_ransom-winish"
VIDEO_PATH = Path("/Users/ninja/Documents/Kesher/dub-output/kesher-daily-20260706-hebrew-dubbed.mp4")
RESULT_PATH = Path("/Users/ninja/Documents/Kesher/notebooklm-output/kesher-daily-20260706-youtube-upload-v31.json")

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


def post_json(base_url, path, body):
    response = requests.post(
        f"{base_url}{path}",
        headers={"x-api-key": API_KEY, "Content-Type": "application/json"},
        json=body,
        timeout=120,
    )
    return response


def main():
    data = VIDEO_PATH.read_bytes()
    md5 = hashlib.md5(data).hexdigest()
    upload_body = {
        "toolkit_slug": "youtube",
        "tool_slug": "YOUTUBE_MULTIPART_UPLOAD_VIDEO",
        "filename": VIDEO_PATH.name,
        "mimetype": "video/mp4",
        "md5": md5,
    }
    last_error = None
    for base_url in BASE_URLS:
        response = post_json(base_url, "/api/v3.1/files/upload/request", upload_body)
        print("upload_request", base_url, response.status_code, response.text[:1000])
        if response.ok:
            upload = response.json()
            break
        last_error = response.text
    else:
        raise RuntimeError(f"upload request failed: {last_error}")

    presigned_url = upload.get("new_presigned_url") or upload.get("newPresignedUrl") or upload.get("url")
    key = upload.get("key") or upload.get("s3key")
    if not presigned_url or not key:
        raise RuntimeError(f"unexpected upload response: {upload}")

    if upload.get("type") != "existing":
        put = requests.put(presigned_url, data=data, headers={"Content-Type": "video/mp4"}, timeout=300)
        print("s3_put", put.status_code, put.text[:500])
        put.raise_for_status()

    execute_body = {
        "connected_account_id": CONNECTED_ACCOUNT_ID,
        "arguments": {
            "title": TITLE,
            "description": DESCRIPTION,
            "tags": TAGS,
            "categoryId": "22",
            "privacyStatus": "public",
            "videoFile": {
                "name": VIDEO_PATH.name,
                "mimetype": "video/mp4",
                "s3key": key,
            },
        },
    }
    execute = post_json(base_url, "/api/v3.1/tools/execute/YOUTUBE_MULTIPART_UPLOAD_VIDEO", execute_body)
    print("execute", execute.status_code, execute.text[:4000])
    payload = {
        "base_url": base_url,
        "upload": upload,
        "execute_status": execute.status_code,
        "execute_body": execute.text,
        "title": TITLE,
        "description": DESCRIPTION,
        "privacyStatus": "public",
    }
    RESULT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    execute.raise_for_status()


if __name__ == "__main__":
    main()

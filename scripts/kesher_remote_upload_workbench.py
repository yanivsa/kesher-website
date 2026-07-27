#!/usr/bin/env python3
import json
import sys

sys.path.append("scripts")
from composio_mcp_client import ComposioMCPClient


TMP_URL = "https://tmpfiles.org/dl/wwwtv9oG3Pr2/kesher-daily-20260706-hebrew-dubbed.mp4"

code = f'''
import json, os, urllib.request

tmp_url = "{TMP_URL}"
local_path = "/tmp/kesher-daily-20260706-hebrew-dubbed.mp4"
req = urllib.request.Request(tmp_url, headers={{"User-Agent": "Mozilla/5.0"}})
with urllib.request.urlopen(req, timeout=120) as response:
    with open(local_path, "wb") as f:
        f.write(response.read())

print("downloaded", local_path, os.path.getsize(local_path))
uploaded, upload_err = upload_local_file(local_path)
if upload_err:
    print("upload_local_file error", upload_err)
else:
    print("uploaded", json.dumps(uploaded, ensure_ascii=False))
    title = "מלכודת המתקן: למה עזרה פוגעת בזוגיות?"
    description = """לפעמים אנחנו מנסים לעזור לבן או בת הזוג מהר מדי, ודווקא שם הקשר נסגר.

בסרטון הזה נראה דרך סיפור קצר איך עצות טובות יכולות להישמע כמו ביקורת, למה הקשבה רגועה חשובה לפני פתרונות, ואיך אפשר ליצור בבית מרחב רגשי בטוח יותר.

למידע נוסף ותיאום פגישה:
https://kesher.saharoni.com

קשר - ייעוץ זוגי ומשפחתי

#ייעוץזוגי #הדרכתהורים #הנחייתהורים #הורות #זוגיות #תקשורתזוגית #גבולות #ויסותרגשי #משפחה #אשדוד #שירהסהרוני"""
    tags = [
        "ייעוץ זוגי", "הדרכת הורים", "הנחיית הורים", "הורות", "זוגיות",
        "תקשורת זוגית", "גבולות", "ויסות רגשי", "משפחה", "אשדוד",
        "שירה סהרוני", "קשר ייעוץ זוגי ומשפחתי", "הקשבה בזוגיות",
        "מרחב רגשי", "תקשורת מקרבת"
    ]
    video_file = {{
        "name": "kesher-daily-20260706-hebrew-dubbed.mp4",
        "mimetype": "video/mp4",
        "s3key": uploaded["s3key"],
    }}
    result, err = run_composio_tool("YOUTUBE_MULTIPART_UPLOAD_VIDEO", {{
        "title": title,
        "description": description,
        "tags": tags,
        "categoryId": "22",
        "privacyStatus": "public",
        "videoFile": video_file,
    }}, account="kesher")
    print("youtube_err", err)
    print("youtube_result", json.dumps(result, ensure_ascii=False))
'''


def main():
    client = ComposioMCPClient()
    try:
        client.connect()
        result = client.call_tool(
            "COMPOSIO_REMOTE_WORKBENCH",
            {
                "code_to_execute": code,
                "sync_response_to_workbench": False,
            },
            timeout=190,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()

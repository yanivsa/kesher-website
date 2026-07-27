#!/usr/bin/env python3
import argparse
import json
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


EXPECTED_CHANNEL_ID = "UCx5fEFvdVf28HLAR2dFW64Q"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
SCRIPT_DIR = Path(__file__).resolve().parent
TOKEN_PATH = SCRIPT_DIR / "token-kesher-youtube.pickle"
CLIENT_SECRETS_PATH = SCRIPT_DIR / "client_secrets.json"


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


def load_credentials():
    credentials = None
    if TOKEN_PATH.exists():
        with TOKEN_PATH.open("rb") as token_file:
            credentials = pickle.load(token_file)

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        if not CLIENT_SECRETS_PATH.exists():
            raise FileNotFoundError(
                f"Missing OAuth client secrets: {CLIENT_SECRETS_PATH}. "
                "Create a Desktop OAuth client in Google Cloud, enable YouTube Data API v3, "
                "and save it there for the one-time authorization."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_PATH), SCOPES)
        credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        with TOKEN_PATH.open("wb") as token_file:
            pickle.dump(credentials, token_file)

    return credentials


def build_youtube():
    return build("youtube", "v3", credentials=load_credentials())


def get_own_channel(youtube):
    response = youtube.channels().list(part="id,snippet", mine=True).execute()
    items = response.get("items", [])
    if len(items) != 1:
        raise RuntimeError(f"Expected exactly one authenticated channel, got {len(items)}: {response}")
    return items[0]


def assert_kesher_channel(youtube):
    channel = get_own_channel(youtube)
    channel_id = channel.get("id")
    title = channel.get("snippet", {}).get("title")
    if channel_id != EXPECTED_CHANNEL_ID:
        raise RuntimeError(
            f"Refusing upload: authenticated YouTube channel is {channel_id!r} ({title!r}), "
            f"expected {EXPECTED_CHANNEL_ID!r}."
        )
    return channel


def upload_video(youtube, video_path, privacy_status):
    body = {
        "snippet": {
            "title": TITLE,
            "description": DESCRIPTION,
            "tags": TAGS,
            "categoryId": "22",
            "defaultLanguage": "he",
            "defaultAudioLanguage": "he",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), chunksize=1024 * 1024, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"upload_progress={int(status.progress() * 100)}")
    return response


def get_video_details(youtube, video_id):
    return youtube.videos().list(part="snippet,status,processingDetails", id=video_id).execute()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--video",
        default="/Users/ninja/Documents/Kesher/dub-output/kesher-daily-20260706-hebrew-dubbed.mp4",
    )
    parser.add_argument("--privacy", default="public", choices=["public", "private", "unlisted"])
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--result",
        default="/Users/ninja/Documents/Kesher/notebooklm-output/kesher-daily-20260706-youtube-direct-upload.json",
    )
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists() or video_path.stat().st_size == 0:
        raise FileNotFoundError(f"Video file missing or empty: {video_path}")

    youtube = build_youtube()
    channel = assert_kesher_channel(youtube)
    print(f"authenticated_channel={channel['id']} title={channel.get('snippet', {}).get('title')}")

    result = {
        "channel": channel,
        "video_path": str(video_path),
        "privacy": args.privacy,
        "title": TITLE,
        "description": DESCRIPTION,
        "tags": TAGS,
    }

    if not args.preflight_only:
        upload_response = upload_video(youtube, video_path, args.privacy)
        video_id = upload_response["id"]
        details = get_video_details(youtube, video_id)
        result.update(
            {
                "upload_response": upload_response,
                "video_id": video_id,
                "url": f"https://youtu.be/{video_id}",
                "details": details,
            }
        )

    Path(args.result).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

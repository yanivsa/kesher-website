#!/usr/bin/env python3
import sys
import pickle
from pathlib import Path
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl"
]
SCRIPT_DIR = Path(__file__).resolve().parent
TOKEN_PATH = SCRIPT_DIR / "token-kesher-youtube.pickle"
CLIENT_SECRETS_PATH = SCRIPT_DIR / "client_secrets.json"
EXPECTED_CHANNEL_ID = "UCx5fEFvdVf28HLAR2dFW64Q"

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
                "Please configure OAuth credentials first."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_PATH), SCOPES)
        # Using local server flow
        credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        with TOKEN_PATH.open("wb") as token_file:
            pickle.dump(credentials, token_file)

    return credentials

def main():
    try:
        credentials = load_credentials()
    except Exception as e:
        print(f"Error loading credentials: {e}")
        print("Please run this script in an interactive terminal to authenticate first.")
        sys.exit(1)
        
    youtube = build("youtube", "v3", credentials=credentials)
    
    # Verify channel ID
    channels_response = youtube.channels().list(part="id,snippet", mine=True).execute()
    items = channels_response.get("items", [])
    if not items:
        print("No authenticated channel found.")
        sys.exit(1)
        
    channel_id = items[0]["id"]
    print(f"Connected Channel: {channel_id} ({items[0]['snippet']['title']})")
    
    if channel_id != EXPECTED_CHANNEL_ID:
        print(f"Error: Connected channel is not the expected Kesher channel ({EXPECTED_CHANNEL_ID}).")
        sys.exit(1)
        
    # List channel's uploaded videos (using the uploads playlist)
    uploads_playlist_id = "UUx5fEFvdVf28HLAR2dFW64Q"
    print("Fetching uploaded videos...")
    
    video_ids = []
    next_page_token = None
    while True:
        playlist_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()
        
        for item in playlist_response.get("items", []):
            snippet = item.get("snippet", {})
            title = snippet.get("title")
            video_id = snippet.get("resourceId", {}).get("videoId")
            if video_id and title != "Deleted video":
                video_ids.append(video_id)
                
        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break
            
    print(f"Found {len(video_ids)} active videos. Inspecting metadata...")
    
    # Process videos in batches of 50
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        videos_response = youtube.videos().list(
            part="snippet,localizations",
            id=",".join(batch)
        ).execute()
        
        for video in videos_response.get("items", []):
            video_id = video["id"]
            snippet = video.get("snippet", {})
            localizations = video.get("localizations", {})
            title = snippet.get("title")
            
            # Check if there are English translations or if default language is not set to iw/he
            has_english = "en" in localizations or "en-US" in localizations or "en-GB" in localizations
            default_lang = snippet.get("defaultLanguage")
            default_audio_lang = snippet.get("defaultAudioLanguage")
            
            needs_update = False
            
            # Ensure default languages are set to Hebrew (iw)
            if default_lang != "iw":
                snippet["defaultLanguage"] = "iw"
                needs_update = True
            if default_audio_lang != "iw":
                snippet["defaultAudioLanguage"] = "iw"
                needs_update = True
                
            # If there is any English localization, overwrite it with Hebrew or remove it
            if has_english:
                print(f"Video '{title}' ({video_id}) has English localizations. Fixing...")
                # We can replace all english localizations with Hebrew text so it always shows Hebrew
                he_title = title
                he_desc = snippet.get("description", "")
                
                for lang in list(localizations.keys()):
                    if lang.startswith("en"):
                        localizations[lang] = {
                            "title": he_title,
                            "description": he_desc
                        }
                needs_update = True
                
            if needs_update:
                print(f"Updating metadata for video '{title}' ({video_id})...")
                # Update the video resource
                try:
                    update_body = {
                        "id": video_id,
                        "snippet": {
                            "title": title,
                            "description": snippet.get("description", ""),
                            "tags": snippet.get("tags", []),
                            "categoryId": snippet.get("categoryId", "22"),
                            "defaultLanguage": snippet.get("defaultLanguage", "iw"),
                            "defaultAudioLanguage": snippet.get("defaultAudioLanguage", "iw")
                        },
                        "localizations": localizations
                    }
                    youtube.videos().update(
                        part="snippet,localizations",
                        body=update_body
                    ).execute()
                    print(f"Successfully fixed '{title}' ({video_id})")
                except Exception as ex:
                    print(f"Error updating video {video_id}: {ex}")

if __name__ == "__main__":
    main()

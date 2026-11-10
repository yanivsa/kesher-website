#!/usr/bin/env python3
"""Safe read-only KESHER OAuth probe. Never uploads or alters a YouTube video."""
from __future__ import annotations
import argparse
import json
import os
import hashlib
import re
from scripts.kesher_owner_vantage_short import youtube_client

SLUG = "positivity-resonance-marriage-micro-moments"
SHA = "6bb5723bbadc7b78725e4cdb477857e7194cca47c1140f27d1c4f3921b6e2d5f"
CHANNEL = "UCx5fEFvdVf28HLAR2dFW64Q"
MIDYEAR_SLUG = "changing-kindergarten-midyear"
MIDYEAR_SHA = "5b0d6c5e8ba2c7fb001d1b7944a4abca1dbe4d5b0248889466dca4225e393a1a"
MIDYEAR_TITLE = "מעבר גן באמצע שנה: איך לעזור לילד להיפרד ולהתחיל מחדש?"
KIND_MARKERS = {"overview": "owner-overview-20261110-6bb5723bbadc",
                "short": "owner-short-20261110-6bb5723bbadc"}

def find_all_exact(youtube, playlist):
    """Enumerate the upload playlist completely; never guess an absent video."""
    token = None
    seen_tokens = set()
    ids = []
    while True:
        page = youtube.playlistItems().list(part="contentDetails", playlistId=playlist,
                                            maxResults=50, pageToken=token).execute()
        ids.extend(row["contentDetails"]["videoId"] for row in page.get("items", []))
        next_token = page.get("nextPageToken")
        if not next_token:
            break
        if next_token in seen_tokens or len(seen_tokens) > 200:
            raise RuntimeError("DUPLICATE_SCAN_INCOMPLETE")
        seen_tokens.add(next_token)
        token = next_token
    matches = {k: [] for k in KIND_MARKERS}
    for i in range(0, len(ids), 50):
        video_data = youtube.videos().list(part="snippet,status,processingDetails",
                                           id=",".join(ids[i:i+50])).execute()
        for record in video_data.get("items", []):
            snip = record.get("snippet") or {}
            if snip.get("channelId") != CHANNEL:
                raise RuntimeError("UNEXPECTED_CHANNEL")
            desc = str(snip.get("description") or "")
            if "source_slug="+SLUG not in desc or "content_sha256="+SHA not in desc:
                continue
            for kind, ident in KIND_MARKERS.items():
                if "KESHER_OWNER_MEDIA_ITEM="+ident in desc:
                    matches[kind].append({"id":record["id"],"privacy":(record.get("status") or {}).get("privacyStatus"),
                                           "processing":(record.get("processingDetails") or {}).get("processingStatus")})
    if any(len(rows)>1 for rows in matches.values()):
        raise RuntimeError("DUPLICATE_SOURCE_VIDEO_IDENTITY")
    return {"uploaded_video_count":len(ids),"exact_matches":matches}

def midyear_candidates(records):
    """Return only relevant existing records; never expose nonpublic video IDs."""
    candidates = []
    for row in records:
        snip = row.get("snippet") or {}
        if snip.get("channelId") != CHANNEL:
            raise RuntimeError("UNEXPECTED_CHANNEL")
        desc = str(snip.get("description") or "")
        title = str(snip.get("title") or "")
        normalized = re.sub(r"[^\w\s]", " ", title)
        normalized = " ".join(normalized.split())
        title_match = bool(re.search(r"מעבר (?:ל)?גן באמצע (?:ה)?שנה", normalized))
        if MIDYEAR_SLUG not in desc and MIDYEAR_SHA not in desc and not title_match and title != MIDYEAR_TITLE:
            continue
        privacy = (row.get("status") or {}).get("privacyStatus")
        vid = row["id"]
        candidates.append({"privacy": privacy, "title": title if privacy == "public" else None,
                           "public_id": vid if privacy == "public" else None,
                           "id_fingerprint": hashlib.sha256(vid.encode()).hexdigest()[:12]})
    return candidates


def find_midyear_candidates(youtube, playlist):
    """Use the reviewed publisher's fail-closed complete read-only scan."""
    from scripts.kesher_owner_reviewed_publish import deleted_upload_marker, scan_video_records
    token, seen_tokens, ids, deleted_candidates = None, set(), [], set()
    while True:
        page = youtube.playlistItems().list(part="snippet,contentDetails,status",
                                            playlistId=playlist, maxResults=50,
                                            pageToken=token).execute()
        for row in page.get("items", []):
            vid = row["contentDetails"]["videoId"]
            ids.append(vid)
            if deleted_upload_marker(row, playlist):
                deleted_candidates.add(vid)
        token = page.get("nextPageToken")
        if not token:
            break
        if token in seen_tokens or len(seen_tokens) >= 200:
            raise RuntimeError("DUPLICATE_SCAN_INCOMPLETE")
        seen_tokens.add(token)
    records = scan_video_records(youtube, ids, deleted_candidates, playlist)
    return {"source_slug": MIDYEAR_SLUG, "content_sha256": MIDYEAR_SHA,
            "uploaded_video_count": len(ids), "resolved_video_count": len(records),
            "candidates": midyear_candidates(records)}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--slug",required=True)
    ap.add_argument("--source-sha",required=True)
    args=ap.parse_args()
    if (args.slug, args.source_sha) not in {(SLUG, SHA), (MIDYEAR_SLUG, MIDYEAR_SHA)}:
        raise SystemExit("EXACT_USER_APPROVED_SOURCE_REQUIRED")
    yt=youtube_client()
    rows=yt.channels().list(part="id,contentDetails",mine=True).execute().get("items",[])
    if len(rows)!=1 or rows[0].get("id")!=CHANNEL:
        raise RuntimeError("YOUTUBE_ACCOUNT_WRONG_CHANNEL")
    uploads=rows[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    result=(find_all_exact(yt,uploads) if args.slug == SLUG else find_midyear_candidates(yt,uploads))
    print("KESHER_SOURCE_YOUTUBE_READ_ONLY_PREFLIGHT "+json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)
    print("NO_YOUTUBE_MUTATION_PERFORMED",flush=True)

if __name__=="__main__":
    main()

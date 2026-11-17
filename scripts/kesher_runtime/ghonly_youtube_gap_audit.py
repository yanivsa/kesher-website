"""Audited read-only YouTube channel reconciliation for six KESHER media gaps.

This cannot create articles, generate NotebookLM items, upload to YouTube, or
authorize a GH-only owner. A missing exact YouTube description marker is NOT
proof an external task is absent. Owner-approved source identities are from
the original persisted GitHub controller artifacts (Issue #1210).

Run ONLY from existing kesher-daily-video.yml operation=preflight on main.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from scripts.kesher_owner_vantage_short import youtube_client

CHANNEL = "UCx5fEFvdVf28HLAR2dFW64Q"
TARGETS = (
    ("2026-11-09", "self-distancing-couple-arguments",
     "9b9c06cb05d5e33f4117c2798d7decede0dab2d1f7c7a483d69218c198cbc5d2"),
    ("2026-11-10", "transition-to-separate-room",
     "4751cfeae272ce8d42e8311236d3bbacf44e94cd99b571db6b8544b103bfe8d0"),
    ("2026-11-11", "gratitude-relationship-genuine-thank-you",
     "d4921756c12061359fca7cefea175387b534735d1af841a59e46a392edcc8c5f"),
    ("2026-11-12", "invisible-support-couples-responsive-help",
     "c612b113ea3939a9ca60beb2e88d87e7b639c563e5469ae72715b05cf54a3ea6"),
    ("2026-11-13", "tiger-parenting-myth-vs-supportive-parenting",
     "1433affd3b6b0d715145ef26ff2f27792aa98e788d5d7a07df52e57d1bc45eb8"),
    ("2026-11-16", "child-led-play-10-minutes-connection",
     "36c1d366485db4908dfaf34139c73457307c0562b0e3fd7d52eab347a80a1c2c"),
)

class IncompleteYouTubeInventory(ValueError):
    pass


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _is_deleted_upload_marker(row, playlist):
    """Only the exact authenticated YouTube deleted-upload tombstone counts."""
    import re

    snippet = row.get("snippet") or {}
    resource = snippet.get("resourceId") or {}
    video_id = (row.get("contentDetails") or {}).get("videoId")
    return (
        isinstance(video_id, str)
        and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) is not None
        and snippet.get("channelId") == CHANNEL
        and snippet.get("playlistId") == playlist
        and resource.get("kind") == "youtube#video"
        and resource.get("videoId") == video_id
        and snippet.get("title") == "Deleted video"
        and not snippet.get("videoOwnerChannelId")
        and (row.get("status") or {}).get("privacyStatus") == "privacyStatusUnspecified"
    )


def _confirm_deleted_upload(youtube, playlist, video_id):
    """Independent exact-video 404 reason is mandatory; no guessed deletion."""
    try:
        youtube.playlistItems().list(
            part="snippet,contentDetails,status",
            playlistId=playlist, videoId=video_id, maxResults=1,
        ).execute()
    except Exception as exc:
        if getattr(getattr(exc, "resp", None), "status", None) != 404:
            return False
        try:
            error = json.loads(exc.content)["error"]
            return error.get("code") == 404 and any(
                r.get("reason") == "videoNotFound"
                and r.get("domain") == "youtube.playlistItem"
                and r.get("location") == "videoId"
                for r in error.get("errors", [])
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            return False
    return False


def _complete_upload_list(youtube, playlist: str):
    ids = []
    deleted_candidates = set()
    token = None
    seen = set()
    while True:
        page = youtube.playlistItems().list(
            part="snippet,contentDetails,status", playlistId=playlist, maxResults=50,
            **({"pageToken": token} if token else {}),
        ).execute()
        if not isinstance(page, dict) or not isinstance(page.get("items"), list):
            raise IncompleteYouTubeInventory("UNTRUSTED_UPLOAD_PLAYLIST_PAGE")
        for item in page["items"]:
            vid = (item.get("contentDetails") or {}).get("videoId")
            if not isinstance(vid, str) or not vid:
                raise IncompleteYouTubeInventory("UNTRUSTED_UPLOAD_VIDEO_ID")
            ids.append(vid)
            if _is_deleted_upload_marker(item, playlist):
                deleted_candidates.add(vid)
        new = page.get("nextPageToken")
        if new is not None and (not isinstance(new, str) or not new):
            raise IncompleteYouTubeInventory("UNTRUSTED_NEXT_PAGE_TOKEN")
        if not new:
            break
        if new in seen or len(seen) >= 200:
            raise IncompleteYouTubeInventory("UPLOAD_PLAYLIST_PAGINATION_INCOMPLETE")
        seen.add(new)
        token = new
    if len(ids) != len(set(ids)):
        raise IncompleteYouTubeInventory("DUPLICATE_UPLOAD_VIDEO_ID")
    return ids, deleted_candidates


def audit_channel(youtube):
    """One complete channel scan, never an API write or inferred publication."""
    who = youtube.channels().list(part="id,contentDetails", mine=True).execute()
    accounts = who.get("items") if isinstance(who, dict) else None
    if not isinstance(accounts, list) or len(accounts) != 1:
        raise IncompleteYouTubeInventory("UNKNOWN_YOUTUBE_ACCOUNT")
    account = accounts[0]
    if account.get("id") != CHANNEL:
        raise IncompleteYouTubeInventory("WRONG_YOUTUBE_CHANNEL")
    playlist = (account.get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads")
    if not isinstance(playlist, str) or not playlist:
        raise IncompleteYouTubeInventory("UPLOAD_PLAYLIST_UNKNOWN")
    ids, deleted_candidates = _complete_upload_list(youtube, playlist)
    records = {}

    def collect(chunk):
        response = youtube.videos().list(
            part="snippet,status,processingDetails", id=",".join(chunk),
        ).execute()
        videos = response.get("items") if isinstance(response, dict) else None
        if not isinstance(videos, list):
            raise IncompleteYouTubeInventory("UNKNOWN_YOUTUBE_VIDEO_PAGE")
        for row in videos:
            if not isinstance(row, dict):
                raise IncompleteYouTubeInventory("INVALID_YOUTUBE_VIDEO")
            vid = row.get("id")
            if vid not in chunk or vid in records:
                raise IncompleteYouTubeInventory("UNTRUSTED_YOUTUBE_VIDEO_ID")
            if (row.get("snippet") or {}).get("channelId") != CHANNEL:
                raise IncompleteYouTubeInventory("WRONG_YOUTUBE_VIDEO_CHANNEL")
            records[vid] = row

    for i in range(0, len(ids), 50):
        collect(ids[i:i+50])
    # A batch omission is not proof of deletion. Retry every ID individually.
    for vid in ids:
        if vid not in records:
            collect([vid])
    missing = set(ids) - set(records)
    confirmed_deleted = {
        vid for vid in missing
        if vid in deleted_candidates and _confirm_deleted_upload(youtube, playlist, vid)
    }
    # Any unknown/missing ID remains a hard blocker and is redacted in logs.
    unreturned = missing - confirmed_deleted
    scan_complete = not unreturned
    results = []
    for day, slug, source_sha in TARGETS:
        exact = []
        slug_only = []
        for vid, record in records.items():
            snippet = record.get("snippet") or {}
            desc = snippet.get("description") or ""
            if not isinstance(desc, str):
                raise IncompleteYouTubeInventory("INVALID_YOUTUBE_DESCRIPTION")
            if "source_slug=" + slug not in desc:
                continue
            privacy = (record.get("status") or {}).get("privacyStatus")
            processing = (record.get("processingDetails") or {}).get("processingStatus")
            media_kind = (
                "short" if ("KESHER_MEDIA_KIND=short" in desc or
                            "kind=short" in desc or "#Shorts" in desc)
                else "unclassified"
            )
            row = {
                "kind_hint": media_kind,
                "privacy": privacy if privacy in ("private", "unlisted", "public") else "UNKNOWN",
                "processing": processing if isinstance(processing, str) else "UNKNOWN",
            }
            public = privacy == "public" and processing in ("succeeded", "processed")
            if public:
                row["public_url"] = "https://www.youtube.com/watch?v=" + vid
            else:
                row["nonpublic_fingerprint"] = _fingerprint(vid)
            if "content_sha256=" + source_sha in desc:
                exact.append(row)
            else:
                slug_only.append(row)
        # Ambiguity and missing provenance always require a human source review.
        results.append({
            "date": day, "slug": slug, "persisted_source_sha256": source_sha,
            "exact_source_candidates": exact, "slug_only_candidates": slug_only,
            "exact_match_count": len(exact), "legacy_candidate_count": len(slug_only),
            "youtube_scan_complete": scan_complete,
            "source_qa_approved": False,
            "new_provider_generation_authorized": False,
            "upload_authorized": False,
        })
    return {
        "channel_verified": True, "uploaded_playlist_count": len(ids),
        "resolved_video_count": len(records),
        "confirmed_deleted_tombstones": len(confirmed_deleted),
        "unresolved_video_fingerprints": sorted(_fingerprint(x) for x in unreturned),
        "youtube_scan_complete": scan_complete,
        "items": results,
        "production_activated": False,
        "provider_dispatch": False,
    }


def main():
    import os
    import sys
    if (os.environ.get("GITHUB_REPOSITORY") != "yanivsa/kesher-website"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_WORKFLOW_REF") !=
               "yanivsa/kesher-website/.github/workflows/kesher-daily-video.yml@refs/heads/main"
            or os.environ.get("KESHER_RECOVERY_READ_ONLY") != "true"):
        print("KESHER_GHONLY_YOUTUBE_AUDIT_WRONG_INVOCATION", file=sys.stderr)
        return 2
    try:
        result = audit_channel(youtube_client())
    except Exception:
        # Do not leak OAuth or provider error text.
        print("KESHER_GHONLY_YOUTUBE_AUDIT_INCOMPLETE", file=sys.stderr)
        return 2
    print("KESHER_GHONLY_YOUTUBE_AUDIT " + json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["youtube_scan_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

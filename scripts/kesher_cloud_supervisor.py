#!/usr/bin/env python3
"""Kesher Cloud Supervisor and Autonomous Healing Engine.

Audits GitHub Actions production controller (V5/V6), verifies the Three-Link
Delivery Contract for target cycle(s), diagnoses workflow failures, and triggers
autonomous healing when interventions are required.

Guarantees:
- Never falls back to previous dates for today's contract completion.
- Supports multi-article publication on the same date (each audited as a distinct triad).
- Verifies HTTP 200, canonical URL matching, content presence, and YouTube delivery.
- Clearly distinguishes between COMPLETE, PENDING, BLOCKED, and FAILED states.
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import struct
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent
POSTS_FILE = PROJECT_DIR / "src" / "data" / "posts.json"
POSTS_RECENT_FILE = PROJECT_DIR / "src" / "data" / "postsRecent.json"
ARTICLE_VIDEOS_FILE = PROJECT_DIR / "src" / "data" / "articleVideos.json"
CACHE_DIR = PROJECT_DIR / ".kesher_supervisor_cache"
SITE_URL = "https://kesher.saharoni.com"
YOUTUBE_CHANNEL_ID = "UCx5fEFvdVf28HLAR2dFW64Q"

WORKFLOWS_TO_WATCH = [
    "Kesher Content Controller",
    "Kesher Daily NotebookLM Video Overview",
    "Kesher Daily Article Short V4",
    "Kesher Article Generation",
    "Auto-merge Jules audit PRs",
    "Deploy to Cloudflare Pages",
]


def israel_now() -> datetime.datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Asia/Jerusalem"))
    except Exception:
        return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))


def run_gh(args: list[str], check: bool = True, timeout: int = 15) -> tuple[int, str, str]:
    cmd = ["gh", *args]
    try:
        res = subprocess.run(
            cmd,
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if check and res.returncode != 0:
            raise RuntimeError(f"gh command failed ({res.returncode}): {' '.join(cmd)}\n{res.stderr}")
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        if check:
            raise RuntimeError(f"gh command timed out after {timeout}s: {' '.join(cmd)}")
        return 124, "", f"timed out after {timeout}s"


def run_gh_bytes(args: list[str], timeout: int = 20) -> tuple[int, bytes, str]:
    cmd = ["gh", *args]
    try:
        res = subprocess.run(
            cmd,
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=False,
            check=False,
            timeout=timeout,
        )
        return res.returncode, res.stdout, res.stderr.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return 124, b"", f"timed out after {timeout}s"


def gh_json(args: list[str], timeout: int = 15) -> Any:
    _, stdout, _ = run_gh(args, check=True, timeout=timeout)
    return json.loads(stdout)


def get_image_size(path: Path) -> tuple[int | None, int | None]:
    """Parse image dimensions (using PIL if available, with pure Python fallback)."""
    if not path.is_file():
        return None, None
    try:
        from PIL import Image
        with Image.open(path) as img:
            return img.size[0], img.size[1]
    except Exception:
        pass
    try:
        with open(path, "rb") as f:
            data = f.read(32)
            if data[:8] == b"\x89PNG\r\n\x1a\n":
                w, h = struct.unpack(">LL", data[16:24])
                return w, h
            elif data[:2] == b"\xff\xd8":
                f.seek(0)
                b = f.read()
                size = len(b)
                i = 2
                while i < size - 9:
                    if b[i] == 0xff:
                        m = b[i+1]
                        if m in (0xc0, 0xc1, 0xc2):
                            h, w = struct.unpack(">HH", b[i+5:i+9])
                            return w, h
                        elif m in (0xd9, 0xda):
                            break
                        elif m not in (0xd8, 0x01, 0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7):
                            l = struct.unpack(">H", b[i+2:i+4])[0]
                            i += 2 + l
                            continue
                    i += 1
    except Exception:
        pass
    return None, None


def load_cached_artifact_state(artifact_name: str) -> dict[str, Any]:
    """Load lightweight state artifact with local caching to avoid heavy downloads."""
    local_state = PROJECT_DIR / f".{artifact_name}" / "state.json"
    if local_state.is_file():
        try:
            return json.loads(local_state.read_text(encoding="utf-8"))
        except Exception:
            pass

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{artifact_name}.json"
    if cache_file.is_file():
        try:
            if (time.time() - cache_file.stat().st_mtime) < 600:
                return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    candidates = [artifact_name]
    if "controller-state" not in artifact_name:
        candidates.insert(0, artifact_name.replace("-state", "-controller-state"))

    for target_name in candidates:
        try:
            data = gh_json([
                "api",
                f"repos/:owner/:repo/actions/artifacts?name={target_name}&per_page=5",
            ], timeout=10)
            rows = data.get("artifacts") or []
            rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
            for row in rows:
                aid = row.get("id")
                if not aid:
                    continue
                code, raw_zip, _ = run_gh_bytes(["api", f"repos/:owner/:repo/actions/artifacts/{aid}/zip"], timeout=15)
                if code == 0 and raw_zip:
                    with zipfile.ZipFile(io.BytesIO(raw_zip)) as z:
                        for name in z.namelist():
                            if name.endswith("state.json"):
                                parsed = json.loads(z.read(name))
                                has_uploaded = any(
                                    isinstance(it, dict) and it.get("uploaded") is True
                                    for it in parsed.get("items", [])
                                )
                                cache_file.write_text(json.dumps(parsed), encoding="utf-8")
                                if has_uploaded:
                                    return parsed
        except Exception:
            continue

    if cache_file.is_file():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {}


def check_site_url(url: str, timeout: int = 15) -> tuple[bool, int, str]:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "KesherCloudSupervisor/2.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status == 200, resp.status, body
    except Exception as exc:
        return False, 0, str(exc)


def load_all_catalog_posts() -> list[dict[str, Any]]:
    """Load and deduplicate all posts from recent and historical catalogs."""
    posts: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()

    for catalog_path in (POSTS_RECENT_FILE, POSTS_FILE):
        if catalog_path.is_file():
            try:
                data = json.loads(catalog_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            slug = str(item.get("slug") or item.get("id") or "").strip()
                            if slug and slug not in seen_slugs:
                                seen_slugs.add(slug)
                                posts.append(item)
            except Exception:
                pass
    return posts


def get_target_articles(
    target_date: str | None = None,
    target_slug: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve articles for the target cycle.

    Strict contract: NEVER falls back to yesterday or prior dates if target_date has no articles.
    """
    posts = load_all_catalog_posts()
    if not posts:
        return []

    if target_slug:
        return [
            p for p in posts
            if str(p.get("slug") or p.get("id") or "").strip() == target_slug.strip()
        ]

    effective_date = target_date or israel_now().date().isoformat()
    return [
        p for p in posts
        if str(p.get("date") or "").strip() == effective_date
    ]


def verify_canonical_url(body: str, expected_url: str) -> bool:
    """Verify that <link rel="canonical" ...> in the rendered HTML matches expected_url."""
    if not body:
        return False
    match = re.search(r'<link\s+[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', body, re.IGNORECASE)
    if not match:
        match = re.search(r'<link\s+[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']', body, re.IGNORECASE)
    if match:
        found_url = match.group(1).strip()
        return found_url == expected_url or found_url.rstrip("/") == expected_url.rstrip("/")
    return False


def verify_youtube_public(video_id: str, is_short: bool = False) -> tuple[bool, dict[str, Any]]:
    """Verify video/short public availability and oEmbed response."""
    if not video_id:
        return False, {}
    prefix = "https://www.youtube.com/shorts/" if is_short else "https://www.youtube.com/watch?v="
    video_url = f"{prefix}{video_id}"
    oembed_url = f"https://www.youtube.com/oembed?url={video_url}&format=json"
    is_pub, status, body = check_site_url(oembed_url, timeout=10)
    meta = {}
    if is_pub:
        try:
            meta = json.loads(body)
        except Exception:
            pass
    return is_pub, meta


def article_content_present(title: str, direct_answer: str, body: str) -> bool:
    """An empty summary must never count as a visible article match."""
    heading = str(title or "").strip()
    snippet = str(direct_answer or "").strip()[:30]
    return bool(body and ((heading and heading in body) or (snippet and snippet in body)))


def strict_triad_quality(triad: dict[str, Any]) -> bool:
    """Only independently evidenced article, long and native Short may pass."""
    article = triad.get("article") or {}
    long_video = triad.get("long_video") or {}
    short = triad.get("short") or {}
    required = [
        article.get("live"),
        article.get("canonical_match"),
        article.get("content_verified"),
        article.get("hero_image_verified"),
        article.get("video_embed_present"),
        long_video.get("public"),
        long_video.get("channel_verified"),
        long_video.get("provenance_verified"),
        long_video.get("technical_verified"),
        long_video.get("signature_verified"),
        long_video.get("landscape_verified"),
        long_video.get("article_link_in_description"),
        short.get("public"),
        short.get("channel_verified"),
        short.get("provenance_verified"),
        short.get("technical_verified"),
        short.get("signature_verified"),
        short.get("portrait_verified"),
        short.get("article_link_in_description"),
        triad.get("cross_links_verified"),
    ]
    return all(value is True for value in required)


def audit_single_triad(
    post: dict[str, Any],
    article_videos: dict[str, Any],
) -> dict[str, Any]:
    """Audit the complete Three-Link Delivery Contract and Quality DoD for a single post."""
    slug = str(post.get("slug") or post.get("id") or "")
    post_date = str(post.get("date") or "")
    article_url = f"{SITE_URL}/blog/{slug}"
    title = str(post.get("title") or "")

    triad: dict[str, Any] = {
        "slug": slug,
        "date": post_date,
        "title": title,
        "expected_source_sha256": None,
        "article": {
            "slug": slug,
            "url": article_url,
            "live": False,
            "http_status": 0,
            "canonical_match": False,
            "content_verified": False,
            "hero_image_verified": False,
            "hero_image_dimensions": None,
            "hero_image_ratio": None,
            "video_embed_present": False,
        },
        "long_video": {
            "youtube_id": None,
            "youtube_url": None,
            "public": False,
            "channel_verified": False,
            "ratio": "16:9",
            "provenance_verified": False,
            "signature_verified": False,
            "technical_verified": False,
            "landscape_verified": False,
            "article_link_in_description": False,
            "state_artifact_id": None,
        },
        "short": {
            "youtube_id": None,
            "youtube_url": None,
            "public": False,
            "channel_verified": False,
            "ratio": "9:16",
            "portrait_verified": False,
            "provenance_verified": False,
            "signature_verified": False,
            "technical_verified": False,
            "article_link_in_description": False,
            "state_artifact_id": None,
        },
        "cross_links_verified": False,
        "quality_verified": False,
        "complete": False,
        "status": "PENDING",
    }

    # Compute the actual immutable NotebookLM identity for this published
    # article. Any malformed article makes provenance unverifiable.
    try:
        from scripts.kesher_daily_pipeline import source_metadata
        expected_sha = str(source_metadata(post)["content_sha256"])
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            expected_sha = ""
    except Exception:
        expected_sha = ""
    triad["expected_source_sha256"] = expected_sha or None

    # 1. Article live & canonical verification
    is_live, status, body = check_site_url(article_url)
    triad["article"]["live"] = is_live
    triad["article"]["http_status"] = status
    if is_live and body:
        triad["article"]["canonical_match"] = verify_canonical_url(body, article_url)
        triad["article"]["content_verified"] = article_content_present(
            title, str(post.get("directAnswer") or ""), body
        )

    # 2. Hero Image 16:9 verification
    hero_rel = post.get("image") or post.get("imageUrl") or f"/images/generated/blog/{slug}-photo.jpg"
    local_hero = PROJECT_DIR / "public" / hero_rel.lstrip("/")
    if not local_hero.is_file():
        local_hero = PROJECT_DIR / hero_rel.lstrip("/")
    if local_hero.is_file():
        w, h = get_image_size(local_hero)
        size_bytes = local_hero.stat().st_size
        triad["article"]["hero_image_dimensions"] = (w, h)
        if w and h:
            ratio = round(w / h, 2)
            triad["article"]["hero_image_ratio"] = ratio
            # 16:9 is 1.777; allow standard editorial photography tolerance 1.65 - 1.90
            hero_ratio_ok = (1.75 <= ratio <= 1.81) and (w >= 800 and h >= 450) and (size_bytes >= 15000)
            triad["article"]["hero_image_verified"] = hero_ratio_ok
            triad["article"]["hero_image_size_bytes"] = size_bytes
    else:
        # Remote HTTP 200 is NOT proof of 16:9 dimensions or licensed pixels.
        # Until a verified image artifact is available locally, fail closed.
        img_ok, _, _ = check_site_url(f"{SITE_URL}{hero_rel}")
        triad["article"]["remote_hero_available"] = bool(img_ok)
        triad["article"]["hero_image_verified"] = False

    # 3. Long Video (16:9 Overview) verification
    vid_entry = article_videos.get(slug) or {}
    long_vid = post.get("youtubeVideoId") or vid_entry.get("youtubeId")
    if long_vid:
        triad["long_video"]["youtube_id"] = long_vid
        triad["long_video"]["youtube_url"] = f"https://www.youtube.com/watch?v={long_vid}"
        is_pub, meta = verify_youtube_public(long_vid, is_short=False)
        triad["long_video"]["public"] = is_pub
        if meta.get("title"):
            triad["long_video"]["verified_title"] = meta.get("title")
        author_url = str(meta.get("author_url") or "")
        author_name = str(meta.get("author_name") or "")
        if YOUTUBE_CHANNEL_ID in author_url or "קשר" in author_name or "Kesher" in author_name:
            triad["long_video"]["channel_verified"] = True

        # Check video embed in article HTML
        if body and (long_vid in body or re.search(rf'(youtube\.com/(?:embed/|watch\?v=)|youtu\.be/){re.escape(long_vid)}', body)):
            triad["article"]["video_embed_present"] = True

    # 4. Short (9:16 Portrait) verification
    short_vid = post.get("youtubeShortId") or vid_entry.get("shortYoutubeId") or vid_entry.get("youtubeShortId")
    if short_vid:
        triad["short"]["youtube_id"] = short_vid
        triad["short"]["youtube_url"] = f"https://www.youtube.com/shorts/{short_vid}"
        is_pub, meta = verify_youtube_public(short_vid, is_short=True)
        triad["short"]["public"] = is_pub
        if meta.get("title"):
            triad["short"]["verified_title"] = meta.get("title")
        author_url = str(meta.get("author_url") or "")
        author_name = str(meta.get("author_name") or "")
        if YOUTUBE_CHANNEL_ID in author_url or "קשר" in author_name or "Kesher" in author_name:
            triad["short"]["channel_verified"] = True

    # 5. Provenance & Outro Signature Evidence from Artifacts
    video_state = load_cached_artifact_state("kesher-video-state")
    if long_vid and expected_sha and video_state and isinstance(video_state.get("items"), list):
        matching_vids = [
            item for item in video_state["items"]
            if isinstance(item, dict)
            and str(item.get("youtube_id") or "") == str(long_vid)
            and str((item.get("source") or {}).get("slug") or "") == slug
            and str((item.get("source") or {}).get("content_sha256") or "") == expected_sha
        ]
        # Never choose the newest of several same-source candidates.
        if len(matching_vids) == 1:
            v_item = matching_vids[0]
            pipeline = str(v_item.get("visual_pipeline") or "")
            triad["long_video"]["provenance_verified"] = bool(
                v_item.get("uploaded") is True
                and str(v_item.get("task_id") or "").strip()
                and ("notebooklm" in pipeline.lower() or "remotion-v1" in pipeline.lower())
            )
            triad["long_video"]["signature_verified"] = v_item.get("signature_verified") is True
            triad["long_video"]["technical_verified"] = v_item.get("technical_verified") is True
            media = v_item.get("media") or v_item.get("provider_raw_media") or {}
            if isinstance(media, dict):
                try:
                    width, height = int(media.get("width") or 0), int(media.get("height") or 0)
                    triad["long_video"]["landscape_verified"] = bool(
                        width >= 800 and height >= 450 and 1.65 <= width / height <= 1.90
                    ) if height > 0 else False
                except (ValueError, TypeError):
                    pass
            desc = str((v_item.get("source") or {}).get("youtube_metadata", {}).get("description") or "")
            triad["long_video"]["article_link_in_description"] = f"/blog/{slug}" in desc

    short_state = load_cached_artifact_state("kesher-short-v4-state")
    if short_vid and expected_sha and short_state and isinstance(short_state.get("items"), list):
        matching_shorts = [
            item for item in short_state["items"]
            if isinstance(item, dict)
            and str(item.get("youtube_id") or "") == str(short_vid)
            and str((item.get("source") or {}).get("slug") or "") == slug
            and str((item.get("source") or {}).get("content_sha256") or "") == expected_sha
        ]
        if len(matching_shorts) == 1:
            s_item = matching_shorts[0]
            triad["short"]["provenance_verified"] = bool(
                s_item.get("uploaded") is True
                and str(s_item.get("task_id") or "").strip()
                and s_item.get("provider_native_short") is True
                and s_item.get("provider_video_format") == "short"
                and s_item.get("shared_provider_identity") is not True
                and not s_item.get("adopted_from_long_item_id")
            )
            triad["short"]["signature_verified"] = s_item.get("signature_verified") is True
            triad["short"]["technical_verified"] = s_item.get("technical_verified") is True
            raw_media = s_item.get("provider_raw_media") or {}
            if isinstance(raw_media, dict):
                try:
                    width, height = int(raw_media.get("width") or 0), int(raw_media.get("height") or 0)
                    triad["short"]["portrait_verified"] = bool(
                        width >= 360 and height >= 640 and height > width
                        and 0.54 <= width / height <= 0.58
                    ) if height > 0 else False
                except (ValueError, TypeError):
                    pass
            source = s_item.get("source") or {}
            desc = str(
                (source.get("youtube_metadata") or {}).get("description")
                or (source.get("short_youtube_metadata") or {}).get("description") or ""
            )
            triad["short"]["article_link_in_description"] = f"/blog/{slug}" in desc

    # 6. Cross-Links Consistency
    cross_links_ok = bool(
        vid_entry
        and post.get("youtubeVideoId") == vid_entry.get("youtubeId")
        and post.get("youtubeShortId") == (vid_entry.get("shortYoutubeId") or vid_entry.get("youtubeShortId"))
    )
    triad["cross_links_verified"] = cross_links_ok

    # 7. Quality Gate — never substitute public oEmbed for provider evidence.
    triad["quality_verified"] = strict_triad_quality(triad)
    quality_passed = triad["quality_verified"]

    # 8. Final Contract Status
    if (
        triad["article"]["live"]
        and triad["article"]["canonical_match"]
        and triad["long_video"]["public"]
        and triad["short"]["public"]
    ):
        if quality_passed:
            triad["complete"] = True
            triad["status"] = "COMPLETE"
        else:
            # When public links exist but evidence is incomplete, strictly flag QUALITY_HOLD
            triad["complete"] = False
            triad["status"] = "QUALITY_HOLD"
    elif triad["article"]["live"]:
        triad["complete"] = False
        triad["status"] = "PENDING_MEDIA"
    else:
        triad["complete"] = False
        triad["status"] = "PENDING_DEPLOY"

    return triad


def audit_delivery(
    target_date: str | None = None,
    target_slug: str | None = None,
) -> dict[str, Any]:
    """Audit delivery contract for target date or slug, supporting multi-article days."""
    effective_date = target_date or israel_now().date().isoformat()
    targets = get_target_articles(target_date=effective_date, target_slug=target_slug)

    delivery: dict[str, Any] = {
        "target_date": effective_date,
        "target_slug": target_slug,
        "article_count": len(targets),
        "triads": [],
        "complete": False,
        "status": "MISSING_TARGET_CYCLE",
    }

    if not targets:
        delivery["message"] = (
            f"No article found for target {target_slug or effective_date}. "
            "Refusing fallback to previous dates."
        )
        return delivery

    article_videos = {}
    if ARTICLE_VIDEOS_FILE.is_file():
        try:
            raw_vids = json.loads(ARTICLE_VIDEOS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw_vids, dict):
                article_videos = raw_vids
        except Exception:
            pass

    triads = [audit_single_triad(p, article_videos) for p in targets]
    delivery["triads"] = triads
    delivery["complete"] = bool(triads and all(t["complete"] for t in triads))

    if delivery["complete"]:
        delivery["status"] = "COMPLETE"
    elif any(t["status"] == "QUALITY_HOLD" for t in triads):
        delivery["status"] = "QUALITY_HOLD"
    elif any(t["status"] == "PENDING_MEDIA" for t in triads):
        delivery["status"] = "PENDING"
    else:
        delivery["status"] = "PENDING"

    # Backward-compatible convenience aliases pointing to the first triad
    if triads:
        first = triads[0]
        delivery["article"] = first["article"]
        delivery["long_video"] = first["long_video"]
        delivery["short"] = first["short"]

    return delivery


def audit_recent_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    try:
        data = gh_json([
            "run", "list",
            "-L", "20",
            "--json", "databaseId,name,status,conclusion,event,createdAt,url,headBranch",
        ])
        for r in data:
            runs.append({
                "id": r.get("databaseId"),
                "name": r.get("name"),
                "status": r.get("status"),
                "conclusion": r.get("conclusion"),
                "event": r.get("event"),
                "branch": r.get("headBranch"),
                "created_at": r.get("createdAt"),
                "url": r.get("url"),
            })
    except Exception as exc:
        runs.append({"error": str(exc)})
    return runs


def audit_controller_health() -> dict[str, Any]:
    health: dict[str, Any] = {
        "active": False,
        "last_conclusion": None,
        "direct_takeover_required": False,
        "takeover_details": None,
    }
    try:
        recent_ctrl = gh_json([
            "run", "list",
            "--workflow=kesher-content-controller.yml",
            "-L", "3",
            "--json", "databaseId,status,conclusion,createdAt,url",
        ])
        if recent_ctrl:
            health["last_run_id"] = recent_ctrl[0].get("databaseId")
            health["last_status"] = recent_ctrl[0].get("status")
            health["last_conclusion"] = recent_ctrl[0].get("conclusion")
            health["last_created_at"] = recent_ctrl[0].get("createdAt")
            health["active"] = recent_ctrl[0].get("status") in ("in_progress", "queued")

            if recent_ctrl[0].get("databaseId"):
                code, out, _ = run_gh([
                    "run", "view", str(recent_ctrl[0]["databaseId"]), "--log",
                ], check=False, timeout=10)
                if re.search(r'"direct_takeover_required"\s*:\s*true', out, re.IGNORECASE) or "DIRECT_TAKEOVER_REQUIRED" in out:
                    health["direct_takeover_required"] = True
                    match = re.search(r'"direct_takeover_required"\s*:\s*true.*', out, re.IGNORECASE)
                    if match:
                        health["takeover_details"] = match.group(0)[:200]
    except Exception as exc:
        health["error"] = str(exc)
    return health


def diagnose_failures() -> list[dict[str, Any]]:
    failures = []
    runs = audit_recent_runs()
    for r in runs:
        if r.get("conclusion") == "failure":
            run_id = r.get("id")
            detail = {"run_id": run_id, "name": r.get("name"), "created_at": r.get("created_at"), "url": r.get("url")}
            code, out, _ = run_gh(["run", "view", str(run_id), "--log-failed"], check=False, timeout=10)
            if code == 0 and out.strip():
                lines = [line.strip() for line in out.splitlines() if line.strip()]
                error_lines = [l for l in lines if any(k in l.lower() for k in ("error", "failed", "blocked", "exception", "mismatch"))]
                detail["errors"] = error_lines[-5:] if error_lines else lines[-3:]
            failures.append(detail)
    return failures


def heal_trigger_controller() -> tuple[bool, str]:
    code, out, err = run_gh(["workflow", "run", "kesher-content-controller.yml"], check=False, timeout=10)
    if code == 0:
        return True, "Triggered kesher-content-controller.yml"
    return False, f"Trigger failed: {err}"


def full_supervisor_report(
    target_date: str | None = None,
    target_slug: str | None = None,
) -> dict[str, Any]:
    delivery = audit_delivery(target_date=target_date, target_slug=target_slug)
    controller = audit_controller_health()
    failures = diagnose_failures()

    healing_actions = []
    if controller.get("direct_takeover_required"):
        healing_actions.append("Direct takeover flagged by controller. Supervisor intervention required.")
    if failures:
        healing_actions.append(f"Detected {len(failures)} failed runs in recent history.")

    return {
        "timestamp_israel": israel_now().isoformat(),
        "delivery": delivery,
        "controller_health": controller,
        "recent_failures_count": len(failures),
        "recent_failures": failures[:5],
        "recommended_actions": healing_actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Kesher Cloud Supervisor v2.0")
    parser.add_argument("--date", type=str, default=None, help="Target cycle date (YYYY-MM-DD, default today)")
    parser.add_argument("--slug", type=str, default=None, help="Target article slug")
    parser.add_argument("--report-json", action="store_true", help="Output full report as JSON")
    parser.add_argument("--heal", action="store_true", help="Attempt automatic healing of stuck controller")
    args = parser.parse_args()

    report = full_supervisor_report(target_date=args.date, target_slug=args.slug)

    if args.heal:
        if report["controller_health"].get("direct_takeover_required") or not report["delivery"]["complete"]:
            ok, msg = heal_trigger_controller()
            report["heal_result"] = {"success": ok, "message": msg}
        else:
            report["heal_result"] = {"success": True, "message": "No healing needed, pipeline is healthy."}

    if args.report_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    d = report["delivery"]
    ch = report["controller_health"]
    print("========================================")
    print("🔍 Kesher Cloud Supervisor Report v2.0")
    print(f"🕒 Time: {report['timestamp_israel']}")
    print(f"📅 Target Date: {d.get('target_date')}")
    if d.get("target_slug"):
        print(f"🎯 Target Slug: {d.get('target_slug')}")
    print(f"📊 Articles Audited: {d.get('article_count', 0)}")
    print("========================================")

    if not d.get("triads"):
        print(f"⚠️ {d.get('message', 'No articles found for target cycle.')}")
        print(f"📦 Contract Complete: ❌ NO")
    else:
        for idx, t in enumerate(d["triads"], start=1):
            art = t["article"]
            lv = t["long_video"]
            sh = t["short"]
            print(f"--- Triad {idx}: {t.get('slug')} ---")
            print(f"📄 Article: {'✅ LIVE' if art.get('live') else '❌ NOT LIVE'} | Canonical: {'✅' if art.get('canonical_match') else '❌'} ({art.get('url')})")
            hero_info = f"16:9 verified (ratio: {art.get('hero_image_ratio')})" if art.get('hero_image_verified') else "ratio unverified"
            print(f"   Hero Image: {'✅' if art.get('hero_image_verified') else '❌'} {hero_info} | Embed: {'✅' if art.get('video_embed_present') else '❌'}")
            lv_prov = f"NotebookLM: {'✅' if lv.get('provenance_verified') else '⏳'} | Outro Sign: {'✅' if lv.get('signature_verified') else '⏳'}"
            print(f"🎬 Long Video (16:9): {'✅ PUBLIC' if lv.get('public') else '⏳ PENDING/NOT VERIFIED'} ({lv.get('youtube_url') or 'N/A'})")
            print(f"   Provenance: {lv_prov} | Canonical in Desc: {'✅' if lv.get('article_link_in_description') else '⏳'}")
            sh_prov = f"Native 9:16: {'✅' if sh.get('portrait_verified') else '⏳'} | Outro Sign: {'✅' if sh.get('signature_verified') else '⏳'}"
            print(f"📱 Short (9:16): {'✅ PUBLIC' if sh.get('public') else '⏳ PENDING/NOT VERIFIED'} ({sh.get('youtube_url') or 'N/A'})")
            print(f"   Provenance: {sh_prov} | Canonical in Desc: {'✅' if sh.get('article_link_in_description') else '⏳'}")
            print(f"🔗 Cross-links: {'✅' if t.get('cross_links_verified') else '❌'} | Quality Verified: {'✅' if t.get('quality_verified') else '❌'}")
            print(f"Triad Status: {t.get('status')} | Complete: {'✅ YES' if t.get('complete') else '⏳ NO'}")

        print("----------------------------------------")
        print(f"📦 Overall Contract Complete: {'✅ YES' if d['complete'] else '⏳ NO'}")

    print("----------------------------------------")
    print(f"🎮 Controller Status: {ch.get('last_status')} ({ch.get('last_conclusion')})")
    print(f"⚠️ Direct Takeover Required: {ch.get('direct_takeover_required')}")
    if ch.get("takeover_details"):
        print(f"   Details: {ch.get('takeover_details')}")
    print(f"❌ Recent Failures: {report['recent_failures_count']}")
    if report["recent_failures"]:
        for f in report["recent_failures"]:
            print(f"   - {f['name']} (run {f['run_id']}): {', '.join(f.get('errors', []))}")
    print("========================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

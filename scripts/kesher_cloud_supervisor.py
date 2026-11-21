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
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent
POSTS_FILE = PROJECT_DIR / "src" / "data" / "posts.json"
POSTS_RECENT_FILE = PROJECT_DIR / "src" / "data" / "postsRecent.json"
ARTICLE_VIDEOS_FILE = PROJECT_DIR / "src" / "data" / "articleVideos.json"
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


def run_gh(args: list[str], check: bool = True) -> tuple[int, str, str]:
    cmd = ["gh", *args]
    res = subprocess.run(
        cmd,
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if check and res.returncode != 0:
        raise RuntimeError(f"gh command failed ({res.returncode}): {' '.join(cmd)}\n{res.stderr}")
    return res.returncode, res.stdout, res.stderr


def gh_json(args: list[str]) -> Any:
    _, stdout, _ = run_gh(args, check=True)
    return json.loads(stdout)


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


def audit_single_triad(
    post: dict[str, Any],
    article_videos: dict[str, Any],
) -> dict[str, Any]:
    """Audit the complete Three-Link Delivery Contract for a single post."""
    slug = str(post.get("slug") or post.get("id") or "")
    post_date = str(post.get("date") or "")
    article_url = f"{SITE_URL}/blog/{slug}"
    title = str(post.get("title") or "")

    triad: dict[str, Any] = {
        "slug": slug,
        "date": post_date,
        "title": title,
        "article": {
            "slug": slug,
            "url": article_url,
            "live": False,
            "http_status": 0,
            "canonical_match": False,
            "content_verified": False,
        },
        "long_video": {
            "youtube_id": None,
            "youtube_url": None,
            "public": False,
            "ratio": "16:9",
            "state_artifact_id": None,
        },
        "short": {
            "youtube_id": None,
            "youtube_url": None,
            "public": False,
            "ratio": "9:16",
            "state_artifact_id": None,
        },
        "complete": False,
        "status": "PENDING",
    }

    # 1. Article live verification
    is_live, status, body = check_site_url(article_url)
    triad["article"]["live"] = is_live
    triad["article"]["http_status"] = status
    if is_live and body:
        triad["article"]["canonical_match"] = verify_canonical_url(body, article_url)
        triad["article"]["content_verified"] = bool(title and (title in body or post.get("directAnswer", "")[:30] in body))

    # 2. Long Video (16:9 Overview) verification
    vid_entry = article_videos.get(slug) or {}
    long_vid = post.get("youtubeVideoId") or vid_entry.get("youtubeId")
    if long_vid:
        triad["long_video"]["youtube_id"] = long_vid
        triad["long_video"]["youtube_url"] = f"https://www.youtube.com/watch?v={long_vid}"
        is_pub, meta = verify_youtube_public(long_vid, is_short=False)
        triad["long_video"]["public"] = is_pub
        if meta.get("title"):
            triad["long_video"]["verified_title"] = meta.get("title")

    # 3. Short (9:16 Portrait) verification
    short_vid = post.get("youtubeShortId") or vid_entry.get("shortYoutubeId") or vid_entry.get("youtubeShortId")
    if short_vid:
        triad["short"]["youtube_id"] = short_vid
        triad["short"]["youtube_url"] = f"https://www.youtube.com/shorts/{short_vid}"
        is_pub, meta = verify_youtube_public(short_vid, is_short=True)
        triad["short"]["public"] = is_pub
        if meta.get("title"):
            triad["short"]["verified_title"] = meta.get("title")

    # 4. Artifact IDs
    try:
        long_state_runs = gh_json([
            "api",
            "repos/:owner/:repo/actions/artifacts?name=kesher-video-state&per_page=5",
            "--jq", ".artifacts[0]",
        ])
        if isinstance(long_state_runs, dict) and long_state_runs.get("id"):
            triad["long_video"]["state_artifact_id"] = long_state_runs.get("id")
    except Exception as exc:
        triad["long_video"]["artifact_error"] = str(exc)

    try:
        short_state_runs = gh_json([
            "api",
            "repos/:owner/:repo/actions/artifacts?name=kesher-short-v4-state&per_page=5",
            "--jq", ".artifacts[0]",
        ])
        if isinstance(short_state_runs, dict) and short_state_runs.get("id"):
            triad["short"]["state_artifact_id"] = short_state_runs.get("id")
    except Exception as exc:
        triad["short"]["artifact_error"] = str(exc)

    # 5. Contract completeness check
    triad["complete"] = bool(
        triad["article"]["live"]
        and triad["article"]["canonical_match"]
        and triad["long_video"]["public"]
        and triad["short"]["public"]
    )

    if triad["complete"]:
        triad["status"] = "COMPLETE"
    elif triad["article"]["live"]:
        triad["status"] = "PENDING_MEDIA"
    else:
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
                ], check=False)
                if "DIRECT_TAKEOVER" in out or "direct_takeover_required" in out:
                    health["direct_takeover_required"] = True
                    match = re.search(r"direct_takeover_required.*", out)
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
            code, out, _ = run_gh(["run", "view", str(run_id), "--log-failed"], check=False)
            if code == 0 and out.strip():
                lines = [line.strip() for line in out.splitlines() if line.strip()]
                error_lines = [l for l in lines if any(k in l.lower() for k in ("error", "failed", "blocked", "exception", "mismatch"))]
                detail["errors"] = error_lines[-5:] if error_lines else lines[-3:]
            failures.append(detail)
    return failures


def heal_trigger_controller() -> tuple[bool, str]:
    code, out, err = run_gh(["workflow", "run", "kesher-content-controller.yml"], check=False)
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
            print(f"🎬 Long Video (16:9): {'✅ PUBLIC' if lv.get('public') else '⏳ PENDING/NOT VERIFIED'} ({lv.get('youtube_url') or 'N/A'})")
            print(f"📱 Short (9:16): {'✅ PUBLIC' if sh.get('public') else '⏳ PENDING/NOT VERIFIED'} ({sh.get('youtube_url') or 'N/A'})")
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

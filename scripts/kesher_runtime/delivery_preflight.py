"""Read-only KESHER daily-source and public-page preflight.

Never dispatch generation, mutate state, or equate a successful workflow with
public YouTube proof. The Short remains UNKNOWN unless verified separately.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

SITE_ORIGIN = "https://kesher.saharoni.com"
ISRAEL = ZoneInfo("Asia/Jerusalem")
YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _catalog(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(p, dict) for p in data):
        raise ValueError(f"INVALID_ARTICLE_CATALOG:{path.name}")
    return data


def source_for_date(root: Path, date: str) -> tuple[dict | None, str | None]:
    """Read BOTH catalogs and refuse more than one current-slot identity."""
    groups: dict[str, dict] = {}
    for name in ("posts.json", "postsRecent.json"):
        for post in _catalog(root / "src" / "data" / name):
            if post.get("date") != date:
                continue
            slug = post.get("slug") or post.get("id")
            if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
                return None, "INVALID_ARTICLE_SLUG"
            if slug in groups:
                former = groups[slug]
                if any(former.get(k) != post.get(k) for k in ("title", "content", "image", "date")):
                    return None, "CONFLICTING_CATALOG_ENTRIES"
            else:
                groups[slug] = post
    if not groups:
        return None, "ARTICLE_NOT_IN_MAIN"
    if len(groups) != 1:
        return None, "DUPLICATE_ARTICLE_SLOT"
    return next(iter(groups.values())), None


def hero_exists(root: Path, path: str) -> bool:
    if not isinstance(path, str) or not path.startswith("/images/"):
        return False
    public = (root / "public").resolve()
    target = (public / path.lstrip("/")).resolve()
    return target.is_relative_to(public) and target.is_file() and target.stat().st_size > 0


def live_article(url: str, video_id: str | None, *, opener=None) -> str:
    """Treat the correctly bound click-to-play facade as an embedded player."""
    get = opener or urllib.request.urlopen
    request = urllib.request.Request(url, headers={"User-Agent": "KESHER-read-only-delivery-audit/1"})
    with get(request, timeout=18) as response:
        if getattr(response, "status", 200) != 200:
            return "ARTICLE_HTTP_NOT_200"
        raw = response.read(3_000_000).decode("utf-8", "replace")
    html = unescape(raw)
    if video_id:
        if f"youtube.com/watch?v={video_id}" not in html or "מעדיפים לצפות?" not in html:
            return "LIVE_LONG_FACADE_MISSING"
        return "LIVE_LONG_FACADE_OK"
    return "LIVE_ARTICLE_OK"


def audit(root: Path, now: datetime, *, live=False, opener=None) -> dict:
    date = now.astimezone(ISRAEL).date().isoformat()
    local_hour = now.astimezone(ISRAEL).hour
    result = {"date": date, "status": "UNKNOWN", "article": "UNKNOWN", "long": "UNKNOWN",
              "short": "UNVERIFIED_EXTERNAL", "controller": "NOT_ATTESTED", "live": "NOT_CHECKED"}
    try:
        article, issue = source_for_date(root, date)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result.update(status="BLOCKED", article="CATALOG_READ_FAILED", reason=type(exc).__name__)
        return result
    if issue:
        result.update(article=issue, status="PENDING" if issue == "ARTICLE_NOT_IN_MAIN" and local_hour < 9 else "BLOCKED")
        return result
    slug = article.get("slug") or article["id"]
    result.update(slug=slug, article_url=f"{SITE_ORIGIN}/blog/{slug}", article="SOURCE_FOUND")
    if not str(article.get("title") or "").strip() or not str(article.get("content") or "").strip():
        result.update(status="BLOCKED", article="ARTICLE_FIELDS_MISSING")
        return result
    if not hero_exists(root, article.get("image", "")):
        result.update(status="BLOCKED", article="HERO_MISSING_OR_INVALID")
        return result
    result["article"] = "SOURCE_AND_HERO_PRESENT"
    try:
        mapping = json.loads((root / "src/data/articleVideos.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        result.update(status="BLOCKED", long="VIDEO_MAP_UNREADABLE")
        return result
    video = mapping.get(slug) if isinstance(mapping, dict) else None
    video_id = video.get("youtubeId") if isinstance(video, dict) else None
    if video_id and YOUTUBE_ID.fullmatch(str(video_id)):
        result["long"] = "VIDEO_ID_MAPPED_NOT_PUBLICLY_VERIFIED"
        result["long_url"] = f"https://youtu.be/{video_id}"
    else:
        result["long"] = "NO_VERIFIED_MAPPING"
    if live:
        try:
            result["live"] = live_article(result["article_url"], video_id, opener=opener)
        except (TimeoutError, OSError, urllib.error.URLError, ValueError):
            result["live"] = "LIVE_CHECK_UNAVAILABLE"
    result["status"] = "OBSERVED_NOT_COMPLETE"
    if local_hour >= 9 and (result["long"] == "NO_VERIFIED_MAPPING" or
                             result["live"] not in ("LIVE_LONG_FACADE_OK", "NOT_CHECKED")):
        result["status"] = "ACTION_REQUIRED"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--live", action="store_true", help="Read-only public article HTTP check")
    args = parser.parse_args(argv)
    result = audit(args.root, datetime.now(ISRAEL), live=args.live)
    print("KESHER_DAILY_PREFLIGHT=" + json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["status"] in ("BLOCKED", "ACTION_REQUIRED"):
        print(f"::warning title=KESHER delivery preflight::{result['date']}: {result['article']}; long={result['long']}; live={result['live']}; short={result['short']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

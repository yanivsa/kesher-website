#!/usr/bin/env python3
"""Autonomous Kesher article -> video reconciliation controller.

GitHub Actions remains the execution surface for secret-bearing jobs. The
controller is the single owner of ordering, durable state, retry/backoff,
idempotency and public success checks. Workers perform bounded work and report
reality; a later event or heartbeat can always resume without creating a second
copy of the same daily task.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
from html.parser import HTMLParser
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

try:
    from .kesher_automation_policy import article_retry_backoff_minutes, load_policy
except ImportError:
    from kesher_automation_policy import article_retry_backoff_minutes, load_policy

SITE_URL = "https://kesher.saharoni.com"
STATE_REF = os.environ.get("KESHER_CONTROLLER_STATE_REF", "automation-state")
STATE_PATH = ".kesher-controller/state.json"
STATE_SCHEMA_VERSION = 2
ARTICLE_WORKFLOW = "kesher-article-generation.yml"
VIDEO_WORKFLOW = "kesher-daily-video.yml"
DEPLOY_WORKFLOW = "deploy.yml"
VIDEO_STATE_ARTIFACT = "kesher-video-state"
ARTICLE_RESULT_ARTIFACT_PREFIX = "kesher-article-result-"
YOUTUBE_CHANNEL_ID = "UCx5fEFvdVf28HLAR2dFW64Q"
ACTIVE_RUN_STATUSES = {"queued", "in_progress", "waiting", "requested", "pending"}
ACTIVE_VIDEO_STATUSES = {
    "source_selected", "source_added", "generating", "downloaded",
    "pending_review", "approved", "uploading",
}
MAX_DEPLOY_ATTEMPTS_BEFORE_LONG_BACKOFF = 3
MAX_DEPLOY_ATTEMPTS = 5
MAX_VIDEO_START_ATTEMPTS_BEFORE_LONG_BACKOFF = 4
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
HEBCAL_ASHDOD_URL = (
    "https://www.hebcal.com/zmanim?cfg=json&geonameid=295629&date={date}&sec=1"
)


class ControllerError(RuntimeError):
    pass


@dataclass(frozen=True)
class Action:
    kind: str
    reason: str
    inputs: dict[str, str] | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


REVIEWED_ADOPTABLE_POST_FREEZE_IDENTITIES: frozenset[tuple[str, str, str]] = frozenset({
    (
        "2026-10-06",
        "child-meltdown-after-school",
        "4f5b0dfa23a56b7088fd332cc3f538a6d0bca9b1e7c09b601d43ec6e8d464e9a",
    ),
    (
        "2026-10-09",
        "how-to-repair-after-couple-fight",
        "317b282607c03c6183ca4d7cd1791c2aa4c2f9bb6b6f5832e0227c413ef5121a",
    ),
    (
        "2026-10-10",
        "child-argues-every-request-boundaries",
        "e0594f772f3f11baacc0ae5c53b7ef9ce9f88f871ee3b6e8c8f67b024b8b8bbc",
    ),
    (
        "2026-10-12",
        "relocation-loneliness-accompanying-partner",
        "93bd8eb7d057faf9ede979e86c891504604c80766287f170b011f05065bd326c",
    ),
    (
        "2026-10-13",
        "when-everyone-around-you-gets-married",
        "667857b17833c378ca3a8f4614b8934c04744d201a53761b781b331b921125e3",
    ),
})
REVIEWED_AMBIGUOUS_POST_FREEZE_DATES: frozenset[str] = frozenset({
    "2026-10-04",
    "2026-10-07",
    "2026-10-08",
})


class _CatalogTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = re.sub(r"\s+", " ", data).strip()
        if value:
            self.parts.append(value)


def _clean_catalog_html(value: str) -> str:
    parser = _CatalogTextExtractor()
    parser.feed(value)
    return html.unescape("\n\n".join(parser.parts))


def canonical_slug(post: dict[str, Any]) -> str:
    return str(post.get("slug") or post.get("id") or "").strip()


def _post_source_sha256(post: dict[str, Any]) -> str:
    slug = canonical_slug(post)
    title = str(post.get("title") or "").strip()
    excerpt_raw = str(post.get("excerpt") or "").strip()
    content_raw = str(post.get("content") or "").strip()
    if slug and title and excerpt_raw and content_raw:
        excerpt = _clean_catalog_html(excerpt_raw)
        article_text = _clean_catalog_html(content_raw)
        canonical_url = f"{SITE_URL}/blog/{slug}"
        body = "\n\n".join(part for part in (title, excerpt, article_text, f"מקור: {canonical_url}") if part)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()
    explicit = str(post.get("content_sha256") or "").strip()
    if explicit:
        return explicit
    if content_raw:
        return hashlib.sha256(" ".join(content_raw.split()).encode("utf-8")).hexdigest()
    return ""


def is_controller_adoptable_post(
    post: dict[str, Any],
    *,
    state_slug: str = "",
    state_content_sha256: str = "",
) -> bool:
    """Return True if a post is owned/adoptable by the autonomous daily controller.

    Editorial/manual posts with `controllerManaged: false` remain excluded by
    default across both catalogs. Only an exact state-disambiguated identity or
    an exact immutable `(date, slug, content_sha256)` entry in
    `REVIEWED_ADOPTABLE_POST_FREEZE_IDENTITIES` may be adopted.
    """
    if not isinstance(post, dict):
        return False
    slug = canonical_slug(post)
    post_date = str(post.get("date") or "").strip()
    if not slug or not post_date:
        return False
    if post.get("controllerManaged") is not False:
        return True
    sha = _post_source_sha256(post)
    if state_slug and state_content_sha256 and slug == state_slug and sha == state_content_sha256:
        return True
    return (post_date, slug, sha) in REVIEWED_ADOPTABLE_POST_FREEZE_IDENTITIES


def today_articles(
    posts: list[dict[str, Any]],
    day: date,
    *,
    state_slug: str = "",
    state_content_sha256: str = "",
) -> list[dict[str, Any]]:
    """Return same-day articles owned by the autonomous daily controller.

    Editorial/manual publications may legitimately share the same public date as
    the daily autonomous article. Such posts opt out explicitly with
    `controllerManaged: false`, so the controller's one-article-per-cycle
    invariant applies only to controller-managed or explicitly reviewed
    post-freeze recovery publications.
    """
    expected = day.isoformat()
    return [
        post for post in posts
        if isinstance(post, dict)
        and str(post.get("date") or "").strip() == expected
        and is_controller_adoptable_post(
            post,
            state_slug=state_slug,
            state_content_sha256=state_content_sha256,
        )
    ]


def merge_catalog_posts(primary: Any, secondary: Any = None) -> list[dict[str, Any]]:
    """Combine posts.json and postsRecent.json into one logical catalog deduplicated by canonical slug/id.

    Never rewrites `controllerManaged: false` on any post.
    """
    primary_list = [p for p in primary if isinstance(p, dict)] if isinstance(primary, list) else []
    secondary_list = [p for p in secondary if isinstance(p, dict)] if isinstance(secondary, list) else []

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for catalog in (primary_list, secondary_list):
        for post in catalog:
            key = canonical_slug(post)
            if key:
                if key in seen:
                    continue
                seen.add(key)
            rows.append(copy.deepcopy(post))
    return rows


def _validate_catalog_post_list(raw: Any, catalog_name: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ControllerError(
            f"ARTICLE_PUBLICATION_CATALOG_UNAVAILABLE: {catalog_name} is not a JSON list"
        )
    validated: list[dict[str, Any]] = []
    seen_in_catalog: set[str] = set()
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ControllerError(
                f"ARTICLE_PUBLICATION_CATALOG_UNAVAILABLE: {catalog_name}[{idx}] is not an object"
            )
        slug = canonical_slug(item)
        if not slug:
            raise ControllerError(
                f"ARTICLE_PUBLICATION_CATALOG_UNAVAILABLE: {catalog_name}[{idx}] missing canonical slug/id"
            )
        raw_date = str(item.get("date") or "").strip()
        try:
            date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ControllerError(
                f"ARTICLE_PUBLICATION_CATALOG_UNAVAILABLE: {catalog_name}[{idx}] invalid date {raw_date!r}"
            ) from exc
        if slug in seen_in_catalog:
            raise ControllerError(
                f"ARTICLE_PUBLICATION_CATALOG_UNAVAILABLE: duplicate slug {slug!r} in {catalog_name}"
            )
        seen_in_catalog.add(slug)
        validated.append(item)
    return validated


def posts_on_main(github: Any, ref: str = "main") -> list[dict[str, Any]]:
    """Read unified publication catalog from posts.json and postsRecent.json (fail-closed)."""
    try:
        posts_raw = github.contents_json("src/data/posts.json", ref)
        recent_raw = github.contents_json("src/data/postsRecent.json", ref)
    except Exception as exc:
        if isinstance(exc, ControllerError) and str(exc).startswith("ARTICLE_PUBLICATION_CATALOG_UNAVAILABLE"):
            raise
        raise ControllerError(
            f"ARTICLE_PUBLICATION_CATALOG_UNAVAILABLE: failed reading unified catalog at {ref}: {exc}"
        ) from exc

    posts = _validate_catalog_post_list(posts_raw, "src/data/posts.json")
    recent = _validate_catalog_post_list(recent_raw, "src/data/postsRecent.json")
    primary_slugs = {canonical_slug(p) for p in posts}
    recent_slugs = {canonical_slug(p) for p in recent}
    overlap = sorted(primary_slugs & recent_slugs)
    if overlap:
        raise ControllerError(
            f"ARTICLE_PUBLICATION_CATALOG_UNAVAILABLE: duplicate slug(s) across posts.json and postsRecent.json: {', '.join(overlap)}"
        )
    return merge_catalog_posts(posts, recent)


def article_is_public(
    html_text: str,
    expected_title: str,
    expected_slug: str | None = None,
    expected_content_sha256: str | None = None,
    expected_hero_path: str | None = None,
    expected_hero_sha256: str | None = None,
    hero_fetcher: Any | None = None,
) -> bool:
    page = re.sub(r"\s+", " ", html_text)
    title = re.sub(r"\s+", " ", expected_title.strip())
    if not title or title not in page:
        return False

    if expected_slug:
        slug = expected_slug.strip()
        expected_url = f"{SITE_URL}/blog/{slug}".rstrip("/")
        canonical_match = re.search(
            r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']|<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']',
            html_text,
            re.IGNORECASE,
        )
        if not canonical_match:
            return False
        canonical_url = (canonical_match.group(1) or canonical_match.group(2) or "").strip()
        if not canonical_url or canonical_url.rstrip("/") != expected_url:
            return False

        og_match = re.search(
            r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']|<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:url["\']',
            html_text,
            re.IGNORECASE,
        )
        if og_match:
            og_url = (og_match.group(1) or og_match.group(2) or "").strip()
            if not og_url or og_url.rstrip("/") != expected_url:
                return False

    if expected_content_sha256:
        expected_sha = expected_content_sha256.strip().lower()
        meta_sha_match = re.search(
            r'<meta[^>]+(?:name|property)=["\'](?:kesher:content-sha256|content-sha256)["\'][^>]+content=["\']([^"\']+)["\']|<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\'](?:kesher:content-sha256|content-sha256)["\']',
            html_text,
            re.IGNORECASE,
        )
        meta_sha = ""
        if meta_sha_match:
            meta_sha = (meta_sha_match.group(1) or meta_sha_match.group(2) or "").strip().lower()

        data_sha_match = re.search(
            r'data-content-sha256=["\']([^"\']+)["\']',
            html_text,
            re.IGNORECASE,
        )
        data_sha = data_sha_match.group(1).strip().lower() if data_sha_match else ""
        observed_shas = [value for value in (meta_sha, data_sha) if value]
        if not observed_shas or any(value != expected_sha for value in observed_shas):
            return False

    if expected_hero_path:
        hero = expected_hero_path.strip()
        if hero not in html_text:
            return False
        og_img_match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']|<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            html_text,
            re.IGNORECASE,
        )
        if og_img_match:
            og_img = (og_img_match.group(1) or og_img_match.group(2) or "").strip()
            if hero not in og_img:
                return False

        if expected_hero_sha256:
            expected_h_sha = expected_hero_sha256.strip().lower()
            hero_url = hero if hero.startswith(("http://", "https://")) else f"{SITE_URL}/{hero.lstrip('/')}"
            try:
                if hero_fetcher is not None:
                    if callable(hero_fetcher):
                        fetch_res = hero_fetcher(hero_url)
                    elif hasattr(hero_fetcher, "get_bytes"):
                        fetch_res = hero_fetcher.get_bytes(hero_url)
                    elif hasattr(hero_fetcher, "get"):
                        fetch_res = hero_fetcher.get(hero_url)
                    else:
                        return False
                    if isinstance(fetch_res, tuple) and len(fetch_res) == 2:
                        status, data = fetch_res
                    else:
                        status, data = 200, fetch_res
                    hero_bytes = data.encode("utf-8") if isinstance(data, str) else data
                else:
                    req = urllib.request.Request(
                        hero_url,
                        headers={"User-Agent": "Kesher-Content-Controller/2.0"},
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        status = int(resp.status)
                        hero_bytes = resp.read()
                if status != 200 or not hero_bytes:
                    return False
                actual_h_sha = hashlib.sha256(hero_bytes).hexdigest().lower()
                if actual_h_sha != expected_h_sha:
                    return False
            except Exception:
                return False

    return True


def verified_youtube_item(item: dict[str, Any], slug: str) -> bool:
    source = item.get("source") or {}
    source_slug = str(source.get("slug") or source.get("id") or "").strip()
    verification = item.get("youtube_verification") or {}
    return bool(
        source_slug == slug
        and item.get("uploaded") is True
        and item.get("status") == "uploaded"
        and item.get("youtube_id")
        and item.get("youtube_url")
        and verification.get("channel_id") == YOUTUBE_CHANNEL_ID
        and verification.get("privacy_status") == "public"
        and verification.get("processing_status") == "succeeded"
    )


def mandatory_video_review_approved(item: dict[str, Any]) -> bool:
    statuses = [item.get(f"{gate}_review_status") for gate in ("visual", "semantic", "metadata")]
    reviewer = item.get("reviewer") or {}
    return bool(
        item.get("technical_verified") is True
        and item.get("status") in {"approved", "uploading"}
        and statuses == ["approved", "approved", "approved"]
        and reviewer.get("type") == "jules"
        and reviewer.get("session")
        and item.get("reviewed_at")
    )


def matching_video_items(video_state: dict[str, Any], slug: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for item in video_state.get("items") or []:
        if not isinstance(item, dict):
            continue
        source = item.get("source") or {}
        source_slug = str(source.get("slug") or source.get("id") or "").strip()
        if source_slug == slug:
            matches.append(item)
    return matches


def _stage_defaults() -> dict[str, Any]:
    return {
        "failure_count_by_type": {},
        "failure_fingerprint": None,
        "same_failure_streak": 0,
        "next_retry_at": None,
        "processed_run_id": None,
    }


def new_cycle_state(day: date, old: dict[str, Any] | None = None) -> dict[str, Any]:
    history = list((old or {}).get("history") or [])[-80:]
    backlog = list((old or {}).get("backlog") or [])
    completed_archive = copy.deepcopy(list((old or {}).get("completed_cycle_archive") or []))
    # Completed cycles need not remain runnable backlog, but their exact public
    # media proof must survive while an independent code correction is reviewed.
    for completed in list((old or {}).get("owner_cycle_archive") or []) + ([old] if isinstance(old, dict) else []):
        if not isinstance(completed, dict) or completed.get("status") != "complete" or not completed.get("cycle"):
            continue
        article = completed.get("article") or {}
        snapshot = {key: copy.deepcopy(completed.get(key) or {}) for key in ("article", "long_video", "short")}
        snapshot.update(cycle=completed["cycle"], status="complete", archived_at=utc_now())
        snapshot["owner_idea_ids"] = sorted(set(completed.get("owner_idea_ids") or []) | {
            row["idea_id"] for row in (old or {}).get("idea_history", [])
            if isinstance(row, dict) and row.get("idea_id") and row.get("status") == "complete"
            and (row.get("outputs") or {}).get("slug") == article.get("slug")
        })
        identity = lambda row: (row.get("cycle"), (row.get("article") or {}).get("slug"),
                                (row.get("article") or {}).get("quality_content_sha256"),
                                (row.get("article") or {}).get("pr_number"))
        completed_archive = [row for row in completed_archive if identity(row) != identity(snapshot)]
        completed_archive.append(snapshot)
    if isinstance(old, dict) and old.get("cycle") and old.get("cycle") != day.isoformat():
        prev_article = old.get("article") if isinstance(old.get("article"), dict) else {}
        prev_long = old.get("long_video") if isinstance(old.get("long_video"), dict) else (old.get("video") if isinstance(old.get("video"), dict) else {})
        prev_short = old.get("short") if isinstance(old.get("short"), dict) else {}
        prev_status = str(old.get("status") or "")

        article_delivered = bool(
            prev_article.get("public") is True
            or prev_article.get("live") is True
            or prev_article.get("status") in {"verified", "published"}
        )
        long_delivered = bool(
            prev_long.get("public") is True
            or bool(prev_long.get("youtube_id"))
            or prev_long.get("status") == "completed"
        )
        short_delivered = bool(
            prev_short.get("public") is True
            or bool(prev_short.get("youtube_id"))
            or prev_short.get("status") == "completed"
        )
        full_delivered = bool(
            prev_status == "complete"
            and article_delivered
            and long_delivered
            and short_delivered
        )

        has_prior_activity = bool(
            prev_article.get("slug")
            or prev_article.get("pr_number")
            or prev_article.get("last_jules_session_id")
            or int(prev_article.get("attempts") or 0) > 0
            or prev_status in {"article_live", "blocked", "video_needed", "long_video_needed", "short_needed", "exhausted"}
            or prev_long.get("run_id")
            or prev_short.get("run_id")
        )

        # A prior cycle may be omitted from backlog ONLY when the complete required contract is proven:
        # Article public exact identity AND Long public exact identity AND Short public exact identity.
        if not full_delivered and has_prior_activity:
            backlog.append({
                "cycle": old.get("cycle"),
                "status": prev_status,
                "exact_slug": prev_article.get("slug"),
                "content_sha256": prev_article.get("content_sha256"),
                "article": copy.deepcopy(prev_article),
                "long_video": copy.deepcopy(prev_long),
                "short": copy.deepcopy(prev_short),
                "media_identities": {
                    "long_video_id": prev_long.get("youtube_id"),
                    "short_video_id": prev_short.get("youtube_id"),
                },
                "counters": {
                    "article_attempts": prev_article.get("attempts", 0),
                    "article_generation_attempts": prev_article.get("generation_attempts", 0),
                    "merge_dispatch_count": prev_article.get("merge_dispatch_count", 0),
                    "deploy_attempts": prev_article.get("deploy_attempts", 0),
                    "long_attempts": prev_long.get("attempts", 0),
                    "short_attempts": prev_short.get("attempts", 0),
                },
                "terminal_state": {
                    "blocked": prev_status == "blocked",
                    "article_exhausted": prev_article.get("status") == "exhausted",
                },
                "archived_at": utc_now(),
            })
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "cycle": day.isoformat(),
        "status": "article_needed",
        "article": {
            "attempts": 0,
            "deploy_attempts": 0,
            **_stage_defaults(),
        },
        "video": {
            "attempts": 0,
            "resume_dispatches": 0,
            **_stage_defaults(),
        },
        "backlog": backlog[-20:],
        "completed_cycle_archive": completed_archive[-20:],
        "last_error": None,
        "history": history,
        "updated_at": utc_now(),
    }


def migrate_same_cycle_state(existing: dict[str, Any], day: date) -> dict[str, Any]:
    migrated = new_cycle_state(day, existing)
    migrated["status"] = str(existing.get("status") or "article_needed")
    for stage in ("article", "video"):
        source = existing.get(stage) or {}
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            migrated[stage][key] = value
        for key, value in _stage_defaults().items():
            migrated[stage].setdefault(key, value)
    migrated["article"].setdefault("attempts", 0)
    migrated["article"].setdefault("deploy_attempts", 0)
    migrated["video"].setdefault("attempts", 0)
    migrated["video"].setdefault("resume_dispatches", 0)
    migrated["last_error"] = existing.get("last_error")
    migrated["updated_at"] = utc_now()
    migrated.setdefault("history", []).append({
        "at": utc_now(),
        "from": existing.get("status"),
        "to": migrated["status"],
        "reason": "controller state migrated to schema v2",
    })
    migrated["history"] = migrated["history"][-100:]
    return migrated


def has_unresolved_media_blocker(state: dict[str, Any]) -> bool:
    """Return True if an unresolved authoritative media blocker controls global state."""
    last_error = state.get("last_error") or {}
    stage = str(last_error.get("stage") or "")
    if stage in {"long_video", "short", "video", "media", "image"} and state.get("status") == "blocked":
        return True
    for stage_key in ("long_video", "short", "video", "image"):
        stage_state = state.get(stage_key) or {}
        if isinstance(stage_state, dict) and stage_state.get("status") in {"blocked", "exhausted"}:
            return True
    return False


def transition(state: dict[str, Any], status: str, reason: str, **details: Any) -> None:
    if has_unresolved_media_blocker(state) and status in {
        "article_live", "complete", "waiting_for_article_window", "article_deploying", "article_generating"
    }:
        state["updated_at"] = utc_now()
        return

    previous = state.get("status")
    if previous != status or details:
        event: dict[str, Any] = {
            "at": utc_now(), "from": previous, "to": status, "reason": reason,
        }
        if details:
            event["details"] = details
        state.setdefault("history", []).append(event)
        state["history"] = state["history"][-100:]
    state["status"] = status
    state["updated_at"] = utc_now()
    state["last_error"] = None


def block(state: dict[str, Any], stage: str, code: str, message: str) -> None:
    previous = state.get("status")
    state["status"] = "blocked"
    state["last_error"] = {
        "stage": stage, "code": code, "message": message, "at": utc_now(),
    }
    state.setdefault("history", []).append({
        "at": utc_now(), "from": previous, "to": "blocked", "reason": code,
        "details": {"message": message},
    })
    state["history"] = state["history"][-100:]
    state["updated_at"] = utc_now()


def retry_ready(stage_state: dict[str, Any], now: datetime) -> bool:
    retry_at = parse_timestamp(stage_state.get("next_retry_at"))
    return retry_at is None or now.astimezone(timezone.utc) >= retry_at


def record_retryable_failure(
    state: dict[str, Any],
    stage: str,
    code: str,
    message: str,
    *,
    run_id: Any = None,
    session_id: Any = None,
    minimum_minutes: int | None = None,
) -> None:
    stage_state = state[stage]
    counts = stage_state.setdefault("failure_count_by_type", {})
    counts[code] = int(counts.get(code) or 0) + 1
    if stage_state.get("failure_fingerprint") == code:
        streak = int(stage_state.get("same_failure_streak") or 0) + 1
    else:
        streak = 1
    stage_state["failure_fingerprint"] = code
    stage_state["same_failure_streak"] = streak
    delay = article_retry_backoff_minutes(streak)
    if minimum_minutes is not None:
        delay = max(delay, int(minimum_minutes))
    retry_at = datetime.now(timezone.utc) + timedelta(minutes=delay)
    stage_state["next_retry_at"] = retry_at.isoformat()
    if run_id:
        stage_state["last_failed_run_id"] = run_id
    if session_id:
        stage_state["last_jules_session_id"] = session_id
    previous = state.get("status")
    status = f"{stage}_retry_wait"
    state["status"] = status
    state["last_error"] = {
        "stage": stage,
        "code": code,
        "message": message,
        "retryable": True,
        "retry_at": stage_state["next_retry_at"],
        "at": utc_now(),
    }
    state.setdefault("history", []).append({
        "at": utc_now(), "from": previous, "to": status, "reason": code,
        "details": {
            "message": message,
            "retry_at": stage_state["next_retry_at"],
            "failure_streak": streak,
            "run_id": run_id,
            "session_id": session_id,
        },
    })
    state["history"] = state["history"][-100:]
    state["updated_at"] = utc_now()


def clear_failure(stage_state: dict[str, Any]) -> None:
    stage_state["failure_fingerprint"] = None
    stage_state["same_failure_streak"] = 0
    stage_state["next_retry_at"] = None


def article_window_open(now: datetime, saturday_sunset: datetime | None = None) -> bool:
    local = now.astimezone(ISRAEL_TZ)
    weekday = local.isoweekday()
    clock = local.timetz().replace(tzinfo=None)
    if weekday in {7, 1, 2, 3, 4}:  # Sunday-Thursday
        return clock >= dt_time(0, 35)
    if weekday == 5:  # Friday
        return clock >= dt_time(8, 0)
    if weekday == 6:
        if saturday_sunset is None:
            return False
        return local >= saturday_sunset.astimezone(ISRAEL_TZ) + timedelta(hours=1)
    return False


class GitHubClient:
    def __init__(self, repo: str, token: str):
        self.repo = repo
        self.token = token
        self.api = f"https://api.github.com/repos/{repo}"
        self._controller_state_loaded = False
        self._controller_state_sha: str | None = None
        self._controller_state_document: dict[str, Any] | None = None

    def request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
        *,
        raw: bool = False,
        allow_404: bool = False,
    ) -> Any:
        from scripts.kesher_runtime.legacy_retirement import github_mutation
        github_mutation(self.repo, method, url)
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        last: Exception | None = None
        # A lost response to a mutation does not prove the server rejected it.
        # The command owner must reconcile before retrying a dispatch/write.
        read_only = method.upper() in {"GET", "HEAD"}
        for attempt in range(4 if read_only else 1):
            request = urllib.request.Request(
                url, data=data, method=method,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                    "User-Agent": "kesher-content-controller",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    payload = response.read()
                    if raw:
                        return payload
                    return json.loads(payload.decode("utf-8")) if payload else {}
            except urllib.error.HTTPError as exc:
                if allow_404 and exc.code == 404:
                    return None
                detail = exc.read().decode("utf-8", errors="replace")[:1500]
                if exc.code not in {429, 500, 502, 503, 504}:
                    raise ControllerError(
                        f"GITHUB_HTTP_{exc.code}: {method} {url} failed: {detail}"
                    ) from exc
                if not read_only:
                    raise ControllerError(
                        f"GITHUB_MUTATION_UNCERTAIN: {method} {url} HTTP {exc.code}; reconcile before retry"
                    ) from exc
                last = exc
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if not read_only:
                    raise ControllerError(
                        f"GITHUB_MUTATION_UNCERTAIN: {method} {url}; reconcile before retry"
                    ) from exc
                last = exc
            time.sleep(2 ** attempt)
        raise ControllerError(f"GITHUB_TRANSIENT_FAILURE: {method} {url}: {last}")

    def download_artifact_archive(self, url: str) -> bytes:
        """Download an Actions artifact without forwarding GitHub auth to signed blob storage."""

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirect())
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "kesher-content-controller",
        }
        last: Exception | None = None
        for attempt in range(4):
            request = urllib.request.Request(url, method="GET", headers=headers)
            try:
                with opener.open(request, timeout=45) as response:
                    return response.read()
            except urllib.error.HTTPError as exc:
                if exc.code in {301, 302, 303, 307, 308}:
                    location = exc.headers.get("Location")
                    if not location:
                        raise ControllerError("GITHUB_ARTIFACT_REDIRECT_MISSING") from exc
                    signed_request = urllib.request.Request(
                        location,
                        method="GET",
                        headers={"User-Agent": "kesher-content-controller"},
                    )
                    try:
                        # Video-state artifacts can temporarily be very large. A
                        # socket read timeout is transient evidence, not a broken
                        # state artifact, so give the signed blob enough time and
                        # retry the same immutable archive before falling back.
                        with urllib.request.urlopen(signed_request, timeout=120) as response:
                            return response.read()
                    except (
                        urllib.error.HTTPError,
                        urllib.error.URLError,
                        TimeoutError,
                    ) as signed_exc:
                        last = signed_exc
                elif exc.code in {429, 500, 502, 503, 504}:
                    last = exc
                else:
                    detail = exc.read().decode("utf-8", errors="replace")[:1000]
                    raise ControllerError(
                        f"GITHUB_ARTIFACT_HTTP_{exc.code}: artifact download failed: {detail}"
                    ) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                # response.read() may raise the built-in TimeoutError directly
                # rather than wrapping it in URLError. Keep it inside the
                # bounded retry/fallback path instead of crashing Controller V5.
                last = exc
            time.sleep(2 ** attempt)
        raise ControllerError(f"GITHUB_ARTIFACT_DOWNLOAD_FAILED: {last}")

    def contents_json(self, path: str, ref: str = "main") -> Any:
        quoted = urllib.parse.quote(path, safe="/")
        payload = self.request(
            "GET", f"{self.api}/contents/{quoted}?ref={urllib.parse.quote(ref, safe='')}"
        )
        if not isinstance(payload, dict):
            raise ControllerError(f"GITHUB_CONTENT_INVALID: {path}@{ref}")

        encoding = payload.get("encoding")
        content = payload.get("content") or ""
        if encoding == "base64" and content:
            raw = base64.b64decode(content)
        else:
            # GitHub Contents API may omit inline content for large files.
            # Fall back to the immutable blob referenced by the same payload.
            blob_sha = str(payload.get("sha") or "").strip()
            if not blob_sha:
                raise ControllerError(f"GITHUB_CONTENT_INVALID: {path}@{ref}")
            blob = self.request("GET", f"{self.api}/git/blobs/{blob_sha}")
            if not isinstance(blob, dict) or blob.get("encoding") != "base64" or not blob.get("content"):
                raise ControllerError(f"GITHUB_CONTENT_INVALID: {path}@{ref}")
            raw = base64.b64decode(blob["content"])

        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ControllerError(f"GITHUB_CONTENT_INVALID: {path}@{ref}") from exc

    def posts_on_main(self, ref: str = "main") -> list[dict[str, Any]]:
        return posts_on_main(self, ref)

    def open_article_prs(self, target_slot: str | None = None) -> list[dict[str, Any]]:
        prs = self.request("GET", f"{self.api}/pulls?state=open&per_page=100")
        if not isinstance(prs, list):
            raise ControllerError("GITHUB_PRS_INVALID")
        matches: list[dict[str, Any]] = []
        for pr in prs:
            if not isinstance(pr, dict):
                continue
            number = pr.get("number")
            title = str(pr.get("title") or "").strip()
            if not number:
                continue
            # Article publication PRs must be titled 'Publish Kesher article: ...'
            if not title.startswith("Publish Kesher article:"):
                continue

            files = self.request("GET", f"{self.api}/pulls/{number}/files?per_page=100")
            if not (isinstance(files, list) and any(
                isinstance(row, dict) and row.get("filename") == "src/data/posts.json"
                for row in files
            )):
                continue

            if target_slot:
                head_sha = str((pr.get("head") or {}).get("sha") or "")
                base_sha = str((pr.get("base") or {}).get("sha") or "main")
                try:
                    base_posts = self.contents_json("src/data/posts.json", base_sha)
                    head_posts = self.contents_json("src/data/posts.json", head_sha)
                    if isinstance(base_posts, list) and isinstance(head_posts, list):
                        base_ids = {canonical_slug(row) for row in base_posts if isinstance(row, dict)}
                        new_posts = [
                            row for row in head_posts
                            if isinstance(row, dict) and canonical_slug(row) not in base_ids
                        ]
                        if not any(str(row.get("date") or "").strip() == target_slot for row in new_posts):
                            continue
                except ControllerError:
                    pass

            matches.append(pr)
        return matches

    def workflow_runs(self, workflow: str, limit: int = 20) -> list[dict[str, Any]]:
        name = urllib.parse.quote(workflow, safe="")
        payload = self.request(
            "GET", f"{self.api}/actions/workflows/{name}/runs?per_page={limit}"
        )
        if not isinstance(payload, dict):
            return []
        return [row for row in payload.get("workflow_runs") or [] if isinstance(row, dict)]

    def workflow_run_by_id(self, run_id: int | str) -> dict[str, Any] | None:
        payload = self.request("GET", f"{self.api}/actions/runs/{run_id}", allow_404=True)
        return payload if isinstance(payload, dict) else None

    def active_workflow_run(
        self, workflow: str, *, production_only: bool = False
    ) -> dict[str, Any] | None:
        for run in self.workflow_runs(workflow):
            if production_only and str(run.get("event") or "") == "pull_request":
                continue
            if str(run.get("status") or "") in ACTIVE_RUN_STATUSES:
                return run
        return None

    def dispatch(self, workflow: str, inputs: dict[str, str] | None = None) -> None:
        body: dict[str, Any] = {"ref": "main"}
        if inputs:
            body["inputs"] = inputs
        name = urllib.parse.quote(workflow, safe="")
        self.request("POST", f"{self.api}/actions/workflows/{name}/dispatches", body)

    def article_result_for_run(self, run_id: int | str) -> dict[str, Any] | None:
        payload = self.request("GET", f"{self.api}/actions/runs/{run_id}/artifacts?per_page=100")
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
        expected_name = f"{ARTICLE_RESULT_ARTIFACT_PREFIX}{run_id}"
        candidates = [
            row for row in (artifacts or [])
            if isinstance(row, dict)
            and row.get("name") == expected_name
            and not row.get("expired")
            and row.get("archive_download_url")
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        raw = self.download_artifact_archive(str(candidates[0]["archive_download_url"]))
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                names = [name for name in archive.namelist() if name.endswith("result.json")]
                if len(names) != 1:
                    return None
                result = json.loads(archive.read(names[0]).decode("utf-8"))
        except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, KeyError):
            return None
        if not isinstance(result, dict) or result.get("schema_version") != 1:
            return None
        return result

    def main_sha(self) -> str:
        payload = self.request("GET", f"{self.api}/git/ref/heads/main")
        return str(((payload or {}).get("object") or {}).get("sha") or "")

    def ensure_state_ref(self) -> None:
        encoded = urllib.parse.quote(STATE_REF, safe="")
        if self.request("GET", f"{self.api}/git/ref/heads/{encoded}", allow_404=True):
            return
        sha = self.main_sha()
        if not sha:
            raise ControllerError("GITHUB_MAIN_REF_MISSING")
        self.request("POST", f"{self.api}/git/refs", {
            "ref": f"refs/heads/{STATE_REF}", "sha": sha,
        })

    def load_controller_state(self) -> dict[str, Any] | None:
        self._controller_state_loaded = False
        self._controller_state_document = None
        self.ensure_state_ref()
        quoted = urllib.parse.quote(STATE_PATH, safe="/")
        payload = self.request(
            "GET",
            f"{self.api}/contents/{quoted}?ref={urllib.parse.quote(STATE_REF, safe='')}",
            allow_404=True,
        )
        if payload is None:
            self._controller_state_sha = None
            self._controller_state_loaded = True
            return None
        if not isinstance(payload, dict) or payload.get("encoding") != "base64":
            raise ControllerError("CONTROLLER_STATE_INVALID")
        state = json.loads(base64.b64decode(payload.get("content") or "").decode("utf-8"))
        if not isinstance(state, dict):
            raise ControllerError("CONTROLLER_STATE_INVALID")
        from scripts.kesher_runtime.legacy_retirement import validate_legacy_read
        validate_legacy_read(state)
        if not payload.get("sha"):
            raise ControllerError("CONTROLLER_STATE_REVISION_MISSING")
        self._controller_state_sha = str(payload["sha"])
        self._controller_state_document = copy.deepcopy(state)
        self._controller_state_loaded = True
        return state

    def save_controller_state(self, state: dict[str, Any]) -> None:
        if not self._controller_state_loaded:
            raise ControllerError("CONTROLLER_STATE_NOT_LOADED")
        from scripts.kesher_runtime.legacy_retirement import validate_legacy_read
        validate_legacy_read(self._controller_state_document)
        validate_legacy_read(state)
        quoted = urllib.parse.quote(STATE_PATH, safe="/")
        body: dict[str, Any] = {
            "message": f"state: Kesher controller {state.get('cycle')} {state.get('status')}",
            "content": base64.b64encode(
                (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            ).decode("ascii"),
            "branch": STATE_REF,
        }
        if self._controller_state_sha is not None:
            body["sha"] = self._controller_state_sha
        # Use the revision on which this tick was based. On conflict, discard
        # its plan; rebinding this payload to a fresh SHA would lose updates.
        self._controller_state_loaded = False
        receipt = self.request("PUT", f"{self.api}/contents/{quoted}", body)
        written_sha = (receipt.get("content") or {}).get("sha") if isinstance(receipt, dict) else None
        if not written_sha:
            raise ControllerError("CONTROLLER_STATE_WRITE_RECEIPT_MISSING")
        self._controller_state_sha = str(written_sha)
        self._controller_state_document = copy.deepcopy(state)
        self._controller_state_loaded = True

    def newest_video_state(self) -> dict[str, Any]:
        payload = self.request(
            "GET",
            f"{self.api}/actions/artifacts?name={VIDEO_STATE_ARTIFACT}&per_page=100",
        )
        artifacts = [
            row for row in (payload.get("artifacts") or [])
            if isinstance(row, dict) and not row.get("expired")
        ] if isinstance(payload, dict) else []
        artifacts.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        failures: list[str] = []
        for artifact in artifacts:
            artifact_id = artifact.get("id") or "unknown"
            archive_url = artifact.get("archive_download_url")
            if not archive_url:
                failures.append(f"artifact {artifact_id}: missing archive_download_url")
                continue
            try:
                raw = self.download_artifact_archive(str(archive_url))
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    names = [name for name in archive.namelist() if name.endswith("state.json")]
                    if not names:
                        failures.append(f"artifact {artifact_id}: missing state.json")
                        continue
                    state = json.loads(archive.read(names[0]).decode("utf-8"))
                    if isinstance(state, dict) and isinstance(state.get("items"), list):
                        return state
                    failures.append(f"artifact {artifact_id}: unsupported state schema")
            except ControllerError as exc:
                failures.append(f"artifact {artifact_id}: {exc}")
                continue
            except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, KeyError) as exc:
                failures.append(f"artifact {artifact_id}: {type(exc).__name__}")
                continue
        if artifacts:
            detail = " | ".join(failures[-5:]) or "no valid state artifact"
            raise ControllerError(f"VIDEO_STATE_ARTIFACTS_UNRECOVERABLE: {detail}")
        return {"version": 1, "items": []}


class PublicSiteClient:
    def get(self, url: str) -> tuple[int, str]:
        request = urllib.request.Request(
            url, headers={"User-Agent": "Kesher-Content-Controller/2.0"}
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return int(response.status), response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return int(exc.code), exc.read().decode("utf-8", errors="replace")

    def get_bytes(self, url: str) -> tuple[int, bytes]:
        request = urllib.request.Request(
            url, headers={"User-Agent": "Kesher-Content-Controller/2.0"}
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return int(response.status), response.read()
        except urllib.error.HTTPError as exc:
            return int(exc.code), exc.read()
        except Exception:
            return 500, b""


def fetch_ashdod_sunset(day: date) -> datetime:
    request = urllib.request.Request(
        HEBCAL_ASHDOD_URL.format(date=day.isoformat()),
        headers={"User-Agent": "Kesher-Content-Controller/2.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except Exception as exc:
        raise ControllerError(f"HEBCAL_SUNSET_UNAVAILABLE: {exc}") from exc
    raw = ((payload or {}).get("times") or {}).get("sunset")
    if not raw:
        raise ControllerError("HEBCAL_SUNSET_MISSING")
    sunset = datetime.fromisoformat(str(raw))
    if sunset.tzinfo is None:
        sunset = sunset.replace(tzinfo=ISRAEL_TZ)
    return sunset.astimezone(ISRAEL_TZ)


class Controller:
    def __init__(
        self,
        github: GitHubClient,
        site: PublicSiteClient,
        *,
        now: datetime | None = None,
        saturday_sunset: datetime | None = None,
    ):
        self.github = github
        self.site = site
        self.now = (now or datetime.now(ISRAEL_TZ)).astimezone(ISRAEL_TZ)
        self.saturday_sunset = saturday_sunset
        self.policy = load_policy()

    def state(self) -> dict[str, Any]:
        existing = self.github.load_controller_state()
        today = self.now.date()
        if not isinstance(existing, dict) or existing.get("cycle") != today.isoformat():
            return new_cycle_state(today, existing)
        if existing.get("schema_version") != STATE_SCHEMA_VERSION:
            return migrate_same_cycle_state(existing, today)
        for stage in ("article", "video"):
            existing.setdefault(stage, {})
            for key, value in _stage_defaults().items():
                existing[stage].setdefault(key, value)
        return existing

    def article_slot_open(self) -> bool:
        sunset = self.saturday_sunset
        if self.now.isoweekday() == 6 and sunset is None:
            sunset = fetch_ashdod_sunset(self.now.date())
        return article_window_open(self.now, sunset)

    def posts_on_main(self, ref: str = "main") -> list[dict[str, Any]]:
        getter = getattr(self.github, "posts_on_main", None)
        if callable(getter):
            return getter(ref)
        return posts_on_main(self.github, ref)

    def posts_for_cycle(self, cycle: str | date | None = None, *, ref: str = "main") -> list[dict[str, Any]]:
        target = self.now.date() if cycle is None else (
            cycle if isinstance(cycle, date) else date.fromisoformat(str(cycle).strip())
        )
        return today_articles(self.posts_on_main(ref), target)

    def _posts_for_date(
        self,
        cycle: str | date,
        posts: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        expected = cycle.isoformat() if isinstance(cycle, date) else str(cycle).strip()
        catalog = self.posts_on_main("main") if posts is None else posts
        return [
            post for post in catalog
            if isinstance(post, dict)
            and str(post.get("date") or "").strip() == expected
            and canonical_slug(post)
        ]

    def tick(self) -> tuple[dict[str, Any], Action]:
        state = self.state()
        try:
            action = self._tick(state)
        except ControllerError as exc:
            code = str(exc).split(":", 1)[0]
            block(state, "controller", code, str(exc))
            action = Action("blocked", str(exc))
        self.github.save_controller_state(state)
        return state, action

    def _workflow_run(self, run_id: Any) -> dict[str, Any] | None:
        getter = getattr(self.github, "workflow_run_by_id", None)
        if not run_id or getter is None:
            return None
        return getter(run_id)

    def _article_result(self, run_id: Any) -> dict[str, Any] | None:
        getter = getattr(self.github, "article_result_for_run", None)
        if not run_id or getter is None:
            return None
        return getter(run_id)

    def _reconcile_existing_current_day_article(
        self,
        state: dict[str, Any],
        posts: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        if posts is None:
            posts = self.posts_on_main("main")
        article_state = state.setdefault("article", {})
        state_slug = str(article_state.get("slug") or "").strip()
        state_sha = str(article_state.get("quality_content_sha256") or "").strip()
        todays = today_articles(
            posts,
            self.now.date(),
            state_slug=state_slug,
            state_content_sha256=state_sha,
        )

        if len(todays) == 1:
            post = todays[0]
            slug = canonical_slug(post)
            title = str(post.get("title") or "").strip()
            url = f"{SITE_URL}/blog/{slug}"
            sha = _post_source_sha256(post)
            article_state.update({
                "slug": slug,
                "title": title,
                "url": url,
                "published_date": str(post.get("date") or ""),
            })
            if sha:
                article_state["quality_content_sha256"] = sha
            worker_outcome = str((article_state.get("last_worker_result") or {}).get("outcome") or "")
            last_error_stage = str((state.get("last_error") or {}).get("stage") or "")
            if (
                article_state.get("status") in {"running", "retry_wait", "failed", "exhausted", "blocked"}
                or article_state.get("last_error")
                or last_error_stage in {"article", "image"}
                or worker_outcome == "ARTICLE_ALREADY_PUBLISHED"
                or state.get("status") in {"blocked", "article_retry_wait", "article_generating"}
            ):
                clear_failure(article_state)
                article_state["last_error"] = None
                article_state["next_retry_at"] = None
                article_state["failure_fingerprint"] = None
                article_state["same_failure_streak"] = 0
                article_state["attempt_count"] = 0
                article_state["attempts"] = 0
                article_state["reconciled_existing_article"] = True
                if article_state.get("status") in {"running", "retry_wait", "failed", "exhausted", "blocked"}:
                    article_state["status"] = "complete" if article_state.get("live") is True else "pending"
                post_image = str(post.get("image") or post.get("hero_image") or "").strip()
                if post_image:
                    image_state = state.setdefault("image", {})
                    clear_failure(image_state)
                    image_state["status"] = "complete"
                    image_state["last_error"] = None
                    image_state["next_retry_at"] = None
                    image_state["image_path"] = post_image
                if last_error_stage in {"article", "image"}:
                    state["last_error"] = None
                    if state.get("status") in {"blocked", "article_retry_wait", "article_generating"}:
                        state["status"] = "article_live" if article_state.get("live") is True else "article_deploying" if article_state.get("status") == "deploying" else "article_needed"
                elif article_state.get("last_error") or worker_outcome == "ARTICLE_ALREADY_PUBLISHED":
                    if state.get("status") in {"article_retry_wait", "article_generating"}:
                        state["status"] = "article_live" if article_state.get("live") is True else "article_deploying" if article_state.get("status") == "deploying" else "article_needed"
        return todays

    def _reconcile_completed_article_run(self, state: dict[str, Any]) -> Action | None:
        article_state = state["article"]
        run_id = article_state.get("run_id")
        if not run_id or article_state.get("processed_run_id") == run_id:
            return None
        run = self._workflow_run(run_id)
        if not run or str(run.get("status") or "") != "completed":
            return None

        article_state["processed_run_id"] = run_id
        article_state["last_run_conclusion"] = run.get("conclusion")
        result = self._article_result(run_id)
        if result:
            article_state["last_worker_result"] = result
            session_id = result.get("session_id")
            if session_id:
                article_state["last_jules_session_id"] = session_id
            outcome = str(result.get("outcome") or "ARTICLE_RESULT_INVALID")
            if outcome == "ARTICLE_ALREADY_PUBLISHED":
                clear_failure(article_state)
                article_state["last_error"] = None
                article_state["next_retry_at"] = None
                article_state["reconcile_already_published"] = True
                article_state["attempts"] = max(0, int(article_state.get("attempts") or 0) - 1)
                if "attempt_count" in article_state:
                    article_state["attempt_count"] = max(0, int(article_state.get("attempt_count") or 0) - 1)
                result_slug = str(result.get("slug") or "").strip()
                if result_slug:
                    article_state["slug"] = result_slug
                if isinstance(state.get("last_error"), dict) and state["last_error"].get("stage") == "article":
                    state["last_error"] = None
                adopted = self._reconcile_existing_current_day_article(state)
                if len(adopted) == 1:
                    transition(
                        state,
                        "article_reconciled",
                        "article worker reported ARTICLE_ALREADY_PUBLISHED; adopted published article without strike",
                        run_id=run_id,
                        outcome=outcome,
                        slug=article_state.get("slug"),
                    )
                    return None
                article_state["next_retry_at"] = (
                    datetime.now(timezone.utc) + timedelta(minutes=2)
                ).isoformat()
                transition(
                    state,
                    "article_result_wait",
                    "article worker reported progress; waiting for GitHub/main reconciliation",
                    run_id=run_id,
                    outcome=outcome,
                    pr_url=result.get("pr_url"),
                )
                return Action("wait", f"article worker outcome {outcome}; reconciling reality")
            if outcome in {"PR_CREATED", "ARTICLE_ALREADY_IN_PROGRESS"}:
                clear_failure(article_state)
                article_state["next_retry_at"] = (
                    datetime.now(timezone.utc) + timedelta(minutes=2)
                ).isoformat()
                transition(
                    state,
                    "article_result_wait",
                    "article worker reported progress; waiting for GitHub/main reconciliation",
                    run_id=run_id,
                    outcome=outcome,
                    pr_url=result.get("pr_url"),
                )
                return Action("wait", f"article worker outcome {outcome}; reconciling reality")
            if result.get("retryable") is True:
                record_retryable_failure(
                    state,
                    "article",
                    outcome,
                    str(result.get("message") or outcome),
                    run_id=run_id,
                    session_id=session_id,
                )
                # A Jules timeout with a preserved authoritative session is not a
                # reason to wait for another scheduler heartbeat. Relaunch the
                # bounded worker immediately; acquire_session() will adopt the
                # exact same slot/session and therefore cannot create a duplicate
                # article identity. This closes the gap where a completed worker
                # could sit in article_retry_wait for hours if scheduled ticks
                # were delayed or queued.
                if outcome == "JULES_TIMEOUT_SESSION_ACTIVE" and session_id:
                    inputs = {"slot": self.now.date().isoformat()}
                    self.github.dispatch(ARTICLE_WORKFLOW, inputs)
                    article_state["resume_dispatches"] = int(
                        article_state.get("resume_dispatches") or 0
                    ) + 1
                    article_state["last_dispatch_at"] = utc_now()
                    article_state["next_retry_at"] = None
                    transition(
                        state,
                        "article_generating",
                        "timed-out Jules session preserved; same-session recovery dispatched immediately",
                        run_id=run_id,
                        session_id=session_id,
                    )
                    return Action(
                        "dispatch_article_recovery",
                        "preserved Jules session recovered immediately after worker timeout",
                        inputs,
                    )
                return Action("wait", f"retryable article failure {outcome}")
            block(state, "article", outcome, str(result.get("message") or outcome))
            return Action("blocked", f"non-retryable article failure {outcome}")

        conclusion = str(run.get("conclusion") or "unknown")
        code = "ARTICLE_RESULT_MISSING" if conclusion == "success" else "ARTICLE_WORKFLOW_FAILED"
        record_retryable_failure(
            state,
            "article",
            code,
            f"article run {run_id} completed with conclusion={conclusion} but no structured result was available",
            run_id=run_id,
        )
        return Action("wait", code)

    def _reconcile_completed_video_run(self, state: dict[str, Any]) -> None:
        video_state = state["video"]
        run_id = video_state.get("run_id")
        if not run_id or video_state.get("processed_run_id") == run_id:
            return
        run = self._workflow_run(run_id)
        if not run or str(run.get("status") or "") != "completed":
            return
        video_state["processed_run_id"] = run_id
        conclusion = str(run.get("conclusion") or "unknown")
        video_state["last_run_conclusion"] = conclusion
        if conclusion == "success":
            clear_failure(video_state)
            return
        record_retryable_failure(
            state,
            "video",
            "VIDEO_WORKFLOW_FAILED",
            f"video run {run_id} completed with conclusion={conclusion}",
            run_id=run_id,
        )

    def _tick(self, state: dict[str, Any]) -> Action:
        posts = self.posts_on_main("main")
        todays = self._reconcile_existing_current_day_article(state, posts)
        if len(todays) > 1:
            block(state, "article", "DUPLICATE_ARTICLE_DATE",
                  f"{len(todays)} articles share Israel date {self.now.date()}")
            return Action("blocked", "duplicate published articles")

        if not todays:
            # A terminal article budget is a durable tombstone for this cycle.
            # Child workflow wake-ups must never replay an older retryable worker
            # result after auto-merge/article attempts were already exhausted.
            # A real same-day article, reconciled above, still takes precedence.
            article_state = state.get("article") if isinstance(state.get("article"), dict) else {}
            last_error = state.get("last_error") if isinstance(state.get("last_error"), dict) else {}
            terminal_article_exhausted = bool(
                article_state.get("status") == "exhausted"
                or int(article_state.get("merge_dispatch_count") or 0) >= 3
                or (
                    state.get("status") == "blocked"
                    and last_error.get("stage") == "article"
                    and last_error.get("code") == "ARTICLE_ATTEMPTS_EXHAUSTED"
                )
            )
            if terminal_article_exhausted:
                message = "article cycle has durable terminal attempt exhaustion; stale worker recovery is forbidden"
                already_terminal = bool(
                    state.get("status") == "blocked"
                    and article_state.get("status") == "exhausted"
                    and last_error.get("stage") == "article"
                    and last_error.get("code") == "ARTICLE_ATTEMPTS_EXHAUSTED"
                )
                article_state["status"] = "exhausted"
                state["article"] = article_state
                if not already_terminal:
                    block(state, "article", "ARTICLE_ATTEMPTS_EXHAUSTED", message)
                return Action("blocked", message)

            if not self.article_slot_open():
                transition(state, "waiting_for_article_window", "publication slot has not opened")
                return Action("wait", "article window not open")

            open_prs = self.github.open_article_prs(self.now.date().isoformat())
            if len(open_prs) > 1:
                block(state, "article", "DUPLICATE_ARTICLE_PRS",
                      f"{len(open_prs)} open article PRs modify posts.json")
                return Action("blocked", "duplicate article PRs")
            if len(open_prs) == 1:
                pr = open_prs[0]
                state["article"].update({
                    "pr_number": pr.get("number"), "pr_url": pr.get("html_url"),
                })
                clear_failure(state["article"])
                transition(state, "article_pr_open", "existing article PR is authoritative")
                return Action("wait", "article PR already open")

            active = self.github.active_workflow_run(ARTICLE_WORKFLOW)
            if active:
                state["article"]["run_id"] = active.get("id")
                transition(state, "article_generating", "article workflow already active")
                return Action("wait", "article workflow active")

            reconciled = self._reconcile_completed_article_run(state)
            if reconciled is not None:
                return reconciled

            todays = self._reconcile_existing_current_day_article(state, posts)
            if not todays:
                if not retry_ready(state["article"], self.now):
                    retry_at = state["article"].get("next_retry_at")
                    transition(state, "article_retry_wait", "article retry backoff is active", retry_at=retry_at)
                    return Action("wait", f"article retry scheduled for {retry_at}")

                inputs = {"slot": self.now.date().isoformat()}
                self.github.dispatch(ARTICLE_WORKFLOW, inputs)
                attempts = int(state["article"].get("attempts") or 0) + 1
                state["article"].update({
                    "attempts": attempts,
                    "last_dispatch_at": utc_now(),
                    "next_retry_at": None,
                })
                transition(state, "article_generating", "single article worker attempt dispatched",
                           attempt=attempts)
                return Action("dispatch_article", "no article or PR exists and retry window is open", inputs)

        article = todays[0]
        slug = canonical_slug(article)
        title = str(article.get("title") or "").strip()
        url = f"{SITE_URL}/blog/{slug}"
        state["article"].update({
            "slug": slug, "title": title, "url": url,
            "published_date": str(article.get("date") or ""),
        })
        clear_failure(state["article"])

        content_sha = str(state["article"].get("quality_content_sha256") or "").strip()
        already_verified = bool(state["article"].pop("_tick_live_verified", None))
        if not already_verified:
            status, page = self.site.get(url)
            if status != 200 or not article_is_public(page, title, expected_slug=slug, expected_content_sha256=content_sha):
                state["article"]["live"] = False
                if self.github.active_workflow_run(DEPLOY_WORKFLOW):
                    transition(state, "article_deploying", "deployment already active")
                    return Action("wait", "deployment active")
                pending_deploy = (state.get("pending_dispatches") or {}).get(DEPLOY_WORKFLOW)
                if isinstance(pending_deploy, dict) and pending_deploy.get("cycle") == state.get("cycle"):
                    if pending_deploy.get("status") in {"intent", "uncertain"}:
                        transition(state, "article_deploying", "deployment dispatch intent pending")
                        return Action("wait", "deployment dispatch pending reconciliation")
                    if pending_deploy.get("status") == "dispatched":
                        intent_dt = parse_timestamp(pending_deploy.get("dispatched_at") or pending_deploy.get("intent_at"))
                        if intent_dt is not None:
                            elapsed = (self.now.astimezone(timezone.utc) - intent_dt).total_seconds()
                            if 0 <= elapsed < 180:
                                transition(state, "article_deploying", "deployment dispatched; waiting for run visibility")
                                return Action("wait", f"deployment dispatched {int(elapsed)}s ago; waiting for run visibility")
                next_deploy = parse_timestamp(state["article"].get("next_deploy_retry_at"))
                if next_deploy and self.now.astimezone(timezone.utc) < next_deploy:
                    transition(state, "article_deploy_wait", "deploy retry backoff is active",
                               retry_at=next_deploy.isoformat())
                    return Action("wait", f"deploy retry scheduled for {next_deploy.isoformat()}")

                current_attempts = int(state["article"].get("deploy_attempts") or 0)
                if current_attempts >= MAX_DEPLOY_ATTEMPTS or state["article"].get("deploy_status") == "exhausted":
                    state["article"]["deploy_status"] = "exhausted"
                    if state.get("status") != "blocked":
                        block(state, "article", "DEPLOY_ATTEMPTS_EXHAUSTED",
                              f"Article deployment exhausted maximum allowed attempts ({MAX_DEPLOY_ATTEMPTS})")
                    return Action("block", f"deploy attempts exhausted ({MAX_DEPLOY_ATTEMPTS})")

                attempts = current_attempts + 1
                self.github.dispatch(DEPLOY_WORKFLOW)
                delay_index = max(1, attempts - MAX_DEPLOY_ATTEMPTS_BEFORE_LONG_BACKOFF + 1)
                delay = 5 if attempts <= MAX_DEPLOY_ATTEMPTS_BEFORE_LONG_BACKOFF else article_retry_backoff_minutes(delay_index)
                state["article"].update({
                    "deploy_attempts": attempts,
                    "last_deploy_dispatch_at": utc_now(),
                    "next_deploy_retry_at": (
                        datetime.now(timezone.utc) + timedelta(minutes=delay)
                    ).isoformat(),
                })
                transition(state, "article_deploying", "public article check failed; recovery deploy dispatched",
                           http_status=status, attempt=attempts)
                return Action("dispatch_deploy", "article not public yet")

        state["article"].update({
            "live": True,
            "live_verified_at": utc_now(),
            "next_deploy_retry_at": None,
        })
        transition(state, "article_live", "HTTP 200 and expected title verified")

        video_state = self.github.newest_video_state()
        matches = matching_video_items(video_state, slug)
        verified = [item for item in matches if verified_youtube_item(item, slug)]
        if has_unresolved_media_blocker(state) and not verified:
            return Action("blocked", (state.get("last_error") or {}).get("message") or "media stage blocked")
        if verified:
            item = sorted(
                verified,
                key=lambda row: str(row.get("uploaded_at") or row.get("updated_at") or ""),
                reverse=True,
            )[0]
            state["video"].update({
                "item_id": item.get("id"), "status": "uploaded",
                "youtube_id": item.get("youtube_id"), "youtube_url": item.get("youtube_url"),
                "verified": True,
            })
            clear_failure(state["video"])
            transition(state, "complete", "public article and YouTube video verified")
            return Action("complete", "public article and video verified")

        active_matches = [
            item for item in matches
            if item.get("status") in ACTIVE_VIDEO_STATUSES or item.get("status") == "rejected"
        ]
        if len(active_matches) > 1:
            block(state, "video", "DUPLICATE_VIDEO_ITEMS",
                  f"{len(active_matches)} active/rejected video items exist for {slug}")
            return Action("blocked", "duplicate video items")

        item = active_matches[0] if active_matches else (matches[-1] if matches else None)
        active_run = self.github.active_workflow_run(VIDEO_WORKFLOW, production_only=True)
        if active_run:
            state["video"]["run_id"] = active_run.get("id")
            if item:
                state["video"].update({"item_id": item.get("id"), "status": item.get("status")})
            transition(state, "video_running", "video workflow already active")
            return Action("wait", "video workflow active")

        self._reconcile_completed_video_run(state)
        if not retry_ready(state["video"], self.now):
            retry_at = state["video"].get("next_retry_at")
            transition(state, "video_retry_wait", "video retry backoff is active", retry_at=retry_at)
            return Action("wait", f"video retry scheduled for {retry_at}")

        if item:
            state["video"].update({"item_id": item.get("id"), "status": item.get("status")})
            has_youtube_id = bool(str(item.get("youtube_id") or "").strip())
            if item.get("status") == "uploaded" and not has_youtube_id:
                block(state, "video", "UPLOADED_VIDEO_NOT_VERIFIED",
                      "video has upload identity but lacks authoritative public verification")
                return Action("blocked", "uploaded video requires reconciliation")

            if has_youtube_id or mandatory_video_review_approved(item):
                operation = "upload"
                inputs = {"operation": operation}
                if has_youtube_id:
                    state["video"].update({
                        "youtube_id": item.get("youtube_id"),
                        "youtube_url": item.get("youtube_url"),
                        "verified": False,
                    })
            elif item.get("status") == "rejected" and item.get("technical_verified") is not True:
                operation = "full"
                inputs = {"operation": operation}
            elif item.get("status") == "rejected" and item.get("visual_review_status") == "rejected":
                operation = "rebuild"
                inputs = {"operation": operation, "rebuild_item_id": str(item.get("id") or "")}
            elif item.get("status") == "rejected":
                block(
                    state,
                    "video",
                    "VIDEO_REVIEW_REJECTED",
                    "mandatory Jules review rejected semantic or metadata quality; automatic visual rebuild cannot safely repair it",
                )
                return Action("blocked", "mandatory Jules review rejected non-visual quality")
            else:
                operation = "full"
                inputs = {"operation": operation}

            self.github.dispatch(VIDEO_WORKFLOW, inputs)
            resumes = int(state["video"].get("resume_dispatches") or 0) + 1
            state["video"].update({
                "resume_dispatches": resumes,
                "last_dispatch_at": utc_now(),
                "next_retry_at": None,
            })
            transition(state, "video_running", "existing video item dispatched/resumed",
                       operation=operation, resume=resumes)
            return Action("dispatch_video", "existing article video is incomplete", inputs)

        attempts = int(state["video"].get("attempts") or 0) + 1
        inputs = {"operation": "full"}
        self.github.dispatch(VIDEO_WORKFLOW, inputs)
        state["video"].update({
            "attempts": attempts,
            "last_dispatch_at": utc_now(),
            "next_retry_at": None,
        })
        transition(state, "video_running", "new video workflow dispatched",
                   operation="full", attempt=attempts)
        if attempts > MAX_VIDEO_START_ATTEMPTS_BEFORE_LONG_BACKOFF:
            state["video"]["next_retry_at"] = (
                datetime.now(timezone.utc) + timedelta(minutes=60)
            ).isoformat()
        return Action("dispatch_video", "article live and no matching video item exists", inputs)


def main() -> int:
    from scripts.kesher_runtime.legacy_retirement import retired_entrypoint
    retired_entrypoint()
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "yanivsa/kesher-website"))
    parser.add_argument("--report-json", action="store_true")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise ControllerError("GITHUB_TOKEN_MISSING")
    state, action = Controller(GitHubClient(args.repo, token), PublicSiteClient()).tick()
    if args.report_json:
        print(json.dumps({"action": action.kind, "reason": action.reason, "state": state},
                         ensure_ascii=False, indent=2))
    else:
        print(f"KESHER_CONTROLLER cycle={state.get('cycle')} status={state.get('status')} "
              f"action={action.kind} reason={action.reason}")
        article = state.get("article") or {}
        video = state.get("video") or {}
        if article.get("url"):
            print(f"ARTICLE {article.get('slug')} {article.get('url')}")
        if video.get("youtube_url"):
            print(f"VIDEO {video.get('youtube_url')}")
    return 1 if action.kind == "blocked" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ControllerError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"KESHER_CONTROLLER_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

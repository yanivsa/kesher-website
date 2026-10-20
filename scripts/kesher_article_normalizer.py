from __future__ import annotations

import copy
from datetime import date, datetime
import os
from typing import Any

try:
    from .kesher_article_contract import forbidden_article_paths
except ImportError:
    from kesher_article_contract import forbidden_article_paths


class ArticleNormalizationError(RuntimeError):
    pass


def _today_israel() -> date:
    env_today = os.environ.get("KESHER_TODAY_ISO", "").strip()
    if env_today:
        try:
            return date.fromisoformat(env_today)
        except ValueError:
            pass
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Jerusalem")).date()
    except Exception:
        return date.today()


def _post_id(post: dict[str, Any]) -> str:
    return str(post.get("id") or post.get("slug") or "").strip()


def _post_date(post: dict[str, Any]) -> date:
    raw = str(post.get("date") or "").strip()
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ArticleNormalizationError(f"invalid article date: {raw or '<missing>'}") from exc


def extract_target_article(
    base_posts: list[dict[str, Any]],
    head_posts: list[dict[str, Any]],
    slot: str,
    *,
    recent_posts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Extract exactly one new article for *slot* from an arbitrarily dirty head.

    Existing base articles (and any articles in postsRecent.json) are not
    trusted from the PR branch. Only an article whose identity is absent from
    current main and whose date equals the target slot may be carried forward
    into the normalized publication branch.
    """
    try:
        target_date = date.fromisoformat(slot)
    except ValueError as exc:
        raise ArticleNormalizationError(f"invalid publication slot: {slot}") from exc

    base_ids = {
        _post_id(post)
        for post in [*base_posts, *(recent_posts or [])]
        if isinstance(post, dict) and _post_id(post)
    }
    candidates = [
        post
        for post in head_posts
        if _post_id(post)
        and _post_id(post) not in base_ids
        and _post_date(post) == target_date
    ]
    if len(candidates) != 1:
        raise ArticleNormalizationError(
            f"expected exactly one new article for {slot}, found {len(candidates)}"
        )
    extracted = copy.deepcopy(candidates[0])
    if extracted.get("controllerManaged") is False:
        extracted["controllerManaged"] = True
    if "subcategory" in extracted and extracted["subcategory"] is None:
        del extracted["subcategory"]
    return extracted


def normalized_posts(
    base_posts: list[dict[str, Any]],
    article: dict[str, Any],
    *,
    recent_posts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return current-main posts plus exactly one target article.

    Relative order and content of every base article are preserved. The new
    article is inserted by ISO publication date into the existing newest-first
    sequence. `src/data/posts.json` is the sole canonical write target;
    `recent_posts` is checked read-only to prevent duplicate identities.

    Multiple distinct controller articles may legitimately share a publication
    date. That remains true when a zero-touch cycle is normalized after the
    date has rolled over; identity, not the calendar date, is the uniqueness
    boundary.
    """
    article_id = _post_id(article)
    if not article_id:
        raise ArticleNormalizationError("target article has no id/slug")
    article_date = _post_date(article)

    for post in [*base_posts, *(recent_posts or [])]:
        if not isinstance(post, dict):
            continue
        if _post_id(post) == article_id:
            raise ArticleNormalizationError(
                f"target article identity already exists in main: {article_id}"
            )

    result: list[dict[str, Any]] = []
    inserted = False
    target = copy.deepcopy(article)
    for post in base_posts:
        if not inserted and _post_date(post) < article_date:
            result.append(target)
            inserted = True
        result.append(copy.deepcopy(post))
    if not inserted:
        result.append(target)
    return result


def normalization_required(
    base_posts: list[dict[str, Any]],
    head_posts: list[dict[str, Any]],
    slot: str,
    changed_paths: list[str],
    *,
    recent_posts: list[dict[str, Any]] | None = None,
) -> bool:
    """Return True when the article branch is not the canonical current-main diff."""
    article = extract_target_article(base_posts, head_posts, slot, recent_posts=recent_posts)
    expected_posts = normalized_posts(base_posts, article, recent_posts=recent_posts)
    return bool(forbidden_article_paths(changed_paths) or head_posts != expected_posts)

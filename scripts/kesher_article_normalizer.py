from __future__ import annotations

import copy
from datetime import date, datetime
import os
from typing import Any

try:
    from .kesher_article_contract import forbidden_article_paths
except ImportError:
    from kesher_article_contract import forbidden_article_paths


OWNED_METADATA_ENFORCEMENT_DATE = date(2026, 10, 20)


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
    source_slot: str | None = None,
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
    source_date = target_date
    if source_slot is not None:
        try:
            source_date = date.fromisoformat(source_slot)
        except ValueError as exc:
            raise ArticleNormalizationError(f"invalid source publication slot: {source_slot}") from exc
        if source_date >= target_date:
            raise ArticleNormalizationError(
                f"source publication slot must precede target slot: {source_slot} -> {slot}"
            )

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
        and _post_date(post) == source_date
    ]
    if len(candidates) != 1:
        raise ArticleNormalizationError(
            f"expected exactly one new article for {slot}, found {len(candidates)}"
        )
    extracted = copy.deepcopy(candidates[0])
    if source_slot is not None:
        extracted["date"] = target_date.isoformat()
    if extracted.get("controllerManaged") is False:
        extracted["controllerManaged"] = True
    if _post_date(extracted) >= OWNED_METADATA_ENFORCEMENT_DATE:
        extracted["controllerManaged"] = True
        if not str(extracted.get("slug") or "").strip():
            extracted["slug"] = _post_id(extracted)
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
    `recent_posts` is checked read-only to prevent duplicate slugs/slots.
    """
    try:
        from .kesher_content_controller import is_controller_adoptable_post
    except ImportError:
        from kesher_content_controller import is_controller_adoptable_post

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
        if _post_date(post) == article_date and is_controller_adoptable_post(post):
            if article_date < _today_israel():
                raise ArticleNormalizationError(
                    f"publication slot already exists in main: {article_date.isoformat()}"
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

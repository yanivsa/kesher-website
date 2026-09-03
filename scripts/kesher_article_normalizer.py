from __future__ import annotations

import copy
from datetime import date
from typing import Any


class ArticleNormalizationError(RuntimeError):
    pass


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
) -> dict[str, Any]:
    """Extract exactly one new article for *slot* from an arbitrarily dirty head.

    Existing base articles are not trusted from the PR branch. Only an article
    whose identity is absent from current main and whose date equals the target
    slot may be carried forward into the normalized publication branch.
    """
    try:
        target_date = date.fromisoformat(slot)
    except ValueError as exc:
        raise ArticleNormalizationError(f"invalid publication slot: {slot}") from exc

    base_ids = {_post_id(post) for post in base_posts if _post_id(post)}
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
    return copy.deepcopy(candidates[0])


def normalized_posts(
    base_posts: list[dict[str, Any]],
    article: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return current-main posts plus exactly one target article.

    Relative order and content of every base article are preserved. The new
    article is inserted by ISO publication date into the existing newest-first
    sequence.
    """
    article_id = _post_id(article)
    if not article_id:
        raise ArticleNormalizationError("target article has no id/slug")
    article_date = _post_date(article)

    for post in base_posts:
        if _post_id(post) == article_id:
            raise ArticleNormalizationError(
                f"target article identity already exists in main: {article_id}"
            )
        if _post_date(post) == article_date:
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

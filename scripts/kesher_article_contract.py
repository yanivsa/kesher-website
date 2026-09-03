from __future__ import annotations

from collections.abc import Iterable

ARTICLE_PUBLICATION_PATHS = frozenset(
    {
        "src/data/posts.json",
        "src/data/postSummaries.json",
        "public/sitemap.xml",
        "public/rss.xml",
        "public/llms.txt",
        "public/llms-full.txt",
    }
)

ARTICLE_IMAGE_PREFIX = "public/images/generated/blog/"


def normalize_repo_path(path: str) -> str:
    return str(path or "").strip().lstrip("./")


def is_article_publication_path(path: str) -> bool:
    normalized = normalize_repo_path(path)
    if not normalized:
        return False
    return normalized in ARTICLE_PUBLICATION_PATHS or normalized.startswith(
        ARTICLE_IMAGE_PREFIX
    )


def forbidden_article_paths(paths: Iterable[str]) -> list[str]:
    return [
        normalize_repo_path(path)
        for path in paths
        if normalize_repo_path(path) and not is_article_publication_path(path)
    ]

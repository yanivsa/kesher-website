#!/usr/bin/env python3
"""Select the CI profile from a set of changed repository paths.

Only a pure article-publication diff may use the focused article gate. Any
unknown, mixed, empty, workflow, code, test, or infrastructure change falls back
to the full gate.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable

ARTICLE_EXACT_PATHS = {
    "src/data/posts.json",
    "src/data/postSummaries.json",
    "public/sitemap.xml",
    "public/llms.txt",
    "public/llms-full.txt",
}
ARTICLE_PREFIXES = (
    "public/images/generated/blog/",
)


def is_article_publication_path(path: str) -> bool:
    normalized = path.strip().lstrip("./")
    if not normalized:
        return False
    return normalized in ARTICLE_EXACT_PATHS or any(
        normalized.startswith(prefix) for prefix in ARTICLE_PREFIXES
    )


def classify_paths(paths: Iterable[str]) -> str:
    normalized = [path.strip() for path in paths if path.strip()]
    if not normalized:
        return "full"
    return "article" if all(is_article_publication_path(path) for path in normalized) else "full"


def main() -> int:
    paths = sys.argv[1:] if len(sys.argv) > 1 else sys.stdin.read().splitlines()
    print(classify_paths(paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

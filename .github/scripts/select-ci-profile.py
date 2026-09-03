#!/usr/bin/env python3
"""Select the CI profile from a set of changed repository paths.

Only a pure article-publication diff may use the focused article gate. Any
unknown, mixed, empty, workflow, code, test, or infrastructure change falls back
to the full gate. Article publication paths come from one canonical module.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.kesher_article_contract import is_article_publication_path


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

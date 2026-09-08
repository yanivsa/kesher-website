#!/usr/bin/env python3
"""Fail-closed deterministic quality gate for the newest Kesher article.

This is deliberately narrow. It catches recurring unsupported/absolute claim
patterns that must be qualified before publication. It does not attempt to
replace human editorial judgment or fact checking.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ERROR_CODE = "ARTICLE_CONTENT_QUALITY_FAILED"

QUALIFIERS = (
    "לפעמים",
    "לעיתים",
    "לעתים",
    "אצל חלק",
    "יכול",
    "יכולה",
    "יכולים",
    "יכולות",
    "עשוי",
    "עשויה",
    "עשויים",
    "עשויות",
    "ייתכן",
    "יתכן",
    "במקרים מסוימים",
    "לא תמיד",
    "תלוי",
    "בהתאם להקשר",
)

# Patterns here are intentionally focused on recurring absolute/clinical claims.
# A matching sentence is allowed when it also contains an explicit qualifier.
STRONG_CLAIM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "defining_trait",
        re.compile(r"(?:אחד|אחת)\s+מ(?:ה)?מאפיינים\s+הבולטים\s+של.+?\s+(?:הוא|היא|הם|הן)\b"),
    ),
    ("vast_majority", re.compile(r"ברוב\s+המכריע\s+של\s+המקרים")),
    ("most_common_mistake", re.compile(r"הטעות\s+הנפוצה\s+ביותר")),
    ("one_right_way", re.compile(r"הדרך\s+הנכונה")),
    ("natural_response", re.compile(r"התגובה\s+הטבעית\s+היא")),
    ("most_important_rule", re.compile(r"הכלל\s+החשוב\s+ביותר")),
    ("neurological_mechanism", re.compile(r"המנגנון\s+הנוירולוגי")),
    ("usually_stems_from", re.compile(r"נובע(?:ת|ים|ות)?\s+לרוב\s+מ")),
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = re.sub(r"\s+", " ", data).strip()
        if value:
            self.parts.append(value)


def strip_html(value: Any) -> str:
    parser = _TextExtractor()
    parser.feed(str(value or ""))
    return html.unescape(" ".join(parser.parts))


def article_text(article: dict[str, Any]) -> str:
    return "\n".join(
        part
        for part in (
            str(article.get("title") or "").strip(),
            strip_html(article.get("excerpt")),
            strip_html(article.get("content")),
        )
        if part
    )


def content_sha256(article: dict[str, Any]) -> str:
    payload = article_text(article).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _sentences(text: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", row).strip()
        for row in re.split(r"(?<=[.!?])\s+|\n+", text)
        if row.strip()
    ]


def _qualified(sentence: str) -> bool:
    return any(marker in sentence for marker in QUALIFIERS)


def article_violations(article: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    for sentence in _sentences(article_text(article)):
        for code, pattern in STRONG_CLAIM_PATTERNS:
            if pattern.search(sentence) and not _qualified(sentence):
                excerpt = sentence[:180]
                violations.append(f"{code}: {excerpt}")
    return violations


def newest_articles(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [row for row in posts if isinstance(row, dict) and str(row.get("date") or "").strip()]
    if not rows:
        return []
    latest = max(str(row.get("date") or "") for row in rows)
    return [row for row in rows if str(row.get("date") or "") == latest]


def validate_posts(posts: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for article in newest_articles(posts):
        slug = str(article.get("slug") or article.get("id") or "unknown")
        for violation in article_violations(article):
            errors.append(f"{slug}: {violation}")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    path = Path(args[0]) if args else Path("src/data/posts.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"{ERROR_CODE}: cannot read {path}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(payload, list):
        print(f"{ERROR_CODE}: {path} must contain a JSON array", file=sys.stderr)
        return 1
    errors = validate_posts(payload)
    if errors:
        print(f"{ERROR_CODE}: newest article contains unsupported absolute claim(s)", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("ARTICLE_CONTENT_QUALITY_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

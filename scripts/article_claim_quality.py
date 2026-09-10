#!/usr/bin/env python3
"""Fail-closed deterministic quality gate for the newest Kesher article.

This gate intentionally catches a narrow set of recurring unsupported absolute
or causal claim shapes. It does not replace editorial judgment or fact checking:
claims must be naturally qualified or explicitly attributed before publication.
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
    "עלול",
    "עלולה",
    "עלולים",
    "עלולות",
    "ייתכן",
    "יתכן",
    "במקרים מסוימים",
    "לא תמיד",
    "תלוי",
    "בהתאם להקשר",
)

ATTRIBUTION_MARKERS = (
    "לפי ",
    "על פי ",
    "בהתאם ל",
    "משרד החינוך",
    "מחקר ",
    "מחקרים ",
    "סקירה ",
    "הנחיות ",
)

# A matching sentence is blocked unless the sentence itself contains an
# explicit limitation or attribution. The causal patterns include the exact
# incident class observed in PR #730, not only its first defining-trait phrase.
STRONG_CLAIM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "defining_trait",
        re.compile(
            r"(?:אחד|אחת)\s+(?:המאפיינים|המאפיינות|מהמאפיינים|מהמאפיינות)\s+"
            r"הבולט(?:ים|ות)\s+של.+?\s+(?:הוא|היא|הם|הן)\b"
        ),
    ),
    ("vast_majority", re.compile(r"ברוב\s+המכריע\s+של\s+המקרים")),
    ("most_common_mistake", re.compile(r"הטעות\s+הנפוצה\s+ביותר")),
    ("one_right_way", re.compile(r"הדרך\s+הנכונה")),
    ("natural_response", re.compile(r"התגובה\s+הטבעית\s+היא")),
    ("most_important_rule", re.compile(r"הכלל\s+החשוב\s+ביותר")),
    ("neurological_mechanism", re.compile(r"המנגנון\s+הנוירולוגי")),
    ("usually_stems_from", re.compile(r"נובע(?:ת|ים|ות)?\s+לרוב\s+מ")),
    (
        "causal_transformation",
        re.compile(r"\bהופכ(?:ת|ים|ות)?\s+אות(?:ם|ן|ו|ה)\s+ל"),
    ),
    (
        "causal_enablement",
        re.compile(r"\bמאפשר(?:ת|ים|ות)?\s+להם\s+ל(?:למוד|פתח|ווסת|התמודד)"),
    ),
    (
        "causal_parent_action",
        re.compile(r"\bאנחנו\s+מורידים\b.+\bומעודדים\b"),
    ),
    (
        "gifted_group_defining_trait",
        re.compile(r"\bילדים\s+מחוננים\s+מאופיינים\b"),
    ),
    (
        "gifted_cognition_causes_behavior",
        re.compile(r"היכולת\s+הקוגניטיבית\s+הגבוהה\s+שלהם\s+גורמת\s+להם"),
    ),
    (
        "gifted_group_preference",
        re.compile(r"\bילדים\s+רבים\s+עם\s+מחוננות\s+מעדיפים\b"),
    ),
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


def _supported(sentence: str) -> bool:
    def contains_marker(marker: str) -> bool:
        return re.search(
            rf"(?<![\u0590-\u05FF]){re.escape(marker)}(?![\u0590-\u05FF])",
            sentence,
        ) is not None

    return any(contains_marker(marker) for marker in QUALIFIERS) or any(
        contains_marker(marker) for marker in ATTRIBUTION_MARKERS
    )


def article_violations(article: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    for sentence in _sentences(article_text(article)):
        for code, pattern in STRONG_CLAIM_PATTERNS:
            if pattern.search(sentence) and not _supported(sentence):
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
        print(f"{ERROR_CODE}: newest article contains unsupported absolute/causal claim(s)", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("ARTICLE_CONTENT_QUALITY_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

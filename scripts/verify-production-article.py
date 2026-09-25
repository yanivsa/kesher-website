#!/usr/bin/env python3
"""Fail deployment unless the newest publishable Kesher article is truly public.

This verifies the user-visible contract, not merely Cloudflare's deploy command.
It is intentionally read-only and retries briefly for edge propagation.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

SITE_URL = "https://kesher.saharoni.com"


def _word_count(html: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", html).split())


def _publishable(post: dict) -> bool:
    content = str(post.get("content") or "")
    return _word_count(content) >= 500 and len(re.findall(r"<h3\b", content)) >= 5


def _latest_post() -> dict:
    posts = json.loads(Path("src/data/posts.json").read_text(encoding="utf-8"))
    eligible = [p for p in posts if isinstance(p, dict) and _publishable(p)]
    if not eligible:
        raise RuntimeError("no publishable article exists in src/data/posts.json")
    eligible.sort(key=lambda p: str(p.get("date") or ""), reverse=True)
    return eligible[0]


def _public_url(post: dict) -> str:
    post_id = str(post.get("id") or "").strip()
    if not post_id:
        raise RuntimeError("latest article has no id")
    quoted = urllib.parse.quote(post_id, safe="-._~")
    return f"{SITE_URL}/blog/{quoted}"


class _CanonicalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "link":
            return
        attributes = {key.lower(): (value or "") for key, value in attrs}
        rel_tokens = {token.lower() for token in attributes.get("rel", "").split()}
        if "canonical" in rel_tokens and attributes.get("href"):
            self.hrefs.append(attributes["href"])


def _canonical_hrefs(html: str) -> list[str]:
    parser = _CanonicalParser()
    parser.feed(html)
    return parser.hrefs


def _fetch(url: str) -> tuple[int, str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Kesher-Deploy-Smoke/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return int(response.status), response.geturl(), response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.geturl(), exc.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retries", type=int, default=12)
    parser.add_argument("--delay", type=float, default=5.0)
    args = parser.parse_args()

    post = _latest_post()
    title = re.sub(r"\s+", " ", str(post.get("title") or "").strip())
    url = _public_url(post)
    if not title:
        raise RuntimeError("latest article has no title")

    last = None
    for attempt in range(1, max(1, args.retries) + 1):
        status, final_url, body = _fetch(url)
        normalized = re.sub(r"\s+", " ", body)
        title_ok = title in normalized
        canonical_hrefs = _canonical_hrefs(body)
        canonical_ok = canonical_hrefs == [url]
        last = (status, final_url, title_ok, canonical_hrefs)
        print(
            f"production article smoke attempt={attempt}/{args.retries} "
            f"status={status} title_ok={title_ok} canonical_ok={canonical_ok} "
            f"final_url={final_url}"
        )
        if status == 200 and final_url == url and title_ok and canonical_ok:
            print(f"production article verified with self-canonical: {final_url}")
            return 0
        if attempt < args.retries:
            time.sleep(max(0.0, args.delay))

    status, final_url, title_ok, canonical_hrefs = last or (0, url, False, [])
    raise SystemExit(
        f"production article verification failed after {args.retries} attempts: "
        f"status={status} title_ok={title_ok} final_url={final_url} "
        f"canonicals={canonical_hrefs!r} expected_canonical={url}"
    )


if __name__ == "__main__":
    raise SystemExit(main())

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
    slug = str(post.get("slug") or post.get("id") or "").strip()
    if not slug:
        raise RuntimeError("latest article has no id/slug")
    quoted = urllib.parse.quote(slug, safe="-._~")
    return f"{SITE_URL}/blog/{quoted}"


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
        last = (status, final_url, title_ok)
        print(
            f"production article smoke attempt={attempt}/{args.retries} "
            f"status={status} title_ok={title_ok} final_url={final_url}"
        )
        if status == 200 and title_ok:
            print(f"production article verified: {final_url}")
            return 0
        if attempt < args.retries:
            time.sleep(max(0.0, args.delay))

    status, final_url, title_ok = last or (0, url, False)
    raise SystemExit(
        f"production article verification failed after {args.retries} attempts: "
        f"status={status} title_ok={title_ok} final_url={final_url}"
    )


if __name__ == "__main__":
    raise SystemExit(main())

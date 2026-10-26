#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value is not None:
                self.hrefs.append(value)
                return


def _page_url(base_url: str, value: str) -> str:
    value = value.strip()
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("/"):
        path = value
    else:
        path = f"/blog/{value}"
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _link_identity(base_url: str, value: str) -> tuple[str, str, str]:
    absolute = _page_url(base_url, value)
    parts = urlsplit(absolute)
    return parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/"


def _fetch(url: str, retries: int, delay: float) -> tuple[int, str]:
    attempts = max(1, retries)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": "KesherProductionLinkVerifier/1.0"})
            with urlopen(request, timeout=15) as response:  # noqa: S310 - verifier fetches configured URLs
                status = int(response.status)
                body = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
                return status, body
        except HTTPError as exc:
            status = int(exc.code)
            try:
                body = exc.read().decode(exc.headers.get_content_charset() or "utf-8", errors="replace")
            except Exception:
                body = ""
            return status, body
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts and delay > 0:
                time.sleep(delay)
    raise RuntimeError(f"request failed for {url}: {last_error}")


def _load_plan(path: Path) -> list[dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("plan must be a JSON array")
    plan: list[dict[str, object]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"plan item {index} must be an object")
        source = item.get("source")
        targets = item.get("targets")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"plan item {index} has invalid source")
        if not isinstance(targets, list) or not targets or not all(isinstance(target, str) and target.strip() for target in targets):
            raise ValueError(f"plan item {index} has invalid targets")
        plan.append(item)
    return plan


def _count_target_links(base_url: str, source_url: str, html: str, target: str) -> int:
    parser = LinkCollector()
    parser.feed(html)
    expected = _link_identity(base_url, target)
    count = 0
    for href in parser.hrefs:
        resolved = urljoin(source_url, href)
        parts = urlsplit(resolved)
        identity = (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/")
        if identity == expected:
            count += 1
    return count


def verify(base_url: str, plan: Iterable[dict[str, object]], retries: int, delay: float) -> tuple[int, int]:
    verified = 0
    total = 0
    errors: list[str] = []

    for item in plan:
        source = str(item["source"])
        targets = [str(target) for target in item["targets"]]  # validated by _load_plan
        source_url = _page_url(base_url, source)
        try:
            source_status, source_html = _fetch(source_url, retries, delay)
        except RuntimeError as exc:
            errors.append(str(exc))
            total += len(targets)
            continue
        if source_status != 200:
            errors.append(f"source returned HTTP {source_status}: {source_url}")
            total += len(targets)
            continue

        for target in targets:
            total += 1
            target_url = _page_url(base_url, target)
            try:
                target_status, _ = _fetch(target_url, retries, delay)
            except RuntimeError as exc:
                errors.append(str(exc))
                continue
            if target_status != 200:
                errors.append(f"target returned HTTP {target_status}: {target_url}")
                continue

            found = _count_target_links(base_url, source_url, source_html, target)
            if found != 1:
                errors.append(
                    f"planned link {source_url} -> {target_url} expected exactly once; found {found}"
                )
                continue
            verified += 1

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
    return verified, total


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify planned Kesher internal links against a deployed site.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    if args.retries < 1:
        parser.error("--retries must be at least 1")
    if args.delay < 0:
        parser.error("--delay must be non-negative")

    try:
        plan = _load_plan(args.plan)
        verified, total = verify(args.base_url, plan, args.retries, args.delay)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"invalid verification plan: {exc}", file=sys.stderr)
        return 2

    if verified != total:
        print(f"{verified}/{total} planned links verified", file=sys.stderr)
        return 1

    print(f"{verified}/{total} planned links verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

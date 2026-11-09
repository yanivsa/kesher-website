#!/usr/bin/env python3
"""Read-only live smoke audit for planned Priority 1 and 2 blog links."""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://kesher.saharoni.com"
HOST = "kesher.saharoni.com"
PLANS = {
    "priority1": ROOT / "scripts" / "internal-link-plan.json",
    "priority2": ROOT / "scripts" / "internal-link-plan-priority2.json",
}
REPORT_PATH = ROOT / "live-internal-link-audit.json"


class AnchorCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.hrefs.extend(value for key, value in attrs if key == "href" and value)


def expected_path(slug):
    return "/blog/" + slug


def normalize_path(path):
    return unquote(path).rstrip("/") or "/"


def fetch_article(slug):
    url = BASE + expected_path(slug)
    last_error = "Unknown network error"
    for attempt in range(3):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; KesherLinkAudit/1.0)",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            with urlopen(request, timeout=22) as response:
                status = response.status
                final_url = response.geturl()
                media_type = response.headers.get_content_type()
                html = response.read().decode(
                    response.headers.get_content_charset() or "utf-8", errors="replace"
                )
            parsed = urlsplit(final_url)
            if status != 200:
                raise ValueError(f"HTTP {status}")
            if parsed.hostname != HOST or normalize_path(parsed.path) != expected_path(slug):
                raise ValueError(f"Unexpected redirect to {final_url}")
            if media_type != "text/html":
                raise ValueError(f"Unexpected content type {media_type}")
            return {"ok": True, "html": html, "url": final_url}
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
            last_error = str(error)
            if attempt < 2:
                time.sleep((attempt + 1) * 1.5)
    return {"ok": False, "error": last_error, "url": url}


def collect_links(html, page_url):
    parser = AnchorCollector()
    parser.feed(html)
    paths = []
    for href in parser.hrefs:
        destination = urlsplit(urljoin(page_url, href))
        if destination.hostname == HOST:
            paths.append(normalize_path(destination.path))
    return paths


def audit():
    plans = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in PLANS.items()}
    expected = {
        name: {(entry["source"], target) for entry in entries for target in entry["targets"]}
        for name, entries in plans.items()
    }
    if len(expected["priority1"]) != 46 or len(expected["priority2"]) != 26:
        raise ValueError("Plans changed: expected 46 Priority-1 and 26 Priority-2 distinct pairs")

    source_slugs = sorted({source for pairs in expected.values() for source, _ in pairs})
    target_slugs = sorted({target for pairs in expected.values() for _, target in pairs})
    all_slugs = sorted(set(source_slugs) | set(target_slugs))
    pages = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(fetch_article, slug): slug for slug in all_slugs}
        for future in as_completed(futures):
            pages[futures[future]] = future.result()

    source_links = {
        source: collect_links(pages[source]["html"], pages[source]["url"])
        if pages[source]["ok"] else []
        for source in source_slugs
    }
    outcomes = {}
    for priority, pairs in expected.items():
        rows = []
        for source, target in sorted(pairs):
            source_result = pages[source]
            target_result = pages[target]
            count = source_links[source].count(expected_path(target))
            passed = source_result["ok"] and target_result["ok"] and count == 1
            rows.append({
                "source": source,
                "target": target,
                "count": count,
                "source_http_ok": source_result["ok"],
                "target_http_ok": target_result["ok"],
                "passed": passed,
            })
        outcomes[priority] = {
            "passed": sum(row["passed"] for row in rows),
            "expected": len(rows),
            "rows": rows,
        }

    failures = [
        {"slug": slug, "error": value["error"]}
        for slug, value in sorted(pages.items()) if not value["ok"]
    ]
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE,
        "source_pages": len(source_slugs),
        "unique_pages_checked": len(all_slugs),
        "page_failures": failures,
        "priorities": outcomes,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for name, result in outcomes.items():
        print(f"{name}: {result['passed']}/{result['expected']} live links verified")
        for row in result["rows"]:
            if not row["passed"]:
                print(
                    f"FAIL {row['source']} -> {row['target']}: "
                    f"links={row['count']}, source_ok={row['source_http_ok']}, "
                    f"target_ok={row['target_http_ok']}"
                )
    for failure in failures:
        print(f"HTTP FAIL {failure['slug']}: {failure['error']}")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## Live internal-link audit\n\n")
            summary.write(f"Checked {len(source_slugs)} sources / {len(all_slugs)} unique pages.\n\n")
            for name, result in outcomes.items():
                summary.write(f"- {name}: **{result['passed']}/{result['expected']}**\n")
            summary.write(f"\nPage fetch failures: {len(failures)}.\n")
            summary.write("\nFull per-link evidence is in the uploaded JSON artifact.\n")

    return int(bool(failures) or any(item["passed"] != item["expected"] for item in outcomes.values()))


if __name__ == "__main__":
    try:
        sys.exit(audit())
    except Exception as exc:
        print(f"Live internal-link audit could not complete: {exc}", file=sys.stderr)
        raise

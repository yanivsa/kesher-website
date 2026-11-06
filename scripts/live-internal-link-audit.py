#!/usr/bin/env python3
"""Read-only production QA for planned Kesher contextual article links."""
import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, unquote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PLANS = (
    ROOT / "scripts/internal-link-plan.json",
    ROOT / "scripts/internal-link-plan-priority2.json",
)
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def blog_path(href, page_url, expected_host):
    parsed = urlsplit(urljoin(page_url, href))
    if parsed.scheme not in ("https", "http") or parsed.hostname != expected_host:
        return None
    return unquote(parsed.path).rstrip("/")


def fetch_article(base, slug):
    url = f"{base}/blog/{slug}"
    last_error = None
    for attempt in range(3):
        try:
            request = Request(url, headers={
                "User-Agent": "Kesher-Live-Internal-Link-Audit/1.0",
                "Accept": "text/html,application/xhtml+xml",
            })
            with urlopen(request, timeout=25) as response:
                status = response.status
                final_url = response.geturl()
                html = response.read(3_000_000).decode("utf-8", errors="replace")
            if status != 200 or urlsplit(final_url).hostname != urlsplit(base).hostname:
                raise ValueError(f"HTTP {status}, unexpected redirect: {final_url}")
            if "<html" not in html.lower() or "</html>" not in html.lower():
                raise ValueError("200 returned without a complete HTML document")
            parser = Links()
            parser.feed(html)
            return {"url": url, "status": status, "hrefs": parser.hrefs}
        except HTTPError as exc:
            last_error = f"HTTP {exc.code}: {url}"
            if exc.code not in (429, 500, 502, 503, 504):
                break
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < 2:
            time.sleep(2 ** attempt)
    return {"url": url, "error": last_error or "unknown request failure"}


def load_plan_files(paths):
    plans = []
    seen_sources = set()
    for priority, path in enumerate(paths, start=1):
        entries = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"Missing/invalid plan: {path}")
        for entry in entries:
            source, targets = entry["source"], entry["targets"]
            if not SLUG.fullmatch(source) or source in seen_sources:
                raise ValueError(f"Invalid or duplicate source: {source}")
            if not targets or len(targets) != len(set(targets)):
                raise ValueError(f"Invalid or duplicate targets: {source}")
            if any(not SLUG.fullmatch(target) or target == source for target in targets):
                raise ValueError(f"Invalid target under {source}")
            seen_sources.add(source)
            plans.append({"priority": priority, "source": source, "targets": targets})
    return plans


def run_self_test():
    parser = Links()
    parser.feed('<article><a href="/blog/foo">Test</a><a href="https://kesher.saharoni.com/blog/foo?x=1">Again</a><a href="/blog/bar#part">More</a></article>')
    host = "kesher.saharoni.com"
    source = "https://kesher.saharoni.com/blog/test"
    paths = [blog_path(href, source, host) for href in parser.hrefs]
    assert paths == ["/blog/foo", "/blog/foo", "/blog/bar"], paths
    assert blog_path("https://elsewhere.com/blog/foo", source, host) is None
    assert blog_path("/blog/foo/", source, host) == "/blog/foo"
    assert blog_path("mailto:someone@example.com", source, host) is None
    print("Parser and link normalization self-tests passed.")


def audit(base, plans, output):
    base = base.rstrip("/")
    host = urlsplit(base).hostname
    if urlsplit(base).scheme != "https" or not host:
        raise ValueError("Base URL must be an HTTPS origin")
    sources = {entry["source"] for entry in plans}
    targets = {target for entry in plans for target in entry["targets"]}
    slugs = sorted(sources | targets)
    pages = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch_article, base, slug): slug for slug in slugs}
        for future in as_completed(futures):
            slug = futures[future]
            pages[slug] = future.result()

    rows = []
    for entry in plans:
        source = entry["source"]
        html_page = pages[source]
        hrefs = html_page.get("hrefs", [])
        normalized = [blog_path(href, html_page["url"], host) for href in hrefs]
        for target in entry["targets"]:
            count = normalized.count(f"/blog/{target}")
            rows.append({
                "priority": entry["priority"],
                "source": source,
                "target": target,
                "anchor_occurrences": count,
                "source_http_ok": html_page.get("status") == 200,
                "target_http_ok": pages[target].get("status") == 200,
                "passed": count >= 1 and pages[target].get("status") == 200,
            })

    by_priority = {}
    for priority in sorted(set(item["priority"] for item in rows)):
        subset = [item for item in rows if item["priority"] == priority]
        by_priority[str(priority)] = {
            "planned": len(subset),
            "passed": sum(item["passed"] for item in subset),
        }
    page_failures = {
        slug: item.get("error", "unexpected HTTP status")
        for slug, item in pages.items() if item.get("status") != 200
    }
    failed_links = [item for item in rows if not item["passed"]]
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "sources": len(sources),
        "unique_pages_checked": len(slugs),
        "planned": len(rows),
        "passed": len(rows) - len(failed_links),
        "by_priority": by_priority,
        "page_failures": page_failures,
        "failed_links": failed_links,
        "duplicate_href_warnings": [
            item for item in rows if item["anchor_occurrences"] > 1
        ],
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Live internal links: {report['passed']}/{report['planned']} present, "
        f"{len(slugs) - len(page_failures)}/{len(slugs)} pages HTTP 200."
    )
    for priority, summary in by_priority.items():
        print(f"Priority {priority}: {summary['passed']}/{summary['planned']}")
    for slug, error in sorted(page_failures.items()):
        print(f"PAGE FAILURE {slug}: {error}", file=sys.stderr)
    for item in failed_links:
        print(
            f"LINK FAILURE P{item['priority']} {item['source']} -> {item['target']} "
            f"(count={item['anchor_occurrences']}, target_200={item['target_http_ok']})",
            file=sys.stderr,
        )
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## Production internal-link audit\n\n")
            summary.write(f"Checked {len(slugs)} unique article URLs; **{report['passed']}/{report['planned']}** planned links passed.\n\n")
            for priority, counts in by_priority.items():
                summary.write(f"- Priority {priority}: {counts['passed']}/{counts['planned']}\n")
            summary.write(f"- HTTP failures: {len(page_failures)}; missing links: {len(failed_links)}\n")
    return not page_failures and not failed_links


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://kesher.saharoni.com")
    parser.add_argument("--output", type=Path, default=Path("live-internal-link-audit.json"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        run_self_test()
        return 0
    plans = load_plan_files(PLANS)
    return 0 if audit(args.base_url, plans, args.output) else 1


if __name__ == "__main__":
    sys.exit(main())

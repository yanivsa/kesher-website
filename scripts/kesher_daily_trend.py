"""Read a pre-researched daily article from an owner-authored, non-triggering issue.

The existing daily publisher remains the sole dispatch owner. Trend signals are
editorial inputs, not proof of any news claim. This module never creates issues,
dispatches workflows, fetches arbitrary source URLs, or grants release approval.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

SCHEMA = "kesher-trend-brief-v1"
MAX_BODY = 60000
ARTICLE_FIELDS = {
    "title", "category", "subcategory", "tags", "serviceUrl", "serviceLabel",
    "excerpt", "directAnswer", "evidence", "content", "primaryKeyword", "imageAlt",
}
CATEGORIES = {"ייעוץ זוגי", "הדרכת הורים", "הנחיית הורים", "גישור", "גישור משפחתי"}
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+){2,6}")
PUBMED_RE = re.compile(r"https://pubmed\.ncbi\.nlm\.nih\.gov/[0-9]+/?")
ALLOWED_TAGS = {"p", "h3", "ul", "ol", "li", "strong", "em", "blockquote", "a"}


def normalized(value):
    return " ".join(str(value or "").casefold().split())


def valid_https(url):
    if not isinstance(url, str) or len(url) > 2048:
        return False
    try:
        parsed = urlsplit(url)
        return parsed.scheme == "https" and bool(parsed.hostname) and not (
            parsed.username or parsed.password or parsed.port not in (None, 443)
        ) and not re.search(r"[\s<>\\]", url)
    except ValueError:
        return False


class ArticleHTML(HTMLParser):
    def __init__(self, allowed_links):
        super().__init__(convert_charrefs=True)
        self.allowed_links = allowed_links
        self.links = set()
        self.text = []
        self.headings = 0

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            raise ValueError("TREND_HTML_TAG")
        if tag == "a":
            if len(attrs) != 1 or attrs[0][0] != "href" or attrs[0][1] not in self.allowed_links:
                raise ValueError("TREND_HTML_LINK")
            self.links.add(attrs[0][1])
        elif attrs:
            raise ValueError("TREND_HTML_ATTRIBUTE")
        if tag == "h3":
            self.headings += 1

    def handle_endtag(self, tag):
        if tag not in ALLOWED_TAGS:
            raise ValueError("TREND_HTML_TAG")

    def handle_startendtag(self, tag, attrs):
        raise ValueError("TREND_HTML_SELF_CLOSING")

    def handle_data(self, value):
        self.text.append(value)

    def handle_comment(self, data):
        raise ValueError("TREND_HTML_COMMENT")

    def handle_decl(self, decl):
        raise ValueError("TREND_HTML_DECL")

    def handle_pi(self, data):
        raise ValueError("TREND_HTML_PI")


def parse_issue(issue, slot, posts):
    target = date.fromisoformat(slot)
    if issue.get("title") != f"[TrendBrief] {slot}" or issue.get("state") != "open":
        raise ValueError("TREND_ISSUE_IDENTITY")
    if issue.get("author_association") != "OWNER" or (issue.get("user") or {}).get("login") != "yanivsa":
        raise ValueError("TREND_ISSUE_OWNER")
    created = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Jerusalem")).date()
    if not target - timedelta(days=1) <= created <= target:
        raise ValueError("TREND_ISSUE_STALE")
    body = issue.get("body")
    if not isinstance(body, str) or len(body.encode("utf-8")) > MAX_BODY:
        raise ValueError("TREND_BODY_SIZE")
    data = json.loads(body)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("slot") != slot:
        raise ValueError("TREND_PACKET_SCHEMA")
    research = data.get("research")
    if not isinstance(research, dict) or not str(research.get("relevance") or "").strip():
        raise ValueError("TREND_RELEVANCE")
    signal = research.get("trend_signal")
    if not isinstance(signal, dict) or not valid_https(signal.get("url")) or not str(signal.get("description") or "").strip():
        raise ValueError("TREND_SIGNAL")
    news = research.get("news")
    if not isinstance(news, list) or not 2 <= len(news) <= 8:
        raise ValueError("TREND_NEWS_COUNT")
    news_urls = set()
    hosts = set()
    for row in news:
        if not isinstance(row, dict) or not valid_https(row.get("url")) or not str(row.get("title") or "").strip():
            raise ValueError("TREND_NEWS_SOURCE")
        published = date.fromisoformat(row["published_date"])
        if not target - timedelta(days=7) <= published <= target:
            raise ValueError("TREND_NEWS_STALE")
        news_urls.add(row["url"])
        hosts.add(urlsplit(row["url"]).hostname.removeprefix("www."))
    if len(hosts) < 2:
        raise ValueError("TREND_NEWS_INDEPENDENCE")
    article = data.get("article")
    if not isinstance(article, dict):
        raise ValueError("TREND_ARTICLE")
    slug = article.get("slug")
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        raise ValueError("TREND_SLUG")
    if article.get("category") not in CATEGORIES:
        raise ValueError("TREND_CATEGORY")
    keyword = normalized(article.get("primaryKeyword"))
    if not keyword or not re.search(r"[\u0590-\u05ff]", keyword) or keyword not in normalized(article.get("title")):
        raise ValueError("TREND_KEYWORD")
    existing = {str(p.get("slug") or p.get("id") or "") for p in posts}
    if slug in existing or any(
        normalized(p.get("primaryKeyword")) == keyword or
        normalized(p.get("title")) == normalized(article.get("title")) for p in posts
    ):
        raise ValueError("TREND_DUPLICATE")
    if not all(isinstance(article.get(k), str) and article[k].strip() for k in ARTICLE_FIELDS - {"tags", "evidence"}):
        raise ValueError("TREND_ARTICLE_FIELDS")
    if not isinstance(article.get("tags"), list) or not all(isinstance(t, str) for t in article["tags"]):
        raise ValueError("TREND_TAGS")
    evidence = article.get("evidence")
    if not isinstance(evidence, list) or not evidence or not all(
        isinstance(e, dict) and valid_https(e.get("url")) for e in evidence
    ) or not any(PUBMED_RE.fullmatch(e["url"]) for e in evidence):
        raise ValueError("TREND_ACADEMIC_EVIDENCE")
    service = article["serviceUrl"]
    if not re.fullmatch(r"/services/[a-z0-9-]+", service) or not any(
        p.get("serviceUrl") == service and p.get("category") == article["category"] for p in posts
    ):
        raise ValueError("TREND_SERVICE")
    internal = {f"/blog/{s}" for s in existing if s}
    source_links = news_urls | {e["url"] for e in evidence}
    html = ArticleHTML(internal | {service} | source_links)
    html.feed(article["content"])
    html.close()
    words = " ".join(html.text).split()
    if not 1000 <= len(words) <= 1200 or html.headings < 5:
        raise ValueError("TREND_ARTICLE_LENGTH")
    if keyword not in normalized(" ".join(words[:100])):
        raise ValueError("TREND_KEYWORD_OPENING")
    if len(html.links & internal) < 3 or service not in html.links or not news_urls <= html.links:
        raise ValueError("TREND_REQUIRED_LINKS")
    post = {k: article[k] for k in ARTICLE_FIELDS}
    post.update(id=slug, slug=slug, date=slot, updatedAt=slot, author="שירה סהרוני",
                controllerManaged=True, image=f"/images/generated/blog/{slug}.jpg",
                imageProvider="CuratedEditorial", imageIsFallback=False)
    from scripts.kesher_cloud_article_generator import validate_article_candidate
    validate_article_candidate(post)
    return post


def select_from_issues(issues, slot, posts):
    candidates = [i for i in issues if i.get("title") == f"[TrendBrief] {slot}" and "pull_request" not in i]
    if not candidates:
        return None
    if len(candidates) != 1:
        raise ValueError("TREND_PACKET_AMBIGUOUS")
    return candidates[0]["number"], parse_issue(candidates[0], slot, posts)


def load_daily_trend(client, slot, posts):
    """Bounded read of current research inputs; absence or invalidity is not approval."""
    request = urllib.request.Request(
        client.base_url + "/issues?state=open&sort=created&direction=desc&per_page=100",
        headers=client._headers(),
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("TREND_ISSUE_LIST_TOO_LARGE")
    issues = json.loads(raw)
    if not isinstance(issues, list):
        raise ValueError("TREND_ISSUE_LIST")
    return select_from_issues(issues, slot, posts)

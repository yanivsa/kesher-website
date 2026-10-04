"""Independently verify the exact deployed article, visible content and hero bytes."""
from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser

from scripts.kesher_article_contract import image_dimensions
from scripts.kesher_daily_pipeline import source_metadata, clean_article_html
from .identity import SourceIdentity, digest, require_sha
from .state import timestamp
from .verification import SITE_URL

MANIFEST_URL = SITE_URL + '/.well-known/kesher-publication.json'


class ArticleVerificationError(ValueError):
    def __init__(self, failure_class: str, detail: str):
        self.failure_class = failure_class
        super().__init__(failure_class + ': ' + detail)


def reject(code: str, detail: str):
    raise ArticleVerificationError(code, detail)


@dataclass(frozen=True)
class SourceSnapshot:
    commit_sha: str
    main_sha: str
    post: dict
    hero_bytes: bytes


@dataclass(frozen=True)
class FetchResult:
    status: int
    url: str
    body: bytes
    redirects: tuple[str, ...] = ()


def transport_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, urllib.parse.quote(parts.path, safe='/%-._~'), parts.query, parts.fragment))


def same_route(actual: str, expected: str, *, trailing_slash: bool = False) -> bool:
    a, b = urllib.parse.urlsplit(actual), urllib.parse.urlsplit(expected)
    if (a.scheme, a.netloc) != ('https', urllib.parse.urlsplit(SITE_URL).netloc) or a.query or a.fragment:
        return False
    allowed = {b.path}
    if trailing_slash:
        allowed.add(b.path + '/')
    return urllib.parse.unquote(a.path, errors='strict') in allowed


def _response(response: FetchResult, expected: str, *, code: str, trailing_slash: bool = False) -> None:
    if response.status != 200:
        reject('ARTICLE_PUBLIC_HTTP', f'Expected HTTP 200, received {response.status}')
    if any(not same_route(url, expected, trailing_slash=trailing_slash) for url in (*response.redirects, response.url)):
        reject(code, 'Response or redirect does not belong to the canonical route')


def _normal(value: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(value)).strip()


class ArticleHTML(HTMLParser):
    def __init__(self, content: bytes):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.canonical = []
        self.stack = []
        self.fields = {'title': [], 'h1': [], 'body': [], 'date': [], 'jsonld': []}
        self.hero = []
        self.date_values = []
        try:
            self.feed(content.decode('utf-8', errors='strict'))
            self.close()
        except (UnicodeError, ValueError) as exc:
            reject('ARTICLE_CONTENT_MISMATCH', 'Invalid public HTML encoding/structure')

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if len(values) != len(attrs):
            reject('ARTICLE_CONTENT_MISMATCH', 'Ambiguous HTML attributes')
        if tag == 'meta':
            name = values.get('name') or values.get('property')
            if name:
                self.meta.setdefault(name, []).append(values.get('content'))
        if tag == 'link' and values.get('rel') == 'canonical':
            self.canonical.append(values.get('href'))
        field = None
        if tag in {'title', 'h1'}:
            field = tag
        elif 'data-kesher-article-body' in values:
            field = 'body'
        elif 'data-kesher-article-date' in values:
            field = 'date'
            self.date_values.append(values.get('data-kesher-article-date'))
        elif tag == 'script' and values.get('type') == 'application/ld+json':
            field = 'jsonld'
        if tag == 'img' and 'data-kesher-article-hero' in values:
            self.hero.append(values)
        if field:
            self.fields[field].append([])
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append((tag, field, len(self.fields[field]) - 1 if field else None, values))

    def handle_endtag(self, tag):
        matches = [i for i, row in enumerate(self.stack) if row[0] == tag]
        if matches:
            self.stack = self.stack[:matches[-1]]

    def handle_data(self, data):
        for tag, field, index, attrs in self.stack:
            if field is not None:
                if field == 'body' and any(row[0] in {'script', 'style', 'template'} or 'hidden' in row[3]
                                            or row[3].get('aria-hidden') == 'true' for row in self.stack):
                    continue
                self.fields[field][index].append(data)

    def one(self, field):
        values = self.fields[field]
        if len(values) != 1:
            reject('ARTICLE_CONTENT_MISMATCH', f'Expected exactly one {field} element')
        return _normal(' '.join(values[0]))


def validate_rendered_html(content: bytes, post: dict, *, deploy_sha: str | None = None) -> None:
    source = source_metadata(post)
    parser = ArticleHTML(content)
    expected_url = source['canonical_url']
    full_title = post['title'] + ' | שירה סהרוני'
    expected_meta = {'description': post['excerpt'], 'og:title': full_title, 'og:description': post['excerpt'],
                     'og:url': expected_url, 'og:image': SITE_URL + post['image'], 'og:type': 'article',
                     'twitter:title': full_title, 'twitter:description': post['excerpt'], 'twitter:image': SITE_URL + post['image']}
    if deploy_sha:
        expected_meta.update({'kesher:deploy-sha': deploy_sha, 'kesher:content-sha256': source['content_sha256']})
    if any(parser.meta.get(key) != [value] for key, value in expected_meta.items()):
        reject('ARTICLE_CONTENT_MISMATCH', 'Public metadata differs from the deployed source')
    if parser.canonical != [expected_url] or parser.one('title') != full_title or parser.one('h1') != post['title']:
        reject('ARTICLE_CONTENT_MISMATCH', 'Canonical URL or visible title differs from source')
    if any('noindex' in str(value).lower() for value in parser.meta.get('robots', [])):
        reject('ARTICLE_CONTENT_MISMATCH', 'Article is marked noindex')
    if parser.one('body') != _normal(clean_article_html(post['content'])):
        reject('ARTICLE_CONTENT_MISMATCH', 'Visible article body differs from exact source')
    if len(parser.hero) != 1 or any(parser.hero[0].get(k) != v for k, v in {'src': post['image'], 'alt': post['imageAlt']}.items()):
        reject('ARTICLE_CONTENT_MISMATCH', 'Visible hero is not the approved article image')
    parsed_date = datetime.strptime(post['date'], '%Y-%m-%d')
    if parser.one('date') not in {post['date'], f'{parsed_date.day}.{parsed_date.month}.{parsed_date.year}', parsed_date.strftime('%d.%m.%Y')}:
        reject('ARTICLE_CONTENT_MISMATCH', 'Visible publication date differs from source')
    documents = []
    try:
        for chunks in parser.fields['jsonld']:
            value = json.loads(''.join(chunks))
            documents.extend(value.get('@graph', [value]) if isinstance(value, dict) else value)
    except (ValueError, TypeError, AttributeError):
        reject('ARTICLE_CONTENT_MISMATCH', 'Invalid structured publication data')
    articles = [row for row in documents if isinstance(row, dict) and row.get('@type') == 'Article']
    expected_ld = {'headline': post['title'], 'url': expected_url, 'datePublished': post['date'],
                   'dateModified': post.get('updatedAt') or post['date'], 'description': post['excerpt'], 'image': SITE_URL + post['image']}
    if len(articles) != 1 or any(articles[0].get(key) != value for key, value in expected_ld.items()):
        reject('ARTICLE_CONTENT_MISMATCH', 'Structured article identity/metadata differs from source')
    if _normal(articles[0].get('articleBody', '')) != _normal(clean_article_html(post['content'])):
        reject('ARTICLE_CONTENT_MISMATCH', 'Structured article body differs from source')


def validate_source_hero(post: dict, hero_bytes: bytes) -> None:
    path = str(post.get('image') or '')
    if (not path.startswith('/images/generated/blog/') or any(part in {'', '.', '..'} for part in path.split('/')[1:])
            or '?' in path or '#' in path or len(str(post.get('imageAlt') or '')) < 20):
        reject('ARTICLE_HERO_MISMATCH', 'Authoritative hero violates the local image contract')
    try:
        width, height = image_dimensions(hero_bytes)
    except ValueError:
        reject('ARTICLE_HERO_MISMATCH', 'Authoritative hero cannot be fully decoded')
    if width < 640 or height < 360 or not 1.2 <= width / height <= 2.2:
        reject('ARTICLE_HERO_MISMATCH', 'Authoritative hero dimensions violate policy')


def verify_article_publication(identity: SourceIdentity, expected_sha: str, *, source: SourceSnapshot,
                               deployment: dict, manifest: FetchResult, article: FetchResult,
                               hero: FetchResult | None, verified_at: str) -> dict:
    require_sha(expected_sha, 40)
    timestamp(verified_at)
    try:
        metadata = source_metadata(source.post)
        actual = SourceIdentity(metadata['date'], metadata['slug'], metadata['content_sha256'])
        if actual != identity or source.commit_sha != expected_sha or source.main_sha != expected_sha:
            raise ValueError('Mismatched source revision')
    except (ValueError, KeyError, RuntimeError):
        reject('ARTICLE_SOURCE_MISMATCH', 'Authoritative article is not this exact source at observed main')
    if any(deployment.get(k) != v for k, v in {'head_sha': expected_sha, 'head_branch': 'main', 'status': 'completed', 'conclusion': 'success'}.items()):
        reject('ARTICLE_DEPLOY_UNVERIFIED', 'Exact main deployment has not succeeded')
    from .cloudflare_pages import PROJECT_ID, UUID
    if (deployment.get('provider') != 'cloudflare_pages' or deployment.get('project_id') != PROJECT_ID
            or not re.fullmatch(UUID, str(deployment.get('deployment_id', '')))
            or not re.fullmatch(r'[a-f0-9]{64}', str(deployment.get('build_sha256', '')))
            or not re.fullmatch(r'[a-f0-9]{64}', str(deployment.get('publication_manifest_sha256', '')))
            or type(deployment.get('artifact_id')) is not int or deployment['artifact_id'] <= 0):
        reject('ARTICLE_DEPLOY_UNVERIFIED', 'Exact canonical Cloudflare deployment and archived build are required')
    _response(manifest, MANIFEST_URL, code='ARTICLE_MANIFEST_MISMATCH')
    if hashlib.sha256(manifest.body).hexdigest() != deployment['publication_manifest_sha256']:
        reject('ARTICLE_MANIFEST_MISMATCH', 'Public manifest differs from the exact immutable build')
    _response(article, metadata['canonical_url'], code='ARTICLE_PUBLIC_ROUTE', trailing_slash=True)
    validate_source_hero(source.post, source.hero_bytes)
    image_sha = hashlib.sha256(source.hero_bytes).hexdigest()
    expected_record = {'identity': identity.to_dict(), 'canonical_url': metadata['canonical_url'],
                       'title': source.post['title'], 'date': source.post['date'],
                       'updated_at': source.post.get('updatedAt') or source.post['date'],
                       'post_sha256': digest(source.post), 'hero': {'path': source.post['image'], 'sha256': image_sha}}
    try:
        proof = json.loads(manifest.body)
        row = proof['articles'][identity.slug]
        if proof['schema_version'] != 1 or proof['deploy_sha'] != expected_sha or any(row.get(k) != v for k, v in expected_record.items()):
            raise ValueError('Manifest differs from source')
    except (ValueError, TypeError, KeyError, AttributeError):
        reject('ARTICLE_MANIFEST_MISMATCH', 'Public deployment manifest differs from independently fetched source')
    validate_rendered_html(article.body, source.post, deploy_sha=expected_sha)
    html_sha = hashlib.sha256(article.body).hexdigest()
    if row.get('html_sha256') != html_sha:
        reject('ARTICLE_CONTENT_MISMATCH', 'Public HTML differs from the deployed artifact')
    if hero is None:
        reject('ARTICLE_HERO_MISMATCH', 'Public hero not fetched')
    _response(hero, SITE_URL + source.post['image'], code='ARTICLE_HERO_MISMATCH')
    if hashlib.sha256(hero.body).hexdigest() != image_sha:
        reject('ARTICLE_HERO_MISMATCH', 'Public hero bytes differ from approved source')
    return {'identity': identity.to_dict(), 'verifier_version': 2, 'verified_at': verified_at,
            'deploy_sha': expected_sha, 'public_url': metadata['canonical_url'], 'hero_sha256': image_sha,
            'post_sha256': digest(source.post), 'html_sha256': html_sha, 'deployment_url': deployment['html_url'],
            'deployment_id': deployment['deployment_id'], 'build_sha256': deployment['build_sha256'],
            'artifact_id': deployment['artifact_id']}


def fetch_public(url: str, *, timeout: int, max_bytes: int) -> FetchResult:
    redirects = []
    class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not same_route(newurl, urllib.parse.unquote(url), trailing_slash=True) or len(redirects) >= 3:
                reject('ARTICLE_PUBLIC_ROUTE', 'Unexpected public redirect')
            redirects.append(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    opener = urllib.request.build_opener(RestrictedRedirect())
    try:
        response = opener.open(urllib.request.Request(url, headers={'User-Agent': 'Kesher-independent-public-verifier', 'Cache-Control': 'no-cache'}), timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            reject('ARTICLE_PUBLIC_HTTP', 'Public response exceeds bounded size')
        return FetchResult(response.status, response.geturl(), body, tuple(redirects))


class ArticlePublicVerifier:
    def __init__(self, source_reader, deployment_reader, transport=None):
        self.source_reader = source_reader
        self.deployment_reader = deployment_reader
        self.transport = transport or fetch_public

    def verify(self, identity: SourceIdentity, expected_sha: str, *, verified_at: str | None = None) -> dict:
        verified_at = verified_at or datetime.now(timezone.utc).isoformat()
        source = self.source_reader(expected_sha, identity.slug)
        deployment = self.deployment_reader(expected_sha)
        try:
            manifest = self.transport(MANIFEST_URL, timeout=20, max_bytes=4*1024*1024)
            article = self.transport(transport_url(SITE_URL + '/blog/' + identity.slug), timeout=20, max_bytes=4*1024*1024)
            hero = self.transport(transport_url(SITE_URL + source.post['image']), timeout=20, max_bytes=20*1024*1024)
        except (TimeoutError, OSError, urllib.error.URLError):
            reject('ARTICLE_PUBLIC_TRANSIENT', 'Read-only public observation temporarily unavailable')
        return verify_article_publication(identity, expected_sha, source=source, deployment=deployment,
                                           manifest=manifest, article=article, hero=hero, verified_at=verified_at)


class GitHubArticleReader:
    def __init__(self, github, repo: str):
        self.github, self.repo = github, repo

    def content(self, sha: str, path: str) -> bytes:
        require_sha(sha, 40)
        row = self.github.request('GET', f'/repos/{self.repo}/contents/{urllib.parse.quote(path, safe="/")}?ref={sha}')
        if row.get('encoding') == 'none':
            row = self.github.request('GET', f'/repos/{self.repo}/git/blobs/{row["sha"]}')
        if row.get('encoding') != 'base64':
            reject('ARTICLE_SOURCE_MISMATCH', 'Exact source blob is unreadable')
        return base64.b64decode(''.join(row['content'].split()), validate=True)

    def __call__(self, expected_sha: str, slug: str) -> SourceSnapshot:
        main = self.github.request('GET', f'/repos/{self.repo}/git/ref/heads/main')['object']['sha']
        posts = json.loads(self.content(expected_sha, 'src/data/posts.json'))
        rows = [post for post in posts if (post.get('slug') or post['id']) == slug]
        if len(rows) != 1:
            reject('ARTICLE_SOURCE_MISMATCH', 'Article slug is missing or ambiguous in exact main snapshot')
        post = rows[0]
        image = str(post.get('image') or '')
        if not image.startswith('/images/generated/blog/') or '..' in image.split('/'):
            reject('ARTICLE_HERO_MISMATCH', 'Unexpected source image path')
        return SourceSnapshot(expected_sha, main, post, self.content(expected_sha, 'public' + image))

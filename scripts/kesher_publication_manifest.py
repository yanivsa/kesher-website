"""Stamp verified build output with its exact deployment/source identity."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import subprocess
from pathlib import Path

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.kesher_daily_pipeline import PipelineError, source_metadata
from scripts.kesher_runtime.article_verification import reject, validate_rendered_html, validate_source_hero
from scripts.kesher_runtime.identity import SourceIdentity, digest, require_sha


def apply_topic_overrides(posts: list[dict], overrides: dict[str, dict]) -> list[dict]:
    """Return the effective post rows rendered by the site topic override layer."""
    return [
        {**post, **overrides.get(str(post.get('id') or ''), {})}
        for post in posts
    ]


def load_site_posts(root: Path) -> list[dict]:
    """Resolve the exact content catalog used by the site build."""
    loader = root / 'scripts' / 'load-posts.cjs'
    resolved = subprocess.run(
        [
            'node',
            '-e',
            (
                "const path=require('path'); "
                "const {loadPosts}=require(path.resolve(process.argv[1])); "
                "process.stdout.write(JSON.stringify(loadPosts()));"
            ),
            str(loader),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    try:
        posts = json.loads(resolved.stdout)
    except json.JSONDecodeError as exc:
        reject('ARTICLE_SOURCE_MISMATCH', f'Site publication catalog emitted invalid JSON: {exc}')
    if not isinstance(posts, list):
        reject('ARTICLE_SOURCE_MISMATCH', 'Site publication catalog is not an array')
    return posts


def generate(dist: Path, posts: list[dict], sha: str, *, exclusions: list[dict] | None = None,
             source_heroes: dict[str, bytes] | None = None) -> dict:
    require_sha(sha, 40)
    manifest = {'schema_version': 1, 'deploy_sha': sha, 'articles': {}, 'exclusions': list(exclusions or [])}
    writes = []
    for post in posts:
        try:
            source = source_metadata(post)
        except PipelineError:
            # These pre-contract legacy posts remain on the site but cannot be
            # used as evidence for the autonomous article/media contract.
            manifest['exclusions'].append({'id': str(post.get('id')), 'reason': 'unsupported_source_contract'})
            continue
        identity = SourceIdentity(source['date'], source['slug'], source['content_sha256'])
        if identity.slug in manifest['articles']:
            reject('ARTICLE_SOURCE_MISMATCH', 'Duplicate canonical article route')
        candidates = [dist/'blog'/identity.slug/'index.html', dist/'blog'/f'{identity.slug}.html']
        found = [path for path in candidates if path.is_file()]
        if len(found) != 1:
            reject('ARTICLE_PUBLIC_ROUTE', 'Canonical rendered route is absent or ambiguous: ' + identity.slug)
        route = found[0]
        hero_path = str(post.get('image') or '')
        if not hero_path.startswith('/images/generated/blog/') or '..' in hero_path.split('/'):
            manifest['exclusions'].append({'id': str(post.get('id')), 'reason': 'unsupported_legacy_hero_path'})
            continue
        image = dist/hero_path.lstrip('/')
        if not image.is_file():
            reject('ARTICLE_HERO_MISMATCH', 'Build is missing the authoritative hero bytes')
        hero_bytes = image.read_bytes()
        if source_heroes is not None and source_heroes.get(hero_path) != hero_bytes:
            reject('ARTICLE_HERO_MISMATCH', 'Rendered hero bytes differ from the exact commit')
        validate_source_hero(post, hero_bytes)
        content = route.read_bytes()
        validate_rendered_html(content, post)
        rendered = content.decode('utf-8')
        rendered = re.sub(r'<meta\b[^>]*\bname=[\"\x27]kesher:(?:deploy-sha|content-sha256)[\"\x27][^>]*>', '', rendered, flags=re.I)
        markers = f'<meta name="kesher:deploy-sha" content="{sha}"><meta name="kesher:content-sha256" content="{identity.content_sha256}">'
        if rendered.count('</head>') != 1:
            reject('ARTICLE_CONTENT_MISMATCH', 'Rendered article has no unique document head')
        final = rendered.replace('</head>', markers + '</head>').encode('utf-8')
        validate_rendered_html(final, post, deploy_sha=sha)
        writes.append((route, final))
        manifest['articles'][identity.slug] = {
            'identity': identity.to_dict(), 'canonical_url': source['canonical_url'], 'title': post['title'],
            'date': post['date'], 'updated_at': post.get('updatedAt') or post['date'],
            'post_sha256': digest(post), 'html_sha256': hashlib.sha256(final).hexdigest(),
            'hero': {'path': hero_path, 'sha256': hashlib.sha256(hero_bytes).hexdigest()},
        }
    # Validate the entire build before mutating any article or issuing a manifest.
    for path, content in writes:
        path.write_bytes(content)
    destination = dist/'.well-known/kesher-publication.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
    return manifest


def _apply_backfill(posts: list[dict], root: Path) -> list[dict]:
    rules = []
    for filename in ('internalLinkBackfill.json', 'internalLinkBackfillManual.json'):
        backfill_path = root / 'src' / 'data' / filename
        if not backfill_path.is_file():
            continue
        try:
            loaded = json.loads(backfill_path.read_text(encoding='utf-8'))
        except Exception:
            continue
        if isinstance(loaded, list):
            rules.extend(loaded)
    rule_map: dict[str, list[dict]] = {}
    for rule in rules:
        if not isinstance(rule, dict) or 'source' not in rule:
            continue
        rule_map.setdefault(str(rule['source']), []).append(rule)
    if not rule_map:
        return posts

    def escape_text(val: str) -> str:
        return val.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def decode_heading_text(h: str) -> str:
        h = re.sub(r'<[^>]+>', ' ', h)
        h = h.replace('&quot;', '"').replace('&#39;', "'").replace('&amp;', '&').replace('&nbsp;', ' ')
        return re.sub(r'\s+', ' ', h).strip()

    def has_internal_target(content: str, target: str) -> bool:
        pattern = rf'href=[\"\x27](?:https:\/\/kesher\.saharoni\.com)?\/blog\/{re.escape(target)}(?:[?#][^\"\x27]*)?[\"\x27]'
        return bool(re.search(pattern, content, re.I))

    applied = []
    for post in posts:
        post_rules = rule_map.get(str(post.get('id') or ''), [])
        if not post_rules or not isinstance(post.get('content'), str):
            applied.append(post)
            continue
        current = dict(post)
        for rule in post_rules:
            content = current['content']
            missing = [it for it in rule.get('items', []) if not has_internal_target(content, it.get('target', ''))]
            if not missing:
                continue
            needle = str(rule.get('afterHeadingIncludes') or '').strip()
            offset = None
            for m in re.finditer(r'<h3\b[^>]*>([\s\S]*?)<\/h3>', content, re.I):
                if needle in decode_heading_text(m.group(1)):
                    offset = m.end()
                    break
            if offset is None:
                continue
            rendered_items = [
                f"{escape_text(it.get('before', ''))}<a href=\"/blog/{it.get('target', '')}\">{escape_text(it.get('anchor', ''))}</a>{escape_text(it.get('after', ''))}"
                for it in missing
            ]
            post_id = current["id"]
            paragraph = f'<p data-kesher-internal-link-backfill="{post_id}">' + " ".join(rendered_items) + '</p>'
            current['content'] = content[:offset] + paragraph + content[offset:]
        applied.append(current)
    return applied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    parser.add_argument('--posts', type=Path, default=Path('src/data/posts.json'))
    parser.add_argument('--sha', required=True)
    args = parser.parse_args()
    checkout = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True, timeout=15).stdout.strip()
    if checkout != args.sha:
        reject('ARTICLE_SOURCE_MISMATCH', 'Deployment SHA differs from actual checkout')
    root = Path(subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True, timeout=15).stdout.strip())
    def committed(path):
        return subprocess.run(['git', 'show', f'{args.sha}:{path}'], capture_output=True, check=True, timeout=15).stdout
    # Resolve publication rows through the same catalog loader used by the site.
    # The checkout SHA is validated above, so these bytes are the exact deploy source.
    posts = load_site_posts(root)
    # Use the site's existing publication selector, not another Python copy of
    # its changing word/heading policy. Non-rendered legacy rows remain explicit.
    policy = Path(__file__).resolve().with_name('content-policy.cjs')
    selected = subprocess.run(['node', '-e',
        "const fs=require('fs'); const p=require(process.argv[1]); process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).filter(p.isPublishable).map(x=>x.id)));", str(policy)],
        input=json.dumps(posts), capture_output=True, text=True, check=True, timeout=30)
    ids = set(json.loads(selected.stdout))
    eligible = [post for post in posts if post['id'] in ids]
    eligible = _apply_backfill(eligible, root)
    excluded = [{'id': post['id'], 'reason': 'not_publishable_by_site_contract'} for post in posts if post['id'] not in ids]
    heroes = {post['image']: committed('public' + post['image']) for post in eligible
              if str(post.get('image') or '').startswith('/images/generated/blog/')
              and '..' not in post['image'].split('/')}
    proof = generate(args.dist, eligible, args.sha, exclusions=excluded, source_heroes=heroes)
    print(json.dumps({'deploy_sha': proof['deploy_sha'], 'verified_articles': len(proof['articles']), 'exclusions': proof['exclusions']}, ensure_ascii=False))


if __name__ == '__main__':
    main()

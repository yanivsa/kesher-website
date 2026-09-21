"""Exact deployed article proof: regressions for false-green 200/title checks."""
import copy
import hashlib
import importlib.util
import json
import io
import unittest
from dataclasses import replace
from urllib.parse import quote

from scripts.kesher_daily_pipeline import source_metadata
from scripts.kesher_runtime.identity import SourceIdentity

SHA = 'a' * 40
SITE = 'https://kesher.saharoni.com'
from PIL import Image
_image = io.BytesIO()
Image.new('RGB', (640, 360), '#abcdef').save(_image, format='PNG')
HERO = _image.getvalue()


def post_fixture(slug='מאמר-מדויק'):
    return {'id': slug, 'date': '2026-09-17', 'category': 'זוגיות', 'title': 'כותרת בעברית',
            'excerpt': 'תקציר בעברית', 'content': '<p>תוכן <strong>מדויק</strong> בעברית.</p>',
            'image': '/images/generated/blog/exact.png', 'imageAlt': 'שני אנשים משוחחים ליד שולחן בבית מואר'}


def html_fixture(post, *, markers=True):
    import html
    src = source_metadata(post)
    full_title = post['title'] + ' | שירה סהרוני'
    image_url = SITE + post['image']
    ld = {'@type': 'Article', 'headline': post['title'], 'url': src['canonical_url'],
          'datePublished': post['date'], 'dateModified': post.get('updatedAt', post['date']),
          'description': post['excerpt'], 'image': image_url,
          'articleBody': 'תוכן  מדויק  בעברית.'}
    meta = {'description': post['excerpt'], 'og:title': full_title, 'og:description': post['excerpt'],
            'og:url': src['canonical_url'], 'og:image': image_url, 'og:type': 'article',
            'twitter:title': full_title, 'twitter:description': post['excerpt'], 'twitter:image': image_url}
    if markers:
        meta.update({'kesher:deploy-sha': SHA, 'kesher:content-sha256': src['content_sha256']})
    tags = ''.join(f'<meta name="{k}" content="{html.escape(v, quote=True)}">' for k, v in meta.items())
    return (f'<!doctype html><html><head><title>{full_title}</title>{tags}'
            f'<link rel="canonical" href="{src["canonical_url"]}"></head><body><article>'
            f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
            f'<h1>{post["title"]}</h1><span data-kesher-article-date>{post["date"]}</span>'
            f'<img data-kesher-article-hero src="{post["image"]}" alt="{post["imageAlt"]}">'
            f'<div data-kesher-article-body>{post["content"]}</div></article></body></html>').encode()


class ArticlePublicTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.kesher_runtime.article_verification'),
                             'exact public article verifier must exist')
        from scripts.kesher_runtime import article_verification as av
        self.av = av
        self.post = post_fixture()
        self.source = source_metadata(self.post)
        self.identity = SourceIdentity(self.post['date'], self.post['id'], self.source['content_sha256'])
        self.url = SITE + '/blog/' + quote(self.post['id'])
        self.html = html_fixture(self.post)
        self.snapshot = av.SourceSnapshot(SHA, SHA, self.post, HERO)
        self.deployment = {'head_sha': SHA, 'head_branch': 'main', 'status': 'completed',
                           'conclusion': 'success', 'html_url': 'https://github.com/example/site/actions/runs/1'}
        row = {'identity': self.identity.to_dict(), 'canonical_url': self.source['canonical_url'],
               'title': self.post['title'], 'date': self.post['date'], 'updated_at': self.post['date'],
               'post_sha256': av.digest(self.post), 'html_sha256': hashlib.sha256(self.html).hexdigest(),
               'hero': {'path': self.post['image'], 'sha256': hashlib.sha256(HERO).hexdigest()}}
        self.manifest = {'schema_version': 1, 'deploy_sha': SHA, 'articles': {self.identity.slug: row}, 'exclusions': []}
        self.responses = {
            SITE + '/.well-known/kesher-publication.json': av.FetchResult(200, SITE + '/.well-known/kesher-publication.json', json.dumps(self.manifest).encode()),
            self.url: av.FetchResult(200, self.url + '/', self.html, (self.url, self.url + '/')),
            SITE + self.post['image']: av.FetchResult(200, SITE + self.post['image'], HERO),
        }

    def verify(self, **kwargs):
        args = {'source': self.snapshot, 'deployment': self.deployment,
                'manifest': self.responses[SITE + '/.well-known/kesher-publication.json'],
                'article': self.responses[self.url], 'hero': self.responses[SITE + self.post['image']],
                'verified_at': '2026-09-20T10:00:00+00:00'}
        args.update(kwargs)
        return self.av.verify_article_publication(self.identity, SHA, **args)

    def assert_rejected(self, failure_class, **kwargs):
        with self.assertRaises(self.av.ArticleVerificationError) as caught:
            self.verify(**kwargs)
        self.assertEqual(caught.exception.failure_class, failure_class)

    def test_exact_sha_source_content_metadata_and_hero_receive_identity_receipt(self):
        receipt = self.verify()
        self.assertEqual(receipt['identity'], self.identity.to_dict())
        self.assertEqual(receipt['deploy_sha'], SHA)
        self.assertEqual(receipt['public_url'], self.source['canonical_url'])
        self.assertEqual(receipt['verified_at'], '2026-09-20T10:00:00+00:00')
        self.assertEqual(receipt['verifier_version'], 1)
        self.assertEqual(receipt['hero_sha256'], hashlib.sha256(HERO).hexdigest())

    def test_green_deploy_with_404_cannot_complete(self):
        self.assert_rejected('ARTICLE_PUBLIC_HTTP', article=self.av.FetchResult(404, self.url, b'not found'))

    def test_success_for_other_sha_branch_or_pending_deployment_cannot_complete(self):
        for field, value in [('head_sha', 'b' * 40), ('head_branch', 'repair'), ('status', 'in_progress'), ('conclusion', 'failure')]:
            with self.subTest(field=field):
                self.assert_rejected('ARTICLE_DEPLOY_UNVERIFIED', deployment={**self.deployment, field: value})

    def test_source_not_at_exact_main_sha_or_changed_body_cannot_complete(self):
        for source in [replace(self.snapshot, commit_sha='b'*40), replace(self.snapshot, main_sha='b'*40),
                       replace(self.snapshot, post={**self.post, 'content': '<p>תוכן אחר</p>'})]:
            self.assert_rejected('ARTICLE_SOURCE_MISMATCH', source=source)

    def test_same_title_in_200_wrong_route_and_redirect_escape_cannot_complete(self):
        targets = [SITE + '/blog/wrong', SITE + '/blog/' + quote(self.identity.slug) + '?cache=1',
                   'https://other.invalid/blog/' + quote(self.identity.slug), self.url + '//',
                   self.url + '#fake', SITE + '/blog/' + quote(quote(self.identity.slug))]
        for target in targets:
            with self.subTest(target=target):
                self.assert_rejected('ARTICLE_PUBLIC_ROUTE', article=replace(self.responses[self.url], url=target))
        self.assert_rejected('ARTICLE_PUBLIC_ROUTE', article=replace(self.responses[self.url], redirects=(SITE + '/blog/wrong', self.url)))

    def test_stale_manifest_or_marker_does_not_pass(self):
        bad = copy.deepcopy(self.manifest); bad['deploy_sha'] = 'b'*40
        self.assert_rejected('ARTICLE_MANIFEST_MISMATCH', manifest=replace(self.responses[SITE + '/.well-known/kesher-publication.json'], body=json.dumps(bad).encode()))
        self.assert_rejected('ARTICLE_CONTENT_MISMATCH', article=replace(self.responses[self.url], body=self.html.replace(SHA.encode(), b'b'*40)))

    def test_forged_matching_manifest_hash_cannot_bypass_actual_body_metadata_or_hero(self):
        replacements = [('תוכן ', 'שונה '), ('כותרת בעברית</h1>', 'אחרת בעברית</h1>'),
                        ('name="description" content="תקציר בעברית"', 'name="description" content="תקציר שונה"'),
                        ('"datePublished": "2026-09-17"', '"datePublished": "2026-09-16"'),
                        ('src="/images/generated/blog/exact.png"', 'src="/images/generated/blog/wrong.png"')]
        for before, after in replacements:
            with self.subTest(before=before):
                changed = self.html.decode().replace(before, after).encode()
                self.assertNotEqual(changed, self.html)
                manifest = copy.deepcopy(self.manifest)
                manifest['articles'][self.identity.slug]['html_sha256'] = hashlib.sha256(changed).hexdigest()
                self.assert_rejected('ARTICLE_CONTENT_MISMATCH',
                    article=replace(self.responses[self.url], body=changed),
                    manifest=replace(self.responses[SITE + '/.well-known/kesher-publication.json'], body=json.dumps(manifest).encode()))

    def test_wrong_remote_image_bytes_cannot_be_authorized_by_manifest(self):
        changed = copy.deepcopy(self.manifest)
        changed['articles'][self.identity.slug]['hero']['sha256'] = hashlib.sha256(b'wrong').hexdigest()
        self.assert_rejected('ARTICLE_MANIFEST_MISMATCH', manifest=replace(self.responses[SITE + '/.well-known/kesher-publication.json'], body=json.dumps(changed).encode()))
        self.assert_rejected('ARTICLE_HERO_MISMATCH', hero=replace(self.responses[SITE+self.post['image']], body=b'wrong'))

    def test_adapter_fetches_encoded_canonical_routes_with_bounded_timeout(self):
        calls = []
        def fetch(url, *, timeout, max_bytes):
            self.assertGreater(timeout, 0); self.assertLessEqual(timeout, 20)
            self.assertLessEqual(max_bytes, 20*1024*1024)
            calls.append(url)
            return self.responses[url]
        verifier = self.av.ArticlePublicVerifier(lambda sha, slug: self.snapshot,
            lambda sha: self.deployment, transport=fetch)
        result = verifier.verify(self.identity, SHA, verified_at='2026-09-20T10:00:00+00:00')
        self.assertEqual(result['identity'], self.identity.to_dict())
        self.assertEqual(len(calls), 3)
        self.assertIn(self.url, calls)

    def test_transport_timeout_is_classified_and_not_product_completion(self):
        def timeout(*args, **kwargs):
            raise TimeoutError('network timed out')
        verifier = self.av.ArticlePublicVerifier(lambda sha, slug: self.snapshot, lambda sha: self.deployment, transport=timeout)
        with self.assertRaises(self.av.ArticleVerificationError) as caught:
            verifier.verify(self.identity, SHA)
        self.assertEqual(caught.exception.failure_class, 'ARTICLE_PUBLIC_TRANSIENT')


if __name__ == '__main__':
    unittest.main()

"""Deployment proofs are derived from real build bytes and cannot authorize bad HTML."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_kesher_article_public import HERO, SHA, html_fixture, post_fixture


class PublicationManifestTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.kesher_publication_manifest'), 'Build proof generator must exist')
        from scripts.kesher_publication_manifest import generate
        self.generate = generate

    def build(self, root, post):
        route = root / 'blog' / (post.get('slug') or post['id']) / 'index.html'
        route.parent.mkdir(parents=True)
        route.write_bytes(html_fixture(post, markers=False))
        hero = root / post['image'].lstrip('/')
        hero.parent.mkdir(parents=True)
        hero.write_bytes(HERO)
        return route

    def test_stamp_real_html_and_verify_repeatable_manifest(self):
        from scripts.kesher_runtime.article_verification import validate_rendered_html
        post = post_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            route = self.build(root, post)
            first = self.generate(root, [post], SHA)
            self.assertEqual(first['articles'][post['id']]['identity']['slug'], post['id'])
            validate_rendered_html(route.read_bytes(), post, deploy_sha=SHA)
            before = route.read_bytes()
            second = self.generate(root, [post], SHA)
            self.assertEqual(first, second)
            self.assertEqual(before, route.read_bytes())
            self.assertEqual(json.loads((root/'.well-known/kesher-publication.json').read_text()), first)

    def test_bad_render_is_not_certified_even_with_matching_title(self):
        from scripts.kesher_runtime.article_verification import ArticleVerificationError
        post = post_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            route = self.build(root, post)
            route.write_bytes(route.read_bytes().replace('תוכן '.encode(), 'שונה '.encode()))
            with self.assertRaises(ArticleVerificationError):
                self.generate(root, [post], SHA)
            self.assertFalse((root/'.well-known/kesher-publication.json').exists())

    def test_canonical_slug_cannot_be_replaced_by_id_alias(self):
        from scripts.kesher_runtime.article_verification import ArticleVerificationError
        post = {**post_fixture(), 'slug': 'מסלול-מוסמך'}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            route = self.build(root, post)
            alias = root/'blog'/post['id']/'index.html'
            alias.parent.mkdir(parents=True)
            route.rename(alias)
            with self.assertRaises(ArticleVerificationError):
                self.generate(root, [post], SHA)

    def test_build_image_cannot_substitute_for_exact_commit_image(self):
        from scripts.kesher_runtime.article_verification import ArticleVerificationError
        post = post_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build(root, post)
            with self.assertRaises(ArticleVerificationError):
                self.generate(root, [post], SHA, source_heroes={post['image']: b'different committed image'})


if __name__ == '__main__':
    unittest.main()

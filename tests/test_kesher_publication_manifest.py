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

    def test_effective_publication_source_applies_topic_override_before_verification(self):
        from scripts import kesher_publication_manifest as manifest

        self.assertTrue(
            hasattr(manifest, 'apply_topic_overrides'),
            'Publication proof must use the same topic overrides as the rendered site',
        )
        base = post_fixture()
        overrides = {
            base['id']: {
                'title': 'כותרת אפקטיבית',
                'excerpt': 'תקציר אפקטיבי',
                'updatedAt': '2026-10-23',
                'content': base['content'].replace('תוכן ', 'תוכן אפקטיבי ', 1),
            }
        }
        effective = manifest.apply_topic_overrides([base], overrides)
        self.assertEqual(effective[0]['title'], 'כותרת אפקטיבית')
        self.assertEqual(effective[0]['excerpt'], 'תקציר אפקטיבי')
        self.assertEqual(effective[0]['updatedAt'], '2026-10-23')
        self.assertIn('תוכן אפקטיבי', effective[0]['content'])
        self.assertEqual(base['title'], post_fixture()['title'], 'Applying an override must not mutate the source row')

    def test_publication_catalog_uses_same_resolved_posts_as_site(self):
        from scripts import kesher_publication_manifest as manifest

        posts = manifest.load_site_posts(Path.cwd())
        by_id = {post['id']: post for post in posts}
        self.assertIn('gifted-test-first-emotional-preparation-parents', by_id)
        self.assertIn('how-to-talk-to-child-about-being-gifted', by_id)

        pillar = by_id['how-to-identify-a-gifted-child-parents-guide']
        self.assertEqual(
            pillar['title'],
            'מה זה ילד מחונן? הגדרה, מאפיינים ומה חשוב להורים לדעת',
            'Wave 2 additions must not replace the earlier title/content override',
        )
        self.assertIn(
            'gifted-child-emotional-sensitivity-myths',
            pillar['relatedPostIds'],
            'Wave 2 related-post additions must still be present',
        )

    def test_effective_publication_source_applies_all_backfill_rules_for_same_post(self):
        from scripts import kesher_publication_manifest as manifest

        post = {
            **post_fixture(),
            'id': 'multi-backfill-source',
            'slug': 'multi-backfill-source',
            'content': '<h3>כותרת ראשונה</h3><p>פתיחה.</p><h3>כותרת שנייה</h3><p>המשך.</p>',
        }
        automatic_rule = {
            'source': post['id'],
            'afterHeadingIncludes': '',
            'items': [{
                'target': 'automatic-target',
                'anchor': 'קישור אוטומטי',
                'before': 'אוטומטי: ',
                'after': '.',
            }],
        }
        manual_rule = {
            'source': post['id'],
            'afterHeadingIncludes': 'כותרת שנייה',
            'items': [{
                'target': 'manual-target',
                'anchor': 'קישור ידני',
                'before': 'ידני: ',
                'after': '.',
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / 'src' / 'data'
            data.mkdir(parents=True)
            (data / 'internalLinkBackfill.json').write_text(
                json.dumps([automatic_rule], ensure_ascii=False),
                encoding='utf-8',
            )
            (data / 'internalLinkBackfillManual.json').write_text(
                json.dumps([manual_rule], ensure_ascii=False),
                encoding='utf-8',
            )

            effective = manifest._apply_backfill([post], root)

        content = effective[0]['content']
        self.assertIn('/blog/automatic-target', content)
        self.assertIn('/blog/manual-target', content)
        self.assertLess(content.index('/blog/automatic-target'), content.index('/blog/manual-target'))

    def test_effective_publication_source_applies_manual_internal_link_backfill(self):
        from scripts import kesher_publication_manifest as manifest

        post = {
            **post_fixture(),
            'id': 'manual-backfill-source',
            'slug': 'manual-backfill-source',
            'content': '<h3>כותרת יעד לבדיקה</h3><p>תוכן קיים.</p>',
        }
        manual_rule = {
            'source': post['id'],
            'afterHeadingIncludes': 'כותרת יעד',
            'items': [{
                'target': 'family-chores-quality-time-with-kids',
                'anchor': 'מטלות בית עם ילדים',
                'before': 'להמשך קריאה: ',
                'after': '.',
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / 'src' / 'data'
            data.mkdir(parents=True)
            (data / 'internalLinkBackfill.json').write_text('[]\n', encoding='utf-8')
            (data / 'internalLinkBackfillManual.json').write_text(
                json.dumps([manual_rule], ensure_ascii=False),
                encoding='utf-8',
            )

            effective = manifest._apply_backfill([post], root)

        self.assertIn('/blog/family-chores-quality-time-with-kids', effective[0]['content'])
        self.assertIn('מטלות בית עם ילדים', effective[0]['content'])


if __name__ == '__main__':
    unittest.main()

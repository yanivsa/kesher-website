import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / '.github/scripts/validate-article-pr.py'
spec = importlib.util.spec_from_file_location('internal_link_validator', path)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ArticleInternalLinkGateTests(unittest.TestCase):
    def test_complete_trusted_publication_index_includes_topic_and_archived_sources(self):
        pr = {'state': 'open', 'title': 'Publish Kesher article: Test',
              'head': {'repo': {'full_name': 'owner/repo'}},
              'base': {'ref': 'main', 'repo': {'full_name': 'owner/repo'}}}
        post = {'id': 'new-post', 'content': '<a href="/blog/gifted-test-first-emotional-preparation-parents">א</a><a href="/blog/archive-only">ב</a><a href="/blog/thin-unpublished">ג</a>'}
        thin = {'id': 'thin-unpublished', 'content': 'too short'}
        errors = validator.evaluate_content(pr, [{'filename': 'src/data/posts.json'}], [thin],
            [post, thin], lambda _: b'',
            published_catalog=[{'id': 'gifted-test-first-emotional-preparation-parents'}, {'id': 'archive-only'}])
        links = [e for e in errors if e.startswith('internal_blog_link_missing')]
        self.assertEqual(links, ['internal_blog_link_missing: /blog/thin-unpublished'])

    def test_invented_blog_target_is_rejected_before_image_checks(self):
        pr = {'state': 'open', 'title': 'Publish Kesher article: Test',
              'head': {'repo': {'full_name': 'owner/repo'}},
              'base': {'ref': 'main', 'repo': {'full_name': 'owner/repo'}}}
        post = {'id': 'new-post', 'title': 'Test',
                'content': '<a href="/blog/toddler-tantrums-causes">קישור</a>'}
        errors = validator.evaluate_content(pr, [{'filename': 'src/data/posts.json'}], [], [post], lambda _: self.fail('image must not be read'))
        self.assertTrue(any('internal_blog_link_missing: /blog/toddler-tantrums-causes' in e for e in errors), errors)

    def test_real_targets_support_archived_posts_encoded_slugs_and_fragments(self):
        content = ('<a href=/blog/existing?x=1#section>א</a>'
                   '<a href="https://kesher.saharoni.com/blog/%D7%92%D7%9F/">ב</a>'
                   '<a href="https://other.example/blog/external">ג</a>')
        self.assertEqual(validator.internal_blog_link_errors(content, [{'id': 'existing'}, {'slug': 'גן'}]), [])

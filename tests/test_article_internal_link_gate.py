import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / '.github/scripts/validate-article-pr.py'
spec = importlib.util.spec_from_file_location('internal_link_validator', path)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ArticleInternalLinkGateTests(unittest.TestCase):
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

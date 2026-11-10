import unittest

from scripts.kesher_runtime.article_quiescence import is_master_article_pr


class MasterArticleOriginTests(unittest.TestCase):
    def pr(self, *, ref='master/kesher-article/2026-10-31-example', body='Kesher-Origin: master-active-supervisor'):
        return {'number': 1264, 'body': body, 'head': {'ref': ref, 'sha': 'a' * 40}}

    def test_requires_branch_and_provenance_marker(self):
        self.assertTrue(is_master_article_pr(self.pr()))
        self.assertFalse(is_master_article_pr(self.pr(ref='publish-article-example')))
        self.assertFalse(is_master_article_pr(self.pr(body='')))

    def test_rejects_marker_hidden_inside_other_text(self):
        self.assertFalse(is_master_article_pr(self.pr(body='note: Kesher-Origin: master-active-supervisor later')))


if __name__ == '__main__':
    unittest.main()

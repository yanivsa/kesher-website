import unittest

from scripts.kesher_article_normalizer import (
    ArticleNormalizationError,
    extract_target_article,
    normalized_posts,
)


class ArticleNormalizerTests(unittest.TestCase):
    def setUp(self):
        self.main_posts = [
            {"id": "sep-03", "date": "2026-09-03", "title": "newest", "content": "A"},
            {"id": "sep-01", "date": "2026-09-01", "title": "later", "content": "B"},
            {"id": "aug-26", "date": "2026-08-26", "title": "older", "content": "C"},
        ]
        self.target = {
            "id": "aug-27-target",
            "date": "2026-08-27",
            "title": "target",
            "content": "TARGET",
        }

    def test_extracts_only_target_slot_from_dirty_head(self):
        dirty_head = [
            {"id": "sep-03", "date": "2026-09-03", "title": "MUTATED", "content": "BAD"},
            {"id": "aug-31-unrelated", "date": "2026-08-31", "title": "unrelated", "content": "X"},
            self.target,
            {"id": "aug-26", "date": "2026-08-26", "title": "older", "content": "C"},
        ]
        self.assertEqual(
            extract_target_article(self.main_posts, dirty_head, "2026-08-27"),
            self.target,
        )

    def test_normalized_posts_preserve_main_and_insert_target_by_date(self):
        result = normalized_posts(self.main_posts, self.target)
        self.assertEqual(
            [post["id"] for post in result],
            ["sep-03", "sep-01", "aug-27-target", "aug-26"],
        )
        self.assertEqual(result[0], self.main_posts[0])
        self.assertEqual(result[1], self.main_posts[1])
        self.assertEqual(result[3], self.main_posts[2])

    def test_normalized_posts_do_not_mutate_base_objects(self):
        before = [dict(post) for post in self.main_posts]
        normalized_posts(self.main_posts, self.target)
        self.assertEqual(self.main_posts, before)

    def test_rejects_duplicate_target_slot_already_in_main(self):
        base = [*self.main_posts, {"id": "already", "date": "2026-08-27"}]
        with self.assertRaises(ArticleNormalizationError):
            normalized_posts(base, self.target)

    def test_rejects_missing_target_article(self):
        with self.assertRaises(ArticleNormalizationError):
            extract_target_article(self.main_posts, self.main_posts, "2026-08-27")


if __name__ == "__main__":
    unittest.main()

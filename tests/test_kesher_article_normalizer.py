import unittest

from scripts.kesher_article_normalizer import (
    ArticleNormalizationError,
    extract_target_article,
    normalization_required,
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
            "slug": "aug-27-target",
            "controllerManaged": True,
            "date": "2026-08-27",
            "title": "target",
            "content": "TARGET",
        }

    def test_recent_owned_article_cannot_omit_slug_or_management_marker(self):
        post = {**self.target, "date": "2026-10-25"}
        post.pop("slug")
        post.pop("controllerManaged")
        result = extract_target_article(self.main_posts, [*self.main_posts, post], "2026-10-25")
        self.assertEqual(result.get("slug"), post["id"])
        self.assertIs(result.get("controllerManaged"), True)
        self.assertNotIn("slug", post)
        self.assertNotIn("controllerManaged", post)

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

    def test_allows_distinct_articles_on_current_active_date(self):
        import os
        old_env = os.environ.get("KESHER_TODAY_ISO")
        try:
            os.environ["KESHER_TODAY_ISO"] = "2026-10-19"
            base = [
                {"id": "pacifier-weaning", "date": "2026-10-19", "controllerManaged": True},
                {"id": "older-post", "date": "2026-10-15"},
            ]
            new_target = {
                "id": "potty-training-toddlers",
                "date": "2026-10-19",
                "controllerManaged": True,
            }
            res = normalized_posts(base, new_target)
            ids = [p["id"] for p in res]
            self.assertIn("pacifier-weaning", ids)
            self.assertIn("potty-training-toddlers", ids)
            self.assertEqual(len(res), 3)

            # But duplicate slug fails
            dup_slug = {
                "id": "pacifier-weaning",
                "date": "2026-10-19",
                "controllerManaged": True,
            }
            with self.assertRaises(ArticleNormalizationError):
                normalized_posts(base, dup_slug)
        finally:
            if old_env is None:
                os.environ.pop("KESHER_TODAY_ISO", None)
            else:
                os.environ["KESHER_TODAY_ISO"] = old_env

    def test_rejects_missing_target_article(self):
        with self.assertRaises(ArticleNormalizationError):
            extract_target_article(self.main_posts, self.main_posts, "2026-08-27")

    def test_dirty_head_requires_normalization(self):
        dirty_head = [
            {"id": "sep-03", "date": "2026-09-03", "title": "MUTATED", "content": "BAD"},
            self.target,
            {"id": "aug-26", "date": "2026-08-26", "title": "older", "content": "C"},
        ]
        self.assertTrue(
            normalization_required(
                self.main_posts,
                dirty_head,
                "2026-08-27",
                ["src/data/posts.json", "src/pages/Home/Home.module.css"],
            )
        )

    def test_clean_canonical_head_does_not_require_normalization(self):
        clean_head = normalized_posts(self.main_posts, self.target)
        self.assertFalse(
            normalization_required(
                self.main_posts,
                clean_head,
                "2026-08-27",
                ["src/data/posts.json", "src/data/postSummaries.json", "public/rss.xml"],
            )
        )


if __name__ == "__main__":
    unittest.main()

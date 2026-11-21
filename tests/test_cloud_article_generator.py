"""Unit tests for the Kesher Cloud Article & Hero Image Generator."""

import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

import scripts.kesher_cloud_article_generator as generator


class CloudArticleGeneratorTests(unittest.TestCase):
    def test_topic_selection_anti_cannibalization(self):
        posts = generator.load_all_posts()
        slugs, titles, _ = generator.existing_slugs_and_titles(posts)
        topic = generator.select_original_topic(posts)
        self.assertNotIn(topic["slug"].lower(), slugs)
        self.assertNotIn(topic["title"].lower(), titles)
        self.assertTrue(len(topic["title"]) > 10)
        self.assertTrue(topic["slug"])

    def test_hero_image_generation_dimensions_and_size(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            size_bytes = generator.generate_hero_image(
                "test-cloud-hero-spec",
                "איך להתמודד עם מריחות זמן בהשכבה",
                "הדרכת הורים",
                tmp_path,
            )
            self.assertTrue(tmp_path.is_file())
            self.assertGreaterEqual(size_bytes, 15000)

            with Image.open(tmp_path) as img:
                self.assertEqual(img.width, 1200)
                self.assertEqual(img.height, 675)
                ratio = round(img.width / img.height, 2)
                self.assertEqual(ratio, 1.78)
        finally:
            if tmp_path.is_file():
                tmp_path.unlink()

    def test_dry_run_does_not_mutate_files(self):
        recent_text_before = generator.RECENT_POSTS_FILE.read_text(encoding="utf-8")
        result = generator.generate_article("2026-11-21", dry_run=True)
        self.assertEqual(result["status"], "dry_run_success")
        self.assertTrue(result["slug"])
        self.assertTrue(result["source_sha256"])
        recent_text_after = generator.RECENT_POSTS_FILE.read_text(encoding="utf-8")
        self.assertEqual(recent_text_before, recent_text_after)

    def test_article_structure_and_no_latin_characters_in_prose(self):
        posts = generator.load_all_posts()
        topic = generator.select_original_topic(posts)
        html = generator.build_article_html(topic["content_sections"])

        # Strip html tags to inspect visible text
        import re
        visible_text = re.sub(r"<[^>]+>", " ", html)
        latin_matches = re.findall(r"[A-Za-z]+", visible_text)
        self.assertEqual(
            latin_matches,
            [],
            f"Found forbidden Latin characters in visible prose: {latin_matches}"
        )

        # Check required structure
        self.assertIn("<h3>", html)
        self.assertIn("<p>", html)
        self.assertIn("<ul>", html)
        self.assertIn("שירה סהרוני", html)

    def test_custom_topic_brief_synthesis(self):
        posts = generator.load_all_posts()
        topic = generator.select_original_topic(
            posts,
            requested_brief="איך לעזור לילד שמתקשה להיפרד בבוקר בכניסה לגן?",
            requested_keyword="פרידה בבוקר בגן",
            requested_id="morning-separation-daycare-tears",
        )
        self.assertEqual(topic["slug"], "morning-separation-daycare-tears")
        self.assertIn("פרידה בבוקר בגן", topic["title"])
        self.assertEqual(topic["primaryKeyword"], "פרידה בבוקר בגן")
        self.assertEqual(len(topic["content_sections"]), 5)
        self.assertTrue(len(topic["evidence"]) >= 1)
        for ev in topic["evidence"]:
            self.assertTrue(ev["url"].startswith("https://pubmed.ncbi.nlm.nih.gov/"))

    def test_publishable_word_and_section_count(self):
        posts = generator.load_all_posts()
        topic = generator.select_original_topic(posts)
        html = generator.build_article_html(topic["content_sections"])
        import re
        words = len(re.sub(r"<[^>]+>", " ", html).split())
        h3_count = len(re.findall(r"<h3", html))
        self.assertGreaterEqual(words, 450)
        self.assertGreaterEqual(h3_count, 4)

    def test_duplicate_slug_injection_rejected(self):
        posts = generator.load_all_posts()
        if not posts:
            return
        existing = posts[0]
        existing_slug = existing.get("slug") or existing.get("id")
        with self.assertRaises(ValueError):
            generator.generate_article(
                "2026-11-21",
                article_json={"id": existing_slug, "slug": existing_slug, "title": "Test"},
                dry_run=True,
            )


if __name__ == "__main__":
    unittest.main()

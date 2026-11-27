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

    def test_production_hero_is_written_to_git_staging_public_path(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generated = []

            def save_hero(slug, title, category, output_path):
                generated.append(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(b"verified hero path test fixture")
                return output_path.stat().st_size

            with (
                patch.object(generator, "ROOT", root),
                patch.object(generator, "load_all_posts", return_value=[]),
                patch.object(generator, "generate_hero_image", side_effect=save_hero),
            ):
                article = generator.generate_article("2026-11-22", dry_run=False)

            expected = root / "public" / article["hero_image"].lstrip("/")
            self.assertEqual(generated, [expected])
            self.assertTrue(expected.is_file())
            self.assertFalse((root / article["hero_image"].lstrip("/")).is_file())

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

    def test_source_hash_matches_notebooklm(self):
        """Regression: no JSON-record hash can be substituted for media identity."""
        from scripts.kesher_daily_pipeline import source_metadata

        topic = generator.select_original_topic(generator.load_all_posts())
        post = {
            "id": topic["slug"],
            "slug": topic["slug"],
            "title": topic["title"],
            "date": "2026-11-22",
            "category": topic["category"],
            "subcategory": topic.get("subcategory", ""),
            "excerpt": topic["excerpt"],
            "content": generator.build_article_html(topic["content_sections"]),
        }
        expected = source_metadata(post)["content_sha256"]
        self.assertEqual(generator.compute_article_sha256(post), expected)

        # Previously the publisher hashed a JSON subset rather than the
        # exact published NotebookLM source body. This must not regress.
        import hashlib
        legacy_subset = {
            "id": post["id"],
            "title": post["title"],
            "excerpt": post["excerpt"],
            "content": post["content"],
            "directAnswer": "",
            "primaryKeyword": "",
        }
        legacy = hashlib.sha256(
            json.dumps(legacy_subset, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        self.assertNotEqual(expected, legacy)

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



class DailyTrendInputTests(unittest.TestCase):
    def fixture(self):
        from datetime import datetime, timezone
        from scripts.kesher_daily_trend import SCHEMA
        slot = "2026-11-27"
        posts = [{"slug": s, "category": "הדרכת הורים", "serviceUrl": "/services/parenting"}
                 for s in ("first-link", "second-link", "third-link")]
        urls = ["https://example.org/news", "https://example.net/report"]
        content = "<p>הורות קשובה " + " ".join(["דוגמה"] * 1000) + "</p>"
        content += "<h3>כותרת</h3>" * 5
        content += "".join(f'<a href="/blog/{p["slug"]}">קריאה</a>' for p in posts)
        content += '<a href="/services/parenting">הדרכה</a>'
        content += "".join(f'<a href="{u}">מקור</a>' for u in urls)
        article = dict(slug="daily-parenting-trend", title="הורות קשובה בבית", category="הדרכת הורים",
                       subcategory="קשר", tags=["הורות"], serviceUrl="/services/parenting",
                       serviceLabel="הדרכת הורים", excerpt="תקציר", directAnswer="תשובה",
                       evidence=[{"url":"https://pubmed.ncbi.nlm.nih.gov/12345/"}],
                       content=content, primaryKeyword="הורות קשובה", imageAlt="צילום משפחתי")
        packet = dict(schema=SCHEMA, slot=slot, article=article,
                      research=dict(relevance="קשר להורות", trend_signal=dict(url=urls[0], description="סיקור"),
                                    news=[dict(url=u, title="דיווח", published_date="2026-11-26") for u in urls]))
        issue = dict(number=1, title=f"[TrendBrief] {slot}", state="open", author_association="OWNER",
                     user=dict(login="yanivsa"), created_at="2026-11-26T21:00:00Z")
        return slot, posts, packet, issue

    def test_valid_owner_packet_and_safe_image_identity(self):
        from unittest.mock import patch
        from scripts.kesher_daily_trend import select_from_issues
        slot, posts, packet, issue = self.fixture()
        issue["body"] = json.dumps(packet, ensure_ascii=False)
        with patch.object(generator, "validate_article_candidate"):
            number, post = select_from_issues([issue], slot, posts)
        self.assertEqual(number, 1)
        self.assertEqual(post["image"], "/images/generated/blog/daily-parenting-trend.jpg")
        self.assertEqual(post["date"], slot)
        self.assertEqual(post["content"], packet["article"]["content"])

    def test_missing_packet_is_regular_fallback(self):
        from scripts.kesher_daily_trend import select_from_issues
        slot, posts, _, _ = self.fixture()
        self.assertIsNone(select_from_issues([], slot, posts))

    def test_duplicate_packet_rejected(self):
        from scripts.kesher_daily_trend import select_from_issues
        slot, posts, packet, issue = self.fixture()
        issue["body"] = json.dumps(packet)
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS"):
            select_from_issues([issue, dict(issue, number=2)], slot, posts)

    def test_unsafe_html_and_stale_news_are_rejected(self):
        from scripts.kesher_daily_trend import parse_issue
        slot, posts, packet, issue = self.fixture()
        packet["article"]["content"] += "<script>bad()</script>"
        issue["body"] = json.dumps(packet)
        with self.assertRaisesRegex(ValueError, "HTML_TAG"):
            parse_issue(issue, slot, posts)
        packet["research"]["news"][0]["published_date"] = "2026-10-01"
        issue["body"] = json.dumps(packet)
        with self.assertRaisesRegex(ValueError, "NEWS_STALE"):
            parse_issue(issue, slot, posts)

    def test_other_owner_or_reused_keyword_rejected(self):
        from scripts.kesher_daily_trend import parse_issue
        slot, posts, packet, issue = self.fixture()
        issue["body"] = json.dumps(packet)
        with self.assertRaisesRegex(ValueError, "ISSUE_OWNER"):
            parse_issue(dict(issue, user={"login":"other"}), slot, posts)
        posts[0]["primaryKeyword"] = packet["article"]["primaryKeyword"]
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            parse_issue(issue, slot, posts)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from scripts.kesher_cloud_article_generator import synthesize_article_from_brief


class SemanticSlugAndEditorialGuardTests(unittest.TestCase):
    def test_parenting_keyword_wins_over_incidental_couples_words(self):
        row = synthesize_article_from_brief(
            "הדרכת הורים ומחקר על קשר עם ילדים לצד אזכור זוגיות ברקע.",
            primary_keyword="הורים בטלפון ליד הילדים",
            idea_id="parents-phone-distraction-child-connection",
            posts=[],
        )
        self.assertEqual(row["slug"], "parents-phone-distraction-child-connection")
        self.assertEqual(row["category"], "הדרכת הורים")
        self.assertEqual(row["serviceUrl"], "/services/parenting")

    def test_hebrew_brief_never_falls_back_to_hash_slug(self):
        with self.assertRaisesRegex(ValueError, "SEO_SEMANTIC_SLUG_REQUIRED"):
            synthesize_article_from_brief(
                "הורה מסתכל בטלפון בזמן שהילד מדבר",
                primary_keyword="הורים בטלפון ליד הילדים",
                posts=[],
            )

    def test_opaque_guidance_id_rejected_even_if_explicit(self):
        with self.assertRaisesRegex(ValueError, "SEO_SEMANTIC_SLUG_INVALID"):
            synthesize_article_from_brief(
                "הורה בטלפון", primary_keyword="הורים בטלפון",
                idea_id="guidance-1234abcd", posts=[],
            )

    def test_detailed_research_brief_requires_verified_article_json(self):
        with self.assertRaisesRegex(ValueError, "EDITORIAL_BRIEF_REQUIRES_ARTICLE_JSON"):
            synthesize_article_from_brief(
                "הורים בטלפון ומחקר: " + "הקשר בין שימוש בטלפון, קשר עם הילד, משפחות ומשחק. " * 20,
                primary_keyword="הורים בטלפון ליד הילדים",
                idea_id="parents-phone-distraction-child-connection",
                posts=[],
            )

    def test_short_english_topic_remains_readable(self):
        row = synthesize_article_from_brief(
            "parents phone distraction child connection",
            primary_keyword="הורים בטלפון ליד הילדים",
            posts=[],
        )
        self.assertEqual(row["slug"], "parents-phone-distraction-child-connection")


if __name__ == "__main__":
    unittest.main()

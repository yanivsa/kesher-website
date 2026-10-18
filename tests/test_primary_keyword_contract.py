#!/usr/bin/env python3
"""Comprehensive test suite for Jules article Primary Keyword contract."""

import json
from pathlib import Path
import unittest
from unittest import mock

from scripts.jules_article_runner_v4 import PRIMARY_KEYWORD_CONTRACT, build_prompt
from scripts.kesher_primary_keyword_contract import (
    SEMANTIC_KEYWORD_DICTIONARY,
    extract_first_paragraph,
    keyword_in_opening,
    matches_keyword,
    normalize_hebrew_text,
    parse_owner_required_keyword,
    slug_represents_keyword,
    validate_primary_keyword_contract,
)


class TestPrimaryKeywordContract(unittest.TestCase):
    def setUp(self):
        self.posts_file = Path(__file__).resolve().parent.parent / "src" / "data" / "posts.json"

    def test_01_valid_pr_fixture_passes(self):
        """Valid article post and PR body containing Primary Keyword pass validation."""
        post = {
            "id": "potty-training-toddlers",
            "slug": "potty-training-toddlers",
            "title": "גמילה מטיטול: איך לזהות מוכנות ולהתחיל נכון",
            "content": "<p>גמילה מטיטול היא שלב התפתחותי מרגש ומאתגר עבור כל הורה. במדריך זה נבחן את כל הסימנים.</p><p>המשך התוכן...</p>",
            "canonicalUrl": "https://kesher.saharoni.com/blog/potty-training-toddlers",
            "primaryKeyword": "גמילה מטיטול",
        }
        pr_body = """## Jules Article Candidate
- Slug: potty-training-toddlers
- Primary Keyword: גמילה מטיטול
- Primary Search Query: גמילה מטיטול
"""
        errors = validate_primary_keyword_contract(post, pr_body)
        self.assertEqual(errors, [])

    def test_02_fails_when_primary_keyword_audit_field_is_missing(self):
        """Fails when Primary Keyword is missing from both PR body and post object."""
        post = {
            "id": "potty-training-toddlers",
            "slug": "potty-training-toddlers",
            "title": "גמילה מטיטול: איך לזהות מוכנות",
            "content": "<p>גמילה מטיטול היא שלב התפתחותי מרגש.</p>",
        }
        pr_body = """## Jules Article Candidate
- Slug: potty-training-toddlers
"""
        errors = validate_primary_keyword_contract(post, pr_body)
        self.assertTrue(any("missing required 'Primary Keyword'" in e for e in errors))

    def test_03_fails_when_owner_required_keyword_does_not_match(self):
        """Fails when owner topic brief specified Required Primary Keyword that was not used."""
        post = {
            "id": "couples-communication",
            "slug": "couples-communication",
            "title": "תקשורת זוגית: איך לפתור מחלוקות",
            "content": "<p>תקשורת זוגית בריאה היא בסיס לכל קשר יציב.</p>",
            "primaryKeyword": "תקשורת זוגית",
        }
        pr_body = "- Primary Keyword: תקשורת זוגית\n"
        topic_brief = "Required Primary Keyword: גמילה מטיטול\nTopic: גמילה מוקדמת"

        errors = validate_primary_keyword_contract(post, pr_body, owner_topic_brief=topic_brief)
        self.assertTrue(any("does not match required owner keyword" in e for e in errors))

    def test_04_fails_when_primary_keyword_missing_from_title(self):
        """Fails when declared Primary Keyword is absent from title / H1."""
        post = {
            "id": "potty-training-toddlers",
            "slug": "potty-training-toddlers",
            "title": "איך לעבור את הקיץ בשלום עם פעוטות",  # Missing "גמילה מטיטול"
            "content": "<p>גמילה מטיטול היא שלב התפתחותי מרגש.</p>",
            "primaryKeyword": "גמילה מטיטול",
        }
        pr_body = "- Primary Keyword: גמילה מטיטול\n"
        errors = validate_primary_keyword_contract(post, pr_body)
        self.assertTrue(any("missing from article title" in e for e in errors))

    def test_05_fails_when_primary_keyword_missing_from_first_paragraph_opening(self):
        """Fails when Primary Keyword appears late (after first 25 words) or not at all in opening."""
        # Multi-sentence filler with > 25 words before mentioning the keyword
        filler = (
            "זהו מאמר מקיף ומעמיק אשר מציג בפני ההורים את התהליכים ההתפתחותיים השונים שעוברים ילדים בגיל הרך בישראל. "
            "צוות המומחים שלנו אסף עבורכם תובנות וכלים מעשיים להתמודדות יומיומית. "
        )
        post = {
            "id": "potty-training-toddlers",
            "slug": "potty-training-toddlers",
            "title": "גמילה מטיטול: צעדים ראשונים",
            "content": f"<p>{filler}גמילה מטיטול היא נושא חשוב.</p>",
            "primaryKeyword": "גמילה מטיטול",
        }
        pr_body = "- Primary Keyword: גמילה מטיטול\n"
        errors = validate_primary_keyword_contract(post, pr_body)
        self.assertTrue(any("must appear in the first paragraph opening sentence or first 25 words" in e for e in errors))

    def test_06_fails_when_slug_does_not_represent_keyword(self):
        """Fails when slug contains unrelated English words that do not represent keyword concepts."""
        post = {
            "id": "financial-planning-advice",  # Unrelated slug
            "slug": "financial-planning-advice",
            "title": "גמילה מטיטול: צעדים ראשונים",
            "content": "<p>גמילה מטיטול היא שלב חשוב בהתפתחות הפעוט.</p>",
            "primaryKeyword": "גמילה מטיטול",
        }
        pr_body = "- Primary Keyword: גמילה מטיטול\n"
        errors = validate_primary_keyword_contract(post, pr_body)
        self.assertTrue(any("does not contain expected semantic concepts" in e for e in errors))

    def test_07_fails_when_canonical_url_does_not_match_slug(self):
        """Fails when canonical URL path does not match /blog/<slug>."""
        post = {
            "id": "potty-training-toddlers",
            "slug": "potty-training-toddlers",
            "title": "גמילה מטיטול: צעדים ראשונים",
            "content": "<p>גמילה מטיטול היא שלב חשוב בהתפתחות הפעוט.</p>",
            "canonicalUrl": "https://kesher.saharoni.com/blog/different-slug-here",
            "primaryKeyword": "גמילה מטיטול",
        }
        pr_body = "- Primary Keyword: גמילה מטיטול\n"
        errors = validate_primary_keyword_contract(post, pr_body)
        self.assertTrue(any("does not use the expected slug" in e for e in errors))

    def test_08_passes_with_hebrew_prefix_variants(self):
        """Passes when title or opening uses valid Hebrew prefixes (ב, ל, מ, ש, ה, ו, כ...)."""
        prefixes = ["ב", "ל", "מ", "ש", "ה", "כ", "ו"]
        for pfx in prefixes:
            postfx_title = f"{pfx}גמילה מטיטול: מדריך להורים"
            postfx_content = f"<p>{pfx}גמילה מטיטול יכולה להיות תהליך נעים כשיודעים לזהות את הסימנים.</p>"
            post = {
                "id": "potty-training-toddlers",
                "slug": "potty-training-toddlers",
                "title": postfx_title,
                "content": postfx_content,
                "primaryKeyword": "גמילה מטיטול",
            }
            pr_body = "- Primary Keyword: גמילה מטיטול\n"
            errors = validate_primary_keyword_contract(post, pr_body)
            self.assertEqual(errors, [], f"Failed on Hebrew prefix: {pfx}")

    def test_09_dedicated_fixture_for_potty_training_not_in_posts(self):
        """Contract test fixture for 'גמילה מטיטול' passes contract and is NOT published to posts.json."""
        fixture_slug = "potty-training-toddlers"
        fixture_post = {
            "id": fixture_slug,
            "slug": fixture_slug,
            "title": "גמילה מטיטול: איך לזהות מוכנות ולהתחיל נכון",
            "content": "<p>גמילה מטיטול היא שלב התפתחותי מרגש ומאתגר עבור כל הורה. במדריך זה נבחן את כל הסימנים.</p>",
            "canonicalUrl": f"https://kesher.saharoni.com/blog/{fixture_slug}",
            "primaryKeyword": "גמילה מטיטול",
            "primarySearchQuery": "גמילה מטיטול",
        }
        fixture_pr_body = f"""## Jules Article Candidate
- Slug: {fixture_slug}
- Primary Keyword: גמילה מטיטול
- Primary Search Query: גמילה מטיטול
- Canonical URL: https://kesher.saharoni.com/blog/{fixture_slug}
"""
        # Validate fixture passes all checks
        errors = validate_primary_keyword_contract(fixture_post, fixture_pr_body)
        self.assertEqual(errors, [])

        # Assert fixture is NOT in src/data/posts.json
        if self.posts_file.is_file():
            posts_data = json.loads(self.posts_file.read_text(encoding="utf-8"))
            all_slugs = {p.get("slug") for p in posts_data if isinstance(p, dict)}
            self.assertNotIn(
                fixture_slug,
                all_slugs,
                f"Dedicated test fixture slug '{fixture_slug}' must NOT be in production posts.json!",
            )

    def test_10_jules_article_runner_system_prompt_includes_contract(self):
        """Verify that PRIMARY_KEYWORD_CONTRACT is embedded into build_prompt()."""
        self.assertIn("PRIMARY KEYWORD CONTRACT", PRIMARY_KEYWORD_CONTRACT)
        self.assertIn("The final article title (H1) MUST contain the Primary Keyword", PRIMARY_KEYWORD_CONTRACT)
        self.assertIn("The Primary Keyword MUST appear in the opening of the article body", PRIMARY_KEYWORD_CONTRACT)
        self.assertIn("The article `slug`/`id` MUST semantically represent the Primary Keyword", PRIMARY_KEYWORD_CONTRACT)

        # Check prompt generation
        with mock.patch.dict("os.environ", {"KESHER_ARTICLE_TOPIC_BRIEF": "Required Primary Keyword: גמילה מטיטול"}):
            prompt = build_prompt("morning", "daily")
            self.assertIn("PRIMARY KEYWORD CONTRACT", prompt)
            self.assertIn("Required Primary Keyword: גמילה מטיטול", prompt)
            self.assertIn("MUST adopt that exact Primary Keyword", prompt)

    def test_11_slug_represents_keyword_potty_training_variations(self):
        """Test variations of potty training in semantic dictionary."""
        for kw in ["גמילה מטיטול", "גמילה מטיטולים", "גמילה מחיתולים", "גמילה מחיתול"]:
            ok, msg = slug_represents_keyword("potty-training-guide", kw)
            self.assertTrue(ok, f"Failed for {kw}: {msg}")
            ok, msg = slug_represents_keyword("toddler-toilet-training", kw)
            self.assertTrue(ok, f"Failed for {kw}: {msg}")
            ok, msg = slug_represents_keyword("diaper-weaning-tips", kw)
            self.assertTrue(ok, f"Failed for {kw}: {msg}")

    def test_12_parse_owner_required_keyword_formats(self):
        """Test parsing owner required primary keyword from various brief formats."""
        b1 = "Required Primary Keyword: גמילה מטיטול\nTopic: גמילה"
        self.assertEqual(parse_owner_required_keyword(b1), "גמילה מטיטול")

        b2 = "- Primary Keyword: תקשורת זוגית\n- Focus: נישואין"
        self.assertEqual(parse_owner_required_keyword(b2), "תקשורת זוגית")

        b3 = "* Required Primary Keyword: ילד מחונן"
        self.assertEqual(parse_owner_required_keyword(b3), "ילד מחונן")

        b4 = "No keyword requirement here"
        self.assertIsNone(parse_owner_required_keyword(b4))


if __name__ == "__main__":
    unittest.main()

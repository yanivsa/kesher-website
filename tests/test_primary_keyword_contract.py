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
    def test_midyear_kindergarten_topic_accepts_relevant_slug_only(self):
        self.assertEqual(slug_represents_keyword("changing-kindergarten-midyear", "מעבר גן באמצע שנה"), (True, ""))
        self.assertFalse(slug_represents_keyword("stock-market-investments", "מעבר גן באמצע שנה")[0])

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
        fixture_slug = "potty-training-toddlers-test-fixture"
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

    @staticmethod
    def _load_validator():
        import importlib.util
        path = Path(__file__).resolve().parent.parent / ".github" / "scripts" / "validate-article-pr.py"
        spec = importlib.util.spec_from_file_location("validate_article_pr", path)
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        return validator

    def test_k_article_content_changed_with_image_pipeline_prefix_fails_without_keyword(self):
        """K: Article content changed. PR body starts with Image Pipeline Version: 2, no keyword => FAILS."""
        validator = self._load_validator()
        content = "<p>תוכן מאמר עברי חדש ללא הצהרת מילת מפתח. " + ("מילה " * 750) + "</p>" + ("<h3>כותרת</h3>" * 5)
        new_post = {
            "id": "new-test-article",
            "title": "מאמר חדש לבדיקה",
            "content": content,
            "image": "/images/generated/blog/new-test-article.png",
            "imageAlt": "תיאור תמונה מפורט העומד בכללי השער האוטומטי",
        }
        pr = {
            "state": "open",
            "draft": False,
            "title": "Publish Kesher article: new-test-article",
            "body": "Image Pipeline Version: 2\nImage Provider: Local\n",
            "base": {"ref": "main", "sha": "0" * 40, "repo": {"full_name": "yanivsa/kesher-website"}},
            "head": {"sha": "1" * 40, "repo": {"full_name": "yanivsa/kesher-website"}},
        }
        files = [{"filename": "src/data/posts.json"}, {"filename": "public/images/generated/blog/new-test-article.png"}]
        errors = validator.evaluate_content(pr, files, [], [new_post], lambda _: b"png")
        self.assertTrue(
            any("missing required 'Primary Keyword'" in e for e in errors),
            f"Expected Primary Keyword required error, got: {errors}",
        )

    def test_l_true_image_only_pr_no_article_content_modified_passes_without_keyword_check(self):
        """L: True image-only PR, no article content modified => passes without keyword check."""
        validator = self._load_validator()
        content = "<p>תוכן קיים ומאושר. " + ("מילה " * 750) + "</p>" + ("<h3>כותרת</h3>" * 5)
        base_post = {
            "id": "existing-art",
            "slug": "existing-art",
            "title": "כותרת קיימת ומאושרת",
            "excerpt": "תקציר קיים",
            "content": content,
            "image": "/images/old.png",
            "imageAlt": "תיאור תמונה ישן",
        }
        # Head post updates only image fields, zero content modification
        head_post = {
            "id": "existing-art",
            "slug": "existing-art",
            "title": "כותרת קיימת ומאושרת",
            "excerpt": "תקציר קיים",
            "content": content,
            "image": "/images/generated/blog/new.png",
            "imageAlt": "תיאור תמונה חדש ומפורט העומד בכללי השער",
        }
        pr = {
            "state": "open",
            "draft": False,
            "title": "Publish Kesher article: existing-art",
            "body": "Image Pipeline Version: 2\n",
            "base": {"ref": "main", "sha": "0" * 40, "repo": {"full_name": "yanivsa/kesher-website"}},
            "head": {"sha": "1" * 40, "repo": {"full_name": "yanivsa/kesher-website"}},
        }
        files = [{"filename": "src/data/posts.json"}, {"filename": "public/images/generated/blog/new.png"}]
        errors = validator.evaluate_content(pr, files, [base_post], [head_post], lambda _: b"png")
        # Assert no Primary Keyword error was raised
        self.assertFalse(any("Primary Keyword" in e for e in errors), f"Unexpected Primary Keyword error: {errors}")

    def test_m_owner_required_exact_match_passes(self):
        """M: Required = 'גמילה מטיטול', Declared = 'גמילה מטיטול' => PASS."""
        post = {
            "id": "potty-training-toddlers",
            "slug": "potty-training-toddlers",
            "title": "גמילה מטיטול: מדריך מעשי",
            "content": "<p>גמילה מטיטול היא שלב חשוב בהתפתחות הפעוט.</p>",
            "primaryKeyword": "גמילה מטיטול",
        }
        pr_body = "- Primary Keyword: גמילה מטיטול\n"
        topic_brief = "Required Primary Keyword: גמילה מטיטול"
        errors = validate_primary_keyword_contract(post, pr_body, owner_topic_brief=topic_brief)
        self.assertEqual(errors, [])

    def test_n_owner_required_substring_match_fails(self):
        """N: Required = 'גמילה מטיטול', Declared = 'גמילה' => FAIL (substring matching forbidden)."""
        post = {
            "id": "potty-training-toddlers",
            "slug": "potty-training-toddlers",
            "title": "גמילה: מדריך מעשי",
            "content": "<p>גמילה היא שלב חשוב בהתפתחות הפעוט.</p>",
            "primaryKeyword": "גמילה",
        }
        pr_body = "- Primary Keyword: גמילה\n"
        topic_brief = "Required Primary Keyword: גמילה מטיטול"
        errors = validate_primary_keyword_contract(post, pr_body, owner_topic_brief=topic_brief)
        self.assertTrue(any("does not match required owner keyword" in e for e in errors))

    def test_o_owner_required_unrelated_fails(self):
        """O: Required = 'גמילה מטיטול', Declared = 'תקשורת זוגית' => FAIL."""
        post = {
            "id": "couples-communication",
            "slug": "couples-communication",
            "title": "תקשורת זוגית: מדריך מעשי",
            "content": "<p>תקשורת זוגית היא הבסיס לכל מערכת יחסים.</p>",
            "primaryKeyword": "תקשורת זוגית",
        }
        pr_body = "- Primary Keyword: תקשורת זוגית\n"
        topic_brief = "Required Primary Keyword: גמילה מטיטול"
        errors = validate_primary_keyword_contract(post, pr_body, owner_topic_brief=topic_brief)
        self.assertTrue(any("does not match required owner keyword" in e for e in errors))

    def test_p_altered_pr_body_cannot_override_trusted_owner_requirement(self):
        """P: Attempt to alter PR body to hide/change owner requirement fails; trusted metadata wins."""
        post = {
            "id": "couples-communication",
            "slug": "couples-communication",
            "title": "תקשורת זוגית: מדריך מעשי",
            "content": "<p>תקשורת זוגית היא הבסיס לכל מערכת יחסים.</p>",
            "primaryKeyword": "תקשורת זוגית",
        }
        # Attacker PR body attempts to declare owner required keyword as something else
        pr_body = "- Primary Keyword: תקשורת זוגית\n- Required Primary Keyword: תקשורת זוגית\n"
        with mock.patch.dict("os.environ", {"KESHER_ARTICLE_TOPIC_BRIEF": "Required Primary Keyword: גמילה מטיטול"}):
            errors = validate_primary_keyword_contract(post, pr_body)
            self.assertTrue(any("does not match required owner keyword 'גמילה מטיטול'" in e for e in errors))

    def test_q_potty_training_toddlers_slug_passes(self):
        """Q: גמילה מטיטול -> potty-training-toddlers PASS."""
        ok, msg = slug_represents_keyword("potty-training-toddlers", "גמילה מטיטול")
        self.assertTrue(ok, f"Expected PASS, got: {msg}")

    def test_r_marathon_training_shoes_slug_fails(self):
        """R: גמילה מטיטול -> marathon-training-shoes FAIL (generic training alone forbidden)."""
        ok, msg = slug_represents_keyword("marathon-training-shoes", "גמילה מטיטול")
        self.assertFalse(ok)
        self.assertIn("does not contain expected semantic concepts", msg)

    def test_s_stock_market_investments_slug_fails(self):
        """S: גמישות מחשבתית -> stock-market-investments FAIL."""
        ok, msg = slug_represents_keyword("stock-market-investments", "גמישות מחשבתית")
        self.assertFalse(ok)

    def test_t_unknown_hebrew_keyword_without_semantic_mapping_fails_closed(self):
        """T: Unknown Hebrew Primary Keyword with no trusted semantic mapping => FAIL CLOSED, not pass."""
        ok, msg = slug_represents_keyword("any-random-english-slug", "שאילתה עברית לא מוכרת כלל")
        self.assertFalse(ok)
        self.assertIn("unknown keyword", msg)


    def test_u_untrusted_post_metadata_cannot_override_owner_or_slug_semantics(self):
        """PR-controlled metadata is never a trusted owner requirement or slug semantic mapping."""
        post = {
            "id": "stock-market-investments",
            "slug": "stock-market-investments",
            "title": "שאילתה עברית לא מוכרת כלל: מדריך",
            "content": "<p>שאילתה עברית לא מוכרת כלל היא נושא לבחינה.</p>",
            "primaryKeyword": "שאילתה עברית לא מוכרת כלל",
            "ownerRequiredPrimaryKeyword": "שאילתה עברית לא מוכרת כלל",
            "slugSemanticTokens": ["stock", "market"],
        }
        errors = validate_primary_keyword_contract(post, "- Primary Keyword: שאילתה עברית לא מוכרת כלל\n")
        self.assertTrue(any("unknown keyword" in e for e in errors), errors)

    def test_v_trusted_owner_keyword_is_loaded_only_from_bound_controller_artifact(self):
        """GitHub gate binds owner keyword to controller run artifact, not PR body/post fields."""
        import io
        import zipfile
        validator = self._load_validator()
        pr = {"number": 123, "html_url": "https://github.com/yanivsa/kesher-website/pull/123"}
        state = {"cycle": "2026-10-18", "article": {"pr_number": 123, "run_id": 999}}
        artifact_listing = {"artifacts": [{"id": 77, "name": "kesher-article-result-999", "expired": False}]}
        payload = {
            "slot": "2026-10-18",
            "pr_url": pr["html_url"],
            "owner_required_primary_keyword": "גמילה מטיטול",
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("result.json", json.dumps(payload, ensure_ascii=False))
        with mock.patch.object(validator, "fetch_repo_json", return_value=state), \
                mock.patch.object(validator, "api_json", return_value=artifact_listing), \
                mock.patch.object(validator, "api_bytes", return_value=buf.getvalue()):
            brief = validator.trusted_owner_topic_brief("yanivsa/kesher-website", pr, "token")
        self.assertEqual(brief, "Required Primary Keyword: גמילה מטיטול")

    def test_w_runner_persists_owner_keyword_into_trusted_result_artifact(self):
        """Article runner persists owner keyword to the workflow result artifact after Jules returns."""
        import os
        import tempfile
        import scripts.jules_article_runner_v4 as runner
        with tempfile.TemporaryDirectory() as td:
            result = Path(td) / "result.json"
            result.write_text(json.dumps({"slot": "2026-10-18", "pr_url": "https://github.com/x/y/pull/1"}), encoding="utf-8")
            brief = Path(td) / "brief.txt"
            brief.write_text("Topic: גמילה\nRequired Primary Keyword: גמילה מטיטול\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"KESHER_ARTICLE_TOPIC_BRIEF_FILE": str(brief)}, clear=False), \
                    mock.patch.object(runner.v3.core, "result_path", return_value=result):
                runner.persist_owner_keyword_result_metadata()
            payload = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(payload["owner_required_primary_keyword"], "גמילה מטיטול")
            self.assertTrue(payload["owner_topic_brief_sha256"])

    def test_x_pacifier_weaning_contract_passes(self):
        """Pacifier weaning keyword and slug pass semantic validation."""
        post = {
            "id": "pacifier-weaning",
            "slug": "pacifier-weaning",
            "title": "גמילה ממוצץ בגיל שנתיים או שלוש: איך נפרדים בלי מאבקים מיותרים",
            "content": "<p>גמילה ממוצץ היא אחד המעברים הרגישים ביותר עבור פעוטות והורים כאחד.</p>",
            "canonicalUrl": "https://kesher.saharoni.com/blog/pacifier-weaning",
            "primaryKeyword": "גמילה ממוצץ",
        }
        pr_body = "- Primary Keyword: גמילה ממוצץ\n"
        errors = validate_primary_keyword_contract(post, pr_body)
        self.assertEqual(errors, [])

    def test_y_owner_trusted_semantic_stems_allow_unmapped_keyword(self):
        """Owner topic brief can supply trusted semantic stems for novel concepts."""
        post = {
            "id": "kindergarten-readiness-adaptation",
            "slug": "kindergarten-readiness-adaptation",
            "title": "הסתגלות לגן חדש: איך מסייעים לילד להתאקלם ברוגע",
            "content": "<p>הסתגלות לגן חדש דורשת סבלנות והכלה רגשית מצד ההורים והצוות.</p>",
            "canonicalUrl": "https://kesher.saharoni.com/blog/kindergarten-readiness-adaptation",
            "primaryKeyword": "הסתגלות לגן חדש",
        }
        pr_body = "- Primary Keyword: הסתגלות לגן חדש\n"
        brief = "Required Primary Keyword: הסתגלות לגן חדש\nSemantic Stems: kindergarten, readiness, adaptation"
        errors = validate_primary_keyword_contract(post, pr_body, owner_topic_brief=brief)
        self.assertEqual(errors, [])

    def test_z_strip_auth_redirect_handler_strips_authorization(self):
        """StripAuthRedirectHandler removes Authorization header upon redirect."""
        import urllib.request
        validator = self._load_validator()
        handler = validator.StripAuthRedirectHandler()
        req = urllib.request.Request(
            "https://api.github.com/artifacts/123",
            headers={"Authorization": "Bearer token123", "User-Agent": "test"},
        )
        new_req = handler.redirect_request(
            req, None, 302, "Found", {}, "https://pipelines.actions.githubusercontent.com/blob"
        )
        self.assertIsNotNone(new_req)
        self.assertNotIn("Authorization", new_req.headers)
        self.assertNotIn("authorization", new_req.headers)


if __name__ == "__main__":
    unittest.main()

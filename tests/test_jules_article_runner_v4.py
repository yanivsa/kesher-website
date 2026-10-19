from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from scripts import jules_article_runner_v4 as runner


class JulesArticleRunnerV4Tests(unittest.TestCase):
    def test_failure_diagnostic_is_persisted_for_preserved_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(
                json.dumps({
                    "outcome": "JULES_TIMEOUT_SESSION_ACTIVE",
                    "message": "session preserved",
                    "session_id": "sessions/123",
                }),
                encoding="utf-8",
            )
            diagnostic = {
                "activity_count": 4,
                "change_set_count": 1,
                "last_agent_message": "waiting on repository step",
            }
            with mock.patch.dict(
                "os.environ",
                {"JULES_API_KEY": "key", "KESHER_ARTICLE_RESULT_PATH": str(path)},
                clear=False,
            ), mock.patch.object(
                runner.v3.diagnostics, "diagnose", return_value=diagnostic
            ) as diagnose, mock.patch.object(
                runner.v3.diagnostics, "attach_to_result"
            ) as attach:
                runner.attach_failure_diagnostic()

        diagnose.assert_called_once_with("key", "sessions/123")
        attach.assert_called_once_with(path, diagnostic)

    def test_autonomous_mode_is_exactly_seven_seo_gap_three_trend_per_ten_slots(self):
        start = date(2026, 9, 20)
        modes = [
            runner.autonomous_discovery_mode((start + timedelta(days=offset)).isoformat())
            for offset in range(10)
        ]

        self.assertEqual(modes.count("seo-gap"), 7)
        self.assertEqual(modes.count("trend"), 3)

    def test_seo_gap_discovery_runs_on_seo_slot_without_owner_topic(self):
        with mock.patch.dict(
            "os.environ",
            {
                "KESHER_ARTICLE_TOPIC_BRIEF": "",
                "KESHER_ARTICLE_TOPIC_BRIEF_FILE": "",
            },
            clear=False,
        ), mock.patch.object(runner, "_v3_build_prompt", return_value="BASE"):
            prompt = runner.build_prompt("2026-09-21", "POLICY")

        self.assertIn("SEO GAP TOPIC DISCOVERY CONTRACT", prompt)
        self.assertNotIn("VIRAL TOPIC DISCOVERY CONTRACT", prompt)
        self.assertIn("Discovery Mix: seo-gap", prompt)
        self.assertIn("CLICKABLE SEARCH-INTENT TITLE CONTRACT", prompt)
        self.assertNotIn("OWNER-SUPPLIED TOPIC BRIEF CONTRACT", prompt)

    def test_viral_discovery_runs_only_without_owner_topic(self):
        with mock.patch.dict(
            "os.environ",
            {
                "KESHER_ARTICLE_TOPIC_BRIEF": "",
                "KESHER_ARTICLE_TOPIC_BRIEF_FILE": "",
            },
            clear=False,
        ), mock.patch.object(runner, "_v3_build_prompt", return_value="BASE"):
            prompt = runner.build_prompt("2026-09-28", "POLICY")

        self.assertIn("VIRAL TOPIC DISCOVERY CONTRACT", prompt)
        self.assertNotIn("SEO GAP TOPIC DISCOVERY CONTRACT", prompt)
        self.assertIn("Discovery Mix: trend", prompt)
        self.assertIn("CLICKABLE SEARCH-INTENT TITLE CONTRACT", prompt)
        self.assertNotIn("OWNER-SUPPLIED TOPIC BRIEF CONTRACT", prompt)
        self.assertLess(
            prompt.index("VIRAL TOPIC DISCOVERY CONTRACT"),
            prompt.index("CLICKABLE SEARCH-INTENT TITLE CONTRACT"),
        )

    def test_viral_discovery_preserves_seo_gap_fallback(self):
        with mock.patch.dict(
            "os.environ",
            {
                "KESHER_ARTICLE_TOPIC_BRIEF": "",
                "KESHER_ARTICLE_TOPIC_BRIEF_FILE": "",
            },
            clear=False,
        ), mock.patch.object(
            runner, "_v3_build_prompt", return_value="LEGACY_BASE_PROMPT"
        ):
            prompt = runner.build_prompt("2026-09-29", "POLICY")

        self.assertTrue(prompt.startswith("LEGACY_BASE_PROMPT"))
        self.assertIn("fall back to the SEO GAP TOPIC DISCOVERY CONTRACT", prompt)
        self.assertIn("fallback-to-seo-gap", prompt)
        self.assertIn("EXACTLY ONE article and one PR", prompt)

    def test_owner_topic_bypasses_all_autonomous_discovery(self):
        with mock.patch.dict(
            "os.environ",
            {
                "KESHER_ARTICLE_TOPIC_BRIEF": "נושא מפורש מהבעלים",
                "KESHER_ARTICLE_TOPIC_BRIEF_FILE": "",
            },
            clear=False,
        ), mock.patch.object(runner, "_v3_build_prompt", return_value="BASE"):
            prompt = runner.build_prompt("2026-09-28", "POLICY")

        self.assertNotIn("VIRAL TOPIC DISCOVERY CONTRACT", prompt)
        self.assertNotIn("SEO GAP TOPIC DISCOVERY CONTRACT", prompt)
        self.assertNotIn("Discovery Mix:", prompt)
        self.assertIn("CLICKABLE SEARCH-INTENT TITLE CONTRACT", prompt)
        self.assertIn("OWNER-SUPPLIED TOPIC BRIEF CONTRACT", prompt)
        self.assertIn("נושא מפורש מהבעלים", prompt)

    def test_clickable_title_contract_prioritizes_reader_payoff_without_losing_search_intent(self):
        contract = runner.SEARCH_FIRST_CONTRACT
        self.assertIn("generate at least FIVE materially different", contract)
        self.assertIn("Search intent is a constraint, not permission to publish a boring title", contract)
        self.assertIn("איך [להשיג תוצאה רצויה] בלי", contract)
        self.assertIn("Headline Frame: ...", contract)
        self.assertIn("may not be misleading", contract)

    def test_preflight_allows_different_topic_on_same_date_when_owner_brief_present(self):
        posts = [
            {"id": "pacifier-weaning", "date": "2026-10-19", "primaryKeyword": "גמילה ממוצץ", "title": "גמילה ממוצץ"},
        ]
        brief = "נושא גמילה מטיטול\n\nRequired Primary Keyword: גמילה מטיטול"
        with mock.patch.dict(
            "os.environ",
            {"KESHER_ARTICLE_TOPIC_BRIEF": brief, "KESHER_ARTICLE_TOPIC_BRIEF_FILE": "", "KESHER_TEST_MODE": ""},
            clear=False,
        ), mock.patch.object(
            runner.v3, "_load_local_posts", return_value=posts
        ), mock.patch.object(
            runner.v3, "open_article_prs_for_slot", return_value=[]
        ):
            res = runner.preflight("2026-10-19", "token")
        self.assertEqual(res, "READY")

    def test_preflight_blocks_when_same_required_keyword_already_published(self):
        posts = [
            {"id": "potty-training", "date": "2026-10-19", "primaryKeyword": "גמילה מטיטול", "title": "גמילה מטיטול"},
        ]
        brief = "נושא גמילה מטיטול\n\nRequired Primary Keyword: גמילה מטיטול"
        with mock.patch.dict(
            "os.environ",
            {"KESHER_ARTICLE_TOPIC_BRIEF": brief, "KESHER_ARTICLE_TOPIC_BRIEF_FILE": "", "KESHER_TEST_MODE": ""},
            clear=False,
        ), mock.patch.object(
            runner.v3, "_load_local_posts", return_value=posts
        ):
            res = runner.preflight("2026-10-19", "token")
        self.assertEqual(res, "ARTICLE_ALREADY_PUBLISHED")

    def test_build_prompt_scopes_stop_condition_to_required_keyword(self):
        brief = "מאמר על טיטולים\n\nRequired Primary Keyword: גמילה מטיטול"
        with mock.patch.dict(
            "os.environ",
            {"KESHER_ARTICLE_TOPIC_BRIEF": brief, "KESHER_ARTICLE_TOPIC_BRIEF_FILE": ""},
            clear=False,
        ):
            prompt = runner.build_prompt("2026-10-19", "POLICY")
        self.assertIn("Primary Keyword == 'גמילה מטיטול'", prompt)
        self.assertNotIn("date == 2026-10-19", prompt)


if __name__ == "__main__":
    unittest.main()

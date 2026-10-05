from __future__ import annotations

import json
import tempfile
import unittest
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
        self.assertIn("CLICKABLE SEARCH-INTENT TITLE CONTRACT", prompt)
        self.assertNotIn("OWNER-SUPPLIED TOPIC BRIEF CONTRACT", prompt)
        self.assertLess(
            prompt.index("VIRAL TOPIC DISCOVERY CONTRACT"),
            prompt.index("CLICKABLE SEARCH-INTENT TITLE CONTRACT"),
        )

    def test_viral_discovery_preserves_legacy_fallback(self):
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
        self.assertIn("pre-existing V3/base article topic-selection mechanism", prompt)
        self.assertIn("fallback-to-legacy-selection", prompt)
        self.assertIn("EXACTLY ONE article and one PR", prompt)

    def test_owner_topic_bypasses_viral_discovery(self):
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


if __name__ == "__main__":
    unittest.main()

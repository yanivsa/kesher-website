from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller_stabilized as stabilized

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Jerusalem")


def risky_article() -> dict:
    return {
        "id": "gifted-intensity-claim",
        "slug": "gifted-intensity-claim",
        "title": "כותרת מאמר",
        "date": "2026-09-08",
        "category": "הדרכת הורים",
        "excerpt": "תקציר",
        "content": (
            "<p>אחד המאפיינים הבולטים של ילדים מחוננים הוא שהם חווים "
            "את העולם בעוצמה רבה יותר.</p>"
        ),
    }


def run_gate(content: str):
    payload = [
        {
            "id": "incident-730-claim",
            "slug": "incident-730-claim",
            "title": "כותרת מאמר",
            "date": "2026-09-08",
            "category": "הדרכת הורים",
            "excerpt": "תקציר",
            "content": f"<p>{content}</p>",
        }
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "posts.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            ["python3", "scripts/article_claim_quality.py", str(path)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )


class ArticleQualityStabilizationTests(unittest.TestCase):
    def test_risky_article_gate_fails_closed_with_stable_error_code(self):
        payload = [risky_article()]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "posts.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                ["python3", "scripts/article_claim_quality.py", str(path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("ARTICLE_CONTENT_QUALITY_FAILED", result.stderr)

    def test_incident_730_additional_causal_claims_are_blocked(self):
        claims = (
            "הרגישות הזו הופכת אותם לפגיעים יותר.",
            "מתן מקום בטוח להבעת הרגשות ללא שיפוט מאפשר להם ללמוד לווסת את העוצמות האלו בהדרגה.",
            "כשאנחנו מדגישים את הערך של הדרך ושל ההתמודדות עם הקושי, אנחנו מורידים מהם את עול השלמות ומעודדים אותם לקחת סיכונים מחושבים.",
        )
        for claim in claims:
            with self.subTest(claim=claim):
                result = run_gate(claim)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("ARTICLE_CONTENT_QUALITY_FAILED", result.stderr)

    def test_qualified_article_gate_passes(self):
        payload = [
            {
                "id": "gifted-qualified",
                "title": "כותרת מאמר",
                "date": "2026-09-08",
                "category": "הדרכת הורים",
                "excerpt": "תקציר",
                "content": "<p>אצל חלק מהילדים המחוננים יכולה להופיע רגישות בעוצמות שונות, בהתאם להקשר.</p>",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "posts.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                ["python3", "scripts/article_claim_quality.py", str(path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_stabilized_v5_preflight_blocks_risky_article_before_super_tick(self):
        class FakeGitHub:
            def __init__(self):
                self.saved = None

            def contents_json(self, path, ref="main"):
                self.assertion = (path, ref)
                return [risky_article()]

            def save_controller_state(self, state):
                self.saved = json.loads(json.dumps(state))

        gh = FakeGitHub()
        controller = object.__new__(stabilized.StabilizedRuntimeV5Controller)
        controller.github = gh
        controller.now = datetime(2026, 9, 8, 16, 30, tzinfo=TZ)
        state = {"article": {}}

        with mock.patch.object(stabilized.v5.core, "block") as block:
            action = controller._quality_preflight(state)

        block.assert_called_once()
        self.assertEqual(action.kind, "blocked")
        self.assertEqual(state["article"]["quality_status"], "failed")
        self.assertTrue(state["article"]["quality_content_sha256"])
        self.assertEqual(gh.assertion, ("src/data/posts.json", "main"))
        self.assertIsNotNone(gh.saved)

    def test_production_controller_workflow_uses_stabilized_runtime(self):
        workflow = (ROOT / ".github/workflows/kesher-content-controller.yml").read_text(encoding="utf-8")
        self.assertIn(
            "python3 -u scripts/kesher_content_controller_stabilized.py --report-json",
            workflow,
        )

    def test_article_generation_uses_pre_pr_evidence_contract_runner(self):
        workflow = (ROOT / ".github/workflows/kesher-article-generation.yml").read_text(encoding="utf-8")
        self.assertIn("jules_article_runner_v4.py", workflow)
        wrapper = ROOT / "scripts/jules_article_runner_v4.py"
        self.assertTrue(wrapper.is_file())
        text = wrapper.read_text(encoding="utf-8")
        self.assertIn("ARTICLE EVIDENCE CONTRACT", text)
        self.assertIn("Do not submit the PR until this self-check passes", text)

    def test_article_generation_requires_search_intent_first_titles(self):
        wrapper = ROOT / "scripts/jules_article_runner_v4.py"
        text = wrapper.read_text(encoding="utf-8")
        self.assertIn("SEARCH-INTENT-FIRST TITLE CONTRACT", text)
        self.assertIn("Primary Search Query:", text)
        self.assertIn("Search Variants:", text)
        self.assertIn("Search Evidence:", text)
        self.assertIn("live Hebrew search-language research", text)
        self.assertIn("OBSERVED QUERY SIGNAL", text)
        self.assertIn("are NOT sufficient by themselves to prove a query people", text)
        self.assertIn("Do not\n   submit the article PR until at least one current observed query signal", text)


if __name__ == "__main__":
    unittest.main()

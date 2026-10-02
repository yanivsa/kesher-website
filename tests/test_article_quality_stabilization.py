from __future__ import annotations

import json
import os
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

    def test_incident_766_group_stereotypes_are_blocked(self):
        claims = (
            "ילדים מחוננים מאופיינים פעמים רבות ברגישות רגשית גבוהה.",
            "היכולת הקוגניטיבית הגבוהה שלהם גורמת להם לזהות דקויות חברתיות שילדים אחרים מפספסים.",
            "ילדים רבים עם מחוננות מעדיפים מצבים מובנים וברורים.",
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

    def test_multiple_same_day_articles_preserve_durable_controller_identity(self):
        chosen = {
            "id": "chosen-article",
            "slug": "chosen-article",
            "title": "כותרת נבחרת",
            "date": "2026-10-01",
            "category": "זוגיות",
            "excerpt": "תקציר",
            "content": "<p>תוכן נבחר.</p>",
        }
        other = {
            "id": "other-article",
            "slug": "other-article",
            "title": "כותרת אחרת",
            "date": "2026-10-01",
            "category": "זוגיות",
            "excerpt": "תקציר",
            "content": "<p>תוכן אחר.</p>",
        }
        chosen_source = stabilized.v5.article_source_identity(chosen)

        class FakeGitHub:
            def load_controller_state(self):
                return {
                    "cycle": "2026-10-01",
                    "article": {
                        "slug": chosen["slug"],
                        "quality_content_sha256": chosen_source["content_sha256"],
                    },
                }

        controller = object.__new__(stabilized.StabilizedRuntimeV5Controller)
        controller.github = FakeGitHub()
        controller.now = datetime(2026, 10, 1, 20, 0, tzinfo=TZ)

        selected = controller._selected_article([other, chosen])

        self.assertEqual(selected["slug"], chosen["slug"])

    def test_multiple_same_day_articles_fail_closed_without_durable_identity(self):
        first = {
            "id": "first",
            "slug": "first",
            "title": "ראשון",
            "date": "2026-10-01",
            "category": "זוגיות",
            "excerpt": "תקציר",
            "content": "<p>תוכן.</p>",
        }
        second = dict(first, id="second", slug="second", title="שני")

        class FakeGitHub:
            def load_controller_state(self):
                return {"cycle": "2026-10-01", "article": {}}

        controller = object.__new__(stabilized.StabilizedRuntimeV5Controller)
        controller.github = FakeGitHub()
        controller.now = datetime(2026, 10, 1, 20, 0, tzinfo=TZ)

        with self.assertRaisesRegex(
            stabilized.v5.core.ControllerError,
            "BACKLOG_ARTICLE_IDENTITY_AMBIGUOUS",
        ):
            controller._selected_article([first, second])

    def test_targeted_media_recovery_selects_existing_old_article(self):
        old_article = {
            "id": "gifted-children-perfectionism-tears",
            "slug": "gifted-children-perfectionism-tears",
            "title": "פרפקציוניזם אצל ילדים מחוננים",
            "date": "2026-08-18",
            "category": "הדרכת הורים",
            "excerpt": "תקציר",
            "content": "<p>תוכן בדיקה בטוח.</p>",
        }
        today_article = {
            "id": "today-other-topic",
            "slug": "today-other-topic",
            "title": "מאמר אחר",
            "date": "2026-09-27",
            "category": "זוגיות",
            "excerpt": "תקציר",
            "content": "<p>תוכן אחר.</p>",
        }

        class FakeGitHub:
            def contents_json(self, path, ref="main"):
                if path == "src/data/posts.json":
                    return [today_article, old_article]
                raise AssertionError(path)

        controller = object.__new__(stabilized.StabilizedRuntimeV5Controller)
        controller.github = FakeGitHub()
        controller.now = datetime(2026, 9, 27, 1, 0, tzinfo=TZ)

        with mock.patch.dict(
            os.environ,
            {"KESHER_TARGET_MEDIA_SLUG": "gifted-children-perfectionism-tears"},
            clear=False,
        ):
            source = controller._article_source()

        self.assertEqual(source["slug"], "gifted-children-perfectionism-tears")
        self.assertTrue(source["content_sha256"])

    def test_targeted_media_recovery_bypasses_current_article_cycle_for_exact_old_slug(self):
        old_article = {
            "id": "gifted-children-perfectionism-tears",
            "slug": "gifted-children-perfectionism-tears",
            "title": "פרפקציוניזם אצל ילדים מחוננים",
            "date": "2026-08-18",
            "category": "הדרכת הורים",
            "excerpt": "תקציר",
            "content": "<p>תוכן בדיקה בטוח.</p>",
        }
        today_article = {
            "id": "today-other-topic",
            "slug": "today-other-topic",
            "title": "מאמר אחר",
            "date": "2026-09-27",
            "category": "זוגיות",
            "excerpt": "תקציר",
            "content": "<p>תוכן אחר.</p>",
        }

        class FakeGitHub:
            def __init__(self):
                self.saved = None

            def contents_json(self, path, ref="main"):
                self.assertion = (path, ref)
                return [today_article, old_article]

            def newest_video_state(self):
                return {"version": 1, "items": []}

            def active_workflow_run(self, workflow, production_only=False):
                return None

            def save_controller_state(self, state):
                self.saved = json.loads(json.dumps(state))

        class FakeSite:
            def get(self, url):
                return 200, "<h1>פרפקציוניזם אצל ילדים מחוננים</h1>"

        controller = object.__new__(stabilized.StabilizedRuntimeV5Controller)
        controller.github = FakeGitHub()
        controller.site = FakeSite()
        controller.now = datetime(2026, 9, 27, 1, 0, tzinfo=TZ)
        controller._verified_long_from_artifact_history = mock.Mock(return_value=None)
        controller._dispatch_budgeted = mock.Mock()

        state = {
            "status": "article_pr_open",
            "article": {"status": "running"},
            "long_video": {"attempt_count": 0, "status": "pending"},
            "short": {"attempt_count": 0, "status": "pending"},
            "history": [],
        }

        with mock.patch.dict(
            os.environ,
            {"KESHER_TARGET_MEDIA_SLUG": "gifted-children-perfectionism-tears"},
            clear=False,
        ):
            returned, action = controller._tick_targeted_media_recovery(state)

        self.assertIs(returned, state)
        self.assertEqual(action.kind, "dispatch_long_video")
        controller._dispatch_budgeted.assert_called_once_with(
            state,
            "video",
            stabilized.v5.LONG_VIDEO_WORKFLOW,
            {
                "operation": "full",
                "target_slug": "gifted-children-perfectionism-tears",
            },
        )
        self.assertEqual(
            state["targeted_media_recovery"]["slug"],
            "gifted-children-perfectionism-tears",
        )
        self.assertEqual(state["long_video"]["status"], "running")
        self.assertIsNotNone(controller.github.saved)

    def test_targeted_tick_skips_duplicate_overview_history_preflight(self):
        controller = object.__new__(stabilized.StabilizedRuntimeV5Controller)
        state = {"article": {}, "long_video": {}, "short": {}, "history": []}
        expected = (
            state,
            stabilized.v5.core.Action("wait", "targeted recovery"),
        )
        controller.state = mock.Mock(return_value=state)
        controller._quality_preflight = mock.Mock(return_value=None)
        controller._dispatch_exact_rejected_rebuild = mock.Mock(return_value=None)
        controller._tick_targeted_media_recovery = mock.Mock(return_value=expected)
        controller._overview_evidence_preflight = mock.Mock(
            side_effect=AssertionError("duplicate overview preflight should not run")
        )

        with mock.patch.dict(
            os.environ,
            {"KESHER_TARGET_MEDIA_SLUG": "gifted-children-perfectionism-tears"},
            clear=False,
        ):
            actual = controller.tick()

        self.assertEqual(actual, expected)
        controller._overview_evidence_preflight.assert_not_called()
        controller._tick_targeted_media_recovery.assert_called_once_with(state)

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

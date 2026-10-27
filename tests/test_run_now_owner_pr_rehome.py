from __future__ import annotations

import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import kesher_article_normalizer as normalizer
from scripts import kesher_content_controller_stabilized as stabilized


ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


class RunNowOwnerPrRehomeTests(unittest.TestCase):
    def test_normalizer_can_rehome_one_exact_prior_slot_article_when_explicit(self) -> None:
        base = [
            {
                "id": "kindergarten-adjustment-difficulties",
                "slug": "kindergarten-adjustment-difficulties",
                "title": "קשיי הסתגלות לגן",
                "date": "2026-10-27",
                "controllerManaged": True,
            }
        ]
        target = {
            "id": "changing-kindergarten-midyear",
            "slug": "changing-kindergarten-midyear",
            "title": "מעבר גן באמצע שנה: איך לעזור לילד להיפרד ולהתחיל מחדש?",
            "date": "2026-10-26",
            "controllerManaged": True,
            "content": "<p>מעבר גן באמצע שנה דורש הכנה.</p>",
        }

        article = normalizer.extract_target_article(
            base,
            [*base, target],
            "2026-10-27",
            source_slot="2026-10-26",
        )

        self.assertEqual(article["id"], "changing-kindergarten-midyear")
        self.assertEqual(article["date"], "2026-10-27")
        self.assertEqual(article["content"], target["content"])

    def test_run_now_adopts_exact_owner_pr_from_prior_slot_instead_of_dispatching_jules(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 27, 17, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )
        head_sha = "e" * 40
        pr = {
            "number": 1226,
            "state": "open",
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1226",
            "title": "Publish Kesher article: changing-kindergarten-midyear",
            "body": "- Primary Keyword: מעבר גן באמצע שנה\n",
            "base": {"ref": "main"},
            "head": {"sha": head_sha, "repo": {"full_name": "yanivsa/kesher-website"}},
        }
        state = {
            "schema_version": 5,
            "cycle": "2026-10-27",
            "status": "article_needed",
            "active_idea": {
                "idea_id": "parenting-p1-changing-kindergarten-midyear",
                "status": "claimed",
                "run_now": True,
                "publication_slot": "2026-10-27",
                "required_primary_keyword": "מעבר גן באמצע שנה",
                "topic_brief": "Canonical ID נדרש: changing-kindergarten-midyear",
            },
            "article": {"attempt_count": 0, "attempts": 0, "status": "pending", "next_retry_at": None},
            "image": {"status": "pending"},
            "long_video": {"status": "pending"},
            "short": {"status": "pending"},
            "pending_dispatches": {},
            "history": [],
        }
        controller.posts_on_main = mock.MagicMock(return_value=[])
        controller._reconcile_existing_current_day_article = mock.MagicMock(return_value=[])
        controller._reconcile_completed_article_run = mock.MagicMock(return_value=None)
        github.open_article_prs.return_value = []
        github.active_workflow_run.return_value = None
        github.active_normalizer_run.return_value = None
        github.request.return_value = [pr]
        github.contents_json.return_value = [
            {
                "id": "changing-kindergarten-midyear",
                "slug": "changing-kindergarten-midyear",
                "title": "מעבר גן באמצע שנה: איך לעזור לילד להיפרד ולהתחיל מחדש?",
                "date": "2026-10-26",
                "controllerManaged": True,
            }
        ]

        action = controller._run_now_article_phase(state)

        self.assertEqual(action.kind, "dispatch_normalize")
        github.dispatch.assert_called_once_with(
            "normalize-article-pr.yml",
            {"pr_number": "1226", "slot": "2026-10-27", "source_slot": "2026-10-26"},
        )
        self.assertEqual(state["article"]["pr_number"], 1226)
        self.assertEqual(state["article"]["normalization_slot"], "2026-10-27")
        self.assertEqual(state["article"]["owner_rehome_source_slot"], "2026-10-26")
        self.assertEqual(state["article"]["attempt_count"], 0)


if __name__ == "__main__":
    unittest.main()

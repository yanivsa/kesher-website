from __future__ import annotations

import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

import scripts.kesher_content_controller as core
import scripts.kesher_content_controller_stabilized as stabilized

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


class CrossSlotArticlePrAdoptionTests(unittest.TestCase):
    def _state(self) -> dict:
        return {
            "cycle": "2026-10-27",
            "status": "article_retry_wait",
            "schema_version": 5,
            "article": {"attempts": 3, "attempt_count": 3, "status": "retry_wait", "next_retry_at": None},
            "active_idea": {
                "idea_id": "parenting-p1-changing-kindergarten-midyear",
                "run_now": True,
                "status": "claimed",
                "publication_slot": "2026-10-27",
                "required_primary_keyword": "מעבר גן באמצע שנה",
                "topic_brief": "Canonical ID נדרש: changing-kindergarten-midyear. כותרת עבודה",
            },
            "history": [],
        }

    def test_exact_identity_from_prior_slot_is_adopted_without_redispatch(self) -> None:
        github = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 27, 21, 45, tzinfo=ISRAEL_TZ), github=github, site=mock.MagicMock()
        )
        pr = {
            "number": 1226,
            "title": "Publish Kesher article: changing-kindergarten-midyear",
            "body": "- Primary Keyword: מעבר גן באמצע שנה\n",
            "head": {"sha": "e" * 40},
        }
        github.open_article_prs.side_effect = [[], [pr]]
        with mock.patch.object(controller, "posts_on_main", return_value=[]), \
             mock.patch.object(controller, "_reconcile_completed_article_run", return_value=None), \
             mock.patch.object(controller, "_handle_open_article_pr", return_value=core.Action("wait", "adopted")) as handle:
            action = controller._run_now_article_phase(self._state())
        self.assertEqual(action.kind, "wait")
        self.assertEqual(github.open_article_prs.call_args_list, [mock.call("2026-10-27"), mock.call(None)])
        handle.assert_called_once_with(mock.ANY, pr)
        github.dispatch.assert_not_called()

    def test_mismatched_keyword_is_not_adopted(self) -> None:
        github = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 27, 21, 45, tzinfo=ISRAEL_TZ), github=github, site=mock.MagicMock()
        )
        pr = {
            "number": 1226,
            "title": "Publish Kesher article: changing-kindergarten-midyear",
            "body": "- Primary Keyword: מילת מפתח אחרת\n",
            "head": {"sha": "e" * 40},
        }
        github.open_article_prs.side_effect = [[], [pr]]
        with mock.patch.object(controller, "posts_on_main", return_value=[]), \
             mock.patch.object(controller, "_reconcile_completed_article_run", return_value=None), \
             mock.patch.object(controller, "_handle_open_article_pr") as handle:
            action = controller._run_now_article_phase(self._state())
        self.assertEqual(action.kind, "dispatch_article")
        handle.assert_not_called()
        github.dispatch.assert_called_once()


if __name__ == "__main__":
    unittest.main()

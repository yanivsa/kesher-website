from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_daily_pipeline as pipeline
from tests.test_v5_shared_video_controller import FakeGitHub, FakeSite, article

TZ = ZoneInfo("Asia/Jerusalem")
ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "kesher-daily-video.yml"


def prior_article() -> dict:
    post = article("unattached-adults-missed-chances-regrets")
    post.update({
        "title": "התמודדות עם תחושת החמצה ברווקות מאוחרת",
        "date": "2026-08-19",
        "category": "רווקות",
        "excerpt": "תחושת החמצה יכולה להופיע גם כשממשיכים לבנות חיים מלאים.",
        "content": "<p>תוכן מלא בעברית על רווקות מאוחרת, בחירה, קשרים והמשך תנועה קדימה.</p>",
    })
    return post


def current_cycle_state() -> dict:
    return {
        "schema_version": v5.STATE_SCHEMA_VERSION,
        "cycle": "2026-08-20",
        "status": "article_generating",
        "article": {"attempt_count": 1, **copy.deepcopy(v5.v3._stage_template())},
        "image": copy.deepcopy(v5.v3._stage_template()),
        "long_video": copy.deepcopy(v5.v3._stage_template()),
        "short": copy.deepcopy(v5.v3._stage_template()),
        "backlog": [{
            "cycle": "2026-08-19",
            "status": "article_pr_open",
            "article": {"pr_number": 694, "attempt_count": 1},
            "archived_at": "2026-08-19T21:01:00+00:00",
        }],
        "history": [],
        "last_error": None,
        "updated_at": "2026-08-19T21:02:00+00:00",
    }


class V5BacklogMediaRecoveryTests(unittest.TestCase):
    def test_backlog_media_dispatches_exact_long_form_while_today_article_worker_active(self):
        gh = FakeGitHub()
        old_post = prior_article()
        gh.posts = [old_post]
        gh.saved_state = current_cycle_state()
        gh.active[core.ARTICLE_WORKFLOW] = {
            "id": 9001,
            "status": "in_progress",
            "event": "workflow_dispatch",
            "run_started_at": "2026-08-19T21:05:00Z",
        }
        gh.jules_snapshots["2026-08-20"] = {
            "session_id": "sessions/today",
            "state": "IN_PROGRESS",
            "fingerprint": "today-fp",
        }
        controller = v5.V5Controller(
            gh,
            FakeSite(),
            now=datetime(2026, 8, 20, 0, 40, tzinfo=TZ),
        )
        source = v5.article_source_identity(old_post)

        state, action = controller.tick()

        self.assertEqual(action.kind, "dispatch_backlog_long_video")
        self.assertEqual(gh.dispatches, [(
            v5.LONG_VIDEO_WORKFLOW,
            {
                "operation": "full",
                "target_slug": source["slug"],
                "target_content_sha256": source["content_sha256"],
            },
        )])
        self.assertEqual(gh.cancelled_runs, [])
        self.assertEqual(gh.jules_nudges, [])
        self.assertEqual(state["article"]["attempt_count"], 1)
        media = state["backlog"][0]["media"]
        self.assertEqual(media["source_slug"], source["slug"])
        self.assertEqual(media["source_content_sha256"], source["content_sha256"])
        self.assertEqual(media["long_status"], "running")

    def test_pipeline_target_selection_is_exact_and_hash_bound(self):
        old_post = prior_article()
        newer = article("newer-article")
        newer["date"] = "2026-08-20"
        state = {"version": 1, "items": []}
        expected = pipeline.source_metadata(old_post)

        with tempfile.TemporaryDirectory() as tmp:
            posts_path = Path(tmp) / "posts.json"
            posts_path.write_text(json.dumps([newer, old_post], ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(pipeline, "POSTS_FILE", posts_path), mock.patch.object(
                pipeline,
                "israel_now",
                return_value=datetime(2026, 8, 20, 12, 0, tzinfo=TZ),
            ):
                selected = pipeline.select_article_for_generation(
                    state,
                    target_slug=expected["slug"],
                    target_content_sha256=expected["content_sha256"],
                )
                self.assertEqual(selected["slug"], expected["slug"])
                self.assertEqual(selected["content_sha256"], expected["content_sha256"])
                with self.assertRaisesRegex(pipeline.PipelineError, "hash"):
                    pipeline.select_article_for_generation(
                        state,
                        target_slug=expected["slug"],
                        target_content_sha256="0" * 64,
                    )

    def test_video_workflow_exposes_exact_target_inputs(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("target_slug:", workflow)
        self.assertIn("target_content_sha256:", workflow)
        self.assertIn("KESHER_TARGET_SLUG", workflow)
        self.assertIn("KESHER_TARGET_CONTENT_SHA256", workflow)


if __name__ == "__main__":
    unittest.main()

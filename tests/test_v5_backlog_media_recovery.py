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
from scripts import kesher_content_controller_v5_runtime as runtime
from scripts import kesher_daily_pipeline as pipeline
from scripts import kesher_exact_video_target as exact_target
from tests.test_v5_shared_video_controller import FakeGitHub, article

TZ = ZoneInfo("Asia/Jerusalem")
ROOT = Path(__file__).resolve().parents[1]
RECOVERY_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "kesher-backlog-media-recovery.yml"


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


class PriorArticleSite:
    def get(self, url):
        return 200, "<html><h1>התמודדות עם תחושת החמצה ברווקות מאוחרת</h1></html>"


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
    def test_backlog_media_dispatches_exact_seed_while_today_article_worker_active(self):
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
        controller = runtime.RuntimeV5Controller(
            gh,
            PriorArticleSite(),
            now=datetime(2026, 8, 20, 0, 40, tzinfo=TZ),
        )
        source = v5.article_source_identity(old_post)

        state, action = controller.tick()

        self.assertEqual(action.kind, "dispatch_backlog_long_video")
        self.assertEqual(gh.dispatches, [(
            runtime.BACKLOG_MEDIA_RECOVERY_WORKFLOW,
            {
                "target_slug": source["slug"],
                "target_content_sha256": source["content_sha256"],
            },
        )])
        self.assertEqual(gh.cancelled_runs, [])
        self.assertEqual(gh.jules_nudges, [])
        media = state["backlog"][0]["media"]
        self.assertEqual(media["source_slug"], source["slug"])
        self.assertEqual(media["source_content_sha256"], source["content_sha256"])
        self.assertEqual(media["long_status"], "running")

    def test_exact_seed_selection_is_slug_and_hash_bound(self):
        old_post = prior_article()
        newer = article("newer-article")
        newer["date"] = "2026-08-20"
        expected = pipeline.source_metadata(old_post)

        with tempfile.TemporaryDirectory() as tmp:
            posts_path = Path(tmp) / "posts.json"
            posts_path.write_text(json.dumps([newer, old_post], ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(pipeline, "POSTS_FILE", posts_path):
                selected = exact_target.exact_source(
                    expected["slug"],
                    expected["content_sha256"],
                )
                self.assertEqual(selected["slug"], expected["slug"])
                self.assertEqual(selected["content_sha256"], expected["content_sha256"])
                with self.assertRaisesRegex(pipeline.PipelineError, "hash mismatch"):
                    exact_target.exact_source(expected["slug"], "0" * 64)

    def test_exact_seed_reuses_existing_identity_without_duplicate_generation(self):
        old_post = prior_article()
        expected = pipeline.source_metadata(old_post)
        existing = pipeline.new_item(expected)
        state = {"version": 1, "items": [existing], "updated_at": None}

        with tempfile.TemporaryDirectory() as tmp:
            posts_path = Path(tmp) / "posts.json"
            state_dir = Path(tmp) / "state"
            posts_path.write_text(json.dumps([old_post], ensure_ascii=False), encoding="utf-8")
            state_dir.mkdir()
            (state_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(pipeline, "POSTS_FILE", posts_path), mock.patch.object(
                pipeline, "STATE_DIR", state_dir
            ), mock.patch.object(pipeline, "STATE_FILE", state_dir / "state.json"):
                chosen = exact_target.seed_exact_target(expected["slug"], expected["content_sha256"])
                saved = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))
                self.assertEqual(chosen["id"], existing["id"])
                self.assertEqual(len(saved["items"]), 1)

    def test_recovery_workflow_is_exact_handoff_into_canonical_pipeline(self):
        workflow = RECOVERY_WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("target_slug:", workflow)
        self.assertIn("target_content_sha256:", workflow)
        self.assertIn("kesher_exact_video_target.py", workflow)
        self.assertIn("kesher-daily-video.yml -f operation=full", workflow)
        self.assertIn("name: kesher-video-state", workflow)


if __name__ == "__main__":
    unittest.main()

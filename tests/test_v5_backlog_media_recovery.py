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
    def test_backlog_media_waits_while_today_article_worker_active(self):
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

        state, action = controller.tick()

        self.assertEqual(action.kind, "article_watchdog_nudge")
        self.assertNotEqual(action.kind, "dispatch_backlog_long_video")
        self.assertEqual(gh.dispatches, [])
        self.assertEqual(gh.cancelled_runs, [])
        self.assertEqual(gh.jules_nudges, ["sessions/today"])
        self.assertNotIn("media", state["backlog"][0])

    def test_published_backlog_source_disambiguates_same_date_posts(self):
        gh = FakeGitHub()
        post_a = prior_article()
        post_a["slug"] = "post-a"
        post_a["controllerManaged"] = True

        post_b = copy.deepcopy(post_a)
        post_b["slug"] = "post-b"
        post_b["controllerManaged"] = False
        post_b["title"] = "פוסט נוסף באותו תאריך"

        source_a = v5.article_source_identity(post_a)
        source_b = v5.article_source_identity(post_b)
        gh.posts = [post_a, post_b]

        class Site:
            def get(self, url):
                if "post-b" in url:
                    return 200, (
                        "<html><head>"
                        '<link rel="canonical" href="https://kesher.saharoni.com/blog/post-b">'
                        '<meta property="og:url" content="https://kesher.saharoni.com/blog/post-b">'
                        f'<meta name="kesher:content-sha256" content="{source_b["content_sha256"]}">'
                        "</head><h1>פוסט נוסף באותו תאריך</h1></html>"
                    )
                return 200, (
                    "<html><head>"
                    '<link rel="canonical" href="https://kesher.saharoni.com/blog/post-a">'
                    '<meta property="og:url" content="https://kesher.saharoni.com/blog/post-a">'
                    f'<meta name="kesher:content-sha256" content="{source_a["content_sha256"]}">'
                    "</head><h1>התמודדות עם תחושת החמצה ברווקות מאוחרת</h1></html>"
                )

        controller = runtime.RuntimeV5Controller(
            gh,
            Site(),
            now=datetime(2026, 8, 20, 0, 40, tzinfo=TZ),
        )

        # Manual/editorial backlog identity is not adoptable from slug alone.
        weak_manual_state = {
            "backlog": [{
                "cycle": "2026-08-19",
                "article": {"slug": "post-b"},
            }]
        }
        row, source = controller._published_backlog_source(weak_manual_state)
        self.assertIsNone(row)
        self.assertIsNone(source)

        # Exact immutable slug + content SHA may adopt the explicit manual source.
        state_b = {
            "backlog": [{
                "cycle": "2026-08-19",
                "article": {
                    "slug": "post-b",
                    "quality_content_sha256": source_b["content_sha256"],
                },
            }]
        }
        row, source = controller._published_backlog_source(state_b)
        self.assertIsNotNone(row)
        self.assertEqual(source["slug"], "post-b")
        self.assertEqual(source["content_sha256"], source_b["content_sha256"])

        # A single controller-managed source remains deterministic without a saved slug.
        state_no_slug = {
            "backlog": [{
                "cycle": "2026-08-19",
                "article": {},
            }]
        }
        row, source = controller._published_backlog_source(state_no_slug)
        self.assertIsNotNone(row)
        self.assertEqual(source["slug"], "post-a")
        self.assertEqual(source["content_sha256"], source_a["content_sha256"])

    def test_exact_backlog_source_404_dispatches_one_deploy_and_dedups_active_run(self):
        gh = FakeGitHub()
        post = prior_article()
        post["controllerManaged"] = True
        source = v5.article_source_identity(post)
        gh.posts = [post]

        class MissingSite:
            def get(self, url):
                return 404, "<html><h1>not found</h1></html>"

        state = {
            "status": "waiting_for_article_window",
            "backlog": [{
                "cycle": "2026-08-19",
                "status": "blocked",
                "article": {
                    "slug": source["slug"],
                    "quality_content_sha256": source["content_sha256"],
                    "attempt_count": 3,
                    "deploy_attempts": 0,
                },
            }],
            "history": [],
        }
        controller = runtime.RuntimeV5Controller(
            gh,
            MissingSite(),
            now=datetime(2026, 8, 20, 0, 40, tzinfo=TZ),
        )

        action = controller._backlog_media_preflight(state)
        self.assertEqual(action.kind, "dispatch_backlog_deploy")
        self.assertEqual(gh.dispatches, [(core.DEPLOY_WORKFLOW, None)])
        self.assertEqual(state["backlog"][0]["article"]["deploy_attempts"], 1)
        self.assertFalse(state["backlog"][0]["media"]["article_live"])

        second = controller._backlog_media_preflight(state)
        self.assertEqual(second.kind, "wait")
        self.assertEqual(gh.dispatches, [(core.DEPLOY_WORKFLOW, None)])

    def test_deploy_exhausted_backlog_that_is_now_public_advances_to_long_video(self):
        gh = FakeGitHub()
        post = prior_article()
        post["controllerManaged"] = True
        source = v5.article_source_identity(post)
        gh.posts = [post]

        class LiveSite:
            def get(self, _url):
                return 200, (
                    "<html><head>"
                    f'<link rel="canonical" href="https://kesher.saharoni.com/blog/{source["slug"]}">'
                    f'<meta property="og:url" content="https://kesher.saharoni.com/blog/{source["slug"]}">'
                    f'<meta name="kesher:content-sha256" content="{source["content_sha256"]}">'
                    "</head>"
                    f"<body><h1>{post['title']}</h1></body></html>"
                )

        state = {
            "status": "waiting_for_article_window",
            "backlog": [{
                "cycle": "2026-08-19",
                "status": "article_deploying",
                "article": {
                    "slug": source["slug"],
                    "quality_content_sha256": source["content_sha256"],
                    "deploy_attempts": runtime.MAX_BACKLOG_DEPLOY_DISPATCHES,
                },
                "media": {
                    "article_live": False,
                    "article_deploy_status": "exhausted",
                    "last_error": "BACKLOG_ARTICLE_DEPLOY_ATTEMPTS_EXHAUSTED",
                },
            }],
            "history": [],
        }
        controller = runtime.RuntimeV5Controller(
            gh,
            LiveSite(),
            now=datetime(2026, 8, 20, 0, 40, tzinfo=TZ),
        )

        action = controller._backlog_media_preflight(state)

        self.assertEqual(action.kind, "dispatch_backlog_long_video")
        self.assertTrue(state["backlog"][0]["media"]["article_live"])
        self.assertEqual(state["backlog"][0]["media"]["article_deploy_status"], "complete")
        self.assertIsNone(state["backlog"][0]["media"]["last_error"])
        self.assertEqual(
            gh.dispatches,
            [(
                v5.LONG_VIDEO_WORKFLOW,
                {
                    "operation": "full",
                    "target_slug": source["slug"],
                    "target_content_sha256": source["content_sha256"],
                },
            )],
        )

    def test_deploy_exhausted_backlog_still_404s_without_an_extra_deploy(self):
        gh = FakeGitHub()
        post = prior_article()
        post["controllerManaged"] = True
        source = v5.article_source_identity(post)
        gh.posts = [post]

        class MissingSite:
            def get(self, _url):
                return 404, "<html><h1>not found</h1></html>"

        state = {
            "status": "waiting_for_article_window",
            "backlog": [{
                "cycle": "2026-08-19",
                "article": {
                    "slug": source["slug"],
                    "quality_content_sha256": source["content_sha256"],
                    "deploy_attempts": runtime.MAX_BACKLOG_DEPLOY_DISPATCHES,
                },
                "media": {
                    "article_live": False,
                    "article_deploy_status": "exhausted",
                    "last_error": "BACKLOG_ARTICLE_DEPLOY_ATTEMPTS_EXHAUSTED",
                },
            }],
            "history": [],
        }
        controller = runtime.RuntimeV5Controller(
            gh,
            MissingSite(),
            now=datetime(2026, 8, 20, 0, 40, tzinfo=TZ),
        )

        action = controller._backlog_media_preflight(state)

        self.assertEqual(action.kind, "backlog_unresolved")
        self.assertEqual(action.reason, "prior-cycle backlog items remain unresolved or exhausted")
        self.assertEqual(gh.dispatches, [])
        self.assertFalse(state["backlog"][0]["media"]["article_live"])
        self.assertEqual(state["backlog"][0]["media"]["article_deploy_status"], "exhausted")

    def test_published_backlog_source_rejects_title_only_public_page(self):
        gh = FakeGitHub()
        post = prior_article()
        post["controllerManaged"] = True
        gh.posts = [post]

        class TitleOnlySite:
            def get(self, url):
                return 200, "<html><h1>התמודדות עם תחושת החמצה ברווקות מאוחרת</h1></html>"

        controller = runtime.RuntimeV5Controller(
            gh,
            TitleOnlySite(),
            now=datetime(2026, 8, 20, 0, 40, tzinfo=TZ),
        )
        state = {
            "backlog": [{
                "cycle": "2026-08-19",
                "article": {"slug": post["slug"]},
            }]
        }

        row, source = controller._published_backlog_source(state)

        self.assertIsNone(row)
        self.assertIsNone(source)

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

    def test_exact_seed_does_not_reuse_short_item_for_long_video(self):
        old_post = prior_article()
        expected = pipeline.source_metadata(old_post)
        short_item = pipeline.new_item(expected)
        short_item.update({
            "id": "short-existing-same-source",
            "type": "article_short",
            "source_mode": "direct-short",
            "status": "downloaded",
        })
        state = {"version": 1, "items": [short_item], "updated_at": None}

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

        self.assertNotEqual(chosen["id"], short_item["id"])
        self.assertEqual(chosen["type"], "video_overview")
        self.assertEqual(len(saved["items"]), 2)

    def test_exact_seed_supersedes_stale_same_slug_hash_before_seeding_current_identity(self):
        old_post = prior_article()
        expected = pipeline.source_metadata(old_post)
        stale = pipeline.new_item(expected)
        stale.update({
            "id": "video-stale-same-slug",
            "type": "video_overview",
            "status": "downloaded",
        })
        stale["source"] = dict(stale["source"])
        stale["source"]["content_sha256"] = "f" * 64
        state = {"version": 1, "items": [stale], "updated_at": None}

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

        self.assertNotEqual(chosen["id"], stale["id"])
        self.assertEqual(chosen["source"]["content_sha256"], expected["content_sha256"])
        self.assertEqual(saved["items"][0]["status"], "superseded")
        self.assertEqual(saved["items"][0]["superseded_reason"], "stale_source_content_sha256")
        self.assertEqual(saved["items"][0]["superseded_by_content_sha256"], expected["content_sha256"])
        self.assertEqual(len(saved["items"]), 2)

    def test_exact_seed_still_blocks_unrelated_active_long_video(self):
        old_post = prior_article()
        expected = pipeline.source_metadata(old_post)
        other_source = dict(expected)
        other_source["slug"] = "different-article"
        other_source["id"] = "different-article"
        other = pipeline.new_item(other_source)
        other.update({"id": "video-other-active", "type": "video_overview", "status": "downloaded"})
        state = {"version": 1, "items": [other], "updated_at": None}

        with tempfile.TemporaryDirectory() as tmp:
            posts_path = Path(tmp) / "posts.json"
            state_dir = Path(tmp) / "state"
            posts_path.write_text(json.dumps([old_post], ensure_ascii=False), encoding="utf-8")
            state_dir.mkdir()
            (state_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(pipeline, "POSTS_FILE", posts_path), mock.patch.object(
                pipeline, "STATE_DIR", state_dir
            ), mock.patch.object(pipeline, "STATE_FILE", state_dir / "state.json"):
                with self.assertRaisesRegex(pipeline.PipelineError, "unrelated unresolved video"):
                    exact_target.seed_exact_target(expected["slug"], expected["content_sha256"])

    def test_exact_seed_does_not_let_newer_unrelated_item_block_older_fifo_target(self):
        old_post = prior_article()
        expected = pipeline.source_metadata(old_post)
        newer_source = dict(expected)
        newer_source.update({
            "slug": "newer-different-article",
            "id": "newer-different-article",
            "date": "2026-08-20",
            "content_sha256": "e" * 64,
        })
        newer = pipeline.new_item(newer_source)
        newer.update({"id": "video-newer-active", "type": "video_overview", "status": "downloaded"})
        state = {"version": 1, "items": [newer], "updated_at": None}

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

        self.assertEqual(chosen["source"]["slug"], expected["slug"])
        self.assertEqual(chosen["source"]["content_sha256"], expected["content_sha256"])
        self.assertEqual(saved["items"][0]["status"], "downloaded")
        self.assertEqual(len(saved["items"]), 2)

    def test_recovery_workflow_is_exact_handoff_into_canonical_pipeline(self):
        workflow = RECOVERY_WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("target_slug:", workflow)
        self.assertIn("target_content_sha256:", workflow)
        self.assertIn("kesher_exact_video_target.py", workflow)
        self.assertIn("kesher-daily-video.yml -f operation=full", workflow)
        self.assertIn("name: kesher-video-state", workflow)

    def test_exhausted_newest_row_allows_older_eligible_row_to_advance(self):
        gh = FakeGitHub()
        post_new = prior_article()
        post_new["slug"] = "newest-article"
        post_new["date"] = "2026-08-20"
        post_new["controllerManaged"] = True
        source_new = v5.article_source_identity(post_new)

        post_old = article("older-article")
        post_old["date"] = "2026-08-19"
        post_old["controllerManaged"] = True
        source_old = v5.article_source_identity(post_old)

        gh.posts = [post_new, post_old]

        class HybridSite:
            def get(self, url):
                if source_old["slug"] in url:
                    return 200, (
                        "<html><head>"
                        f'<link rel="canonical" href="https://kesher.saharoni.com/blog/{source_old["slug"]}">'
                        f'<meta property="og:url" content="https://kesher.saharoni.com/blog/{source_old["slug"]}">'
                        f'<meta name="kesher:content-sha256" content="{source_old["content_sha256"]}">'
                        "</head>"
                        f"<body><h1>{post_old['title']}</h1></body></html>"
                    )
                return 404, "<html><h1>not found</h1></html>"

        state = {
            "status": "waiting_for_article_window",
            "backlog": [
                {
                    "cycle": "2026-08-20",
                    "article": {
                        "slug": source_new["slug"],
                        "quality_content_sha256": source_new["content_sha256"],
                        "deploy_attempts": runtime.MAX_BACKLOG_DEPLOY_DISPATCHES,
                    },
                    "media": {
                        "article_live": False,
                        "article_deploy_status": "exhausted",
                        "last_error": "BACKLOG_ARTICLE_DEPLOY_ATTEMPTS_EXHAUSTED",
                    },
                },
                {
                    "cycle": "2026-08-19",
                    "article": {
                        "slug": source_old["slug"],
                        "quality_content_sha256": source_old["content_sha256"],
                        "deploy_attempts": 0,
                    },
                    "media": {
                        "article_live": False,
                    },
                },
            ],
            "history": [],
        }
        controller = runtime.RuntimeV5Controller(
            gh,
            HybridSite(),
            now=datetime(2026, 8, 20, 0, 40, tzinfo=TZ),
        )

        action = controller._backlog_media_preflight(state)

        self.assertEqual(action.kind, "dispatch_backlog_long_video")
        self.assertEqual(state["backlog"][0]["media"]["article_deploy_status"], "exhausted")
        self.assertEqual(state["backlog"][0]["article"]["deploy_attempts"], runtime.MAX_BACKLOG_DEPLOY_DISPATCHES)
        self.assertTrue(state["backlog"][1]["media"]["article_live"])
        self.assertEqual(
            gh.dispatches,
            [(
                v5.LONG_VIDEO_WORKFLOW,
                {
                    "operation": "full",
                    "target_slug": source_old["slug"],
                    "target_content_sha256": source_old["content_sha256"],
                },
            )],
        )

    def test_all_deploy_exhausted_backlog_ends_boundedly_without_global_controller_failure(self):
        gh = FakeGitHub()
        prior_post = prior_article()
        prior_post["controllerManaged"] = True
        source = v5.article_source_identity(prior_post)

        today_post = article("today-article")
        today_post["date"] = "2026-08-20"
        today_post["controllerManaged"] = True
        source_today = v5.article_source_identity(today_post)
        gh.posts = [today_post, prior_post]

        class SiteWithTodayPublic:
            def get(self, url):
                if source_today["slug"] in url:
                    return 200, (
                        "<html><head>"
                        f'<link rel="canonical" href="https://kesher.saharoni.com/blog/{source_today["slug"]}">'
                        f'<meta property="og:url" content="https://kesher.saharoni.com/blog/{source_today["slug"]}">'
                        f'<meta name="kesher:content-sha256" content="{source_today["content_sha256"]}">'
                        "</head>"
                        f"<body><h1>{today_post['title']}</h1></body></html>"
                    )
                return 404, "<html><h1>not found</h1></html>"

        gh.active[v5.LONG_VIDEO_WORKFLOW] = {
            "id": 999,
            "status": "in_progress",
            "event": "workflow_dispatch",
        }

        state = {
            "schema_version": v5.STATE_SCHEMA_VERSION,
            "cycle": "2026-08-20",
            "status": "waiting_for_article_window",
            "article": {"status": "pending"},
            "image": {"status": "pending"},
            "long_video": {"status": "running", "run_id": 999},
            "short": {"status": "pending"},
            "backlog": [{
                "cycle": "2026-08-19",
                "article": {
                    "slug": source["slug"],
                    "quality_content_sha256": source["content_sha256"],
                    "deploy_attempts": runtime.MAX_BACKLOG_DEPLOY_DISPATCHES,
                },
                "media": {
                    "article_live": False,
                    "article_deploy_status": "exhausted",
                    "last_error": "BACKLOG_ARTICLE_DEPLOY_ATTEMPTS_EXHAUSTED",
                },
            }],
            "history": [],
        }
        gh.saved_state = state

        controller = runtime.RuntimeV5Controller(
            gh,
            SiteWithTodayPublic(),
            now=datetime(2026, 8, 20, 0, 40, tzinfo=TZ),
        )

        state_out, action = controller.tick()

        self.assertEqual(action.kind, "wait")
        self.assertEqual(gh.dispatches, [])
        self.assertEqual(state_out["backlog"][0]["media"]["article_deploy_status"], "exhausted")

    def test_current_actionable_cycle_unaffected_by_backlog_exhaustion(self):
        gh = FakeGitHub()
        prior_post = prior_article()
        prior_post["controllerManaged"] = True
        source = v5.article_source_identity(prior_post)

        today_post = article("today-article")
        today_post["date"] = "2026-08-20"
        today_post["controllerManaged"] = True
        source_today = v5.article_source_identity(today_post)
        gh.posts = [today_post, prior_post]

        class SiteWithTodayPublic:
            def get(self, url):
                if source_today["slug"] in url:
                    return 200, (
                        "<html><head>"
                        f'<link rel="canonical" href="https://kesher.saharoni.com/blog/{source_today["slug"]}">'
                        f'<meta property="og:url" content="https://kesher.saharoni.com/blog/{source_today["slug"]}">'
                        f'<meta name="kesher:content-sha256" content="{source_today["content_sha256"]}">'
                        "</head>"
                        f"<body><h1>{today_post['title']}</h1></body></html>"
                    )
                return 404, "<html><h1>not found</h1></html>"

        state = {
            "schema_version": v5.STATE_SCHEMA_VERSION,
            "cycle": "2026-08-20",
            "status": "long_video_running",
            "article": {"status": "complete", "live": True},
            "image": {"status": "complete"},
            "long_video": {"status": "running", "run_id": 123},
            "short": {"status": "pending"},
            "backlog": [{
                "cycle": "2026-08-19",
                "article": {
                    "slug": source["slug"],
                    "quality_content_sha256": source["content_sha256"],
                    "deploy_attempts": runtime.MAX_BACKLOG_DEPLOY_DISPATCHES,
                },
                "media": {
                    "article_live": False,
                    "article_deploy_status": "exhausted",
                    "last_error": "BACKLOG_ARTICLE_DEPLOY_ATTEMPTS_EXHAUSTED",
                },
            }],
            "history": [],
        }
        gh.saved_state = state
        gh.active[v5.LONG_VIDEO_WORKFLOW] = {
            "id": 123,
            "status": "in_progress",
            "event": "workflow_dispatch",
        }

        controller = runtime.RuntimeV5Controller(
            gh,
            SiteWithTodayPublic(),
            now=datetime(2026, 8, 20, 0, 40, tzinfo=TZ),
        )

        state_out, action = controller.tick()

        self.assertEqual(action.kind, "wait")
        self.assertEqual(action.reason, "video workflow active")


if __name__ == "__main__":
    unittest.main()

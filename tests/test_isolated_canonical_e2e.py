from __future__ import annotations

import copy
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest import mock
import urllib.parse

from scripts import kesher_article_contract as article_contract
from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_stabilized as stabilized
from scripts import kesher_content_controller_v5 as v5
from tests.test_media_provenance_contract import bound_short


ROOT = Path(__file__).resolve().parents[1]


def make_valid_article(slug: str, date_str: str) -> dict:
    """Create a fully conformant article post with 5 H3 sections, 800 words, and local hero image."""
    content = "".join(f"<h3>Section {i}</h3>" + " word" * 160 for i in range(1, 6))
    return {
        "id": slug,
        "slug": slug,
        "title": f"Article Title for {slug}",
        "date": date_str,
        "category": "זוגיות",
        "excerpt": "A sufficiently long and meaningful excerpt for the article post.",
        "content": content,
        "image": f"/images/generated/blog/{slug}.jpg",
        "imageAlt": "Detailed descriptive alt text for this generated article hero image.",
    }


def make_public_html(post: dict) -> str:
    source = v5.article_source_identity(post)
    hero = post.get("image", "")
    return (
        f"<!DOCTYPE html><html><head><title>{post['title']}</title>"
        f"<meta property='article:published_time' content='{post['date']}'>"
        f"<link rel='canonical' href='https://kesher.saharoni.com/blog/{post['slug']}'>"
        f"<meta name='kesher:content-sha256' content='{source['content_sha256']}'>"
        f"<meta property='og:image' content='https://kesher.saharoni.com{hero}'>"
        f"</head><body><h1>{post['title']}</h1><img src='{hero}'>{post['content']}</body></html>"
    )


class IsolatedE2ESimGitHub:
    api = "https://api.github.test/repos/yanivsa/kesher-website"

    def __init__(self, initial_state: dict, posts: list[dict], recent_posts: list[dict] | None = None) -> None:
        self.state = copy.deepcopy(initial_state)
        self.posts = copy.deepcopy(posts)
        self.recent_posts = copy.deepcopy(recent_posts or [])
        self.open_prs: list[dict] = []
        self.pr_comments: dict[int, list[dict]] = {}
        self.dispatches: list[tuple[str, dict]] = []
        self.active_runs: dict[str, dict | None] = {}
        self.workflow_runs_history: list[dict] = []
        self.video_items: list[dict] = []
        self.short_items: list[dict] = []
        self.needs_norm = False
        self.image_ready = False
        self.image_evidence: dict = {}
        self.next_run_id = 9000

    def load_controller_state(self) -> dict:
        return copy.deepcopy(self.state)

    def save_controller_state(self, state: dict) -> None:
        self.state = copy.deepcopy(state)

    def contents_json(self, path: str, ref: str = "main") -> list[dict]:
        if path == "src/data/posts.json":
            posts = copy.deepcopy(self.posts)
            for pr in self.open_prs:
                if ref == (pr.get("head") or {}).get("sha"):
                    pr_posts = pr.get("posts_override")
                    if pr_posts is not None:
                        return copy.deepcopy(pr_posts)
                    post_data = pr.get("post_data")
                    if post_data and not any(core.canonical_slug(p) == post_data["slug"] for p in posts):
                        posts.append(copy.deepcopy(post_data))
            return posts
        if path == "src/data/postsRecent.json":
            return copy.deepcopy(self.recent_posts)
        raise ValueError(f"Unknown path: {path}")

    def posts_on_main(self, ref: str = "main") -> list[dict]:
        return copy.deepcopy(self.posts)

    def open_article_prs(self, slot: str | None = None) -> list[dict]:
        return copy.deepcopy(self.open_prs)

    def article_pr_normalization_required(self, pr: dict) -> tuple[bool, str]:
        return self.needs_norm, str(self.state.get("cycle") or "2026-10-15")

    def active_normalizer_run(self, number: int) -> dict | None:
        return self.active_runs.get("normalize-article-pr.yml")

    def article_pr_image_ready(self, pr: dict) -> tuple[bool, dict]:
        return self.image_ready, copy.deepcopy(self.image_evidence)

    def active_image_run(self, number: int) -> dict | None:
        return self.active_runs.get(v5.v3.IMAGE_WORKFLOW)

    def active_workflow_run(self, workflow: str, production_only: bool = False) -> dict | None:
        return self.active_runs.get(workflow)

    def workflow_run_by_id(self, run_id: int | str) -> dict | None:
        for run in self.workflow_runs_history:
            if str(run.get("id")) == str(run_id):
                return copy.deepcopy(run)
        return None

    def workflow_runs(self, workflow: str) -> list[dict]:
        return [copy.deepcopy(r) for r in self.workflow_runs_history if r.get("workflow") == workflow]

    def newest_video_state(self) -> dict:
        return {"version": 1, "items": copy.deepcopy(self.video_items)}

    def newest_short_state(self) -> dict:
        return {"version": 1, "items": copy.deepcopy(self.short_items)}

    def _record_dispatch(self, workflow: str, inputs: dict | None = None) -> None:
        self.dispatches.append((workflow, copy.deepcopy(inputs or {})))
        self.next_run_id += 1
        run_record = {
            "id": self.next_run_id,
            "name": workflow,
            "workflow": workflow,
            "status": "in_progress",
            "conclusion": None,
            "event": "workflow_dispatch",
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        self.workflow_runs_history.append(run_record)

    def dispatch(self, workflow: str, inputs: dict | None = None) -> None:
        self._record_dispatch(workflow, inputs)

    def request(self, method: str, path: str, body: dict | None = None, allow_404: bool = False) -> Any:
        if method == "GET" and "/issues/" in path and "/comments" in path:
            pr_num = int(path.split("/issues/")[1].split("/comments")[0])
            return copy.deepcopy(self.pr_comments.get(pr_num, []))
        if method == "POST" and "/dispatches" in path:
            wf = urllib.parse.unquote(path.split("/actions/workflows/")[1].split("/dispatches")[0])
            inputs = copy.deepcopy((body or {}).get("inputs") or {})
            self._record_dispatch(wf, inputs)
            return {}
        if method == "GET" and "/actions/artifacts" in path:
            return {"artifacts": []}
        return {}


class IsolatedCanonicalE2ETests(unittest.TestCase):
    """Production-faithful isolated end-to-end suite verifying zero-touch Article -> Long -> Short lifecycle."""

    def test_happy_path_rollover_2026_10_14_to_2026_10_15_and_full_lifecycle(self) -> None:
        """Rollover from terminal 2026-10-14 to 2026-10-15 through full Article, Long, Short lifecycle."""
        # 1. Start from real-world terminal blocked 2026-10-14 state
        terminal_2026_10_14_state = {
            "schema_version": 5,
            "cycle": "2026-10-14",
            "status": "blocked",
            "blocked_stage": "article",
            "blocked_code": "ARTICLE_ATTEMPTS_EXHAUSTED",
            "blocked_reason": "PR #1113 exceeded maximum auto-merge dispatch budget (6 dispatches)",
            "article": {
                "status": "exhausted",
                "pr_number": 1113,
                "merge_dispatch_count": 6,
                "attempts": 3,
                "live": False,
            },
            "image": {"status": "complete", "attempt_count": 1},
            "long_video": {"status": "pending", "attempt_count": 0},
            "short": {"status": "pending", "attempt_count": 0},
            "history": [{"timestamp": "2026-10-14T10:00:00+00:00", "transition": "blocked"}],
            "backlog": [],
        }

        base_post_historical = make_valid_article("historical-oct13", "2026-10-13")
        sim_gh = IsolatedE2ESimGitHub(terminal_2026_10_14_state, [base_post_historical])
        sim_site = mock.Mock()
        sim_site.get.return_value = (404, "Not Found")

        def run_tick(now_dt: dt.datetime, **child_env: str):
            env = {
                "GITHUB_REPOSITORY": "yanivsa/kesher-website",
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_EVENT_NAME": "workflow_dispatch" if child_env else "schedule",
                "GITHUB_WORKFLOW_REF": "yanivsa/kesher-website/.github/workflows/kesher-content-controller.yml@refs/heads/main",
                "KESHER_TRIGGER_EVENT": "workflow_dispatch" if child_env else "schedule",
                "KESHER_PRE_CUTOVER_DAILY_AUTHORITY": "true",
            }
            env.update(child_env)
            with mock.patch.dict(os.environ, env, clear=False):
                ctrl = stabilized.StabilizedRuntimeV5Controller(sim_gh, sim_site, now=now_dt)
                return ctrl.tick()

        # STEP 1: Early morning 2026-10-15 tick at 00:10 (waiting for window)
        st_0010, act_0010 = run_tick(dt.datetime(2026, 10, 15, 0, 10, tzinfo=core.ISRAEL_TZ))
        self.assertEqual(st_0010["cycle"], "2026-10-15")
        self.assertEqual(st_0010["status"], "waiting_for_article_window")
        self.assertEqual(act_0010.kind, "wait")
        # Ensure 2026-10-14 remains quarantined in backlog without resurrection
        backlog_cycles = {r["cycle"]: r for r in st_0010.get("backlog", [])}
        self.assertIn("2026-10-14", backlog_cycles)
        self.assertEqual(backlog_cycles["2026-10-14"]["status"], "blocked")

        # STEP 2: Window opens at 00:36 -> dispatches Article Generation Attempt #1
        sim_gh.dispatches.clear()
        st_0036, act_0036 = run_tick(dt.datetime(2026, 10, 15, 0, 36, tzinfo=core.ISRAEL_TZ))
        self.assertEqual(act_0036.kind, "dispatch_article")
        self.assertEqual(st_0036["status"], "article_generating")
        self.assertEqual(st_0036["article"]["attempts"], 1)
        self.assertEqual(sim_gh.dispatches, [(core.ARTICLE_WORKFLOW, {"slot": "2026-10-15"})])

        # STEP 3: Article worker finishes, opens PR #1125, wakes controller
        new_post = make_valid_article("oct15-wedding-communication", "2026-10-15")
        new_source = v5.article_source_identity(new_post)
        sim_gh.dispatches.clear()
        sim_gh.open_prs = [{
            "number": 1125,
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1125",
            "title": f"Publish Kesher article: {new_post['slug']}",
            "head": {"sha": "head1125"},
            "base": {"sha": "base1125"},
            "post_data": new_post,
        }]
        sim_gh.workflow_runs_history.append({
            "id": 9010,
            "name": "Kesher Article Generation",
            "workflow": core.ARTICLE_WORKFLOW,
            "conclusion": "success",
            "event": "workflow_dispatch",
        })
        sim_gh.needs_norm = True

        st_art_done, act_art_done = run_tick(
            dt.datetime(2026, 10, 15, 0, 42, tzinfo=core.ISRAEL_TZ),
            KESHER_CHILD_WORKFLOW="Kesher Article Generation",
            KESHER_CHILD_RUN_ID="9010",
            KESHER_CHILD_CONCLUSION="success",
            KESHER_CHILD_SLOT="2026-10-15",
        )
        self.assertEqual(act_art_done.kind, "dispatch_normalize")
        self.assertEqual(sim_gh.dispatches, [("normalize-article-pr.yml", {"pr_number": "1125", "slot": "2026-10-15"})])

        # STEP 4: Normalizer completes, PR content validated, image required -> dispatch Image Attempt #1
        sim_gh.dispatches.clear()
        sim_gh.needs_norm = False
        sim_gh.image_ready = False
        sim_gh.workflow_runs_history.append({
            "id": 9011,
            "name": "Kesher Normalize Article PR",
            "workflow": "normalize-article-pr.yml",
            "conclusion": "success",
            "event": "workflow_dispatch",
        })

        st_norm_done, act_norm_done = run_tick(
            dt.datetime(2026, 10, 15, 0, 44, tzinfo=core.ISRAEL_TZ),
            KESHER_CHILD_WORKFLOW="Kesher Normalize Article PR",
            KESHER_CHILD_RUN_ID="9011",
            KESHER_CHILD_CONCLUSION="success",
        )
        self.assertEqual(act_norm_done.kind, "dispatch_image")
        self.assertEqual(st_norm_done["image"]["attempt_count"], 1)
        self.assertEqual(sim_gh.dispatches, [(v5.v3.IMAGE_WORKFLOW, {"pr_number": "1125"})])

        # STEP 5: Image worker attaches local image, controller verifies image proof -> auto-merge dispatched
        sim_gh.dispatches.clear()
        sim_gh.image_ready = True
        sim_gh.image_evidence = {
            "provider": "Local",
            "sha256": "aaaaaaaaaabbbbbbbbbbccccccccccdddddddddd11111111112222222222333333333344",
            "source": f"local://public{new_post['image']}",
            "article_id": new_post["id"],
            "article_sha256": new_source["content_sha256"],
            "head_sha": "head1125",
        }
        sim_gh.workflow_runs_history.append({
            "id": 9012,
            "name": "Kesher Trusted Article Image",
            "workflow": v5.v3.IMAGE_WORKFLOW,
            "conclusion": "success",
            "event": "workflow_dispatch",
        })

        st_img_done, act_img_done = run_tick(
            dt.datetime(2026, 10, 15, 0, 47, tzinfo=core.ISRAEL_TZ),
            KESHER_CHILD_WORKFLOW="Kesher Trusted Article Image",
            KESHER_CHILD_RUN_ID="9012",
            KESHER_CHILD_CONCLUSION="success",
        )
        self.assertEqual(act_img_done.kind, "wait")
        self.assertIn("merge gate dispatched", act_img_done.reason)
        self.assertEqual(sim_gh.dispatches, [("auto-merge-article-prs.yml", {"pr_number": "1125", "slot": "2026-10-15"})])

        # STEP 6: PR merged into main, but NOT yet public on Cloudflare Pages -> dispatch Deploy Attempt #1
        sim_gh.dispatches.clear()
        sim_gh.open_prs.clear()
        sim_gh.posts.append(new_post)  # merged into main!
        sim_site.get.return_value = (404, "Not Found")  # Cloudflare still returns 404

        st_merged, act_merged = run_tick(dt.datetime(2026, 10, 15, 0, 50, tzinfo=core.ISRAEL_TZ))
        self.assertEqual(act_merged.kind, "dispatch_deploy")
        self.assertEqual(st_merged["status"], "article_deploying")
        self.assertEqual(st_merged["article"]["deploy_attempts"], 1)
        self.assertEqual(st_merged["long_video"]["status"], "pending")  # Long MUST NOT advance!

        # STEP 7: Cloudflare deployment becomes live and returns HTTP 200 with matching sha
        sim_gh.dispatches.clear()
        sim_site.get.return_value = (200, make_public_html(new_post))

        st_pub_art, act_pub_art = run_tick(dt.datetime(2026, 10, 15, 0, 55, tzinfo=core.ISRAEL_TZ))
        self.assertTrue(st_pub_art["article"]["live"])
        self.assertEqual(st_pub_art["status"], "long_video_running")
        self.assertEqual(act_pub_art.kind, "dispatch_long_video")
        self.assertEqual(st_pub_art["long_video"]["attempt_count"], 1)

        # STEP 8: Long Video finishes and uploads, sends child notification with exact source_slug and source_sha
        sim_gh.dispatches.clear()
        sim_gh.video_items.append({
            "id": "video-oct15",
            "slug": new_post["slug"],
            "uploaded": True,
            "status": "uploaded",
            "youtube_id": "yt-long-oct15",
            "youtube_url": "https://youtu.be/yt-long-oct15",
            "technical_verified": True,
            "visual_pipeline": "remotion-v1-notebooklm-audio",
            "content_duration_seconds": 120.0,
            "signature_duration_seconds": 3.0,
            "signature_fullscreen": False,
            "signature_overlay": True,
            "signature_asset_sha256": "s" * 64,
            "source": {"slug": new_post["slug"], "content_sha256": new_source["content_sha256"]},
            "youtube_verification": {
                "channel_id": core.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
            "media": {"codec": "h264", "width": 1280, "height": 720, "duration": 120.0},
        })
        sim_gh.workflow_runs_history.append({
            "id": 9015,
            "name": "Kesher Daily NotebookLM Video Overview",
            "workflow": v5.LONG_VIDEO_WORKFLOW,
            "conclusion": "success",
            "event": "workflow_dispatch",
        })

        st_long_done, act_long_done = run_tick(
            dt.datetime(2026, 10, 15, 1, 10, tzinfo=core.ISRAEL_TZ),
            KESHER_CHILD_WORKFLOW="Kesher Daily NotebookLM Video Overview",
            KESHER_CHILD_RUN_ID="9015",
            KESHER_CHILD_CONCLUSION="success",
            KESHER_CHILD_SOURCE_SLUG=new_post["slug"],
            KESHER_CHILD_SOURCE_SHA=new_source["content_sha256"],
        )
        self.assertTrue(st_long_done["long_video"]["verified"])
        self.assertEqual(st_long_done["status"], "short_running")
        self.assertEqual(act_long_done.kind, "dispatch_short")
        self.assertEqual(st_long_done["short"]["attempt_count"], 1)

        # STEP 9: Short Video finishes and uploads, sends child notification with exact source_slug and source_sha
        sim_gh.dispatches.clear()
        sim_gh.short_items.append({
            **bound_short(120.0),
            "id": "short-oct15",
            "slug": new_post["slug"],
            "uploaded": True,
            "status": "uploaded",
            "youtube_id": "yt-short-oct15",
            "youtube_url": "https://youtube.com/shorts/yt-short-oct15",
            "technical_verified": True,
            "source": {"slug": new_post["slug"], "content_sha256": new_source["content_sha256"]},
            "youtube_verification": {
                "channel_id": core.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        })
        sim_gh.workflow_runs_history.append({
            "id": 9016,
            "name": "Kesher Daily Article Short V4",
            "workflow": v5.SHORT_WORKFLOW,
            "conclusion": "success",
            "event": "workflow_dispatch",
        })

        st_short_done, act_short_done = run_tick(
            dt.datetime(2026, 10, 15, 1, 20, tzinfo=core.ISRAEL_TZ),
            KESHER_CHILD_WORKFLOW="Kesher Daily Article Short V4",
            KESHER_CHILD_RUN_ID="9016",
            KESHER_CHILD_CONCLUSION="success",
            KESHER_CHILD_SOURCE_SLUG=new_post["slug"],
            KESHER_CHILD_SOURCE_SHA=new_source["content_sha256"],
        )
        self.assertTrue(st_short_done["short"]["verified"])
        self.assertEqual(st_short_done["status"], "complete")
        self.assertEqual(act_short_done.kind, "complete")

        # STEP 10: Deliverables contract verification
        deliv = st_short_done.get("deliverables") or {}
        self.assertEqual(deliv["article_url"], f"https://kesher.saharoni.com/blog/{new_post['slug']}")
        self.assertEqual(deliv["overview_youtube_url"], "https://youtu.be/yt-long-oct15")
        self.assertEqual(deliv["short_youtube_url"], "https://youtube.com/shorts/yt-short-oct15")

        # STEP 11: Generation Ledger Verification across all stages
        self.assertTrue(st_short_done["article"].get("reconciled_existing_article"))
        self.assertEqual(st_short_done["image"]["attempt_count"], 1)
        self.assertEqual(st_short_done["long_video"]["attempt_count"], 1)
        self.assertEqual(st_short_done["short"]["attempt_count"], 1)
        self.assertLessEqual(st_short_done["article"]["attempts"], 3)
        self.assertLessEqual(st_short_done["image"]["attempt_count"], 3)
        self.assertLessEqual(st_short_done["long_video"]["attempt_count"], 3)
        self.assertLessEqual(st_short_done["short"]["attempt_count"], 3)

    def test_failure_recovery_and_budget_enforcement_e2e(self) -> None:
        """Failure and recovery E2E: content repair, uncertain dispatch reconciliation, and 3-attempt caps."""
        initial_state = {
            "schema_version": 5,
            "cycle": "2026-10-15",
            "status": "waiting_for_article_window",
            "article": {"attempts": 0, "live": False},
            "image": {"attempt_count": 0},
            "long_video": {"attempt_count": 0},
            "short": {"attempt_count": 0},
            "history": [],
            "backlog": [],
        }
        sim_gh = IsolatedE2ESimGitHub(initial_state, [])
        sim_site = mock.Mock()
        sim_site.get.return_value = (404, "Not Found")

        def run_tick(now_dt: dt.datetime, **child_env: str):
            env = {
                "GITHUB_REPOSITORY": "yanivsa/kesher-website",
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_EVENT_NAME": "workflow_dispatch" if child_env else "schedule",
                "GITHUB_WORKFLOW_REF": "yanivsa/kesher-website/.github/workflows/kesher-content-controller.yml@refs/heads/main",
                "KESHER_TRIGGER_EVENT": "workflow_dispatch" if child_env else "schedule",
                "KESHER_PRE_CUTOVER_DAILY_AUTHORITY": "true",
            }
            env.update(child_env)
            with mock.patch.dict(os.environ, env, clear=False):
                ctrl = stabilized.StabilizedRuntimeV5Controller(sim_gh, sim_site, now=now_dt)
                return ctrl.tick()

        # 1. Content Preflight Failure (4 H3 sections) -> repair triggered without consuming image
        post_bad = make_valid_article("oct15-flawed-h3", "2026-10-15")
        post_bad["content"] = "".join(f"<h3>Section {i}</h3>" + " word" * 200 for i in range(1, 5))  # only 4 H3s!
        sim_gh.open_prs = [{
            "number": 1130,
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1130",
            "title": "Publish Kesher article: oct15-flawed-h3",
            "head": {"sha": "a" * 40, "ref": "same-article-branch"},
            "body": "https://jules.google.com/task/12345",
            "base": {"sha": "base_sha"},
            "post_data": post_bad,
        }]
        # Keep the production repair adapter real; isolate only its HTTP boundary.
        import io
        sim_gh.repo = "yanivsa/kesher-website"
        sim_gh.token = "isolated-test-token"
        repair_writes = []
        def repair_http(request, **kwargs):
            if request.method == "GET":
                return io.BytesIO(b"[]")
            repair_writes.append(request.full_url)
            return io.BytesIO(b"{}")
        with mock.patch.dict(os.environ, {"JULES_API_KEY": "isolated-test-key"}), mock.patch("urllib.request.urlopen", side_effect=repair_http):
            st_bad, act_bad = run_tick(dt.datetime(2026, 10, 15, 0, 40, tzinfo=core.ISRAEL_TZ))
        self.assertEqual(act_bad.kind, "request_text_repair")
        self.assertEqual(repair_writes, [
            "https://jules.googleapis.com/v1alpha/sessions/12345:sendMessage",
            "https://api.github.com/repos/yanivsa/kesher-website/issues/1130/comments",
        ])
        self.assertIn("at least five H3 sections", act_bad.reason)
        # Image attempts were NOT consumed:
        self.assertEqual(int(st_bad["image"].get("attempt_count") or 0), 0)

        # 2. Autonomous repair succeeds -> head advances, 5 H3s present
        post_repaired = copy.deepcopy(post_bad)
        post_repaired["content"] = "".join(f"<h3>Section {i}</h3>" + " word" * 160 for i in range(1, 6))
        sim_gh.open_prs[0]["head"]["sha"] = "head_repaired_sha"
        sim_gh.open_prs[0]["post_data"] = post_repaired
        sim_gh.pr_comments[1130] = [
            {"body": "<!-- kesher-article-repair attempt=1 head=head_bad_sha -->"}
        ]
        st_rep, act_rep = run_tick(dt.datetime(2026, 10, 15, 0, 45, tzinfo=core.ISRAEL_TZ))
        self.assertEqual(act_rep.kind, "dispatch_image")
        self.assertEqual(st_rep["image"]["attempt_count"], 1)

        # 3. Uncertain Dispatch Reconciliation: simulate lost HTTP dispatch response
        # State records uncertain pending dispatch; second POST must be suppressed
        ctrl = stabilized.StabilizedRuntimeV5Controller(sim_gh, sim_site, now=dt.datetime(2026, 10, 15, 1, 0, tzinfo=core.ISRAEL_TZ))
        ctrl._active_state_ref = {
            "cycle": "2026-10-15",
            "status": "article_deploying",
            "pending_dispatches": {
                core.DEPLOY_WORKFLOW: {
                    "workflow": core.DEPLOY_WORKFLOW,
                    "cycle": "2026-10-15",
                    "inputs": {},
                    "intent_at": "2026-10-15T01:00:00+00:00",
                    "status": "uncertain",
                }
            }
        }
        raw_dispatch = mock.MagicMock()
        with self.assertRaises(stabilized._DuplicateDispatchSuppressed) as ctx:
            ctrl._guarded_dispatch(ctrl._active_state_ref, core.DEPLOY_WORKFLOW, {}, raw_dispatch)
        raw_dispatch.assert_not_called()
        self.assertIn("uncertain", ctx.exception.reason)

        # 4. Strict Cap Enforcement: 4th generation attempt forbidden across all stages
        test_state = {
            "cycle": "2026-10-15",
            "status": "running",
            "article": {"attempts": 3},
            "image": {"attempt_count": 3},
            "long_video": {"attempt_count": 3},
            "short": {"attempt_count": 3},
            "pending_dispatches": {},
        }
        ctrl._active_state_ref = test_state
        # Article cap
        with self.assertRaises(core.ControllerError) as ctx_art:
            ctrl._guarded_dispatch(test_state, core.ARTICLE_WORKFLOW, {"slot": "2026-10-15"}, raw_dispatch)
        self.assertIn("ARTICLE_ATTEMPTS_EXHAUSTED", str(ctx_art.exception))

        # Image cap
        with self.assertRaises(core.ControllerError) as ctx_img:
            ctrl._guarded_dispatch(test_state, v5.v3.IMAGE_WORKFLOW, {"pr_number": "1130"}, raw_dispatch)
        self.assertIn("IMAGE_ATTEMPTS_EXHAUSTED", str(ctx_img.exception))

        # Long cap
        with self.assertRaises(core.ControllerError) as ctx_long:
            ctrl._guarded_dispatch(test_state, v5.LONG_VIDEO_WORKFLOW, {"operation": "full"}, raw_dispatch)
        self.assertIn("VIDEO_ATTEMPTS_EXHAUSTED", str(ctx_long.exception))

        # Short cap
        with self.assertRaises(core.ControllerError) as ctx_short:
            ctrl._guarded_dispatch(test_state, v5.SHORT_WORKFLOW, {"operation": "derive", "derive_slug": "slug"}, raw_dispatch)
        self.assertIn("SHORT_ATTEMPTS_EXHAUSTED", str(ctx_short.exception))


if __name__ == "__main__":
    unittest.main()

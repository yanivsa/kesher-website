from __future__ import annotations

import copy
import datetime as dt
import json
import os
from pathlib import Path
import unittest
from unittest import mock

import yaml

from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_stabilized as stabilized
from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_content_controller_v5_runtime as v5_runtime
from scripts import kesher_daily_pipeline as pipeline
from scripts.kesher_runtime import authority_topology, bridge_admission, legacy_retirement, sync_authority_policy, workflow_governance
from scripts.kesher_runtime.state import StateInvalid

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"


class PreCutoverDailyAuthorityTests(unittest.TestCase):
    WORKER_WORKFLOWS = (
        "kesher-article-generation.yml",
        "normalize-article-pr.yml",
        "kesher-article-image.yml",
        "auto-merge-article-prs.yml",
        "deploy.yml",
        "kesher-daily-video.yml",
        "kesher-short-v4.yml",
    )

    def _controller_env(self, event_name: str = "schedule") -> dict[str, str]:
        return {
            "GITHUB_REPOSITORY": "yanivsa/kesher-website",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": event_name,
            "GITHUB_WORKFLOW_REF": "yanivsa/kesher-website/.github/workflows/kesher-content-controller.yml@refs/heads/main",
            "KESHER_PRE_CUTOVER_DAILY_AUTHORITY": "true",
        }

    # 9.A. Pre-cutover controller authority
    def test_controller_admitted_across_all_supported_events_on_schema5_state(self) -> None:
        state_v5 = {"schema_version": 5, "cycle": "2026-10-11"}
        for event in ("schedule", "workflow_run", "push", "workflow_dispatch"):
            with self.subTest(event=event):
                env = self._controller_env(event)
                bridge_admission.require_invocation(env, controller=True)
                bridge_admission.require_bridge(state_v5)
                with mock.patch.dict(os.environ, env, clear=True):
                    legacy_retirement.validate_legacy_read(state_v5)
                    legacy_retirement.retired_entrypoint(state_v5)
                with mock.patch.dict(os.environ, env, clear=True), \
                     mock.patch.object(bridge_admission, "GitHub"), \
                     mock.patch.object(bridge_admission, "GitHubHandover") as handover:
                    handover.return_value.read_snapshot.return_value.state = state_v5
                    self.assertEqual(bridge_admission.main(["--controller"]), 0)

    def test_other_workflows_or_non_main_refs_fail_closed_under_pre_cutover_flag(self) -> None:
        state_v5 = {"schema_version": 5, "cycle": "2026-10-11"}
        base = self._controller_env("schedule")
        invalid_changes = (
            {"GITHUB_WORKFLOW_REF": "yanivsa/kesher-website/.github/workflows/kesher-master-supervisor.yml@refs/heads/main"},
            {"GITHUB_WORKFLOW_REF": "yanivsa/kesher-website/.github/workflows/kesher-daily-video.yml@refs/heads/main"},
            {"GITHUB_WORKFLOW_REF": "yanivsa/kesher-website/.github/workflows/kesher-content-controller.yml@refs/heads/feature"},
            {"GITHUB_REPOSITORY": "other/repo"},
            {"GITHUB_REF": "refs/heads/feature"},
            {"GITHUB_EVENT_NAME": "pull_request"},
        )
        for change in invalid_changes:
            with self.subTest(change=change):
                bad_env = base | change
                with self.assertRaises(StateInvalid):
                    bridge_admission.require_invocation(bad_env, controller=True)
                with mock.patch.dict(os.environ, bad_env, clear=True):
                    with self.assertRaises(StateInvalid):
                        legacy_retirement.retired_entrypoint(state_v5)

    def test_schema6_or_handover_markers_automatically_invalidate_pre_cutover_authority(self) -> None:
        env = self._controller_env("schedule")
        for invalid_state in (
            {"schema_version": 6},
            {"schema_version": 5, "handover": {}},
            {"schema_version": 5, "github_exclusion": {}},
            {"schema_version": 4},
        ):
            with self.subTest(state=invalid_state), mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaises(StateInvalid):
                    legacy_retirement.validate_legacy_read(invalid_state)
                with self.assertRaises(StateInvalid):
                    legacy_retirement.retired_entrypoint(invalid_state)
                with mock.patch.object(bridge_admission, "GitHub"), \
                     mock.patch.object(bridge_admission, "GitHubHandover") as handover:
                    handover.return_value.read_snapshot.return_value.state = invalid_state
                    self.assertEqual(bridge_admission.main(["--controller"]), 1)

    # 9.B. Worker dispatch-only contract
    def test_all_seven_workers_are_workflow_dispatch_only_on_main_and_fail_closed_on_schema6(self) -> None:
        expected_if = "${{ github.event_name == 'workflow_dispatch' && github.repository == 'yanivsa/kesher-website' && github.ref == 'refs/heads/main' }}"
        for name in self.WORKER_WORKFLOWS:
            with self.subTest(workflow=name):
                path = WORKFLOWS_DIR / name
                text = path.read_text(encoding="utf-8")
                data = yaml.safe_load(text)
                events = data.get("on", data.get(True))
                self.assertEqual(set(events), {"workflow_dispatch"})
                for forbidden in ("schedule", "push", "pull_request", "pull_request_target", "workflow_run"):
                    self.assertNotIn(forbidden, events)
                for job in data["jobs"].values():
                    self.assertEqual(job.get("if"), expected_if)
                self.assertIn("scripts.kesher_runtime.bridge_admission", text)

                worker_env = {
                    "GITHUB_REPOSITORY": "yanivsa/kesher-website",
                    "GITHUB_REF": "refs/heads/main",
                    "GITHUB_EVENT_NAME": "workflow_dispatch",
                    "GITHUB_WORKFLOW_REF": f"yanivsa/kesher-website/.github/workflows/{name}@refs/heads/main",
                }
                bridge_admission.require_invocation(worker_env)
                with mock.patch.dict(os.environ, worker_env, clear=True), \
                     mock.patch.object(bridge_admission, "GitHub"), \
                     mock.patch.object(bridge_admission, "GitHubHandover") as handover:
                    handover.return_value.read_snapshot.return_value.state = {"schema_version": 6}
                    self.assertEqual(bridge_admission.main([]), 1)

    # 9.C. Single scheduler policy
    def test_only_content_controller_is_active_kesher_production_scheduler(self) -> None:
        controller_text = (WORKFLOWS_DIR / "kesher-content-controller.yml").read_text(encoding="utf-8")
        controller_data = yaml.safe_load(controller_text)
        events = controller_data.get("on", controller_data.get(True))
        self.assertEqual(set(events), {"schedule", "workflow_run", "push", "workflow_dispatch"})
        self.assertEqual(
            events["schedule"],
            [{"cron": "3,8,13,18,23,28,33,38,43,48,53,58 * * * *"}],
        )
        self.assertEqual(
            controller_data["concurrency"],
            {"group": "kesher-content-controller", "cancel-in-progress": False},
        )
        self.assertNotIn("KESHER_MANUAL_EMERGENCY_BRIDGE", controller_text)
        self.assertIn('KESHER_PRE_CUTOVER_DAILY_AUTHORITY: "true"', controller_text)

        for wf_path in sorted(WORKFLOWS_DIR.glob("kesher-*.yml")):
            if wf_path.name == "kesher-content-controller.yml":
                continue
            wf_data = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
            wf_events = wf_data.get("on", wf_data.get(True))
            if isinstance(wf_events, dict) and "schedule" in wf_events:
                for job in wf_data.get("jobs", {}).values():
                    self.assertEqual(job.get("if"), "${{ github.repository == '__KESHER_RETIRED__' }}")

    # 9.D. Catalog unification (posts.json + postsRecent.json)
    def test_unified_catalog_finds_articles_in_posts_recent_and_deduplicates(self) -> None:
        posts_historical = json.loads((ROOT / "src" / "data" / "posts.json").read_text(encoding="utf-8"))
        posts_recent = json.loads((ROOT / "src" / "data" / "postsRecent.json").read_text(encoding="utf-8"))

        class RepoGitHub:
            api = "https://api.github.test/repos/yanivsa/kesher-website"

            def __init__(self) -> None:
                self.dispatches: list[tuple[str, dict]] = []
                self.saved_state: dict | None = None

            def request(self, method: str, path: str, body=None, allow_404: bool = False):
                if method == "GET" and "/actions/artifacts" in path:
                    return {"artifacts": []}
                if method == "POST" and "/dispatches" in path:
                    wf = path.split("/actions/workflows/")[1].split("/dispatches")[0]
                    self.dispatches.append((wf, (body or {}).get("inputs") or {}))
                    return {}
                return {}

            def contents_json(self, path: str, ref: str = "main"):
                if path == "src/data/posts.json":
                    return posts_historical
                if path == "src/data/postsRecent.json":
                    return posts_recent
                raise AssertionError(path)

            def load_controller_state(self):
                return {"schema_version": 5, "cycle": "2026-10-10", "status": "article_needed"}

            def save_controller_state(self, state):
                self.saved_state = copy.deepcopy(state)

            def open_article_prs(self, slot=None):
                return []

            def active_workflow_run(self, workflow, production_only=False):
                return None

            def newest_video_state(self):
                return {"version": 1, "items": []}

            def newest_short_state(self):
                return {"version": 1, "items": []}

            def dispatch(self, workflow: str, inputs: dict | None = None):
                self.dispatches.append((workflow, inputs or {}))

        gh = RepoGitHub()
        site = mock.Mock()
        site.get.return_value = (
            200,
            "<html>איך מרגיעים ילד שחוזר מבית הספר ומתפרץ בבית? הילד מתווכח על כל בקשה? כך מציבים גבול בלי להיגרר למאבק כוח</html>",
        )

        # Instantiate StabilizedRuntimeV5Controller directly without mutating global v5.V5Controller
        for cycle_date, expected_slug in (
            (dt.date(2026, 10, 6), "child-meltdown-after-school"),
            (dt.date(2026, 10, 10), "child-argues-every-request-boundaries"),
        ):
            with self.subTest(cycle=cycle_date.isoformat()):
                ctrl = stabilized.StabilizedRuntimeV5Controller(
                    gh,
                    site,
                    now=dt.datetime(cycle_date.year, cycle_date.month, cycle_date.day, 10, 0, tzinfo=core.ISRAEL_TZ),
                )
                found = ctrl.posts_for_cycle(cycle_date)
                self.assertEqual(len(found), 1)
                self.assertEqual(core.canonical_slug(found[0]), expected_slug)
                source = ctrl._article_source()
                self.assertIsNotNone(source)
                self.assertEqual(source["slug"], expected_slug)
                self.assertEqual(len(source["content_sha256"]), 64)

        # Verify deduplication when an article appears in both files
        dup = copy.deepcopy(posts_recent[0])
        merged = core.merge_catalog_posts([dup], [dup])
        self.assertEqual(len(merged), 1)

        # Verify controller does NOT dispatch duplicate article generation when Oct 10 article is in postsRecent.json
        ctrl_oct10 = stabilized.StabilizedRuntimeV5Controller(
            gh,
            site,
            now=dt.datetime(2026, 10, 10, 12, 0, tzinfo=core.ISRAEL_TZ),
        )
        with mock.patch.dict(os.environ, self._controller_env("schedule"), clear=False):
            _, action = ctrl_oct10.tick()
        article_dispatches = [w for w, _ in gh.dispatches if w == core.ARTICLE_WORKFLOW]
        self.assertEqual(article_dispatches, [])
        self.assertNotEqual(action.kind, "dispatch_article")

    # 9.E. 2026-10-04 ambiguous backlog isolation & 9.F. Current-cycle priority
    def test_ambiguous_2026_10_04_backlog_is_quarantined_and_unambiguous_backlog_advances(self) -> None:
        posts_historical = json.loads((ROOT / "src" / "data" / "posts.json").read_text(encoding="utf-8"))
        posts_recent = json.loads((ROOT / "src" / "data" / "postsRecent.json").read_text(encoding="utf-8"))

        oct6_post = next(p for p in posts_recent if p.get("date") == "2026-10-06")
        oct6_source = v5.article_source_identity(oct6_post)
        today_post = copy.deepcopy(oct6_post)
        today_post.update(
            {
                "id": "today-2026-10-11-article",
                "slug": "today-2026-10-11-article",
                "date": "2026-10-11",
                "controllerManaged": True,
            }
        )
        today_source = v5.article_source_identity(today_post)

        initial_state = {
            "schema_version": 5,
            "cycle": "2026-10-11",
            "status": "complete",
            "article": {
                "status": "complete",
                "live": True,
                "slug": today_source["slug"],
                "url": f"{core.SITE_URL}/blog/{today_source['slug']}",
                "quality_status": "passed",
                "quality_content_sha256": today_source["content_sha256"],
            },
            "image": {"status": "complete"},
            "long_video": {
                "status": "complete",
                "verified": True,
                "item_id": "long-today",
                "youtube_id": "yt-long-today",
                "youtube_url": "https://youtu.be/yt-long-today",
                "technical_verified": True,
                "visual_pipeline": "remotion",
                "codec": "h264",
                "width": 1920,
                "height": 1080,
                "duration": 120.0,
                "content_duration_seconds": 116.0,
                "signature_duration_seconds": 4.0,
                "signature_fullscreen": True,
                "signature_asset_sha256": "a" * 64,
            },
            "short": {
                "status": "complete",
                "verified": True,
                "item_id": "short-today",
                "youtube_id": "yt-short-today",
                "youtube_url": "https://youtu.be/yt-short-today",
            },
            "backlog": [
                {"cycle": "2026-10-04", "status": "article_live"},
                {"cycle": "2026-10-06", "status": "article_live"},
            ],
        }

        class BacklogGitHub:
            def __init__(self) -> None:
                self.state = copy.deepcopy(initial_state)
                self.dispatches: list[tuple[str, dict]] = []

            def contents_json(self, path: str, ref: str = "main"):
                if path == "src/data/posts.json":
                    return posts_historical + [today_post]
                if path == "src/data/postsRecent.json":
                    return posts_recent
                raise AssertionError(path)

            def load_controller_state(self):
                return copy.deepcopy(self.state)

            def save_controller_state(self, state):
                self.state = copy.deepcopy(state)

            def open_article_prs(self, slot=None):
                return []

            def active_workflow_run(self, workflow, production_only=False):
                return None

            def newest_video_state(self):
                return {
                    "version": 1,
                    "items": [
                        {
                            "id": "long-today",
                            "type": "video_overview",
                            "status": "uploaded",
                            "uploaded": True,
                            "youtube_id": "yt-long-today",
                            "youtube_url": "https://youtu.be/yt-long-today",
                            "technical_verified": True,
                            "visual_pipeline": "remotion",
                            "media": {"codec": "h264", "width": 1920, "height": 1080, "duration": 120.0},
                            "content_duration_seconds": 116.0,
                            "signature_duration_seconds": 4.0,
                            "signature_fullscreen": True,
                            "signature_asset_sha256": "a" * 64,
                            "source": {"slug": today_source["slug"], "content_sha256": today_source["content_sha256"]},
                            "youtube_verification": {
                                "channel_id": core.YOUTUBE_CHANNEL_ID,
                                "privacy_status": "public",
                                "processing_status": "succeeded",
                            },
                        }
                    ],
                }

            def newest_short_state(self):
                return {
                    "version": 1,
                    "items": [
                        {
                            "id": "short-today",
                            "type": "article_short",
                            "status": "uploaded",
                            "uploaded": True,
                            "youtube_id": "yt-short-today",
                            "youtube_url": "https://youtu.be/yt-short-today",
                            "technical_verified": True,
                            "visual_pipeline": "remotion",
                            "media": {"codec": "h264", "width": 1080, "height": 1920, "duration": 45.0},
                            "signature_duration_seconds": 4.0,
                            "signature_fullscreen": True,
                            "signature_asset_sha256": "b" * 64,
                            "adopted_from_long_item_id": "long-today",
                            "source": {"slug": today_source["slug"], "content_sha256": today_source["content_sha256"]},
                            "youtube_verification": {
                                "channel_id": core.YOUTUBE_CHANNEL_ID,
                                "privacy_status": "public",
                                "processing_status": "succeeded",
                            },
                        }
                    ],
                }

            def dispatch(self, workflow: str, inputs: dict | None = None):
                self.dispatches.append((workflow, inputs or {}))

        gh = BacklogGitHub()
        site = mock.Mock()
        site.get.side_effect = lambda url: (
            (200, f"<html>{today_post['title']} {oct6_post['title']}</html>")
        )

        # Instantiate StabilizedRuntimeV5Controller directly without mutating global v5.V5Controller
        ctrl = stabilized.StabilizedRuntimeV5Controller(
            gh,
            site,
            now=dt.datetime(2026, 10, 11, 14, 0, tzinfo=core.ISRAEL_TZ),
        )
        # Put 2026-10-04 first in ordered_recoverable_backlog by testing it directly and alongside 2026-10-06
        with mock.patch.dict(os.environ, self._controller_env("schedule"), clear=False), \
             mock.patch.object(v5_runtime.delivery_guard, "delivery_contract", return_value=(True, {})), \
             mock.patch.object(
                 v5_runtime,
                 "ordered_recoverable_backlog",
                 side_effect=lambda rows: [r for r in rows if not r.get("quarantined")],
             ):
            final_state, action = ctrl.tick()

        backlog_by_cycle = {row["cycle"]: row for row in final_state["backlog"]}
        self.assertEqual(backlog_by_cycle["2026-10-04"]["status"], "quarantined_ambiguous_identity")
        self.assertTrue(backlog_by_cycle["2026-10-04"].get("quarantined"))
        self.assertIn("BACKLOG_ARTICLE_IDENTITY_AMBIGUOUS", backlog_by_cycle["2026-10-04"].get("last_error", ""))

        # And unambiguous 2026-10-06 backlog item advanced without crashing!
        self.assertEqual(action.kind, "dispatch_backlog_long_video")
        self.assertEqual(action.inputs.get("target_slug"), oct6_source["slug"])
        self.assertEqual(gh.dispatches, [(v5.LONG_VIDEO_WORKFLOW, action.inputs)])

    def test_current_cycle_in_progress_takes_priority_over_backlog(self) -> None:
        in_progress_state = {
            "schema_version": 5,
            "cycle": "2026-10-11",
            "status": "article_pr_open",
            "article": {"status": "pr_open"},
            "backlog": [{"cycle": "2026-10-06", "status": "article_live"}],
        }
        self.assertFalse(v5_runtime.backlog_may_run(in_progress_state, current_cycle_complete=False))

    # 9.G. No duplicate provider/YouTube side effects
    def test_existing_youtube_id_verifies_without_second_insert(self) -> None:
        source = pipeline.source_metadata(
            {
                "id": "no-dup-upload",
                "slug": "no-dup-upload",
                "title": "איך בונים אמון מחדש?",
                "date": "2026-10-10",
                "category": "זוגיות",
                "excerpt": "תקציר בעברית.",
                "content": "<p>תוכן מלא בעברית.</p>",
            }
        )
        item = pipeline.new_item(source)
        item.update(
            {
                "status": "uploading",
                "technical_verified": True,
                "youtube_id": "existing-yt-id-123",
                "final_mp4": "final.mp4",
                "final_sha256": "c" * 64,
            }
        )
        with mock.patch.object(pipeline, "load_state", return_value={"version": 1, "items": [item]}), \
             mock.patch.object(pipeline, "save_state"), \
             mock.patch.object(pipeline, "youtube_access_token", return_value="token"), \
             mock.patch.object(pipeline, "verify_authenticated_channel"), \
             mock.patch.object(pipeline, "start_resumable_upload") as start_upload, \
             mock.patch.object(pipeline, "upload_bytes") as upload_bytes, \
             mock.patch.object(
                 pipeline,
                 "verify_public_upload",
                 return_value={
                     "channel_id": core.YOUTUBE_CHANNEL_ID,
                     "privacy_status": "public",
                     "processing_status": "succeeded",
                 },
             ) as verify_upload:
            with mock.patch.dict(os.environ, {"TARGET_ITEM_ID": item["id"]}, clear=False):
                rc = pipeline.upload_only(item_id=item["id"])
        self.assertEqual(rc, 0)
        start_upload.assert_not_called()
        upload_bytes.assert_not_called()
        verify_upload.assert_called_once()

    # 9.H. Authority policy sync & 9.I. Schema-6 preservation
    def test_authority_policy_sync_and_workflow_governance_and_schema6_preservation(self) -> None:
        changes = sync_authority_policy.synchronize(ROOT, update=False)
        self.assertEqual(changes, [])

        failures = workflow_governance.check(ROOT)
        self.assertEqual(failures, [])

        # Schema-6 shadow and cutover workflows remain intact
        self.assertTrue((WORKFLOWS_DIR / "kesher-content-controller-v6.yml").is_file())
        self.assertTrue((WORKFLOWS_DIR / "kesher-production-cutover.yml").is_file())
        rules = authority_topology.policy(ROOT)
        self.assertEqual(
            rules["workflows"][".github/workflows/kesher-production-cutover.yml"]["role"],
            "handover",
        )
        self.assertEqual(
            rules["workflows"][".github/workflows/kesher-content-controller-v6.yml"]["role"],
            "diagnostic",
        )


if __name__ == "__main__":
    unittest.main()

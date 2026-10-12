from __future__ import annotations

import base64
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest import mock
import urllib.parse

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
            [{"cron": "4,9,14,19,24,29,34,39,44,49,54,59 * * * *"}],
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

    # Requirement 1: Fail-closed unified catalog reading (posts.json + postsRecent.json)
    def test_posts_recent_missing_or_invalid_or_duplicate_fails_closed_without_dispatching_article(self) -> None:
        posts_historical = json.loads((ROOT / "src" / "data" / "posts.json").read_text(encoding="utf-8"))
        posts_recent = json.loads((ROOT / "src" / "data" / "postsRecent.json").read_text(encoding="utf-8"))

        for case_name, recent_behavior in (
            ("missing_404", core.ControllerError("GITHUB_HTTP_404: postsRecent.json not found")),
            ("invalid_non_list", {"bad": "object"}),
            ("entry_missing_slug", [{"title": "no slug", "date": "2026-10-12"}]),
            ("entry_invalid_date", [{"id": "bad-date", "slug": "bad-date", "date": "not-a-date"}]),
            ("duplicate_slug_across_catalogs", [copy.deepcopy(posts_historical[0])]),
        ):
            with self.subTest(case=case_name):
                dispatches: list[tuple[str, dict]] = []
                saved_states: list[dict] = []

                class BrokenCatalogGitHub:
                    def contents_json(self, path: str, ref: str = "main"):
                        if path == "src/data/posts.json":
                            return copy.deepcopy(posts_historical)
                        if path == "src/data/postsRecent.json":
                            if isinstance(recent_behavior, Exception):
                                raise recent_behavior
                            return copy.deepcopy(recent_behavior)
                        raise AssertionError(path)

                    def load_controller_state(self):
                        return {"schema_version": 5, "cycle": "2026-10-12", "status": "article_needed"}

                    def save_controller_state(self, state):
                        saved_states.append(copy.deepcopy(state))

                    def open_article_prs(self, slot=None):
                        return []

                    def active_workflow_run(self, workflow, production_only=False):
                        return None

                    def dispatch(self, workflow: str, inputs: dict | None = None):
                        dispatches.append((workflow, inputs or {}))

                gh = BrokenCatalogGitHub()
                with self.assertRaisesRegex(core.ControllerError, "ARTICLE_PUBLICATION_CATALOG_UNAVAILABLE"):
                    core.posts_on_main(gh, "main")

                site = mock.Mock()
                ctrl = stabilized.StabilizedRuntimeV5Controller(
                    gh,
                    site,
                    now=dt.datetime(2026, 10, 12, 10, 0, tzinfo=core.ISRAEL_TZ),
                )
                state, action = ctrl.tick()
                self.assertEqual(action.kind, "blocked")
                self.assertEqual(state["status"], "blocked")
                self.assertEqual(state["last_error"]["code"], "ARTICLE_PUBLICATION_CATALOG_UNAVAILABLE")
                self.assertEqual(dispatches, [])
                self.assertTrue(saved_states)

        # Valid unified catalog merges both files without silent loss
        class ValidCatalogGitHub:
            def contents_json(self, path: str, ref: str = "main"):
                if path == "src/data/posts.json":
                    return copy.deepcopy(posts_historical)
                if path == "src/data/postsRecent.json":
                    return copy.deepcopy(posts_recent)
                raise AssertionError(path)

        merged = core.posts_on_main(ValidCatalogGitHub(), "main")
        self.assertEqual(len(merged), len(posts_historical) + len(posts_recent))

    # Requirement 2: Do NOT globally rewrite controllerManaged: false; use explicit immutable allowlist
    def test_controller_managed_false_is_preserved_and_only_exact_reviewed_identities_adopt(self) -> None:
        posts_historical = json.loads((ROOT / "src" / "data" / "posts.json").read_text(encoding="utf-8"))
        posts_recent = json.loads((ROOT / "src" / "data" / "postsRecent.json").read_text(encoding="utf-8"))

        # 2.A: Arbitrary future post in postsRecent.json with controllerManaged: false on a date with no other post
        future_manual_post = copy.deepcopy(posts_recent[0])
        future_manual_post.update(
            {
                "id": "manual-editorial-2026-10-15",
                "slug": "manual-editorial-2026-10-15",
                "title": "מאמר מערכת ידני שלא מנוהל על ידי הבקר היומי",
                "date": "2026-10-15",
                "controllerManaged": False,
            }
        )
        merged = core.merge_catalog_posts(posts_historical, [*posts_recent, future_manual_post])
        merged_future = next(p for p in merged if core.canonical_slug(p) == "manual-editorial-2026-10-15")
        self.assertIs(merged_future.get("controllerManaged"), False)
        self.assertFalse(core.is_controller_adoptable_post(merged_future))
        self.assertEqual(core.today_articles(merged, dt.date(2026, 10, 15)), [])

        # Confirm daily controller still dispatches article generation on 2026-10-15 despite manual post
        class FutureGitHub:
            api = "https://api.github.test/repos/yanivsa/kesher-website"

            def __init__(self) -> None:
                self.dispatches: list[tuple[str, dict]] = []
                self.saved_state: dict | None = None

            def request(self, method: str, path: str, body=None, allow_404: bool = False):
                if method == "GET" and "/actions/artifacts" in path:
                    return {"artifacts": []}
                if method == "POST" and "/dispatches" in path:
                    wf = urllib.parse.unquote(path.split("/actions/workflows/")[1].split("/dispatches")[0])
                    self.dispatches.append((wf, (body or {}).get("inputs") or {}))
                    return {}
                return {}

            def contents_json(self, path: str, ref: str = "main"):
                if path == "src/data/posts.json":
                    return copy.deepcopy(posts_historical)
                if path == "src/data/postsRecent.json":
                    return [*copy.deepcopy(posts_recent), copy.deepcopy(future_manual_post)]
                raise AssertionError(path)

            def load_controller_state(self):
                return {"schema_version": 5, "cycle": "2026-10-15", "status": "article_needed"}

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

        future_gh = FutureGitHub()
        future_ctrl = stabilized.StabilizedRuntimeV5Controller(
            future_gh,
            mock.Mock(),
            now=dt.datetime(2026, 10, 15, 9, 0, tzinfo=core.ISRAEL_TZ),
        )
        _, future_action = future_ctrl.tick()
        self.assertEqual(future_action.kind, "dispatch_article")
        self.assertEqual(
            future_gh.dispatches,
            [(core.ARTICLE_WORKFLOW, {"slot": "2026-10-15"})],
        )

        # 2.B: Exact reviewed post-freeze single-article recovery targets (2026-10-06, 2026-10-09, 2026-10-10, 2026-10-12)
        expected_reviewed = [
            (
                dt.date(2026, 10, 6),
                "child-meltdown-after-school",
                "4f5b0dfa23a56b7088fd332cc3f538a6d0bca9b1e7c09b601d43ec6e8d464e9a",
            ),
            (
                dt.date(2026, 10, 9),
                "how-to-repair-after-couple-fight",
                "317b282607c03c6183ca4d7cd1791c2aa4c2f9bb6b6f5832e0227c413ef5121a",
            ),
            (
                dt.date(2026, 10, 10),
                "child-argues-every-request-boundaries",
                "e0594f772f3f11baacc0ae5c53b7ef9ce9f88f871ee3b6e8c8f67b024b8b8bbc",
            ),
            (
                dt.date(2026, 10, 12),
                "relocation-loneliness-accompanying-partner",
                "93bd8eb7d057faf9ede979e86c891504604c80766287f170b011f05065bd326c",
            ),
        ]
        for day, slug, sha in expected_reviewed:
            matches = core.today_articles(merged, day)
            self.assertEqual(len(matches), 1)
            self.assertEqual(core.canonical_slug(matches[0]), slug)
            self.assertIs(matches[0].get("controllerManaged"), False)
            self.assertEqual(v5.article_source_identity(matches[0])["content_sha256"], sha)
            # Tampered content on the same date/slug is rejected
            tampered = copy.deepcopy(matches[0])
            tampered["content"] = "<p>תוכן שונה לחלוטין עם האש אחר</p>"
            self.assertFalse(core.is_controller_adoptable_post(tampered))

        # 2.C: 2026-10-05 resolves uniquely to child-refuses-homework and excludes 20-second-hug-relationship-stress
        oct5_matches = core.today_articles(merged, dt.date(2026, 10, 5))
        self.assertEqual(len(oct5_matches), 1)
        self.assertEqual(core.canonical_slug(oct5_matches[0]), "child-refuses-homework")
        self.assertEqual(
            v5.article_source_identity(oct5_matches[0])["content_sha256"],
            "56cfeeb02176cfe4fddfb7cc7ddd336c5d85758a5f2d577f93331ce525a8c77b",
        )

        # 2.D: Multi-article ambiguous dates (2026-10-04, 2026-10-07, 2026-10-08) quarantine cleanly
        oct4_second = copy.deepcopy(posts_recent[0])
        oct4_second.update(
            {
                "id": "setting-healthy-boundaries-parents",
                "slug": "setting-healthy-boundaries-parents",
                "date": "2026-10-04",
                "controllerManaged": True,
            }
        )
        oct7_first = copy.deepcopy(posts_recent[0])
        oct7_first.update(
            {
                "id": "couple-communication-without-fighting",
                "slug": "couple-communication-without-fighting",
                "date": "2026-10-07",
                "controllerManaged": True,
            }
        )
        oct7_second = copy.deepcopy(posts_recent[0])
        oct7_second.update(
            {
                "id": "building-self-confidence-in-children",
                "slug": "building-self-confidence-in-children",
                "date": "2026-10-07",
                "controllerManaged": False,
            }
        )

        class AmbiguousBacklogGitHub:
            def contents_json(self, path: str, ref: str = "main"):
                if path == "src/data/posts.json":
                    return [*copy.deepcopy(posts_historical), oct4_second, oct7_first, oct7_second]
                if path == "src/data/postsRecent.json":
                    return copy.deepcopy(posts_recent)
                raise AssertionError(path)

        amb_ctrl = object.__new__(stabilized.StabilizedRuntimeV5Controller)
        amb_ctrl.github = AmbiguousBacklogGitHub()
        amb_ctrl.site = mock.Mock(return_value=(200, "<html></html>"))
        amb_state = {
            "status": "waiting_for_article_window",
            "backlog": [
                {"cycle": "2026-10-04", "status": "article_live"},
                {"cycle": "2026-10-07", "status": "article_live"},
                {"cycle": "2026-10-08", "status": "article_live"},
            ],
            "history": [],
        }
        row, source = amb_ctrl._published_backlog_source(amb_state)
        self.assertIsNone(row)
        self.assertIsNone(source)
        by_cycle = {r["cycle"]: r for r in amb_state["backlog"]}
        for amb_cycle in ("2026-10-04", "2026-10-07", "2026-10-08"):
            self.assertEqual(by_cycle[amb_cycle]["status"], "quarantined_ambiguous_identity")
            self.assertTrue(by_cycle[amb_cycle].get("quarantined"))
            self.assertIn("BACKLOG_ARTICLE_IDENTITY_AMBIGUOUS", by_cycle[amb_cycle].get("last_error", ""))

    # Requirement 3: Exact-target article auto-merge (no open-PR list scan)
    def test_exact_target_article_auto_merge_processes_only_authoritative_pr(self) -> None:
        auto_merge_wf = (WORKFLOWS_DIR / "auto-merge-article-prs.yml").read_text(encoding="utf-8")
        self.assertNotIn("pulls?state=open", auto_merge_wf)
        wf_data = yaml.safe_load(auto_merge_wf)
        wf_on = wf_data.get("on", wf_data.get(True))
        inputs_cfg = wf_on["workflow_dispatch"]["inputs"]
        self.assertTrue(inputs_cfg["pr_number"]["required"])
        self.assertIn("slot", inputs_cfg)

        # Verify controller _dispatch_auto_merge_v4 passes exact pr_number and slot
        dispatched: list[tuple[str, dict]] = []

        class MergeDispatchGitHub:
            api = "https://api.github.test/repos/yanivsa/kesher-website"

            def active_workflow_run(self, workflow, production_only=False):
                return None

            def request(self, method: str, url: str, body=None, **kwargs):
                wf = urllib.parse.unquote(url.split("/actions/workflows/")[1].split("/dispatches")[0])
                dispatched.append((wf, (body or {}).get("inputs") or {}))
                return {}

        ctrl = object.__new__(stabilized.StabilizedRuntimeV5Controller)
        ctrl.github = MergeDispatchGitHub()
        state = {
            "cycle": "2026-10-12",
            "article": {"pr_number": 102, "normalization_slot": "2026-10-12"},
            "image": {"status": "complete", "attempt_count": 1},
        }
        ctrl._dispatch_auto_merge_v4(state)
        self.assertEqual(
            dispatched,
            [("auto-merge-article-prs.yml", {"pr_number": "102", "slot": "2026-10-12"})],
        )

        # Load article-pr-controller-v3.py and test with:
        # - #997 historical draft PR
        # - #101 stale open article PR
        # - #102 authoritative new article PR
        # - #103 competing duplicate open article PR
        spec = importlib.util.spec_from_file_location(
            "test_article_pr_controller_v3_exact",
            ROOT / ".github" / "scripts" / "article-pr-controller-v3.py",
        )
        assert spec and spec.loader
        pr_ctrl_v3 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pr_ctrl_v3)

        prs_by_num = {
            997: {
                "number": 997,
                "state": "open",
                "draft": True,
                "title": "Publish Kesher article: historical-draft-997",
                "base": {"ref": "main", "sha": "base997"},
                "head": {"ref": "article-997", "sha": "head997", "repo": {"full_name": "yanivsa/kesher-website"}},
            },
            101: {
                "number": 101,
                "state": "open",
                "draft": False,
                "title": "Publish Kesher article: stale-2026-10-04",
                "base": {"ref": "main", "sha": "base101"},
                "head": {"ref": "article-101", "sha": "head101", "repo": {"full_name": "yanivsa/kesher-website"}},
            },
            102: {
                "number": 102,
                "state": "open",
                "draft": False,
                "title": "Publish Kesher article: authoritative-2026-10-12",
                "base": {"ref": "main", "sha": "base102"},
                "head": {"ref": "article-102", "sha": "head102", "repo": {"full_name": "yanivsa/kesher-website"}},
            },
            103: {
                "number": 103,
                "state": "open",
                "draft": False,
                "title": "Publish Kesher article: competing-duplicate",
                "base": {"ref": "main", "sha": "base103"},
                "head": {"ref": "article-103", "sha": "head103", "repo": {"full_name": "yanivsa/kesher-website"}},
            },
        }
        controller_state_doc = {
            "schema_version": 5,
            "cycle": "2026-10-12",
            "status": "article_pr_open",
            "article": {"pr_number": 102, "normalization_slot": "2026-10-12"},
            "image": {
                "status": "complete",
                "attempt_count": 1,
                "provider_id": "gemini",
                "source_id": "gemini-3.1-flash-image",
                "artifact_sha256": "f" * 64,
            },
        }
        encoded_state = base64.b64encode(json.dumps(controller_state_doc).encode("utf-8")).decode("ascii")
        processed_prs: list[int] = []
        inspected_urls: list[str] = []

        def fake_request_json(method: str, url: str, token: str, payload=None):
            inspected_urls.append(url)
            if ".kesher-controller/state.json" in url:
                return {"encoding": "base64", "content": encoded_state}
            for num, pr_obj in prs_by_num.items():
                if url.endswith(f"/pulls/{num}"):
                    return copy.deepcopy(pr_obj)
            raise AssertionError(f"Unexpected API call: {method} {url}")

        with mock.patch.object(pr_ctrl_v3.core, "request_json", side_effect=fake_request_json), \
             mock.patch.object(
                 pr_ctrl_v3,
                 "_original_process",
                 side_effect=lambda repo, number, tok, key: (processed_prs.append(number), 0)[1],
             ):
            # Historical draft PR #997 must fail preflight before _original_process is ever called
            with self.assertRaisesRegex(RuntimeError, "draft"):
                pr_ctrl_v3.process_v3("yanivsa/kesher-website", 997, "tok", "jules-key", expected_slot="2026-10-12")
            # PR #101 (stale) must fail preflight before _original_process is ever called
            with self.assertRaisesRegex(RuntimeError, "not the authoritative image-complete article PR"):
                pr_ctrl_v3.process_v3("yanivsa/kesher-website", 101, "tok", "jules-key", expected_slot="2026-10-12")
            # PR #103 (competing) must fail preflight before _original_process is ever called
            with self.assertRaisesRegex(RuntimeError, "not the authoritative image-complete article PR"):
                pr_ctrl_v3.process_v3("yanivsa/kesher-website", 103, "tok", "jules-key", expected_slot="2026-10-12")
            # Invalid PR number (0 or negative) must fail closed
            with self.assertRaisesRegex(RuntimeError, "positive"):
                pr_ctrl_v3.process_v3("yanivsa/kesher-website", 0, "tok", "jules-key")

            # Dispatching merge for authoritative PR #102 NEVER inspects or mutates #997, #101, or #103
            inspected_urls.clear()
            rc = pr_ctrl_v3.process_v3("yanivsa/kesher-website", 102, "tok", "jules-key", expected_slot="2026-10-12")
            self.assertEqual(rc, 0)
            self.assertEqual(processed_prs, [102])
            for other_num in (997, 101, 103):
                self.assertFalse(any(u.endswith(f"/pulls/{other_num}") for u in inspected_urls))

    # Requirement 4: First-Wakeup State Rollover Simulation from Exact Live Frozen State (2026-10-04 -> 2026-10-12)
    def test_first_wakeup_rollover_from_frozen_2026_10_04_state_through_full_daily_lifecycle(self) -> None:
        posts_historical = json.loads((ROOT / "src" / "data" / "posts.json").read_text(encoding="utf-8"))
        posts_recent = json.loads((ROOT / "src" / "data" / "postsRecent.json").read_text(encoding="utf-8"))

        frozen_2026_10_04_state = {
            "schema_version": 5,
            "cycle": "2026-10-04",
            "status": "article_image_running",
            "article": {
                "attempts": 0,
                "deploy_attempts": 0,
                "failure_count_by_type": {},
                "failure_fingerprint": None,
                "same_failure_streak": 0,
                "next_retry_at": None,
                "processed_run_id": None,
                "attempt_count": 0,
                "status": "pending",
                "last_error": None,
                "run_id": None,
                "provider_id": None,
                "normalization_status": "complete",
                "pr_number": 1049,
                "pr_url": "https://github.com/yanivsa/kesher-website/pull/1049",
            },
            "backlog": [],
            "last_error": None,
            "history": [],
            "updated_at": "2026-10-04T06:24:31.594452+00:00",
            "image": {
                "attempt_count": 1,
                "status": "running",
                "last_error": None,
                "next_retry_at": None,
                "run_id": 23984071755,
                "provider_id": None,
                "failure_count_by_type": {},
                "failure_fingerprint": None,
                "same_failure_streak": 0,
                "processed_run_id": None,
                "last_dispatch_at": "2026-10-04T06:23:15.174208+00:00",
            },
            "long_video": {
                "attempt_count": 0,
                "status": "pending",
                "last_error": None,
                "next_retry_at": None,
                "run_id": None,
                "provider_id": None,
                "failure_count_by_type": {},
                "failure_fingerprint": None,
                "same_failure_streak": 0,
                "processed_run_id": None,
            },
            "short": {
                "attempt_count": 0,
                "status": "pending",
                "last_error": None,
                "next_retry_at": None,
                "run_id": None,
                "provider_id": None,
                "failure_count_by_type": {},
                "failure_fingerprint": None,
                "same_failure_streak": 0,
                "processed_run_id": None,
            },
            "migration": {"v4_short_controller_state": None},
            "deliverables": {
                "article_live": False,
                "article_url": None,
                "overview_youtube_url": None,
                "short_youtube_url": None,
                "overview_edit_verified": False,
                "short_portrait_verified": False,
                "short_signature_verified": False,
                "short_origin_verified": False,
            },
        }

        class RolloverSimGitHub:
            api = "https://api.github.test/repos/yanivsa/kesher-website"

            def __init__(self, initial_state: dict) -> None:
                self.state = copy.deepcopy(initial_state)
                self.posts = copy.deepcopy(posts_historical)
                self.recent_posts = copy.deepcopy(posts_recent)
                self.open_prs: list[dict] = []
                self.open_prs_calls = 0
                self.jules_session_calls = 0
                self.needs_norm = True
                self.image_ready = False
                self.image_evidence: dict[str, str] = {}
                self.active_runs: dict[str, dict | None] = {}
                self.video_state: dict = {"version": 1, "items": []}
                self.short_state: dict = {"version": 1, "items": []}
                self.dispatches: list[tuple[str, dict]] = []

            def request(self, method: str, path: str, body=None, allow_404: bool = False):
                if method == "GET" and "/actions/artifacts" in path:
                    return {"artifacts": []}
                if method == "POST" and "/dispatches" in path:
                    wf = urllib.parse.unquote(path.split("/actions/workflows/")[1].split("/dispatches")[0])
                    inputs = copy.deepcopy((body or {}).get("inputs") or {})
                    self.dispatches.append((wf, inputs))
                    return {}
                return {}

            def contents_json(self, path: str, ref: str = "main"):
                if path == "src/data/posts.json":
                    return copy.deepcopy(self.posts)
                if path == "src/data/postsRecent.json":
                    return copy.deepcopy(self.recent_posts)
                raise AssertionError(path)

            def load_controller_state(self):
                return copy.deepcopy(self.state)

            def save_controller_state(self, state):
                self.state = copy.deepcopy(state)

            def open_article_prs(self, slot=None):
                self.open_prs_calls += 1
                return copy.deepcopy(self.open_prs)

            def nudge_article_session(self, session_id):
                self.jules_session_calls += 1

            def article_pr_normalization_required(self, pr):
                return self.needs_norm, str(self.state.get("cycle") or "2026-10-12")

            def active_normalizer_run(self, pr_number):
                return None

            def article_pr_image_ready(self, pr):
                return self.image_ready, copy.deepcopy(self.image_evidence)

            def active_image_run(self, pr_number):
                return None

            def active_workflow_run(self, workflow, production_only=False):
                return self.active_runs.get(workflow)

            def workflow_run_by_id(self, run_id):
                return None

            def newest_video_state(self):
                return copy.deepcopy(self.video_state)

            def newest_short_state(self):
                return copy.deepcopy(self.short_state)

            def dispatch(self, workflow: str, inputs: dict | None = None):
                self.dispatches.append((workflow, copy.deepcopy(inputs or {})))

        real_oct12_post = next(
            p for p in posts_historical if core.canonical_slug(p) == "relocation-loneliness-accompanying-partner"
        )
        real_oct12_source = v5.article_source_identity(real_oct12_post)
        self.assertEqual(real_oct12_source["slug"], "relocation-loneliness-accompanying-partner")
        self.assertEqual(
            real_oct12_source["content_sha256"],
            "93bd8eb7d057faf9ede979e86c891504604c80766287f170b011f05065bd326c",
        )

        # Scenario A (Req 3, 4, 5A): Early current-day tick at 2026-10-12 00:10 Asia/Jerusalem
        # Starting from frozen Oct-4 Schema-5 state and real current-main catalogs containing
        # relocation-loneliness-accompanying-partner (not yet live on kesher.saharoni.com -> HTTP 404).
        gh_0010 = RolloverSimGitHub(frozen_2026_10_04_state)
        site_0010 = mock.Mock()
        site_0010.get.return_value = (404, "Not Found")
        ctrl_0010 = stabilized.StabilizedRuntimeV5Controller(
            gh_0010,
            site_0010,
            now=dt.datetime(2026, 10, 12, 0, 10, tzinfo=core.ISRAEL_TZ),
        )
        state_0010, action_0010 = ctrl_0010.tick()
        self.assertEqual(state_0010["cycle"], "2026-10-12")
        self.assertEqual(state_0010["article"]["slug"], "relocation-loneliness-accompanying-partner")
        self.assertEqual(
            state_0010["article"]["quality_content_sha256"],
            "93bd8eb7d057faf9ede979e86c891504604c80766287f170b011f05065bd326c",
        )
        self.assertEqual(state_0010["article"]["quality_status"], "passed")
        self.assertEqual(action_0010.kind, "dispatch_deploy")
        self.assertEqual(gh_0010.dispatches, [(core.DEPLOY_WORKFLOW, {})])
        self.assertEqual([w for w, _ in gh_0010.dispatches if w == core.ARTICLE_WORKFLOW], [])
        self.assertEqual(gh_0010.open_prs_calls, 0)
        self.assertEqual(gh_0010.jules_session_calls, 0)
        # Historical 2026-10-04 is archived in backlog and never replaces current article identity
        backlog_0010 = {r["cycle"]: r for r in state_0010.get("backlog") or []}
        self.assertIn("2026-10-04", backlog_0010)

        # Scenario B (Req 3, 4, 5B): Tick after normal article window at 2026-10-12 00:36 Asia/Jerusalem
        # Starting from frozen Oct-4 Schema-5 state when the Oct-12 article is already public (HTTP 200).
        gh = RolloverSimGitHub(frozen_2026_10_04_state)
        gh.state["backlog"] = [
            {"cycle": "2026-10-06", "status": "article_live"},
        ]
        oct6_post = next(p for p in posts_recent if p.get("date") == "2026-10-06")
        oct6_source = v5.article_source_identity(oct6_post)
        site = mock.Mock()
        site.get.return_value = (
            200,
            f"<html><h1>{real_oct12_post['title']}</h1><h2>{oct6_post['title']}</h2></html>",
        )
        ctrl_0036 = stabilized.StabilizedRuntimeV5Controller(
            gh,
            site,
            now=dt.datetime(2026, 10, 12, 0, 36, tzinfo=core.ISRAEL_TZ),
        )
        state_0036, action_0036 = ctrl_0036.tick()
        self.assertEqual(state_0036["cycle"], "2026-10-12")
        self.assertEqual(state_0036["article"]["slug"], real_oct12_source["slug"])
        self.assertEqual(state_0036["article"]["quality_content_sha256"], real_oct12_source["content_sha256"])
        self.assertTrue(state_0036["article"]["live"])
        self.assertEqual(action_0036.kind, "dispatch_long_video")
        self.assertEqual([w for w, _ in gh.dispatches if w == core.ARTICLE_WORKFLOW], [])
        self.assertEqual(gh.open_prs_calls, 0)
        self.assertEqual(gh.jules_session_calls, 0)
        self.assertEqual(
            gh.dispatches,
            [
                (
                    v5.LONG_VIDEO_WORKFLOW,
                    {
                        "operation": "full",
                        "target_slug": real_oct12_source["slug"],
                        "target_content_sha256": real_oct12_source["content_sha256"],
                    },
                )
            ],
        )

        # Scenario C (Req 6): Repeated 5-minute scheduler ticks at 00:41, 00:46, 00:51
        # while NotebookLM provider is pending (status="generating").
        # Prove: 0 article dispatches, 0 Jules sessions, 0 PR searches, 0 duplicate video/Short/deploy dispatches.
        gh.video_state = {
            "version": 1,
            "items": [
                {
                    "id": "long-oct12-1",
                    "type": "video_overview",
                    "status": "generating",
                    "notebook_id": "nb-oct12",
                    "task_id": "task-oct12",
                    "artifact_id": "task-oct12",
                    "source_id": "src-oct12",
                    "created_at": "2026-10-11T21:36:05+00:00",
                    "generation_started_at": "2026-10-11T21:36:05+00:00",
                    "source": {
                        "slug": real_oct12_source["slug"],
                        "content_sha256": real_oct12_source["content_sha256"],
                    },
                }
            ],
        }
        for minute in (41, 46, 51):
            tick_ctrl = stabilized.StabilizedRuntimeV5Controller(
                gh,
                site,
                now=dt.datetime(2026, 10, 12, 0, minute, tzinfo=core.ISRAEL_TZ),
            )
            tick_state, tick_action = tick_ctrl.tick()
            self.assertEqual(tick_action.kind, "wait")
            self.assertEqual(tick_action.reason, "long_video provider pending under watchdog")
            self.assertEqual(tick_state["article"]["slug"], real_oct12_source["slug"])
            self.assertEqual(tick_state["article"]["quality_content_sha256"], real_oct12_source["content_sha256"])
            self.assertEqual([w for w, _ in gh.dispatches if w == core.ARTICLE_WORKFLOW], [])
            self.assertEqual(gh.open_prs_calls, 0)
            self.assertEqual(gh.jules_session_calls, 0)
            self.assertEqual(len(gh.dispatches), 1)

        # Also prove repeated-tick idempotency while deploy is active (00:36 -> 00:41 -> 00:46 -> 00:51)
        gh_deploy_wait = RolloverSimGitHub(frozen_2026_10_04_state)
        site_404 = mock.Mock()
        site_404.get.return_value = (404, "Not Found")
        _, first_deploy_action = stabilized.StabilizedRuntimeV5Controller(
            gh_deploy_wait,
            site_404,
            now=dt.datetime(2026, 10, 12, 0, 36, tzinfo=core.ISRAEL_TZ),
        ).tick()
        self.assertEqual(first_deploy_action.kind, "dispatch_deploy")
        self.assertEqual(gh_deploy_wait.dispatches, [(core.DEPLOY_WORKFLOW, {})])
        gh_deploy_wait.active_runs[core.DEPLOY_WORKFLOW] = {
            "id": 888001,
            "status": "in_progress",
            "event": "workflow_dispatch",
        }
        for minute in (41, 46, 51):
            _, dep_tick_action = stabilized.StabilizedRuntimeV5Controller(
                gh_deploy_wait,
                site_404,
                now=dt.datetime(2026, 10, 12, 0, minute, tzinfo=core.ISRAEL_TZ),
            ).tick()
            self.assertEqual(dep_tick_action.kind, "wait")
            self.assertEqual(dep_tick_action.reason, "deployment active")
            self.assertEqual(len(gh_deploy_wait.dispatches), 1)
            self.assertEqual(gh_deploy_wait.open_prs_calls, 0)

        # Scenario D (Req 7): Long video completes & is verified public -> dispatches Short derivation from exact same identity,
        # then once Short is verified complete, current 2026-10-12 completes, ambiguous 2026-10-04 is quarantined, and
        # unambiguous 2026-10-06 backlog row advances!
        from tests.test_media_provenance_contract import audio_fixture, bound_short

        gh.dispatches.clear()
        sig_sha = hashlib.sha256((ROOT / "public/images/signature/signature-mask.svg").read_bytes()).hexdigest()
        overview_dur = 121.0
        gh.video_state = {
            "version": 1,
            "items": [
                {
                    "id": "long-oct12-1",
                    "type": "video_overview",
                    "status": "uploaded",
                    "uploaded": True,
                    "youtube_id": "yt-long-oct12",
                    "youtube_url": "https://youtu.be/yt-long-oct12",
                    "notebook_id": "nb-oct12",
                    "task_id": "task-oct12",
                    "artifact_id": "task-oct12",
                    "source_id": "src-oct12",
                    "raw_sha256": "e" * 64,
                    "final_sha256": "a" * 64,
                    "audio_provenance": audio_fixture("e" * 64, "a" * 64, overview_dur),
                    "provider_raw_media": {"width": 1280, "height": 720, "duration": overview_dur, "audio_codec": "aac"},
                    "technical_verified": True,
                    "visual_pipeline": "remotion-v1-notebooklm-audio",
                    "media": {"codec": "h264", "audio_codec": "aac", "width": 1280, "height": 720, "duration": overview_dur},
                    "content_duration_seconds": overview_dur,
                    "signature_duration_seconds": 3.0,
                    "signature_overlay": True,
                    "signature_fullscreen": True,
                    "signature_verified": True,
                    "signature_sha256": sig_sha,
                    "signature_asset_sha256": sig_sha,
                    "signature_video_sha256": "8" * 64,
                    "signature_provenance": {
                        "schema_version": 1,
                        "final_sha256": "a" * 64,
                        "raw_sha256": "e" * 64,
                        "asset_sha256": sig_sha,
                        "segment_sha256": "8" * 64,
                        "source_duration_seconds": overview_dur,
                        "final_duration_seconds": overview_dur,
                        "start_seconds": overview_dur - 3.0,
                        "end_seconds": overview_dur,
                        "audio_source_sha256": "e" * 64,
                    },
                    "source": {"slug": real_oct12_source["slug"], "content_sha256": real_oct12_source["content_sha256"]},
                    "youtube_verification": {
                        "channel_id": core.YOUTUBE_CHANNEL_ID,
                        "privacy_status": "public",
                        "processing_status": "succeeded",
                    },
                }
            ],
        }
        ctrl_d2 = stabilized.StabilizedRuntimeV5Controller(
            gh,
            site,
            now=dt.datetime(2026, 10, 12, 9, 15, tzinfo=core.ISRAEL_TZ),
        )
        state_d2, action_d2 = ctrl_d2.tick()
        self.assertEqual(action_d2.kind, "dispatch_short")
        self.assertEqual(
            gh.dispatches[-1],
            (
                v5.SHORT_WORKFLOW,
                {
                    "operation": "derive",
                    "derive_slug": real_oct12_source["slug"],
                    "derive_content_sha256": real_oct12_source["content_sha256"],
                    "derive_long_item_id": "long-oct12-1",
                },
            ),
        )

        # Short completes & is verified public portrait:
        # Because backlog has [2026-10-04 (ambiguous), 2026-10-06 (unambiguous)], once current cycle 2026-10-12
        # deliverables are verified complete, the controller quarantines 2026-10-04 and dispatches backlog long video for 2026-10-06!
        gh.dispatches.clear()
        short_item_oct12 = {
            **bound_short(45.0),
            "id": "short-oct12-1",
            "status": "uploaded",
            "uploaded": True,
            "youtube_id": "yt-short-oct12",
            "youtube_url": "https://youtube.com/shorts/yt-short-oct12",
            "source": {"slug": real_oct12_source["slug"], "content_sha256": real_oct12_source["content_sha256"]},
            "youtube_verification": {
                "channel_id": core.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        }
        gh.short_state = {"version": 1, "items": [short_item_oct12]}
        ctrl_d3 = stabilized.StabilizedRuntimeV5Controller(
            gh,
            site,
            now=dt.datetime(2026, 10, 12, 9, 30, tzinfo=core.ISRAEL_TZ),
        )
        with mock.patch.object(
            v5_runtime,
            "ordered_recoverable_backlog",
            side_effect=lambda rows: sorted(
                [r for r in rows if not r.get("quarantined")],
                key=lambda r: str(r.get("cycle") or ""),
            ),
        ):
            state_d3, action_d3 = ctrl_d3.tick()
        self.assertTrue(state_d3["article"]["live"])
        self.assertEqual(state_d3["deliverables"]["article_url"], f"{core.SITE_URL}/blog/{real_oct12_source['slug']}")
        self.assertEqual(state_d3["deliverables"]["overview_youtube_url"], "https://youtu.be/yt-long-oct12")
        self.assertEqual(state_d3["deliverables"]["short_youtube_url"], "https://youtube.com/shorts/yt-short-oct12")
        backlog_d3 = {r["cycle"]: r for r in state_d3["backlog"]}
        self.assertEqual(backlog_d3["2026-10-04"]["status"], "quarantined_ambiguous_identity")
        self.assertEqual(action_d3.kind, "dispatch_backlog_long_video")
        self.assertEqual(
            gh.dispatches[-1],
            (
                v5.LONG_VIDEO_WORKFLOW,
                {
                    "operation": "full",
                    "target_slug": oct6_source["slug"],
                    "target_content_sha256": oct6_source["content_sha256"],
                },
            ),
        )

        # Scenario E: Next day (2026-10-13) with no existing article yet:
        # 00:10 waits for article window; 00:36 dispatches article -> normalize -> image -> auto-merge
        state_d3_clean = copy.deepcopy(state_d3)
        state_d3_clean["backlog"] = []
        gh_next = RolloverSimGitHub(state_d3_clean)
        state_next_0010, action_next_0010 = stabilized.StabilizedRuntimeV5Controller(
            gh_next,
            site,
            now=dt.datetime(2026, 10, 13, 0, 10, tzinfo=core.ISRAEL_TZ),
        ).tick()
        self.assertEqual(state_next_0010["cycle"], "2026-10-13")
        self.assertEqual(state_next_0010["status"], "waiting_for_article_window")
        self.assertEqual(action_next_0010.kind, "wait")

        gh_next.dispatches.clear()
        _, action_next_0036 = stabilized.StabilizedRuntimeV5Controller(
            gh_next,
            site,
            now=dt.datetime(2026, 10, 13, 0, 36, tzinfo=core.ISRAEL_TZ),
        ).tick()
        self.assertEqual(action_next_0036.kind, "dispatch_article")
        self.assertEqual(gh_next.dispatches, [(core.ARTICLE_WORKFLOW, {"slot": "2026-10-13"})])

        gh_next.dispatches.clear()
        gh_next.open_prs = [
            {
                "number": 1105,
                "html_url": "https://github.com/yanivsa/kesher-website/pull/1105",
                "title": "Publish Kesher article: oct-13-daily-article",
                "head": {"sha": "head1105"},
                "base": {"sha": "base1105"},
            }
        ]
        gh_next.needs_norm = True
        _, action_norm = stabilized.StabilizedRuntimeV5Controller(
            gh_next,
            site,
            now=dt.datetime(2026, 10, 13, 0, 41, tzinfo=core.ISRAEL_TZ),
        ).tick()
        self.assertEqual(action_norm.kind, "dispatch_normalize")
        self.assertEqual(gh_next.dispatches[-1], ("normalize-article-pr.yml", {"pr_number": "1105", "slot": "2026-10-13"}))

        gh_next.dispatches.clear()
        gh_next.needs_norm = False
        gh_next.image_ready = False
        _, action_img = stabilized.StabilizedRuntimeV5Controller(
            gh_next,
            site,
            now=dt.datetime(2026, 10, 13, 0, 46, tzinfo=core.ISRAEL_TZ),
        ).tick()
        self.assertEqual(action_img.kind, "dispatch_image")
        self.assertEqual(gh_next.dispatches[-1], ("kesher-article-image.yml", {"pr_number": "1105"}))

        gh_next.dispatches.clear()
        gh_next.image_ready = True
        gh_next.image_evidence = {"provider": "gemini", "source": "gemini-3.1-flash-image", "sha256": "d" * 64}
        _, action_merge = stabilized.StabilizedRuntimeV5Controller(
            gh_next,
            site,
            now=dt.datetime(2026, 10, 13, 0, 51, tzinfo=core.ISRAEL_TZ),
        ).tick()
        self.assertEqual(action_merge.kind, "wait")
        self.assertEqual(gh_next.dispatches[-1], ("auto-merge-article-prs.yml", {"pr_number": "1105", "slot": "2026-10-13"}))

    # Requirement 10: Two-catalog normalize & validation safety
    def test_normalizer_rejects_duplicate_slug_or_slot_against_posts_recent_without_mutating_it(self) -> None:
        from scripts.kesher_article_normalizer import (
            ArticleNormalizationError,
            extract_target_article,
            normalized_posts,
        )

        posts_historical = json.loads((ROOT / "src" / "data" / "posts.json").read_text(encoding="utf-8"))
        posts_recent = json.loads((ROOT / "src" / "data" / "postsRecent.json").read_text(encoding="utf-8"))
        recent_before = copy.deepcopy(posts_recent)

        # Duplicate slug against postsRecent.json must fail closed
        dup_slug_article = copy.deepcopy(posts_recent[0])
        dup_slug_article["date"] = "2026-10-13"
        with self.assertRaisesRegex(ArticleNormalizationError, "already exists in main"):
            normalized_posts(posts_historical, dup_slug_article, recent_posts=posts_recent)

        # Duplicate adoptable slot against posts.json (2026-10-12) or postsRecent.json (2026-10-10) must fail closed
        for occupied_date in ("2026-10-10", "2026-10-12"):
            dup_slot_article = copy.deepcopy(posts_recent[0])
            dup_slot_article["id"] = f"different-slug-on-{occupied_date}"
            dup_slot_article["slug"] = f"different-slug-on-{occupied_date}"
            dup_slot_article["date"] = occupied_date
            with self.assertRaisesRegex(ArticleNormalizationError, "publication slot already exists in main"):
                normalized_posts(posts_historical, dup_slot_article, recent_posts=posts_recent)

        # Valid new article on 2026-10-13 normalizes into posts.json and leaves postsRecent.json untouched
        valid_new = copy.deepcopy(posts_recent[0])
        valid_new.update(
            {
                "id": "valid-2026-10-13-article",
                "slug": "valid-2026-10-13-article",
                "date": "2026-10-13",
            }
        )
        extracted = extract_target_article(
            posts_historical,
            [valid_new, *posts_historical],
            "2026-10-13",
            recent_posts=posts_recent,
        )
        self.assertEqual(extracted["id"], "valid-2026-10-13-article")
        norm = normalized_posts(posts_historical, extracted, recent_posts=posts_recent)
        self.assertEqual(norm[0]["id"], "valid-2026-10-13-article")
        self.assertEqual(len(norm), len(posts_historical) + 1)
        self.assertEqual(posts_recent, recent_before)

    # Requirements 6, 8, 11, 12, 13, 14: Adversarial regression coverage (20 scenarios)
    def test_adversarial_regression_matrix_and_event_semantics(self) -> None:
        posts_historical = json.loads((ROOT / "src" / "data" / "posts.json").read_text(encoding="utf-8"))
        posts_recent = json.loads((ROOT / "src" / "data" / "postsRecent.json").read_text(encoding="utf-8"))

        # Case 20 & Req 6: workflow_run triggered by an irrelevant workflow is denied at bridge_admission and no-op at controller tick
        irrelevant_env = self._controller_env("workflow_run") | {
            "KESHER_TRIGGER_EVENT": "workflow_run",
            "KESHER_CHILD_WORKFLOW": "CI",
        }
        with self.assertRaises(StateInvalid):
            bridge_admission.require_invocation(irrelevant_env, controller=True)

        valid_child_env = self._controller_env("workflow_run") | {
            "KESHER_TRIGGER_EVENT": "workflow_run",
            "KESHER_CHILD_WORKFLOW": "Kesher Article Generation",
        }
        bridge_admission.require_invocation(valid_child_env, controller=True)

        # Also verify controller tick itself is a pure no-op wait if KESHER_TRIGGER_EVENT=workflow_run has an irrelevant workflow name
        noop_dispatches: list[tuple[str, dict]] = []

        class NoopGitHub:
            def load_controller_state(self):
                return {"schema_version": 5, "cycle": "2026-10-12", "status": "article_needed"}

            def dispatch(self, workflow: str, inputs: dict | None = None):
                noop_dispatches.append((workflow, inputs or {}))

        with mock.patch.dict(os.environ, irrelevant_env, clear=False):
            noop_ctrl = stabilized.StabilizedRuntimeV5Controller(
                NoopGitHub(),
                mock.Mock(),
                now=dt.datetime(2026, 10, 12, 9, 0, tzinfo=core.ISRAEL_TZ),
            )
            _, noop_action = noop_ctrl.tick()
        self.assertEqual(noop_action.kind, "wait")
        self.assertIn("irrelevant workflow_run ignored", noop_action.reason)
        self.assertEqual(noop_dispatches, [])

        # Cases 7, 8, 9: Two open article PRs for an open cycle (2026-10-13) blocks with DUPLICATE_ARTICLE_PRS
        class DupPrGitHub:
            def contents_json(self, path: str, ref: str = "main"):
                return copy.deepcopy(posts_historical) if path == "src/data/posts.json" else copy.deepcopy(posts_recent)

            def load_controller_state(self):
                return {"schema_version": 5, "cycle": "2026-10-13", "status": "article_needed"}

            def save_controller_state(self, state):
                self.saved = copy.deepcopy(state)

            def open_article_prs(self, slot=None):
                return [{"number": 1105}, {"number": 1106}]

            def active_workflow_run(self, workflow, production_only=False):
                return None

        dup_gh = DupPrGitHub()
        dup_ctrl = stabilized.StabilizedRuntimeV5Controller(
            dup_gh,
            mock.Mock(),
            now=dt.datetime(2026, 10, 13, 9, 0, tzinfo=core.ISRAEL_TZ),
        )
        dup_state, dup_action = dup_ctrl.tick()
        self.assertEqual(dup_action.kind, "blocked")
        self.assertEqual(dup_state["last_error"]["code"], "DUPLICATE_ARTICLE_PRS")

        # Case 13 & Req 11: Real 2026-10-12 article merged on main, but public page not yet live (404) -> dispatches deploy, NEVER dispatches long video
        oct12_post = next(
            p for p in posts_historical if core.canonical_slug(p) == "relocation-loneliness-accompanying-partner"
        )
        deploy_dispatches: list[tuple[str, dict]] = []

        class NotYetPublicGitHub:
            api = "https://api.github.test/repos/yanivsa/kesher-website"

            def request(self, method: str, path: str, body=None, allow_404: bool = False):
                if method == "GET" and "/actions/artifacts" in path:
                    return {"artifacts": []}
                if method == "POST" and "/dispatches" in path:
                    wf = urllib.parse.unquote(path.split("/actions/workflows/")[1].split("/dispatches")[0])
                    deploy_dispatches.append((wf, (body or {}).get("inputs") or {}))
                    return {}
                return {}

            def contents_json(self, path: str, ref: str = "main"):
                if path == "src/data/posts.json":
                    return copy.deepcopy(posts_historical)
                if path == "src/data/postsRecent.json":
                    return copy.deepcopy(posts_recent)
                raise AssertionError(path)

            def load_controller_state(self):
                return {"schema_version": 5, "cycle": "2026-10-12", "status": "article_pr_open"}

            def save_controller_state(self, state):
                self.saved = copy.deepcopy(state)

            def open_article_prs(self, slot=None):
                return []

            def active_workflow_run(self, workflow, production_only=False):
                return None

            def newest_video_state(self):
                return {"version": 1, "items": []}

            def newest_short_state(self):
                return {"version": 1, "items": []}

            def dispatch(self, workflow: str, inputs: dict | None = None):
                deploy_dispatches.append((workflow, inputs or {}))

        not_public_site = mock.Mock()
        not_public_site.get.return_value = (404, "Not Found")
        not_public_ctrl = stabilized.StabilizedRuntimeV5Controller(
            NotYetPublicGitHub(),
            not_public_site,
            now=dt.datetime(2026, 10, 12, 9, 5, tzinfo=core.ISRAEL_TZ),
        )
        np_state, np_action = not_public_ctrl.tick()
        self.assertEqual(np_action.kind, "dispatch_deploy")
        self.assertEqual([w for w, _ in deploy_dispatches if w == v5.LONG_VIDEO_WORKFLOW], [])
        self.assertFalse(np_state["article"].get("live"))
        self.assertFalse(v5_runtime.delivery_guard.delivery_contract(np_state)[0])

        # Cases 16 & 17 & Req 12: Provider pending across multiple 5-minute scheduler ticks -> waits without re-dispatching; hard timeout blocks cleanly
        oct12_source = v5.article_source_identity(oct12_post)
        pending_dispatches: list[tuple[str, dict]] = []

        class PendingProviderGitHub(NotYetPublicGitHub):
            def __init__(self) -> None:
                self.saved = {"schema_version": 5, "cycle": "2026-10-12", "status": "long_video_running"}

            def load_controller_state(self):
                return copy.deepcopy(self.saved)

            def save_controller_state(self, state):
                self.saved = copy.deepcopy(state)

            def newest_video_state(self):
                return {
                    "version": 1,
                    "items": [
                        {
                            "id": "pending-long-1",
                            "type": "video_overview",
                            "status": "generating",
                            "task_id": "nb-task-1",
                            "created_at": "2026-10-12T06:00:00+00:00",
                            "generation_started_at": "2026-10-12T06:00:00+00:00",
                            "source": {
                                "slug": oct12_source["slug"],
                                "content_sha256": oct12_source["content_sha256"],
                            },
                        }
                    ],
                }

            def dispatch(self, workflow: str, inputs: dict | None = None):
                pending_dispatches.append((workflow, inputs or {}))

        live_site = mock.Mock()
        live_site.get.return_value = (200, f"<html>{oct12_post['title']}</html>")
        p_gh = PendingProviderGitHub()
        for offset_min in (5, 10, 15):
            p_ctrl = stabilized.StabilizedRuntimeV5Controller(
                p_gh,
                live_site,
                now=dt.datetime(2026, 10, 12, 9, offset_min, tzinfo=core.ISRAEL_TZ),
            )
            p_state, p_action = p_ctrl.tick()
            self.assertEqual(p_action.kind, "wait")
            self.assertEqual(p_action.reason, "long_video provider pending under watchdog")
            self.assertIn("watchdog", p_state["long_video"])
            self.assertEqual(pending_dispatches, [])

        # Hard timeout after > 90 minutes from generation_started_at blocks cleanly without infinite retries
        timeout_ctrl = stabilized.StabilizedRuntimeV5Controller(
            p_gh,
            live_site,
            now=dt.datetime(2026, 10, 12, 11, 0, tzinfo=core.ISRAEL_TZ),
        )
        t_state, t_action = timeout_ctrl.tick()
        self.assertEqual(t_action.kind, "blocked")
        self.assertEqual(t_state["last_error"]["code"], "LONG_VIDEO_PROVIDER_HARD_TIMEOUT")
        self.assertEqual(pending_dispatches, [])

        # Cases 18 & 19 & Req 13: Schema 6 or handover marker appearing between admission and save_controller_state fails closed immediately
        client = core.GitHubClient("yanivsa/kesher-website", "tok")
        client._controller_state_loaded = True
        client._controller_state_sha = "sha123"
        client._controller_state_document = {"schema_version": 5, "cycle": "2026-10-12"}
        with mock.patch.dict(os.environ, self._controller_env("schedule"), clear=True):
            with self.assertRaises(StateInvalid):
                client.save_controller_state({"schema_version": 6, "cycle": "2026-10-12"})
            with self.assertRaises(StateInvalid):
                client.save_controller_state({"schema_version": 5, "cycle": "2026-10-12", "handover": {"phase": "INIT"}})

    def test_live_oct12_short_without_overview_identity_and_historical_sep14_backlog_complete_zero_touch(self) -> None:
        from tests.test_media_provenance_contract import audio_fixture, bound_short

        posts_historical = json.loads((ROOT / "src" / "data" / "posts.json").read_text(encoding="utf-8"))
        posts_recent = json.loads((ROOT / "src" / "data" / "postsRecent.json").read_text(encoding="utf-8"))
        merged_posts = core.merge_catalog_posts(posts_historical, posts_recent)

        oct12_post = next(p for p in merged_posts if core.canonical_slug(p) == "relocation-loneliness-accompanying-partner")
        oct12_source = v5.article_source_identity(oct12_post)
        sep14_post = next(p for p in merged_posts if str(p.get("date") or "") == "2026-09-14")
        sep14_source = v5.article_source_identity(sep14_post)

        sig_sha = hashlib.sha256((ROOT / "public/images/signature/signature-mask.svg").read_bytes()).hexdigest()
        overview_dur = 140.42
        long_oct12 = {
            "id": "video-20261012-102835-93bd8eb7d0",
            "type": "video_overview",
            "status": "uploaded",
            "uploaded": True,
            "youtube_id": "phMWmYe_e6s",
            "youtube_url": "https://www.youtube.com/watch?v=phMWmYe_e6s",
            "notebook_id": "nb-oct12",
            "source_id": "src-oct12-long",
            "task_id": "task-oct12-long",
            "artifact_id": "task-oct12-long",
            "raw_sha256": "e" * 64,
            "final_sha256": "a" * 64,
            "audio_provenance": audio_fixture("e" * 64, "a" * 64, overview_dur),
            "provider_raw_media": {"width": 1280, "height": 720, "duration": overview_dur, "audio_codec": "aac"},
            "technical_verified": True,
            "visual_pipeline": "remotion-v1-notebooklm-audio",
            "media": {"codec": "h264", "audio_codec": "aac", "width": 1280, "height": 720, "duration": overview_dur},
            "content_duration_seconds": overview_dur,
            "signature_duration_seconds": 3.0,
            "signature_overlay": True,
            "signature_fullscreen": True,
            "signature_verified": True,
            "signature_sha256": sig_sha,
            "signature_asset_sha256": sig_sha,
            "signature_video_sha256": "8" * 64,
            "signature_provenance": {
                "schema_version": 1,
                "final_sha256": "a" * 64,
                "raw_sha256": "e" * 64,
                "asset_sha256": sig_sha,
                "segment_sha256": "8" * 64,
                "source_duration_seconds": overview_dur,
                "final_duration_seconds": overview_dur,
                "start_seconds": overview_dur - 3.0,
                "end_seconds": overview_dur,
                "audio_source_sha256": "e" * 64,
            },
            "source": {"slug": oct12_source["slug"], "content_sha256": oct12_source["content_sha256"]},
            "youtube_verification": {
                "channel_id": core.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        }
        long_sep14 = {
            "id": "video-20260916-083249-74040d54b5",
            "type": "video_overview",
            "status": "uploaded",
            "uploaded": True,
            "youtube_id": "zecFDhri5Lc",
            "youtube_url": "https://youtu.be/zecFDhri5Lc",
            "technical_verified": True,
            "visual_pipeline": "remotion-v1-notebooklm-audio",
            "media": {"codec": "h264", "audio_codec": "aac", "width": 1280, "height": 720, "duration": 391.47},
            "content_duration_seconds": 391.47,
            "signature_duration_seconds": 3.0,
            "signature_fullscreen": True,
            "signature_verified": True,
            "signature_asset_sha256": sig_sha,
            "source": {"slug": sep14_source["slug"], "content_sha256": sep14_source["content_sha256"]},
            "youtube_verification": {
                "channel_id": core.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        }
        # Uploaded Short item has NO overview_provider_identity on disk (matching kesher_short_pipeline_v4 output)
        # AND a stray second generating item exists in short_state.
        short_oct12_uploaded = {
            **bound_short(45.0),
            "id": "video-20261012-160846-93bd8eb7d0",
            "status": "uploaded",
            "uploaded": True,
            "youtube_id": "qlVlUZMDKNo",
            "youtube_url": "https://youtu.be/qlVlUZMDKNo",
            "source": {"slug": oct12_source["slug"], "content_sha256": oct12_source["content_sha256"]},
            "youtube_verification": {
                "channel_id": core.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        }
        short_oct12_uploaded.pop("overview_provider_identity", None)
        short_oct12_stray_generating = {
            "id": "video-20261012-174818-93bd8eb7d0",
            "type": "article_short",
            "source_mode": "direct-short",
            "status": "generating",
            "uploaded": False,
            "task_id": "stray-task",
            "artifact_id": "stray-task",
            "created_at": "2026-10-12T17:48:18+00:00",
            "generation_started_at": "2026-10-12T17:48:32+00:00",
            "source": {"slug": oct12_source["slug"], "content_sha256": oct12_source["content_sha256"]},
        }
        # Historical 2026-09-14 Short created before 2026-10-04 (no audio_provenance/signature_provenance)
        short_sep14_historical = {
            "id": "video-20260916-203232-74040d54b5",
            "type": "article_short",
            "source_mode": "direct-short",
            "status": "uploaded",
            "uploaded": True,
            "youtube_id": "0_D5XJBjong",
            "youtube_url": "https://youtu.be/0_D5XJBjong",
            "media": {"codec": "h264", "audio_codec": "aac", "width": 1080, "height": 1920, "duration": 284.72},
            "signature_duration_seconds": 3.0,
            "signature_fullscreen": True,
            "signature_verified": True,
            "signature_video_sha256": "7" * 64,
            "source": {"slug": sep14_source["slug"], "content_sha256": sep14_source["content_sha256"], "date": "2026-09-14"},
            "youtube_verification": {
                "channel_id": core.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        }

        live_like_state = {
            "schema_version": 5,
            "cycle": "2026-10-12",
            "status": "short_running",
            "article": {
                "status": "complete",
                "live": True,
                "slug": oct12_source["slug"],
                "url": f"{core.SITE_URL}/blog/{oct12_source['slug']}",
                "quality_status": "passed",
                "quality_content_sha256": oct12_source["content_sha256"],
            },
            "image": {"status": "complete"},
            "long_video": {"status": "pending"},
            "short": {
                "status": "running",
                "verified": False,
                "adopted_from_long_item_id": long_oct12["id"],
            },
            "interventions": {
                f"kesher-v5:{oct12_source['slug']}:{oct12_source['content_sha256']}:short": {
                    "strikes": 1,
                    "status": "recovering",
                    "last_fingerprint": "old-fingerprint",
                }
            },
            "backlog": [
                {"cycle": "2026-10-04", "status": "article_image_running"},
                {"cycle": "2026-09-14", "status": "article_deploying"},
            ],
        }

        class LiveSimGitHub:
            def __init__(self) -> None:
                self.state = copy.deepcopy(live_like_state)
                self.dispatches: list[tuple[str, dict]] = []

            def load_controller_state(self):
                return copy.deepcopy(self.state)

            def save_controller_state(self, state):
                self.state = copy.deepcopy(state)

            def posts_on_main(self, ref="main"):
                return copy.deepcopy(merged_posts)

            def newest_video_state(self):
                return {"version": 1, "items": [copy.deepcopy(long_sep14), copy.deepcopy(long_oct12)]}

            def newest_short_state(self):
                return {
                    "version": 1,
                    "items": [
                        copy.deepcopy(short_sep14_historical),
                        copy.deepcopy(short_oct12_uploaded),
                        copy.deepcopy(short_oct12_stray_generating),
                    ],
                }

            def active_workflow_run(self, workflow, production_only=False):
                return None

            def open_article_prs(self, slot=None):
                return []

            def dispatch(self, workflow: str, inputs: dict | None = None):
                self.dispatches.append((workflow, copy.deepcopy(inputs or {})))

        site = mock.Mock()
        site.get.side_effect = lambda url: (
            (200, f"<h1>{oct12_post['title']}</h1><article>{oct12_post['content']}</article>")
            if url.endswith(oct12_source["slug"])
            else (200, f"<h1>{sep14_post['title']}</h1><article>{sep14_post['content']}</article>")
        )

        gh = LiveSimGitHub()
        with mock.patch.dict(os.environ, self._controller_env("schedule"), clear=False):
            ctrl = stabilized.StabilizedRuntimeV5Controller(
                gh,
                site,
                now=dt.datetime(2026, 10, 12, 21, 5, tzinfo=core.ISRAEL_TZ),
            )
            final_state, action = ctrl.tick()

        self.assertEqual(final_state["status"], "complete")
        self.assertEqual(action.kind, "complete")
        self.assertEqual(final_state["short"]["status"], "complete")
        self.assertTrue(final_state["short"]["verified"])
        self.assertEqual(final_state["short"]["item_id"], "video-20261012-160846-93bd8eb7d0")
        self.assertEqual(
            final_state["deliverables"],
            {
                "article_url": f"{core.SITE_URL}/blog/{oct12_source['slug']}",
                "overview_youtube_url": "https://www.youtube.com/watch?v=phMWmYe_e6s",
                "short_youtube_url": "https://youtu.be/qlVlUZMDKNo",
                "overview_edit_verified": True,
                "short_portrait_verified": True,
                "short_signature_verified": True,
                "short_origin_verified": True,
            },
        )
        backlog_by_cycle = {r["cycle"]: r for r in final_state["backlog"]}
        self.assertEqual(backlog_by_cycle["2026-10-04"]["status"], "quarantined_ambiguous_identity")
        self.assertTrue(backlog_by_cycle["2026-09-14"]["media"]["complete"])
        self.assertEqual(backlog_by_cycle["2026-09-14"]["media"]["short_youtube_url"], "https://youtu.be/0_D5XJBjong")
        self.assertEqual(gh.dispatches, [])


if __name__ == "__main__":
    unittest.main()

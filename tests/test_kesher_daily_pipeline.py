from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "kesher_daily_pipeline.py"
SPEC = importlib.util.spec_from_file_location("kesher_daily_pipeline", MODULE_PATH)
pipeline = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(pipeline)

REVIEWER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "jules_video_reviewer.py"
REVIEWER_SPEC = importlib.util.spec_from_file_location("jules_video_reviewer", REVIEWER_PATH)
reviewer = importlib.util.module_from_spec(REVIEWER_SPEC)
assert REVIEWER_SPEC and REVIEWER_SPEC.loader
REVIEWER_SPEC.loader.exec_module(reviewer)

EVIDENCE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_jules_video_evidence.py"
EVIDENCE_SPEC = importlib.util.spec_from_file_location("prepare_jules_video_evidence", EVIDENCE_PATH)
evidence = importlib.util.module_from_spec(EVIDENCE_SPEC)
assert EVIDENCE_SPEC and EVIDENCE_SPEC.loader
EVIDENCE_SPEC.loader.exec_module(evidence)


def hebrew_post(slug: str = "new-post", published: str = "2026-08-10") -> dict:
    return {
        "id": slug,
        "slug": slug,
        "title": "איך עוזרים לילד להסתגל לשינוי?",
        "date": published,
        "category": "הדרכת הורים",
        "subcategory": "ילדים מחוננים",
        "excerpt": "שינוי במסגרת עלול לעורר חשש. הנה דרך מעשית לעזור לילד.",
        "content": "<p>הקשיבו לחשש, הגדירו תקופת ניסיון ודברו שוב לאחר כמה מפגשים.</p>",
    }


class PipelineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state_dir = self.root / "state"
        self.posts_file = self.root / "posts.json"
        self.patches = [
            mock.patch.object(pipeline, "STATE_DIR", self.state_dir),
            mock.patch.object(pipeline, "STATE_FILE", self.state_dir / "state.json"),
            mock.patch.object(pipeline, "POSTS_FILE", self.posts_file),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()

    def write_posts(self, posts: list[dict]) -> None:
        self.posts_file.write_text(json.dumps(posts, ensure_ascii=False), encoding="utf-8")

    def test_selects_newest_unused_published_hebrew_article(self) -> None:
        older = hebrew_post("older", "2026-08-01")
        newest = hebrew_post("newest", "2026-08-10")
        future = hebrew_post("future", "2099-01-01")
        self.write_posts([older, newest, future])
        state = {"version": 1, "items": [], "updated_at": pipeline.utc_now()}
        selected = pipeline.select_newest_unused_article(state)
        self.assertEqual(selected["slug"], "newest")
        state["items"].append({"source": {"slug": "newest", "content_sha256": selected["content_sha256"]}})
        selected = pipeline.select_newest_unused_article(state)
        self.assertEqual(selected["slug"], "older")

    def test_source_metadata_has_no_default_or_unsupported_metadata(self) -> None:
        source = pipeline.source_metadata(hebrew_post())
        metadata = source["youtube_metadata"]
        self.assertEqual(metadata["title"], "איך עוזרים לילד להסתגל לשינוי?")
        self.assertIn(pipeline.SITE_URL, metadata["description"])
        self.assertEqual(metadata["tags"], ["הדרכת הורים", "ילדים מחוננים"])
        pipeline.require_hebrew(metadata["description"], "description", allow_url=True)

    def test_generation_prompt_always_requests_female_hebrew_voice(self) -> None:
        prompt = pipeline.generation_prompt(pipeline.source_metadata(hebrew_post()))
        self.assertIn("קול של אישה ישראלית", prompt)
        self.assertIn("בעברית טבעית בלבד", prompt)

    def test_latin_visible_metadata_is_rejected(self) -> None:
        post = hebrew_post()
        post["title"] = "טיפ Parenting"
        with self.assertRaisesRegex(pipeline.PipelineError, "Latin"):
            pipeline.source_metadata(post)

    def test_auth_json_must_be_nonempty_storage_state(self) -> None:
        with mock.patch.dict(os.environ, {"NOTEBOOKLM_HOME": str(self.root / "missing")}, clear=True):
            with self.assertRaisesRegex(pipeline.PipelineError, "missing"):
                pipeline.notebooklm_env()
        with mock.patch.dict(os.environ, {"NOTEBOOKLM_AUTH_JSON": "{}"}, clear=True):
            with self.assertRaisesRegex(pipeline.PipelineError, "storage-state"):
                pipeline.notebooklm_env()

    def test_auth_file_allows_master_token_recovery_path(self) -> None:
        profile = self.root / "notebooklm" / "profiles" / "default"
        profile.mkdir(parents=True)
        (profile / "storage_state.json").write_text(
            json.dumps({"cookies": [{"name": "fixture", "value": "redacted"}]}),
            encoding="utf-8",
        )
        with mock.patch.dict(os.environ, {"NOTEBOOKLM_HOME": str(self.root / "notebooklm")}, clear=True):
            env = pipeline.notebooklm_env()
        self.assertNotIn("NOTEBOOKLM_AUTH_JSON", env)
        self.assertEqual(env["NOTEBOOKLM_HOME"], str(self.root / "notebooklm"))

    def test_preflight_requires_exact_pinned_version_and_live_token(self) -> None:
        with mock.patch.object(pipeline.importlib.metadata, "version", return_value="0.8.0"), mock.patch.object(
            pipeline, "run_notebooklm", return_value={"status": "ok", "checks": {"token_fetch": True}}
        ):
            self.assertEqual(pipeline.auth_preflight()["auth_status"], "ok")
        with mock.patch.object(pipeline.importlib.metadata, "version", return_value="0.8.1"):
            with self.assertRaisesRegex(pipeline.PipelineError, "must be 0.8.0"):
                pipeline.auth_preflight()

    def test_generation_persists_exact_task_and_source_ids(self) -> None:
        source = pipeline.source_metadata(hebrew_post())
        self.write_posts([hebrew_post()])
        item = pipeline.new_item(source)
        state = {"version": 1, "items": [item], "updated_at": pipeline.utc_now()}
        pipeline.save_state(state)
        with mock.patch.object(pipeline, "run_notebooklm", return_value={"source": {"id": "source-exact"}}):
            pipeline.add_source(state, item)
        self.assertEqual(item["source_id"], "source-exact")
        with mock.patch.object(pipeline, "run_notebooklm", return_value={"task_id": "task-exact"}) as run:
            pipeline.start_generation(state, item)
        self.assertEqual(item["task_id"], "task-exact")
        self.assertEqual(item["artifact_id"], "task-exact")
        self.assertEqual(item["status"], "generating")
        self.assertIn("קול של אישה ישראלית", item["generation_prompt"])
        self.assertEqual(item["generation_prompt_sha256"], pipeline.sha256_text(item["generation_prompt"]))
        arguments = run.call_args.args[0]
        self.assertEqual(arguments[arguments.index("--style") + 1], "auto")
        self.assertNotIn("--style-prompt", arguments)

    def test_rejected_same_day_item_allows_different_unused_source(self) -> None:
        prior_post = hebrew_post(slug="prior")
        prior_post["title"] = "מאמר קודם על הורות"
        prior_source = pipeline.source_metadata(prior_post)
        prior = pipeline.new_item(prior_source)
        prior["status"] = "rejected"
        state = {"version": 1, "items": [prior], "updated_at": pipeline.utc_now()}
        pipeline.save_state(state)

        next_post = hebrew_post(slug="next")
        next_post["title"] = "מאמר חדש על הסתגלות"
        self.write_posts([prior_post, next_post])

        next_source = pipeline.source_metadata(next_post)
        with mock.patch.object(pipeline, "auth_preflight"), mock.patch.object(
            pipeline, "select_newest_unused_article", return_value=next_source
        ) as select, mock.patch.object(pipeline, "add_source"):
            self.assertEqual(pipeline.run_generation(0, None), 0)
        select.assert_called_once()
        saved = pipeline.load_state()["items"]
        self.assertEqual(len(saved), 2)
        self.assertNotEqual(saved[0]["source"]["content_sha256"], saved[1]["source"]["content_sha256"])

    def test_active_item_concurrency_prevention(self) -> None:
        source = pipeline.source_metadata(hebrew_post())
        self.write_posts([hebrew_post()])

        # Test active statuses that skip or resume pipeline
        for status in ("source_selected", "source_added", "generating", "downloaded", "pending_review", "approved", "uploading"):
            item = pipeline.new_item(source)
            item["status"] = status
            if status == "downloaded":
                item["raw_mp4"] = "synthetic-raw.mp4"
            state = {"version": 1, "items": [item], "updated_at": pipeline.utc_now()}
            pipeline.save_state(state)

            with mock.patch.object(pipeline, "auth_preflight"), mock.patch.object(
                pipeline, "select_newest_unused_article"
            ) as select, mock.patch.object(pipeline, "add_source"), mock.patch.object(
                pipeline, "start_generation"
            ), mock.patch.object(pipeline, "wait_for_generation", return_value=False), mock.patch.object(
                pipeline, "validate_and_manifest"
            ):
                self.assertEqual(pipeline.run_generation(0, None), 0)
            select.assert_not_called()

        # Test duplicate active items raises PipelineError
        item1 = pipeline.new_item(source)
        item1["id"] = "video-active-1"
        item1["status"] = "generating"
        item2 = pipeline.new_item(source)
        item2["id"] = "video-active-2"
        item2["status"] = "downloaded"
        state = {"version": 1, "items": [item1, item2], "updated_at": pipeline.utc_now()}
        pipeline.save_state(state)
        with mock.patch.object(pipeline, "auth_preflight"):
            with self.assertRaisesRegex(pipeline.PipelineError, "More than one active video exists"):
                pipeline.run_generation(0, None)

    def test_pending_poll_never_starts_a_second_generation(self) -> None:
        item = {"id": "one", "task_id": "task-one", "status": "generating"}
        state = {"version": 1, "items": [item], "updated_at": pipeline.utc_now()}
        with mock.patch.object(pipeline, "run_notebooklm", return_value={"status": "processing"}) as run:
            self.assertFalse(pipeline.wait_for_generation(state, item, 0))
        run.assert_called_once_with(["artifact", "poll", "task-one", "--notebook", pipeline.NOTEBOOK_ID], timeout=120)
        self.assertEqual(item["status"], "generating")

    def test_technical_validation_rejects_wrong_duration_or_aspect(self) -> None:
        source = pipeline.source_metadata(hebrew_post())
        item = pipeline.new_item(source)
        item.update({"raw_mp4": "raw.mp4", "raw_sha256": "0" * 64})
        state = {"version": 1, "items": [item], "updated_at": pipeline.utc_now()}
        raw = self.state_dir / "raw.mp4"
        raw.parent.mkdir(parents=True)
        raw.write_bytes(b"raw")
        final = self.state_dir / "final.mp4"
        final.write_bytes(b"final")
        review = self.state_dir / "review.png"
        review.write_bytes(b"review")
        frame_dir = self.state_dir / f"{item['id']}-frames"
        frame_dir.mkdir()
        for index in range(1, 5):
            (frame_dir / f"frame-{index}.png").write_bytes(f"frame-{index}".encode())
        with mock.patch.object(pipeline, "render_remotion_video", return_value=final), mock.patch.object(
            pipeline, "ffprobe", return_value={"codec": "h264", "width": 1280, "height": 720, "duration": 60.0, "format": "mp4"}
        ), mock.patch.object(
            pipeline, "create_contact_sheet", return_value=review
        ):
            pipeline.validate_and_manifest(state, item, raw)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "rejected")
        self.assertFalse(saved["technical_verified"])
        self.assertIn("90–180", saved["review_notes"]["technical"])
        self.assertTrue((self.state_dir / saved["manifest_path"]).is_file())

    def make_pending_item(self) -> tuple[dict, dict]:
        source = pipeline.source_metadata(hebrew_post())
        item = pipeline.new_item(source)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        final = self.state_dir / "final.mp4"
        manifest = self.state_dir / "manifest.json"
        review = self.state_dir / "review.png"
        final.write_bytes(b"real-mp4-evidence")
        manifest.write_text("{}", encoding="utf-8")
        review.write_bytes(b"real-review-evidence")
        item.update(
            {
                "status": "pending_review",
                "technical_verified": True,
                "final_mp4": final.name,
                "final_sha256": pipeline.sha256_file(final),
                "manifest_path": manifest.name,
                "manifest_sha256": pipeline.sha256_file(manifest),
                "visual_review_path": review.name,
                "visual_review_sha256": pipeline.sha256_file(review),
                "transcript_path": "transcript.txt",
                "source_path": "source.txt",
                "frame_paths": [f"frames/frame-{index}.png" for index in range(1, 5)],
            }
        )
        (self.state_dir / "transcript.txt").write_text("תמלול עברי מלא לצורך ביקורת סמנטית", encoding="utf-8")
        (self.state_dir / "source.txt").write_text("תוכן מקור עברי מלא לצורך השוואה", encoding="utf-8")
        item["transcript_sha256"] = pipeline.sha256_file(self.state_dir / "transcript.txt")
        item["source_file_sha256"] = pipeline.sha256_file(self.state_dir / "source.txt")
        item["frame_sha256"] = {}
        for relative in item["frame_paths"]:
            path = self.state_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(relative.encode("utf-8"))
            item["frame_sha256"][relative] = pipeline.sha256_file(path)
        state = {"version": 1, "items": [item], "updated_at": pipeline.utc_now()}
        pipeline.save_state(state)
        return state, item

    def test_review_is_atomic_and_requires_hebrew_notes(self) -> None:
        _, item = self.make_pending_item()
        args = SimpleNamespace(
            review_item=item["id"],
            visual_status="approved",
            semantic_status="approved",
            metadata_status="approved",
            visual_note="ארבעת הפריימים נבדקו ואין טקסט חתוך או פריים שחור",
            semantic_note="הווידאו עוסק בדיוק בהסתגלות הילד המתוארת במקור",
            metadata_note="הכותרת התיאור והתגיות בעברית ונתמכים במאמר",
        )
        pipeline.update_review(args)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "approved")
        self.assertEqual(saved["visual_review_status"], "approved")
        self.assertEqual(saved["semantic_review_status"], "approved")
        self.assertEqual(saved["metadata_review_status"], "approved")

    def test_any_rejected_gate_rejects_whole_item(self) -> None:
        _, item = self.make_pending_item()
        args = SimpleNamespace(
            review_item=item["id"],
            visual_status="rejected",
            semantic_status="approved",
            metadata_status="approved",
            visual_note="הפריים השני כולל טקסט חתוך ולכן הסרטון נפסל",
            semantic_note="הנושא תואם למקור",
            metadata_note="המטא־דאטה נתמך במקור",
        )
        pipeline.update_review(args)
        self.assertEqual(pipeline.load_state()["items"][0]["status"], "rejected")

    def test_remotion_rebuild_preserves_rejected_evidence_history(self) -> None:
        state, item = self.make_pending_item()
        raw = self.state_dir / "raw-notebooklm.mp4"
        raw.write_bytes(b"original-notebooklm")
        item.update(
            {
                "status": "rejected",
                "visual_review_status": "rejected",
                "semantic_review_status": "approved",
                "metadata_review_status": "approved",
                "raw_mp4": raw.name,
                "raw_sha256": pipeline.sha256_file(raw),
                "source_id": "source",
                "task_id": "artifact",
                "artifact_id": "artifact",
            }
        )
        pipeline.save_state(state)
        with mock.patch.object(pipeline, "validate_and_manifest") as validate:
            pipeline.rebuild_rejected_with_remotion(item["id"])

        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "downloaded")
        self.assertEqual(saved["visual_review_status"], "pending")
        self.assertEqual(len(saved["evidence_history"]), 1)
        self.assertEqual(saved["evidence_history"][0]["status"], "rejected")
        validate.assert_called_once()

    def test_rejected_review_item_still_uploads_unconditionally(self) -> None:
        state, item = self.make_pending_item()
        item["status"] = "rejected"
        item["visual_review_status"] = "rejected"
        item["semantic_review_status"] = "approved"
        item["metadata_review_status"] = "approved"
        item["youtube_metadata"] = {
            "title": "איך עוזרים לילד להסתגל לשינוי?",
            "description": f"תיאור עברי לקראת העלאה\n{pipeline.SITE_URL}",
            "tags": ["הדרכת הורים"],
        }
        pipeline.save_state(state)

        with mock.patch.object(pipeline, "youtube_access_token", return_value="mock-token"), mock.patch.object(
            pipeline, "verify_authenticated_channel"
        ), mock.patch.object(
            pipeline, "start_resumable_upload", return_value="https://upload.invalid/session"
        ), mock.patch.object(
            pipeline, "upload_bytes", return_value="video123"
        ), mock.patch.object(
            pipeline, "verify_public_upload", return_value={"privacy_status": "public", "processing_status": "succeeded"}
        ):
            self.assertEqual(pipeline.upload_only(), 0)

        saved = pipeline.load_state()["items"][0]
        self.assertTrue(saved["uploaded"])
        self.assertEqual(saved["status"], "uploaded")
        self.assertEqual(saved["youtube_url"], "https://youtu.be/video123")

    def test_rejected_item_remains_active_and_prevents_duplicate_generation(self) -> None:
        source = pipeline.source_metadata(hebrew_post())
        item = pipeline.new_item(source)
        item["status"] = "rejected"
        item["technical_verified"] = True
        state = {"version": 1, "items": [item], "updated_at": pipeline.utc_now()}
        pipeline.save_state(state)

        active = pipeline.active_item(state)
        self.assertIsNotNone(active)
        self.assertEqual(active["id"], item["id"])

        with mock.patch.object(pipeline, "auth_preflight"), mock.patch.object(
            pipeline, "select_newest_unused_article"
        ) as select:
            self.assertEqual(pipeline.run_generation(0, None), 0)
        select.assert_not_called()

    def test_authenticated_channel_must_match_exactly(self) -> None:
        with mock.patch.object(pipeline, "youtube_get", return_value={"items": [{"id": "wrong"}]}):
            with self.assertRaisesRegex(pipeline.PipelineError, "does not match"):
                pipeline.verify_authenticated_channel("token")

    def test_youtube_upload_declares_synthetic_media(self) -> None:
        video = self.state_dir / "final.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"video")
        item = {
            "id": "item",
            "status": "approved",
            "youtube_metadata": {
                "title": "כותרת בעברית",
                "description": "תיאור בעברית",
                "tags": ["זוגיות"],
            },
        }
        state = {"version": 1, "items": [item], "updated_at": pipeline.utc_now()}
        response = SimpleNamespace(status_code=200, headers={"Location": "https://upload.invalid/session"})
        with mock.patch.object(pipeline.requests, "post", return_value=response) as post:
            pipeline.start_resumable_upload(state, item, "token", video)

        self.assertIs(post.call_args.kwargs["json"]["status"]["containsSyntheticMedia"], True)

    def test_expired_resumable_session_fails_closed(self) -> None:
        response = SimpleNamespace(status_code=410, headers={})
        with mock.patch.object(pipeline.requests, "put", return_value=response):
            with self.assertRaisesRegex(pipeline.PipelineError, "refusing a second insert"):
                pipeline.resume_offset("https://upload.invalid/session", "token", 100)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg tools unavailable")
    def test_real_ffmpeg_probe_and_four_frame_evidence(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        raw = self.state_dir / "synthetic.mp4"
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=blue:s=1280x720:r=25",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                "-t", "2", "-c:v", "libx264", "-c:a", "aac", str(raw),
            ],
            check=True,
            timeout=60,
        )
        item = {"id": "media-smoke"}
        media = pipeline.ffprobe(raw)
        self.assertEqual(media["codec"], "h264")
        self.assertEqual(media["audio_codec"], "aac")
        self.assertEqual((media["width"], media["height"]), (1280, 720))
        sheet = pipeline.create_contact_sheet(raw, item, media["duration"])
        self.assertTrue(sheet.is_file())
        self.assertEqual(len(list((self.state_dir / "media-smoke-frames").glob("frame-*.png"))), 4)

    def test_remotion_rebuild_preserves_notebooklm_audio_source(self) -> None:
        raw = self.state_dir / "item-notebooklm.mp4"
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(b"raw-notebooklm-audio")
        output = self.state_dir / "item-remotion-final.mp4"
        item = {
            "id": "item",
            "source": {"title": "כותרת בעברית", "category": "זוגיות"},
        }
        remotion = pipeline.PROJECT_DIR / "node_modules" / ".bin" / "remotion"
        with mock.patch.object(Path, "is_file", autospec=True, side_effect=lambda path: path == remotion), mock.patch.object(
            pipeline, "ffprobe", return_value={"duration": 104.0}
        ), mock.patch.object(pipeline.subprocess, "run") as run:
            def finish(*_args: object, **_kwargs: object) -> SimpleNamespace:
                output.write_bytes(b"rendered-video" * 100)
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            run.side_effect = finish
            rendered = pipeline.render_remotion_video(raw, item)

        self.assertEqual(rendered, output)
        command = run.call_args.args[0]
        self.assertIn("KesherOverview", command)
        self.assertIn(f"--public-dir={self.state_dir}", command)
        props = json.loads((self.state_dir / "item-remotion-props.json").read_text(encoding="utf-8"))
        self.assertEqual(props["videoSrc"], raw.name)
        self.assertEqual(props["audioSrc"], raw.name)
        self.assertIn("motionPlan", props)
        self.assertEqual(props["durationInFrames"], 3120)
        self.assertEqual(props["url"], "kesher.saharoni.com")
        self.assertEqual(item["visual_pipeline"], "remotion-v1-notebooklm-audio")

    def test_motion_plan_generator_data_driven_and_non_semantic(self) -> None:
        video = self.state_dir / "sample-input.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"sample-video-bytes-for-motion-plan")
        plan_path = self.state_dir / "motion-plan.json"

        plan1 = pipeline.generate_motion_plan(video, plan_path)
        plan2 = pipeline.generate_motion_plan(video)

        self.assertEqual(plan1, plan2)
        self.assertTrue(plan_path.is_file())
        self.assertIn("segments", plan1)
        self.assertGreater(len(plan1["segments"]), 0)

        first = plan1["segments"][0]
        for field in ("startFrame", "endFrame", "transformType", "scaleStart", "scaleEnd", "panXStart", "panXEnd", "originX", "originY"):
            self.assertIn(field, first)

        serialized = json.dumps(plan1).lower()
        for forbidden in ("couple", "parent", "child", "card", "zogiot", "horut"):
            self.assertNotIn(forbidden, serialized)

    def test_remotion_props_and_source_video_contract(self) -> None:
        raw = self.state_dir / "test-source-video.mp4"
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(b"test-source-video-content")
        item = {"id": "test-item-123", "source": {"title": "איך להקשיב לילדים", "category": "הורות"}}
        output = self.state_dir / f"{item['id']}-remotion-final.mp4"

        remotion = pipeline.PROJECT_DIR / "node_modules" / ".bin" / "remotion"
        with mock.patch.object(Path, "is_file", autospec=True, side_effect=lambda p: p == remotion), mock.patch.object(
            pipeline, "ffprobe", return_value={"duration": 90.0}
        ), mock.patch.object(pipeline.subprocess, "run") as run:
            def finish(*_args: object, **_kwargs: object) -> SimpleNamespace:
                output.write_bytes(b"rendered-mp4" * 100)
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            run.side_effect = finish
            rendered = pipeline.render_remotion_video(raw, item)

        self.assertEqual(rendered, output)
        props = json.loads((self.state_dir / f"{item['id']}-remotion-props.json").read_text(encoding="utf-8"))
        self.assertEqual(props["videoSrc"], raw.name)
        self.assertIn("motionPlan", props)
        self.assertEqual(props["motionPlan"]["durationInFrames"], 2700)

    def test_prune_uploaded_media_keeps_small_review_evidence(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        for name in ("raw.mp4", "final.mp4", "props.json", "manifest.json", "review.png"):
            (self.state_dir / name).write_bytes(name.encode())
        state = {
            "version": 1,
            "updated_at": pipeline.utc_now(),
            "items": [{
                "id": "uploaded",
                "uploaded": True,
                "youtube_verification": {"privacy_status": "public"},
                "raw_mp4": "raw.mp4",
                "final_mp4": "final.mp4",
                "remotion_props_path": "props.json",
                "manifest_path": "manifest.json",
                "visual_review_path": "review.png",
            }],
        }
        pipeline.save_state(state)
        pipeline.prune_uploaded_media()
        self.assertFalse((self.state_dir / "raw.mp4").exists())
        self.assertFalse((self.state_dir / "final.mp4").exists())
        self.assertFalse((self.state_dir / "props.json").exists())
        self.assertTrue((self.state_dir / "manifest.json").exists())
        self.assertTrue((self.state_dir / "review.png").exists())

    def test_jules_decision_requires_all_exact_hashes_and_four_observations(self) -> None:
        hashes = {
            "manifest_sha256": "a" * 64,
            "final_sha256": "b" * 64,
            "transcript_sha256": "c" * 64,
            "source_file_sha256": "d" * 64,
            "visual_review_sha256": "e" * 64,
            "frame_sha256": {f"frames/frame-{i}.png": str(i) * 64 for i in range(1, 5)},
        }
        decision = {
            "item_id": "item-1",
            **hashes,
            "frame_observations": [
                "נראית סצנה ביתית ברורה ללא טקסט חתוך בפריים הזה"
                for _ in range(4)
            ],
            "visual_status": "approved",
            "semantic_status": "approved",
            "metadata_status": "approved",
            "visual_note": "ארבעת הפריימים תקינים ללא אנגלית ג׳יבריש או מסכים שחורים",
            "semantic_note": "התמלול והסצנות עוסקים בדיוק בנושא ההסתגלות שבמאמר המקור",
            "metadata_note": "הכותרת התיאור וכל התגיות בעברית ונתמכים ישירות במקור",
        }
        reviewer.validate_decision(decision, {"id": "item-1"}, hashes)
        decision["final_sha256"] = "e" * 64
        with self.assertRaisesRegex(reviewer.ReviewError, "final_sha256"):
            reviewer.validate_decision(decision, {"id": "item-1"}, hashes)

    def test_jules_message_must_end_in_parseable_marked_json(self) -> None:
        payload = {"item_id": "item-1"}
        message = f"בדיקה הושלמה\n{reviewer.FINAL_MARKER}\n{json.dumps(payload)}"
        self.assertEqual(reviewer.parse_decision(message), payload)
        with self.assertRaises(reviewer.ReviewError):
            reviewer.parse_decision(f"{reviewer.FINAL_MARKER}\nnot-json")

    def test_jules_message_accepts_fenced_json_with_trailing_text(self) -> None:
        payload = {"item_id": "item-1", "visual_status": "rejected"}
        message = (
            f"{reviewer.FINAL_MARKER}\n```json\n"
            f"{json.dumps(payload)}\n```\nהביקורת הסתיימה"
        )
        self.assertEqual(reviewer.parse_decision(message), payload)

    @mock.patch.object(reviewer, "request_json")
    @mock.patch.object(reviewer, "list_activities")
    def test_jules_wait_uses_last_parseable_marked_message(
        self,
        activities: mock.Mock,
        request: mock.Mock,
    ) -> None:
        payload = {"item_id": "item-1", "visual_status": "rejected"}
        valid = f"{reviewer.FINAL_MARKER}\n{json.dumps(payload)}"
        trailing_prose = (
            "The review is complete and the KESHER_REVIEW_JSON was already provided."
        )
        request.return_value = {"state": "COMPLETED"}
        activities.return_value = [
            {"agentMessaged": {"agentMessage": valid}},
            {"agentMessaged": {"agentMessage": trailing_prose}},
        ]

        selected = reviewer.wait_for_message("key", "sessions/1", 1)

        self.assertEqual(selected, valid)
        self.assertEqual(reviewer.parse_decision(selected), payload)

    def test_jules_evidence_tree_excludes_video_and_verifies_hashes(self) -> None:
        _, item = self.make_pending_item()
        raw = self.state_dir / "raw.mp4"
        raw.write_bytes(b"raw-video-must-not-be-published")
        item["raw_mp4"] = raw.name
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})
        output = self.root / "evidence"
        prepared = evidence.prepare(self.state_dir, output)
        self.assertEqual(prepared["id"], item["id"])
        self.assertFalse((output / raw.name).exists())
        self.assertFalse((output / item["final_mp4"]).exists())
        self.assertTrue((output / item["manifest_path"]).is_file())
        self.assertEqual(len(list(output.glob("**/frame-*.png"))), 4)
        published_state = json.loads((output / "state.json").read_text(encoding="utf-8"))
        self.assertNotIn("raw_mp4", published_state["items"][0])
        self.assertNotIn("final_mp4", published_state["items"][0])


if __name__ == "__main__":
    unittest.main()

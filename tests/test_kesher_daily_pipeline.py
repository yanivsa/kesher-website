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
        for index in range(1, 9):
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
                "frame_paths": [f"frames/frame-{index}.png" for index in range(1, 9)],
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

    def test_remotion_rebuild_redownloads_raw_if_missing(self) -> None:
        state, item = self.make_pending_item()
        item.update(
            {
                "status": "rejected",
                "visual_review_status": "rejected",
                "semantic_review_status": "approved",
                "metadata_review_status": "approved",
                "raw_mp4": "missing.mp4",
                "raw_sha256": "fake-hash",
                "source_id": "source",
                "task_id": "artifact",
                "artifact_id": "artifact",
            }
        )
        pipeline.save_state(state)

        with mock.patch.object(pipeline, "run_notebooklm") as mock_run:
            def side_effect(args, **kwargs):
                if args[0] == "download":
                    path = Path(args[2])
                    path.write_bytes(b"downloaded-notebooklm" * 100)
                return {}
            mock_run.side_effect = side_effect

            with mock.patch.object(pipeline, "validate_and_manifest") as validate:
                pipeline.rebuild_rejected_with_remotion(item["id"])

        mock_run.assert_called_once()
        self.assertIn("download", mock_run.call_args[0][0])
        self.assertIn("artifact", mock_run.call_args[0][0])

        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "downloaded")
        self.assertEqual(saved["visual_review_status"], "pending")
        raw_path = pipeline.STATE_DIR / saved["raw_mp4"]
        self.assertTrue(raw_path.exists())

    def test_remotion_rebuild_preserves_superseded_youtube_id(self) -> None:
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
                "uploaded": True,
                "youtube_id": "old-youtube-id",
            }
        )
        pipeline.save_state(state)
        with mock.patch.object(pipeline, "validate_and_manifest") as validate:
            pipeline.rebuild_rejected_with_remotion(item["id"])

        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "downloaded")
        self.assertEqual(saved["visual_review_status"], "pending")
        self.assertFalse(saved["uploaded"])
        self.assertNotIn("youtube_id", saved)
        self.assertEqual(len(saved["superseded_history"]), 1)
        self.assertEqual(saved["superseded_history"][0]["youtube_id"], "old-youtube-id")
        self.assertEqual(saved["superseded_history"][0]["reason"], "superseded_by_rebuild")

    def test_rejected_review_item_does_not_upload(self) -> None:
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
        self.assertFalse(saved.get("uploaded", False))
        self.assertEqual(saved["status"], "rejected")
        self.assertNotIn("youtube_url", saved)

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
    def test_real_ffmpeg_probe_and_eight_frame_evidence(self) -> None:
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
        self.assertEqual(len(list((self.state_dir / "media-smoke-frames").glob("frame-*.png"))), 8)

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

    def test_motion_plan_tracks_high_contrast_target_region(self) -> None:
        from motion_plan_generator import analyze_frame_saliency, ANALYSIS_W, ANALYSIS_H

        # Construct frame with high contrast detail in TOP-RIGHT quadrant
        top_right_pixels = bytearray(ANALYSIS_W * ANALYSIS_H)
        for y in range(10, 40):
            for x in range(100, 150):
                top_right_pixels[y * ANALYSIS_W + x] = 255 if (x + y) % 2 == 0 else 0

        saliency_top_right = analyze_frame_saliency(bytes(top_right_pixels))
        self.assertGreater(saliency_top_right["originX"], 60.0)
        self.assertLess(saliency_top_right["originY"], 45.0)

        # Construct frame with high contrast detail in BOTTOM-LEFT quadrant
        bottom_left_pixels = bytearray(ANALYSIS_W * ANALYSIS_H)
        for y in range(50, 80):
            for x in range(10, 50):
                bottom_left_pixels[y * ANALYSIS_W + x] = 255 if (x + y) % 2 == 0 else 0

        saliency_bottom_left = analyze_frame_saliency(bytes(bottom_left_pixels))
        self.assertLess(saliency_bottom_left["originX"], 40.0)
        self.assertGreater(saliency_bottom_left["originY"], 55.0)

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
        self.assertEqual(item["motion_plan_path"], f"{item['id']}-motion-plan.json")
        self.assertTrue((self.state_dir / item["motion_plan_path"]).is_file())

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

    def test_jules_decision_requires_all_exact_hashes_and_eight_observations(self) -> None:
        hashes = {
            "manifest_sha256": "a" * 64,
            "final_sha256": "b" * 64,
            "transcript_sha256": "c" * 64,
            "source_file_sha256": "d" * 64,
            "visual_review_sha256": "e" * 64,
            "frame_sha256": {f"frames/frame-{i}.png": str(i) * 64 for i in range(1, 9)},
        }
        decision = {
            "item_id": "item-1",
            **hashes,
            "frame_observations": [
                "נראית סצנה ביתית ברורה ללא טקסט חתוך בפריים הזה"
                for _ in range(8)
            ],
            "visual_status": "approved",
            "semantic_status": "approved",
            "metadata_status": "approved",
            "visual_note": "שמונת הפריימים תקינים ללא אנגלית ג׳יבריש או מסכים שחורים",
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
        self.assertEqual(len(list(output.glob("**/frame-*.png"))), 8)
        published_state = json.loads((output / "state.json").read_text(encoding="utf-8"))
        self.assertNotIn("raw_mp4", published_state["items"][0])
        self.assertNotIn("final_mp4", published_state["items"][0])

    def test_jules_review_parse_failure_remains_blocked_from_upload(self) -> None:
        _, item = self.make_pending_item()
        error_msg = "Jules completed without parseable structured review JSON"
        handled = reviewer.handle_non_fatal_review_error(self.state_dir, error_msg)
        self.assertTrue(handled)

        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["visual_review_status"], "unavailable")
        self.assertIn("סקירת ג׳ולס לא הושלמה", saved["review_notes"]["visual"])

        with mock.patch.object(pipeline, "youtube_access_token", return_value="mock-token"), mock.patch.object(
            pipeline, "verify_authenticated_channel"
        ), mock.patch.object(
            pipeline, "start_resumable_upload", return_value="https://upload.invalid/session"
        ), mock.patch.object(
            pipeline, "upload_bytes", return_value="video-parse-fail"
        ), mock.patch.object(
            pipeline, "verify_public_upload", return_value={"privacy_status": "public", "processing_status": "succeeded"}
        ):
            self.assertEqual(pipeline.upload_only(), 0)

        blocked = pipeline.load_state()["items"][0]
        self.assertFalse(blocked.get("uploaded", False))
        self.assertNotIn("youtube_url", blocked)

    def test_jules_review_api_timeout_remains_blocked_from_upload(self) -> None:
        _, item = self.make_pending_item()
        error_msg = "Jules review timed out"
        handled = reviewer.handle_non_fatal_review_error(self.state_dir, error_msg)
        self.assertTrue(handled)

        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["visual_review_status"], "unavailable")

        with mock.patch.object(pipeline, "youtube_access_token", return_value="mock-token"), mock.patch.object(
            pipeline, "verify_authenticated_channel"
        ), mock.patch.object(
            pipeline, "start_resumable_upload", return_value="https://upload.invalid/session"
        ), mock.patch.object(
            pipeline, "upload_bytes", return_value="video-timeout"
        ), mock.patch.object(
            pipeline, "verify_public_upload", return_value={"privacy_status": "public", "processing_status": "succeeded"}
        ):
            self.assertEqual(pipeline.upload_only(), 0)

        blocked = pipeline.load_state()["items"][0]
        self.assertFalse(blocked.get("uploaded", False))
        self.assertNotIn("youtube_url", blocked)

    def test_jules_valid_rejected_review_preserves_review_and_blocks_upload(self) -> None:
        _, item = self.make_pending_item()
        args = SimpleNamespace(
            review_item=item["id"],
            visual_status="rejected",
            semantic_status="approved",
            metadata_status="approved",
            visual_note="הפריים השני אינו קריא בסלולר ולכן נפסל",
            semantic_note="תומך במאמר المקור",
            metadata_note="המטא־דאטה תקין",
        )
        pipeline.update_review(args)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "rejected")
        self.assertEqual(saved["visual_review_status"], "rejected")

        with mock.patch.object(pipeline, "youtube_access_token", return_value="mock-token"), mock.patch.object(
            pipeline, "verify_authenticated_channel"
        ), mock.patch.object(
            pipeline, "start_resumable_upload", return_value="https://upload.invalid/session"
        ), mock.patch.object(
            pipeline, "upload_bytes", return_value="video-rejected"
        ), mock.patch.object(
            pipeline, "verify_public_upload", return_value={"privacy_status": "public", "processing_status": "succeeded"}
        ):
            self.assertEqual(pipeline.upload_only(), 0)

        blocked = pipeline.load_state()["items"][0]
        self.assertFalse(blocked.get("uploaded", False))
        self.assertEqual(blocked["status"], "rejected")
        self.assertNotIn("youtube_url", blocked)

    def test_jules_valid_approved_review_preserves_review_and_upload_eligible(self) -> None:
        _, item = self.make_pending_item()
        args = SimpleNamespace(
            review_item=item["id"],
            visual_status="approved",
            semantic_status="approved",
            metadata_status="approved",
            visual_note="כל הפריימים נבדקו ואושר למאמר",
            semantic_note="תואם למקור",
            metadata_note="המטא־דאטה בעברית",
        )
        pipeline.update_review(args)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "approved")

        with mock.patch.object(pipeline, "youtube_access_token", return_value="mock-token"), mock.patch.object(
            pipeline, "verify_authenticated_channel"
        ), mock.patch.object(
            pipeline, "start_resumable_upload", return_value="https://upload.invalid/session"
        ), mock.patch.object(
            pipeline, "upload_bytes", return_value="video-approved"
        ), mock.patch.object(
            pipeline, "verify_public_upload", return_value={"privacy_status": "public", "processing_status": "succeeded"}
        ):
            self.assertEqual(pipeline.upload_only(), 0)

        uploaded = pipeline.load_state()["items"][0]
        self.assertTrue(uploaded["uploaded"])

    def test_technical_verification_failure_fatal_and_blocks_upload(self) -> None:
        state, item = self.make_pending_item()
        item["technical_verified"] = False
        pipeline.save_state(state)

        handled = reviewer.handle_non_fatal_review_error(self.state_dir, "technical error")
        self.assertFalse(handled)

        with mock.patch.object(pipeline, "youtube_access_token", return_value="mock-token"):
            self.assertEqual(pipeline.upload_only(), 0)

        saved = pipeline.load_state()["items"][0]
        self.assertFalse(saved.get("uploaded", False))

    def test_durable_remotion_policy_file_exists_and_contains_required_rules(self) -> None:
        policy_path = pipeline.PROJECT_DIR / ".github" / "prompts" / "jules-remotion-video-upgrade.md"
        self.assertTrue(policy_path.is_file())
        text = policy_path.read_text(encoding="utf-8")

        # Core product rule
        self.assertIn("EXISTING NotebookLM MP4", text)
        self.assertIn("100% of the timeline", text)

        # Captions restriction
        self.assertIn("DO NOT use `remotion-captions`", text)

        # Official Agent Skills routing
        for skill in (
            "remotion-best-practices",
            "remotion-markup",
            "remotion-docs",
            "remotion-render",
            "remotion-multimedia",
            "remotion-studio",
        ):
            self.assertIn(skill, text)

        # CSS transitions/animations restriction
        self.assertIn("DO NOT use CSS transitions", text)

        # Female voice requirement
        self.assertIn("השתמש בקול של אישה ישראלית", text)

        # Mandatory review and policy gates
        self.assertIn("Upload must require explicit approved technical, visual, semantic, and metadata gates.", text)
        self.assertIn("Strict mandatory visual rejection language for slide/card-like", text)

    def test_reviewer_prompt_evaluates_source_video_first_and_no_invented_objects(self) -> None:
        hashes = {
            "manifest_sha256": "a" * 64,
            "final_sha256": "b" * 64,
            "transcript_sha256": "c" * 64,
            "source_file_sha256": "d" * 64,
            "visual_review_sha256": "e" * 64,
            "frame_sha256": {
                f"frames/frame-{i}.png": str(i) * 64
                for i in range(1, pipeline.REVIEW_FRAME_COUNT + 1)
            },
        }
        item = {"id": "item-prompt-test"}
        prompt = reviewer.build_prompt("evidence-root", item, hashes)

        # Frame count wording and JSON shape must derive from the shared constant.
        self.assertIn(
            f"inspect EACH of its {pipeline.REVIEW_FRAME_COUNT} `frame_paths`",
            prompt,
        )
        self.assertEqual(reviewer.REVIEW_FRAME_COUNT, pipeline.REVIEW_FRAME_COUNT)

        # Durable policy is injected into the actual reviewer prompt.
        self.assertIn("100% Visual Continuity", prompt)
        self.assertIn("DO NOT use `remotion-captions`", prompt)
        self.assertIn("already exists inside the pixels of the NotebookLM source MP4", prompt)
        self.assertIn("`remotion-upgrade`", prompt)

        # Female voice requirement is preserved.
        self.assertIn("השתמש בקול של אישה ישראלית", prompt)

        # Old invented-object guidance is not reintroduced outside the policy prohibition.
        for removed in ("phone, bill, table", "parenting object, calendar"):
            self.assertNotIn(removed, prompt)



    def test_workflow_restore_skips_invalid_state_and_restores_valid_older(self) -> None:
        import subprocess
        import tempfile
        import json
        import os
        from pathlib import Path

        workflow_path = Path(".github/workflows/kesher-daily-video.yml")
        workflow = workflow_path.read_text(encoding="utf-8")

        start_idx = workflow.find("- name: Restore newest valid durable pipeline state")
        self.assertNotEqual(start_idx, -1)
        run_idx = workflow.find("run: |", start_idx)
        self.assertNotEqual(run_idx, -1)
        end_idx = workflow.find("- name: Seed an exact orphaned-task recovery state", run_idx)

        script = workflow[run_idx + 6:end_idx].strip()
        lines = script.split("\n")
        indent = len(lines[0]) - len(lines[0].lstrip())
        script = "\n".join(line[indent:] if line.startswith(" " * indent) else line for line in lines)

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)

            mock_bin = td_path / "bin"
            mock_bin.mkdir()

            gh_mock = mock_bin / "gh"
            gh_mock.write_text('''#!/usr/bin/env bash
if [[ "$*" == *"actions/artifacts?name=kesher-video-state"* ]]; then
    echo '[{"id": 3, "created_at": "2023-10-03"}, {"id": 2, "created_at": "2023-10-02"}, {"id": 1, "created_at": "2023-10-01"}]' | jq '[.[] | select(.expired != true)] | sort_by(.created_at) | reverse | .[].id'
    exit_cmd=exit
    $exit_cmd 0
fi

if [[ "$*" == *"actions/artifacts/3/zip"* ]]; then
    echo "bad zip data"
    exit_cmd=exit
    $exit_cmd 0
fi

if [[ "$*" == *"actions/artifacts/2/zip"* ]]; then
    mkdir -p "$KESHER_STATE_DIR"
    echo '{"bad_json": }' > "$KESHER_STATE_DIR/temp2.json"
    cd "$KESHER_STATE_DIR" && zip -q -0 zip2.zip temp2.json && mv zip2.zip "$KESHER_STATE_DIR/out2.zip"
    cat "$KESHER_STATE_DIR/out2.zip"
    exit_cmd=exit
    $exit_cmd 0
fi

if [[ "$*" == *"actions/artifacts/1/zip"* ]]; then
    mkdir -p "$KESHER_STATE_DIR"
    echo '{"valid": true}' > "$KESHER_STATE_DIR/state.json"
    cd "$KESHER_STATE_DIR" && zip -q -0 zip1.zip state.json && mv zip1.zip "$KESHER_STATE_DIR/out1.zip"
    cat "$KESHER_STATE_DIR/out1.zip"
    exit_cmd=exit
    $exit_cmd 0
fi

echo "Unexpected gh call: $*" >&2
exit_cmd=exit
$exit_cmd 1
''')
            gh_mock.chmod(0o755)

            python_mock = mock_bin / "python"
            python_mock.write_text('''#!/usr/bin/env bash
if [[ "$*" == *"--report-json"* ]]; then
    echo "mocked report"
    exit_cmd=exit
    $exit_cmd 0
fi
exec /usr/bin/python3 "$@"
''')
            python_mock.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"
            env["GITHUB_REPOSITORY"] = "test/repo"
            env["KESHER_STATE_DIR"] = str(td_path / "state")

            result = subprocess.run(
                ["bash", "-c", script],
                env=env,
                capture_output=True,
                text=True
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Attempting to restore state artifact 3", result.stdout)
            self.assertIn("Attempting to restore state artifact 2", result.stdout)
            self.assertIn("Attempting to restore state artifact 1", result.stdout)
            self.assertIn("Restored valid state artifact 1", result.stdout)

            state_json = td_path / "state" / "state.json"
            self.assertTrue(state_json.exists())
            self.assertEqual(json.loads(state_json.read_text())["valid"], True)

    def test_workflow_restore_starts_fresh_if_no_valid_artifact(self) -> None:
        import subprocess
        import tempfile
        import json
        import os
        from pathlib import Path

        workflow_path = Path(".github/workflows/kesher-daily-video.yml")
        workflow = workflow_path.read_text(encoding="utf-8")

        start_idx = workflow.find("- name: Restore newest valid durable pipeline state")
        self.assertNotEqual(start_idx, -1)
        run_idx = workflow.find("run: |", start_idx)
        end_idx = workflow.find("- name: Seed an exact orphaned-task recovery state", run_idx)
        script = workflow[run_idx + 6:end_idx].strip()
        lines = script.split("\n")
        indent = len(lines[0]) - len(lines[0].lstrip())
        script = "\n".join(line[indent:] if line.startswith(" " * indent) else line for line in lines)

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)

            mock_bin = td_path / "bin"
            mock_bin.mkdir()

            gh_mock = mock_bin / "gh"
            gh_mock.write_text('''#!/usr/bin/env bash
if [[ "$*" == *"actions/artifacts?name=kesher-video-state"* ]]; then
    echo '[{"id": 1, "created_at": "2023-10-01"}]' | jq '[.[] | select(.expired != true)] | sort_by(.created_at) | reverse | .[].id'
    exit_cmd=exit
    $exit_cmd 0
fi

if [[ "$*" == *"actions/artifacts/1/zip"* ]]; then
    mkdir -p "$KESHER_STATE_DIR"
    echo '{"bad_json": }' > "$KESHER_STATE_DIR/temp1.json"
    cd "$KESHER_STATE_DIR" && zip -q -0 zip1.zip temp1.json && mv zip1.zip "$KESHER_STATE_DIR/out1.zip"
    cat "$KESHER_STATE_DIR/out1.zip"
    exit_cmd=exit
    $exit_cmd 0
fi

echo "Unexpected gh call: $*" >&2
exit_cmd=exit
$exit_cmd 1
''')
            gh_mock.chmod(0o755)

            python_mock = mock_bin / "python"
            python_mock.write_text('''#!/usr/bin/env bash
exec /usr/bin/python3 "$@"
''')
            python_mock.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"
            env["GITHUB_REPOSITORY"] = "test/repo"
            env["KESHER_STATE_DIR"] = str(td_path / "state")

            result = subprocess.run(
                ["bash", "-c", script],
                env=env,
                capture_output=True,
                text=True
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Attempting to restore state artifact 1", result.stdout)
            self.assertIn("Artifact 1 is missing or has invalid state.json", result.stdout)
            self.assertIn("No valid state.json found in any unexpired artifact", result.stdout)

if __name__ == "__main__":
    unittest.main()

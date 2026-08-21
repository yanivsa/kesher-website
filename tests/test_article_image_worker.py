from __future__ import annotations

import importlib.util
import inspect
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / ".github" / "scripts" / "article-image-worker-v3.py"
PRODUCTION_WORKER_PATH = ROOT / ".github" / "scripts" / "article-image-worker-v4.py"
CONTROLLER_PATH = ROOT / ".github" / "scripts" / "article-pr-controller-v3.py"
VALIDATOR_PATH = ROOT / ".github" / "scripts" / "validate-article-pr.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "kesher-article-image.yml"
CONTRACT_PATH = ROOT / "config" / "kesher-production-contract.json"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fake_png(width: int = 1200, height: int = 675) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", width, height) + b"fixture"


class ArticleImageWorkerTests(unittest.TestCase):
    def test_contract_caps_every_stage_at_three_total_attempts(self):
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["controller_state_schema_version"], 3)
        self.assertEqual(contract["retry"]["max_attempts_per_stage"], 3)
        self.assertEqual(contract["retry"]["backoff_minutes"], [5, 15])
        self.assertTrue(contract["retry"]["attempts_include_initial_run"])
        self.assertEqual(contract["image"]["max_attempts"], 3)
        self.assertEqual(contract["image"]["worker_attempts_per_dispatch"], 1)

    def test_provider_order_ends_in_guaranteed_local_fallback(self):
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["image"]["provider_order"], ["gemini", "unsplash", "pexels", "local-curated"])
        self.assertTrue(contract["image"]["fallback_must_be_local"])
        self.assertTrue(contract["image"]["no_image_publication_allowed"])
        self.assertFalse(contract["image"]["publication_blocking"])
        self.assertEqual(contract["image"]["gemini_model"], "gemini-3.1-flash-image")
        self.assertEqual(contract["image"]["visual_verifier_model"], "gemini-3.5-flash")
        self.assertTrue(contract["image"]["external_stock_requires_pixel_verification"])

    def test_all_external_failures_fall_through_to_local(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_fallback_test")
        calls = []
        worker.try_gemini = lambda post, attempts: (attempts.append("gemini"), calls.append("gemini"), None)[2]
        worker.try_unsplash = lambda post, attempts: (attempts.append("unsplash"), calls.append("unsplash"), None)[2]
        worker.try_pexels = lambda post, attempts: (attempts.append("pexels"), calls.append("pexels"), None)[2]
        worker.local_fallback = lambda repo, post, ref, token, attempts: worker.core.ImageCandidate(
            "Local", fake_png(), "png", "local://public/images/generated/blog/listening-in-relationships.jpg",
            "זוג בשיחה פנים אל פנים המדגישה הקשבה ותקשורת באופן ברור", attempts + ["local-curated"]
        )
        candidate = worker.choose_candidate("o/r", {"title": "שיחה זוגית", "id": "x"}, "sha", "token")
        self.assertEqual(calls, ["gemini", "unsplash", "pexels"])
        self.assertEqual(candidate.provider, "Local")
        self.assertEqual(candidate.attempts, ["gemini", "unsplash", "pexels", "local-curated"])

    def test_local_fallback_reads_only_from_trusted_checkout(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_trusted_checkout_test")
        with tempfile.TemporaryDirectory() as tmp:
            worker.REPO_ROOT = Path(tmp)
            source_path, _description = worker.core.LOCAL_FALLBACKS["couples"]
            target = worker.REPO_ROOT / source_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(fake_png())
            with mock.patch.object(worker.core, "github_content", side_effect=AssertionError("local fallback must not use GitHub API")):
                candidate = worker.local_fallback(
                    "o/r", {"title": "שיחה", "id": "x"}, "untrusted-pr-sha", "t", []
                )
        self.assertEqual(candidate.provider, "Local")
        self.assertEqual(candidate.data, fake_png())
        self.assertEqual(candidate.attempts, ["local-curated"])

    def test_provider_preflight_never_requires_external_secrets(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_preflight_test")
        with mock.patch.dict("os.environ", {}, clear=True):
            availability = worker.provider_preflight()
        self.assertEqual(availability, {"gemini": False, "unsplash": False, "pexels": False, "local": True})

    def test_gemini_generation_uses_current_official_generate_content_shape(self):
        source = WORKER_PATH.read_text(encoding="utf-8")
        self.assertIn(f"/v1/models/{{GEMINI_MODEL}}:generateContent", source)
        self.assertIn('"responseModalities": ["IMAGE"]', source)
        self.assertIn('"responseFormat": {"image": {"aspectRatio": "16:9"}}', source)
        self.assertIn('part.get("inlineData")', source)
        self.assertNotIn("/v1beta/interactions", source)

    def test_external_stock_is_never_accepted_from_search_metadata_alone(self):
        source = WORKER_PATH.read_text(encoding="utf-8")
        self.assertIn("verify_pixels(post, data, ext)", source)
        self.assertIn("if not google_key():\n        return None", source)
        self.assertIn("Do not claim anything not visible", source)

    def test_partial_github_failure_is_recoverable_by_writing_evidence_before_commit(self):
        worker = load(WORKER_PATH, "article_image_worker_v3_atomicity_test")
        source = inspect.getsource(worker.ensure_image)
        self.assertLess(source.index("patch_pr_body"), source.index("commit_files("))
        self.assertIn("trusted_image_present", source)

    def test_summary_generation_matches_publishable_content_policy(self):
        worker = load(WORKER_PATH, "article_image_worker_v3_summary_test")
        thick = {
            "id": "thick", "title": "כותרת", "date": "2026-08-20", "category": "זוגיות",
            "excerpt": "תקציר", "content": "<p>" + ("מילה " * 500) + "</p>" + ("<h3>שאלה</h3>" * 5),
        }
        thin = {
            "id": "thin", "title": "ישן", "date": "2024-01-01", "category": "זוגיות",
            "excerpt": "ישן", "content": "<p>קצר</p>",
        }
        self.assertEqual([row["id"] for row in worker.summaries([thick, thin])], ["thick"])

    def test_worker_accepts_only_article_sized_png_or_jpeg(self):
        worker = load(WORKER_PATH, "article_image_worker_v3_dimensions_test")
        self.assertEqual(worker.core.validate_candidate(fake_png())[:2], (1200, 675))
        with self.assertRaisesRegex(RuntimeError, "too small"):
            worker.core.validate_candidate(fake_png(320, 180))

    def test_production_article_gate_allows_no_image(self):
        controller = load(CONTROLLER_PATH, "article_controller_best_effort_test")
        validator = controller.load_validator_best_effort()
        base = [{"id": "old"}]
        new = {
            "id": "new", "title": "כותרת", "date": "2026-08-20", "category": "זוגיות",
            "excerpt": "תקציר", "content": "<p>" + ("מילה " * 700) + "</p>" + ("<h3>שאלה</h3>" * 5),
        }
        pr = {
            "state": "open", "draft": False, "title": "Publish Kesher article: new", "body": "",
            "base": {"ref": "main", "repo": {"full_name": "x/y"}},
            "head": {"repo": {"full_name": "x/y"}},
        }
        errors = validator.evaluate(
            pr,
            [{"filename": "src/data/posts.json"}],
            [{"name": "verify", "conclusion": "success"}],
            base,
            base + [new],
            lambda _: b"",
        )
        self.assertFalse(any("no-image publication is forbidden" in error for error in errors), errors)

    def test_workflow_is_controller_owned_and_executes_only_trusted_main_worker(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        trigger = workflow.split("permissions:", 1)[0]
        self.assertNotIn("pull_request_target:", trigger)
        self.assertIn("workflow_dispatch:", trigger)
        self.assertIn("run-name: Kesher Image PR", workflow)
        self.assertIn("ref: main", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("article-image-worker-v4.py", workflow)
        self.assertIn("GOOGLE_API_KEY", workflow)
        self.assertIn("UNSPLASH_ACCESS_KEY", workflow)
        self.assertIn("PEXELS_API_KEY", workflow)
        self.assertIn("actions/workflows/ci.yml/dispatches", workflow)
        self.assertNotIn("actions/checkout@v", workflow)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / ".github" / "scripts" / "article-image-worker.py"
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
        self.assertEqual(contract["retry"]["max_attempts_per_stage"], 3)
        self.assertEqual(contract["retry"]["backoff_minutes"], [5, 15])
        self.assertTrue(contract["retry"]["attempts_include_initial_run"])
        self.assertEqual(contract["image"]["max_attempts"], 3)
        self.assertEqual(contract["image"]["worker_attempts_per_dispatch"], 1)

    def test_provider_order_ends_in_guaranteed_local_fallback(self):
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["image"]["provider_order"], ["gemini", "unsplash", "pexels", "local-curated"])
        self.assertTrue(contract["image"]["fallback_must_be_local"])
        self.assertFalse(contract["image"]["no_image_publication_allowed"])
        self.assertEqual(contract["image"]["gemini_model"], "gemini-3.1-flash-image")

    def test_all_external_failures_fall_through_to_local(self):
        worker = load(WORKER_PATH, "article_image_worker_test")
        calls = []
        worker.try_gemini = lambda post, attempts: (attempts.append("gemini"), calls.append("gemini"), None)[2]
        worker.try_unsplash = lambda post, attempts: (attempts.append("unsplash"), calls.append("unsplash"), None)[2]
        worker.try_pexels = lambda post, attempts: (attempts.append("pexels"), calls.append("pexels"), None)[2]
        worker.local_fallback = lambda repo, post, ref, token, attempts: worker.ImageCandidate(
            "Local", fake_png(), "png", "local://public/images/generated/blog/listening-in-relationships.jpg",
            "זוג בשיחה פנים אל פנים המדגישה הקשבה ותקשורת באופן ברור", attempts + ["local-curated"]
        )
        candidate = worker.choose_candidate("o/r", {"title": "שיחה זוגית", "id": "x"}, "sha", "token")
        self.assertEqual(calls, ["gemini", "unsplash", "pexels"])
        self.assertEqual(candidate.provider, "Local")
        self.assertEqual(candidate.attempts, ["gemini", "unsplash", "pexels", "local-curated"])

    def test_worker_accepts_only_article_sized_png_or_jpeg(self):
        worker = load(WORKER_PATH, "article_image_worker_dimensions_test")
        self.assertEqual(worker.validate_candidate(fake_png())[:2], (1200, 675))
        with self.assertRaisesRegex(RuntimeError, "too small"):
            worker.validate_candidate(fake_png(320, 180))

    def test_validator_forbids_no_image_publication(self):
        validator = load(VALIDATOR_PATH, "article_validator_image_test")
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
        errors = validator.evaluate(pr, [{"filename": "src/data/posts.json"}], [{"name": "verify", "conclusion": "success"}], base, base + [new], lambda _: b"")
        self.assertTrue(any("no-image publication is forbidden" in error for error in errors), errors)

    def test_workflow_executes_only_trusted_main_worker_and_dispatches_fresh_ci(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("pull_request_target:", workflow)
        self.assertIn("ref: main", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("article-image-worker.py", workflow)
        self.assertIn("GOOGLE_API_KEY", workflow)
        self.assertIn("UNSPLASH_ACCESS_KEY", workflow)
        self.assertIn("PEXELS_API_KEY", workflow)
        self.assertIn("actions/workflows/ci.yml/dispatches", workflow)
        self.assertNotIn("actions/checkout@v", workflow)


if __name__ == "__main__":
    unittest.main()

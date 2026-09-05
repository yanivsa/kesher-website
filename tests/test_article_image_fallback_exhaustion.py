from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / ".github" / "scripts" / "article-image-worker-v4.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "kesher-article-image.yml"


def load_worker():
    spec = importlib.util.spec_from_file_location("article_image_worker_v4_exhaustion_test", WORKER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ArticleImageFallbackExhaustionTests(unittest.TestCase):
    def test_local_fallback_remains_available_after_all_curated_candidates_collide(self):
        worker = load_worker()
        curated_hashes = {
            hashlib.sha256((ROOT / source_path).read_bytes()).hexdigest()
            for candidates in worker.LOCAL_FALLBACK_CANDIDATES.values()
            for source_path, _description in candidates
        }
        post = {
            "id": "unattached-adults-missed-chances-regrets",
            "title": "התמודדות עם תחושת החמצה ברווקות מאוחרת",
        }
        candidate = worker.local_fallback(
            "yanivsa/kesher-website",
            post,
            "sha",
            "token",
            [],
            existing_hashes=curated_hashes,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        width, height, ext = worker.core.validate_candidate(candidate.data)
        self.assertEqual((width, height), (1200, 675))
        self.assertEqual(ext, "png")
        self.assertEqual(candidate.provider, "LocalEditorial")
        self.assertNotIn(hashlib.sha256(candidate.data).hexdigest(), curated_hashes)

    def test_editorial_fallback_is_deterministic_and_unique_per_article(self):
        worker = load_worker()
        first = worker.generate_editorial_fallback(
            {"id": "article-one", "title": "כותרת אחת"}, []
        )
        repeated = worker.generate_editorial_fallback(
            {"id": "article-one", "title": "כותרת אחת"}, []
        )
        second = worker.generate_editorial_fallback(
            {"id": "article-two", "title": "כותרת אחרת"}, []
        )
        self.assertEqual(first.data, repeated.data)
        self.assertNotEqual(
            hashlib.sha256(first.data).hexdigest(),
            hashlib.sha256(second.data).hexdigest(),
        )
        self.assertEqual(worker.core.validate_candidate(first.data)[:2], (1200, 675))

    def test_workflow_fails_closed_when_worker_skips_required_image(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("ARTICLE_IMAGE_SKIPPED", workflow)
        self.assertIn("IMAGE_OUTPUT_MISSING", workflow)
        skip_guard = workflow.index("ARTICLE_IMAGE_SKIPPED")
        next_commit_guard = workflow.index("ARTICLE_IMAGE_COMMITTED")
        self.assertIn("exit 42", workflow[min(skip_guard, next_commit_guard):])


if __name__ == "__main__":
    unittest.main()

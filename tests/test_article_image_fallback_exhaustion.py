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
    def test_local_fallback_reuses_least_used_real_photo_when_unique_pool_is_exhausted(self):
        worker = load_worker()
        post = {
            "id": "unattached-adults-missed-chances-regrets",
            "title": "התמודדות עם תחושת החמצה ברווקות מאוחרת",
        }
        candidates = worker._candidate_pool(post, set())
        hashes = {}
        for source_path, _description in candidates:
            path = ROOT / source_path
            if path.is_file():
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                hashes[digest] = 3

        candidate = worker.local_fallback(
            "yanivsa/kesher-website",
            post,
            "sha",
            "token",
            [],
            existing_hashes=set(hashes),
            existing_usage=hashes,
            banned_paths=set(),
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        width, height, ext = worker.core.validate_candidate(candidate.data)
        self.assertGreaterEqual(width, 640)
        self.assertGreaterEqual(height, 360)
        self.assertIn(ext, {"jpg", "png"})
        self.assertEqual(candidate.provider, "Local")
        self.assertTrue(candidate.source_url.startswith("local://"))

    def test_production_worker_never_generates_abstract_terminal_placeholder(self):
        source = WORKER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("LocalEditorial", source)
        self.assertNotIn("_render_editorial_png", source)
        self.assertNotIn("איור עריכתי מופשט", source)

    def test_workflow_fails_closed_when_worker_skips_required_image(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("ARTICLE_IMAGE_SKIPPED", workflow)
        self.assertIn("IMAGE_OUTPUT_MISSING", workflow)
        skip_guard = workflow.index("ARTICLE_IMAGE_SKIPPED")
        next_commit_guard = workflow.index("ARTICLE_IMAGE_COMMITTED")
        self.assertIn("exit 42", workflow[min(skip_guard, next_commit_guard):])


if __name__ == "__main__":
    unittest.main()

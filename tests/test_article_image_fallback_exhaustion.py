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
    def test_singles_fallback_survives_two_existing_image_collisions(self):
        worker = load_worker()
        singles = worker.LOCAL_FALLBACK_CANDIDATES["singles"]
        self.assertGreaterEqual(len(singles), 3, "singles needs spare curated capacity")

        first_two_hashes = {
            hashlib.sha256((ROOT / source_path).read_bytes()).hexdigest()
            for source_path, _description in singles[:2]
        }
        candidate = worker.local_fallback(
            "yanivsa/kesher-website",
            {"id": "unattached-adults-missed-chances-regrets", "title": "התמודדות עם תחושת החמצה ברווקות מאוחרת"},
            "sha",
            "token",
            [],
            existing_hashes=first_two_hashes,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertNotIn(hashlib.sha256(candidate.data).hexdigest(), first_two_hashes)
        self.assertEqual(candidate.provider, "Local")

    def test_workflow_fails_closed_when_worker_skips_required_image(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("ARTICLE_IMAGE_SKIPPED", workflow)
        self.assertIn("Required article image was not produced", workflow)
        skip_guard = workflow.index("ARTICLE_IMAGE_SKIPPED")
        next_commit_guard = workflow.index("ARTICLE_IMAGE_COMMITTED", skip_guard)
        self.assertIn("exit 1", workflow[skip_guard:next_commit_guard])


if __name__ == "__main__":
    unittest.main()

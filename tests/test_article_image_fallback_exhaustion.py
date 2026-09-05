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
    def test_singles_keeps_two_valid_unpublished_spares(self):
        worker = load_worker()
        singles = worker.LOCAL_FALLBACK_CANDIDATES["singles"]
        published_hashes = worker.collect_existing_hashes(ROOT)
        eligible_hashes: list[str] = []

        for source_path, _description in singles:
            data = (ROOT / source_path).read_bytes()
            worker.core.validate_candidate(data)
            digest = hashlib.sha256(data).hexdigest()
            if digest not in published_hashes:
                eligible_hashes.append(digest)

        self.assertGreaterEqual(
            len(set(eligible_hashes)),
            2,
            "singles must retain at least two valid unpublished fallback images",
        )

        candidate = worker.local_fallback(
            "yanivsa/kesher-website",
            {"id": "unattached-adults-missed-chances-regrets", "title": "התמודדות עם תחושת החמצה ברווקות מאוחרת"},
            "sha",
            "token",
            [],
            existing_hashes=published_hashes,
        )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertNotIn(hashlib.sha256(candidate.data).hexdigest(), published_hashes)
        self.assertEqual(candidate.provider, "Local")

    def test_workflow_fails_closed_when_worker_skips_required_image(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("ARTICLE_IMAGE_SKIPPED", workflow)
        self.assertIn("IMAGE_OUTPUT_MISSING", workflow)
        skip_guard = workflow.index("ARTICLE_IMAGE_SKIPPED")
        next_commit_guard = workflow.index("ARTICLE_IMAGE_COMMITTED")
        self.assertIn("exit 42", workflow[min(skip_guard, next_commit_guard):])


if __name__ == "__main__":
    unittest.main()

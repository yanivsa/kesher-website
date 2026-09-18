from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from datetime import date
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
    def test_local_fallback_blocks_when_all_seed_and_bank_candidates_are_inside_reuse_limits(self):
        worker = load_worker()
        post = {
            "id": "unattached-adults-missed-chances-regrets",
            "title": "התמודדות עם תחושת החמצה ברווקות מאוחרת",
        }
        existing_hashes: set[str] = set()
        usage: dict[str, int] = {}
        last_used: dict[str, date] = {}

        for _tier, source_path in worker._candidate_pool(post, set()):
            path = ROOT / source_path
            if not path.is_file():
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            existing_hashes.add(digest)
            usage[digest] = 1
            last_used[digest] = date.today()

        candidate = worker.local_fallback(
            "yanivsa/kesher-website",
            post,
            "sha",
            "token",
            [],
            existing_hashes=existing_hashes,
            existing_usage=usage,
            last_used=last_used,
            banned_paths=set(),
        )

        self.assertIsNone(candidate)

    def test_production_worker_never_generates_abstract_terminal_placeholder(self):
        source = WORKER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("LocalEditorial", source)
        self.assertNotIn("_render_editorial_png", source)
        self.assertNotIn("generate_editorial_fallback", source)

    def test_workflow_fails_closed_when_worker_skips_required_image(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("ARTICLE_IMAGE_SKIPPED", workflow)
        self.assertIn("IMAGE_OUTPUT_MISSING", workflow)
        skip_guard = workflow.index("ARTICLE_IMAGE_SKIPPED")
        next_commit_guard = workflow.index("ARTICLE_IMAGE_COMMITTED")
        self.assertIn("exit 42", workflow[min(skip_guard, next_commit_guard):])


if __name__ == "__main__":
    unittest.main()

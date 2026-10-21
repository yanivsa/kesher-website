from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / ".github" / "scripts" / "article-image-worker-v5.py"


def load_worker():
    spec = importlib.util.spec_from_file_location("kesher_article_image_worker_v5_test", WORKER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load worker from {WORKER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ArticleImageWorkerV5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.worker = load_worker()

    def _post(self, slug: str, title: str) -> dict[str, str]:
        return {
            "id": slug,
            "slug": slug,
            "title": title,
            "category": "הדרכת הורים",
            "subcategory": "גמילה",
            "excerpt": "מדריך מעשי להורים עם צעדים ברורים ונורות אזהרה.",
        }

    def test_local_editorial_fallback_is_article_bound_and_contract_compatible(self) -> None:
        attempts = ["gemini-1", "gemini-2", "pexels", "pixabay"]
        post = self._post(
            "potty-training-constipation",
            "עצירות בגמילה מחיתולים: למה הילד מתאפק ואיך שוברים את המעגל?",
        )

        candidate = self.worker.local_editorial_fallback(
            "yanivsa/kesher-website",
            post,
            "ignored",
            "ignored",
            attempts,
            existing_hashes=set(),
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.provider, "LocalEditorial")
        self.assertEqual(candidate.attempts, ["local-editorial"])
        self.assertRegex(candidate.source_url, r"^local-editorial://potty-training-constipation/[0-7]$")
        self.assertEqual(candidate.extension, "png")
        width, height, ext = self.worker.core.validate_candidate(candidate.data)
        self.assertEqual((width, height, ext), (1200, 675, "png"))
        self.assertGreaterEqual(len(candidate.visual_match), 24)

    def test_local_editorial_pixels_are_unique_per_article(self) -> None:
        first = self.worker.local_editorial_fallback(
            "yanivsa/kesher-website",
            self._post("potty-training-constipation", "עצירות בגמילה מחיתולים"),
            "ignored",
            "ignored",
            [],
            existing_hashes=set(),
        )
        second = self.worker.local_editorial_fallback(
            "yanivsa/kesher-website",
            self._post("daycare-adjustment", "הסתגלות למעון"),
            "ignored",
            "ignored",
            [],
            existing_hashes=set(),
        )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        assert first is not None and second is not None
        self.assertNotEqual(
            self.worker.core.image_pixel_sha256(first.data),
            self.worker.core.image_pixel_sha256(second.data),
        )

    def test_local_editorial_chooses_an_unused_variant(self) -> None:
        post = self._post("potty-training-constipation", "עצירות בגמילה מחיתולים")
        first = self.worker.local_editorial_fallback(
            "yanivsa/kesher-website", post, "ignored", "ignored", [], existing_hashes=set()
        )
        assert first is not None
        occupied = {"pixels:" + self.worker.core.image_pixel_sha256(first.data)}

        second = self.worker.local_editorial_fallback(
            "yanivsa/kesher-website", post, "ignored", "ignored", [], existing_hashes=occupied
        )

        self.assertIsNotNone(second)
        assert second is not None
        self.assertNotEqual(first.source_url, second.source_url)
        self.assertNotEqual(
            self.worker.core.image_pixel_sha256(first.data),
            self.worker.core.image_pixel_sha256(second.data),
        )


if __name__ == "__main__":
    unittest.main()

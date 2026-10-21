from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
BANK_MANIFEST_PATH = ROOT / "public" / "images" / "fallback" / "manifest.json"
SEED_MANIFEST_PATH = ROOT / "config" / "article-image-fallback-manifest.json"
POSTS_PATH = ROOT / "src" / "data" / "posts.json"

worker_path = ROOT / ".github" / "scripts" / "article-image-worker-v4.py"
spec = importlib.util.spec_from_file_location("worker_v4", worker_path)
worker = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = worker
spec.loader.exec_module(worker)

worker_v5_path = ROOT / ".github" / "scripts" / "article-image-worker-v5.py"
spec_v5 = importlib.util.spec_from_file_location("worker_v5", worker_v5_path)
worker_v5 = importlib.util.module_from_spec(spec_v5)
sys.modules[spec_v5.name] = worker_v5
spec_v5.loader.exec_module(worker_v5)

from scripts.kesher_article_contract import image_dimensions, image_pixel_sha256


class ArticleImageFallbackPoolAndCascadeTests(unittest.TestCase):
    def test_bank_manifest_exists_and_covers_required_categories(self) -> None:
        self.assertTrue(BANK_MANIFEST_PATH.is_file(), "Fallback bank manifest.json must exist")
        data = json.loads(BANK_MANIFEST_PATH.read_text(encoding="utf-8"))
        assets = data.get("assets") or []
        self.assertGreater(len(assets), 0, "Fallback bank manifest must have assets")
        categories_in_bank = {a.get("category") for a in assets}
        for cat in worker.REQUIRED_CATEGORIES:
            self.assertIn(cat, categories_in_bank, f"Category {cat} missing from fallback bank")

    def test_all_bank_assets_are_valid_images_with_no_pixel_collision_in_posts(self) -> None:
        posts = json.loads(POSTS_PATH.read_text(encoding="utf-8"))
        data = json.loads(BANK_MANIFEST_PATH.read_text(encoding="utf-8"))
        for entry in data.get("assets") or []:
            rel_path = entry.get("path")
            self.assertTrue(rel_path, "Asset must have path")
            full_path = ROOT / rel_path
            self.assertTrue(full_path.is_file(), f"Asset file missing: {rel_path}")
            raw = full_path.read_bytes()
            w, h = image_dimensions(raw)
            self.assertGreaterEqual(w, 640)
            self.assertGreaterEqual(h, 360)
            ratio = w / h
            self.assertTrue(1.2 <= ratio <= 2.2, f"Bad aspect ratio: {ratio} for {rel_path}")
            pix = image_pixel_sha256(raw)
            colliding_posts = [
                p.get("id") for p in posts
                if p.get("image") and (ROOT / "public" / str(p["image"]).lstrip("/")).is_file()
                and image_pixel_sha256((ROOT / "public" / str(p["image"]).lstrip("/")).read_bytes()) == pix
                and str(p.get("imageSourceUrl") or "") != f"local://{rel_path}"
            ]
            self.assertEqual(
                colliding_posts,
                [],
                f"Asset {rel_path} collides with published hero pixels in unrelated posts.json: {colliding_posts}",
            )
            desc = entry.get("description") or ""
            self.assertGreaterEqual(len(desc), 20, f"Description too short for {rel_path}")

    def test_category_fallback_order_covers_all_categories(self) -> None:
        for cat in worker.REQUIRED_CATEGORIES:
            self.assertIn(cat, worker.CATEGORY_FALLBACK_ORDER)
            cascade = worker.CATEGORY_FALLBACK_ORDER[cat]
            self.assertEqual(cascade[0], cat, "First element in cascade must be the category itself")
            self.assertGreater(len(cascade), 1, "Cascade must contain related categories")

    def test_local_fallback_selects_unassigned_bank_asset(self) -> None:
        post = {
            "id": "dating-test-article",
            "slug": "dating-test-article",
            "category": "זוגיות",
            "subcategory": "מציאת זוגיות",
            "title": "איך מוצאים זוגיות",
            "excerpt": "מדריך למציאת זוגיות",
        }
        attempts: list[str] = []
        candidate = worker.local_fallback(
            "yanivsa/kesher-website",
            post,
            "main",
            "dummy-token",
            attempts,
        )
        self.assertIsNotNone(candidate, "local_fallback must succeed with bank assets")
        self.assertEqual(candidate.provider, "Local")
        self.assertTrue(candidate.source_url.startswith("local://public/images/fallback/"))
        self.assertGreaterEqual(len(candidate.visual_match), 20)

    def test_audit_image_pool_capacity_reports_available_inventory(self) -> None:
        stats = worker.audit_image_pool_capacity()
        self.assertGreater(stats["total_assets"], 0)
        self.assertGreater(stats["total_available"], 0)
        self.assertIn("dating", stats["categories"])
        self.assertIn("couples", stats["categories"])
        self.assertFalse(stats["capacity_alert"])


class ParentingCanaryImageCategoryTests(unittest.TestCase):
    def test_parenting_pool_never_falls_through_to_unrelated_generic_category(self):
        post = {
            "id": "potty-training-age-4",
            "slug": "potty-training-age-4",
            "title": "גמילה מחיתולים בגיל 4",
            "category": "הדרכת הורים",
            "subcategory": "גמילה מחיתולים",
            "excerpt": "מדריך להורים",
        }
        unrelated_manifest = {
            "version": 1,
            "assets": [{"category": "relocation", "path": "public/images/fallback/relocation/family_relocation_transition.jpg"}],
        }
        with mock.patch.object(worker, "_bank_candidates", return_value=[]), mock.patch.object(
            worker, "_seed_candidates_for_category", return_value=[]
        ), mock.patch.object(worker, "load_bank_manifest", return_value=unrelated_manifest):
            self.assertEqual(worker._candidate_pool(post, set()), [])


class LocalEditorialFallbackTests(unittest.TestCase):
    @staticmethod
    def _post(slug: str, title: str) -> dict[str, str]:
        return {
            "id": slug,
            "slug": slug,
            "title": title,
            "category": "הדרכת הורים",
            "subcategory": "גמילה",
            "excerpt": "מדריך מעשי להורים עם צעדים ברורים ונורות אזהרה.",
        }

    def test_local_editorial_is_article_bound_and_contract_compatible(self) -> None:
        attempts = ["gemini-1", "gemini-2", "pexels", "pixabay"]
        post = self._post(
            "potty-training-constipation",
            "עצירות בגמילה מחיתולים: למה הילד מתאפק ואיך שוברים את המעגל?",
        )
        candidate = worker_v5.local_editorial_fallback(
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
        width, height, ext = worker_v5.core.validate_candidate(candidate.data)
        self.assertEqual((width, height, ext), (1200, 675, "png"))
        self.assertGreaterEqual(len(candidate.visual_match), 24)

    def test_local_editorial_pixels_are_unique_per_article(self) -> None:
        first = worker_v5.local_editorial_fallback(
            "yanivsa/kesher-website",
            self._post("potty-training-constipation", "עצירות בגמילה מחיתולים"),
            "ignored",
            "ignored",
            [],
            existing_hashes=set(),
        )
        second = worker_v5.local_editorial_fallback(
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
            worker_v5.core.image_pixel_sha256(first.data),
            worker_v5.core.image_pixel_sha256(second.data),
        )

    def test_local_editorial_rotates_away_from_used_pixels(self) -> None:
        post = self._post("potty-training-constipation", "עצירות בגמילה מחיתולים")
        first = worker_v5.local_editorial_fallback(
            "yanivsa/kesher-website", post, "ignored", "ignored", [], existing_hashes=set()
        )
        assert first is not None
        occupied = {"pixels:" + worker_v5.core.image_pixel_sha256(first.data)}
        second = worker_v5.local_editorial_fallback(
            "yanivsa/kesher-website", post, "ignored", "ignored", [], existing_hashes=occupied
        )
        self.assertIsNotNone(second)
        assert second is not None
        self.assertNotEqual(first.source_url, second.source_url)
        self.assertNotEqual(
            worker_v5.core.image_pixel_sha256(first.data),
            worker_v5.core.image_pixel_sha256(second.data),
        )


if __name__ == "__main__":
    unittest.main()

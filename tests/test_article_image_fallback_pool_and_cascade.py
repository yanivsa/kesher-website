from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BANK_MANIFEST_PATH = ROOT / "public" / "images" / "fallback" / "manifest.json"
SEED_MANIFEST_PATH = ROOT / "config" / "article-image-fallback-manifest.json"
POSTS_PATH = ROOT / "src" / "data" / "posts.json"

import importlib.util
worker_path = ROOT / ".github" / "scripts" / "article-image-worker-v4.py"
spec = importlib.util.spec_from_file_location("worker_v4", worker_path)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

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
            # A bank asset must not collide with unrelated published posts
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
        # With 10 fresh assets, capacity_alert should be False
        self.assertFalse(stats["capacity_alert"])


if __name__ == "__main__":
    unittest.main()

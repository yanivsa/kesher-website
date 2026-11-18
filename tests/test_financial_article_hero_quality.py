"""Editorial-photo publication gates for the financial article cohort.

The precisely identified 17 SVGs published on 2026-11-17 are migration-only
exceptions. A new financial article cannot inherit the exception. As soon as
the migration PR replaces them, every post must carry a verified local photo.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "src/data/financialGuidancePosts.json"
REPAIR = ROOT / "scripts/repair-financial-guidance-heroes.py"

spec = importlib.util.spec_from_file_location("kesher_financial_hero_repair", REPAIR)
assert spec and spec.loader
repair = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = repair
spec.loader.exec_module(repair)

HEBREW = re.compile(r"[\u0590-\u05FF]")
PHOTO = re.compile(r"^/images/generated/blog/[a-z0-9-]+-financial-hero-[0-9a-f]{12}\.(?:jpg|png)$")


class FinancialHeroQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.posts = json.loads(DATA.read_text(encoding="utf-8"))

    def test_17_original_articles_have_distinct_editorial_scene_briefs(self):
        ids = {p["id"] for p in self.posts}
        self.assertTrue(set(repair.SCENES).issubset(ids))
        self.assertEqual(len(repair.SCENES), 17)
        self.assertEqual(len(set(repair.SCENES.values())), 17)
        for pid, scene in repair.SCENES.items():
            with self.subTest(pid=pid):
                self.assertGreaterEqual(len(scene), 90)
                self.assertTrue(any(word in scene.lower() for word in ("parent", "adult", "child", "partner", "family", "hands")))
                self.assertTrue(any(word in scene.lower() for word in ("budget", "expenses", "bill", "money", "account", "income", "allowance", "spending", "saving", "coins", "financial", "purchase", "cost", "receipts", "invoice")))

    def test_new_articles_and_migrated_heroes_are_verified_photographs(self):
        hashes = set()
        dimensions_ts = (ROOT / "src/data/imageDimensions.ts").read_text(encoding="utf-8")
        for post in self.posts:
            with self.subTest(article=post.get("id")):
                pid = post["id"]
                image = post.get("image") or ""
                is_exact_old_svg = (
                    pid in repair.SCENES
                    and post.get("date") == "2026-11-17"
                    and repair.legacy_image(post)
                )
                if is_exact_old_svg:
                    # Explicit temporary waiver: never grants an exemption to a new post.
                    self.assertTrue((ROOT / "public" / image.lstrip("/")).is_file())
                    continue
                self.assertRegex(image, PHOTO, "Finance heroes must be raster photos, never generic SVG placeholders")
                self.assertTrue(post.get("imageVerified") is True, "Must carry independent pixel-verification proof")
                self.assertIn(post.get("imageProvider"), ("Gemini", "Pexels", "Pixabay"))
                self.assertTrue(post.get("imageSourceUrl"))
                alt = str(post.get("imageAlt") or "")
                self.assertGreaterEqual(len(alt), 30)
                self.assertRegex(alt, HEBREW)
                file = ROOT / "public" / image.lstrip("/")
                self.assertTrue(file.is_file())
                contents = file.read_bytes()
                self.assertGreater(len(contents), 10000, "Tiny placeholders are not editorial photos")
                digest = hashlib.sha256(contents).hexdigest()
                self.assertNotIn(digest, hashes, "All 17 article hero images must be unique")
                hashes.add(digest)
                self.assertIn(f"'{image}':", dimensions_ts, "Layout metadata must use actual image dimensions")


if __name__ == "__main__":
    unittest.main()

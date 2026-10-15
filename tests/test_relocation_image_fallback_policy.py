from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path

from PIL import Image

from scripts import kesher_article_contract as contract

ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / ".github" / "scripts" / "article-image-worker-v4.py"
TRUSTED_SOURCE = "local://public/images/generated/blog/relocation-hero.jpg"
TRUSTED_PATH = "public/images/generated/blog/relocation-hero.jpg"


def load_worker():
    spec = importlib.util.spec_from_file_location("relocation_image_fallback_worker", WORKER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (1200, 675), (90, 110, 125)).save(out, format="JPEG")
    return out.getvalue()


class RelocationFallbackPolicyTests(unittest.TestCase):
    def test_relocation_pool_contains_curated_blog_hero(self) -> None:
        worker = load_worker()
        post = {
            "id": "returning-to-israel-relationship-struggles",
            "title": "חוזרים לישראל: איך מתמודדים עם המתח הזוגי",
            "category": "זוגיות",
            "subcategory": "זוגיות בעלייה ורילוקיישן",
            "excerpt": "חזרה לישראל מרילוקיישן יוצרת מעבר מורכב בזוגיות.",
        }
        paths = [path for _tier, path in worker._candidate_pool(post, set())]
        self.assertIn(TRUSTED_PATH, paths)

    def test_contract_accepts_curated_blog_fallback_source(self) -> None:
        data = jpeg()
        post = {
            "id": "returning-to-israel-relationship-struggles",
            "title": "חוזרים לישראל: איך מתמודדים עם המתח הזוגי",
            "content": "<p>תוכן</p>",
            "image": "/images/generated/blog/returning-to-israel-relationship-struggles.jpg",
            "imageAlt": "זוג בתקופת מעבר והסתגלות לאחר חזרה לישראל מרילוקיישן",
        }
        fields = {
            "Image Pipeline Version": "2",
            "Image Provider": "Local",
            "Image Attempt Chain": "gemini-1/gemini-2/pexels/pixabay/local-curated",
            "Image Generation Result": "local_fallback",
            "Image Source URL": TRUSTED_SOURCE,
            "Image SHA-256": hashlib.sha256(data).hexdigest(),
            "Image Dimensions": "1200x675",
            "Image Visual Match": "צילום מציאותי של זוג או משפחה בתקופת מעבר, הסתגלות או רילוקיישן",
            "Image Article ID": post["id"],
            "Image Article SHA-256": contract.article_sha256(post),
            "Image Evidence Head": "a" * 40,
        }
        body = "\n".join(f"{key}: {value}" for key, value in fields.items())
        self.assertEqual(contract.image_proof_errors(post, body, "a" * 40, data), [])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest import mock

from scripts import article_claim_quality

ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / ".github" / "scripts" / "article-image-worker-v4.py"
spec = importlib.util.spec_from_file_location("article_image_worker_v4_canary", WORKER_PATH)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class ParentingCanaryContentGateTests(unittest.TestCase):
    def _article(self, **overrides):
        article = {
            "id": "potty-training-age-4",
            "slug": "potty-training-age-4",
            "title": "גמילה מחיתולים בגיל 4",
            "date": "2026-10-20",
            "category": "הדרכת הורים",
            "excerpt": "תקציר שימושי להורים.",
            "content": (
                '<p>תוכן זהיר ושימושי.</p>'
                '<p><a href="/blog/potty-training-age-3-problems">גמילה בגיל 3</a></p>'
                '<p><a href="/blog/nighttime-potty-training">גמילת לילה</a></p>'
                '<p><a href="/blog/potty-training-regression">רגרסיה בגמילה</a></p>'
                '<p><a href="/services/parenting">הדרכת הורים</a></p>'
            ),
            "serviceUrl": "/services/parenting",
            "controllerManaged": True,
            "evidence": [
                {
                    "title": "Guidance",
                    "source": "Authoritative source",
                    "url": "https://example.org/guidance",
                    "note": "Source note",
                }
            ],
        }
        article.update(overrides)
        return article

    def test_new_controller_managed_article_requires_evidence(self):
        errors = article_claim_quality.validate_posts([self._article(evidence=[])])
        self.assertTrue(any("evidence_missing" in error for error in errors), errors)

    def test_new_controller_managed_article_requires_three_blog_links(self):
        article = self._article(content='<p><a href="/blog/potty-training-regression">רגרסיה</a></p><p><a href="/services/parenting">הדרכת הורים</a></p>')
        errors = article_claim_quality.validate_posts([article])
        self.assertTrue(any("internal_blog_links" in error for error in errors), errors)

    def test_new_controller_managed_article_requires_service_cta_link(self):
        article = self._article(content=(
            '<p><a href="/blog/potty-training-age-3-problems">א</a></p>'
            '<p><a href="/blog/nighttime-potty-training">ב</a></p>'
            '<p><a href="/blog/potty-training-regression">ג</a></p>'
        ))
        errors = article_claim_quality.validate_posts([article])
        self.assertTrue(any("service_cta_link" in error for error in errors), errors)

    def test_pre_canary_controller_article_is_not_retroactively_blocked(self):
        errors = article_claim_quality.validate_posts([
            self._article(date="2026-10-19", evidence=[], content="<p>תוכן ישן.</p>")
        ])
        self.assertEqual(errors, [])


class ParentingCanaryImageGateTests(unittest.TestCase):
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
            "assets": [
                {
                    "category": "relocation",
                    "path": "public/images/fallback/relocation/family_relocation_transition.jpg",
                }
            ],
        }
        with mock.patch.object(worker, "_bank_candidates", return_value=[]), mock.patch.object(
            worker, "_seed_candidates_for_category", return_value=[]
        ), mock.patch.object(worker, "load_bank_manifest", return_value=unrelated_manifest):
            self.assertEqual(worker._candidate_pool(post, set()), [])


if __name__ == "__main__":
    unittest.main()

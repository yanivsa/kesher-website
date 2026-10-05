from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify-production-article.py"
SPEC = importlib.util.spec_from_file_location("verify_production_article", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VerifyProductionArticleTests(unittest.TestCase):
    def test_public_url_uses_id_even_when_slug_differs(self) -> None:
        self.assertEqual(
            MODULE._public_url({"id": "canonical-id", "slug": "legacy-slug"}),
            "https://kesher.saharoni.com/blog/canonical-id",
        )

    def test_public_url_requires_id(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "no id"):
            MODULE._public_url({"slug": "legacy-only"})

    def test_canonical_parser_requires_exact_single_canonical(self) -> None:
        html = (
            '<html><head>'
            '<link rel="canonical" href="https://kesher.saharoni.com/blog/canonical-id">'
            '</head></html>'
        )
        self.assertEqual(
            MODULE._canonical_hrefs(html),
            ["https://kesher.saharoni.com/blog/canonical-id"],
        )

    def test_canonical_parser_handles_attribute_order(self) -> None:
        html = (
            '<html><head>'
            '<link href="https://kesher.saharoni.com/links" data-kesher-seo="true" rel="canonical">'
            '</head></html>'
        )
        self.assertEqual(
            MODULE._canonical_hrefs(html),
            ["https://kesher.saharoni.com/links"],
        )


if __name__ == "__main__":
    unittest.main()

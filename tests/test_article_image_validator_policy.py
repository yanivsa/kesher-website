from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / ".github" / "scripts" / "validate-article-images.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("article_image_validator_policy_test", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def use(pid: str, published: str, *, trusted_local: bool = False) -> dict[str, object]:
    return {
        "id": pid,
        "date": published,
        "imageProvider": "Local" if trusted_local else None,
        "imageSourceUrl": "local://public/images/generated/blog/source.jpg" if trusted_local else None,
        "imageIsFallback": trusted_local,
    }


class ArticleImageValidatorReusePolicyTests(unittest.TestCase):
    def test_contract_policy_is_unique_only(self):
        validator = load_validator()
        self.assertEqual(validator.reuse_policy(), (0, 1))

    def test_duplicate_pixels_are_rejected_even_after_old_cooldown(self):
        validator = load_validator()
        errors = validator.validate_hash_reuse(
            "abc",
            [
                use("first", "2025-01-01"),
                use("second", "2026-09-24", trusted_local=True),
            ],
            cooldown_days=0,
            max_uses=1,
        )
        self.assertTrue(any("hero pixels must be unique" in error for error in errors), errors)

    def test_duplicate_pixels_are_rejected_for_trusted_local_fallback(self):
        validator = load_validator()
        errors = validator.validate_hash_reuse(
            "abc",
            [
                use("first", "2026-08-01"),
                use("second", "2026-09-24", trusted_local=True),
            ],
            cooldown_days=0,
            max_uses=1,
        )
        self.assertTrue(errors)

    def test_single_use_is_allowed(self):
        validator = load_validator()
        self.assertEqual(
            validator.validate_hash_reuse(
                "abc", [use("first", "2026-09-24")], cooldown_days=0, max_uses=1
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()

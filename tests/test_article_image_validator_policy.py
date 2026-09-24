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
    def test_contract_policy_is_loaded(self):
        validator = load_validator()
        self.assertEqual(validator.reuse_policy(), (90, 3))

    def test_trusted_local_reuse_after_cooldown_is_allowed(self):
        validator = load_validator()
        errors = validator.validate_hash_reuse(
            "abc",
            [
                use("first", "2026-06-01"),
                use("second", "2026-09-24", trusted_local=True),
            ],
            cooldown_days=90,
            max_uses=3,
        )
        self.assertEqual(errors, [])

    def test_recent_reuse_is_rejected(self):
        validator = load_validator()
        errors = validator.validate_hash_reuse(
            "abc",
            [
                use("first", "2026-08-01"),
                use("second", "2026-09-24", trusted_local=True),
            ],
            cooldown_days=90,
            max_uses=3,
        )
        self.assertTrue(any("minimum cooldown is 90 days" in error for error in errors), errors)

    def test_duplicate_requires_trusted_local_fallback_evidence(self):
        validator = load_validator()
        errors = validator.validate_hash_reuse(
            "abc",
            [
                use("first", "2026-06-01"),
                use("second", "2026-09-24"),
            ],
            cooldown_days=90,
            max_uses=3,
        )
        self.assertTrue(any("trusted Local fallback reuse" in error for error in errors), errors)

    def test_lifetime_use_cap_is_enforced(self):
        validator = load_validator()
        errors = validator.validate_hash_reuse(
            "abc",
            [
                use("one", "2025-09-01"),
                use("two", "2025-12-15", trusted_local=True),
                use("three", "2026-03-20", trusted_local=True),
                use("four", "2026-07-01", trusted_local=True),
            ],
            cooldown_days=90,
            max_uses=3,
        )
        self.assertTrue(any("lifetime reuse limit exceeded" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()

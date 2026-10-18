"""Governance test: enforce that mandatory production-safety test suites are covered in CI gates."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

MANDATORY_PRODUCTION_SAFETY_MODULES = [
    "tests.test_controller_liveness",
    "tests.test_media_external_effect_crash_consistency",
    "tests.test_daily_rollover_delivery_completeness",
    "tests.test_deploy_sha_supersession_and_budget",
    "tests.test_exact_public_article_identity",
    "tests.test_article_pr_verify_check_ordering",
    "tests.test_article_normalization_head_tracking",
    "tests.test_article_image_fallback_pool_and_cascade",
    "tests.test_controller_child_failure_recovery",
]


class CiRegressionSuiteCoverageTests(unittest.TestCase):
    def test_mandatory_production_safety_suites_exist_on_disk(self) -> None:
        for mod in MANDATORY_PRODUCTION_SAFETY_MODULES:
            rel_path = mod.replace(".", "/") + ".py"
            file_path = ROOT / rel_path
            self.assertTrue(file_path.is_file(), f"Mandatory test module missing on disk: {rel_path}")

    def test_mandatory_suites_included_in_ci_workflow(self) -> None:
        ci_path = ROOT / ".github/workflows/ci.yml"
        self.assertTrue(ci_path.is_file(), "ci.yml missing")
        content = ci_path.read_text(encoding="utf-8")
        for mod in MANDATORY_PRODUCTION_SAFETY_MODULES:
            self.assertIn(
                mod,
                content,
                f"Mandatory production-safety test {mod} is omitted from .github/workflows/ci.yml",
            )

    def test_mandatory_suites_included_in_stability_pr_workflow(self) -> None:
        stability_path = ROOT / ".github/workflows/kesher-stability-pr.yml"
        self.assertTrue(stability_path.is_file(), "kesher-stability-pr.yml missing")
        content = stability_path.read_text(encoding="utf-8")
        for mod in MANDATORY_PRODUCTION_SAFETY_MODULES:
            self.assertIn(
                mod,
                content,
                f"Mandatory production-safety test {mod} is omitted from .github/workflows/kesher-stability-pr.yml",
            )

    def test_mandatory_suites_included_in_package_json_test_controller(self) -> None:
        pkg_path = ROOT / "package.json"
        self.assertTrue(pkg_path.is_file(), "package.json missing")
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        test_controller_cmd = (pkg.get("scripts") or {}).get("test:controller", "")
        for mod in MANDATORY_PRODUCTION_SAFETY_MODULES:
            self.assertIn(
                mod,
                test_controller_cmd,
                f"Mandatory production-safety test {mod} is omitted from package.json 'test:controller'",
            )


if __name__ == "__main__":
    unittest.main()

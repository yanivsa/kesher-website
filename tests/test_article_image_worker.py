from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import struct
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / ".github" / "scripts" / "article-image-worker-v3.py"
PRODUCTION_WORKER_PATH = ROOT / ".github" / "scripts" / "article-image-worker-v4.py"
CONTROLLER_PATH = ROOT / ".github" / "scripts" / "article-pr-controller-v3.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "kesher-article-image.yml"
CONTRACT_PATH = ROOT / "config" / "kesher-production-contract.json"
MANIFEST_PATH = ROOT / "config" / "article-image-fallback-manifest.json"
POSTS_PATH = ROOT / "src" / "data" / "posts.json"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fake_png(width: int = 1200, height: int = 675, marker: bytes = b"fixture") -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", width, height) + marker


def fake_manifest(paths: list[str]) -> dict:
    return {
        "target_per_category": 40,
        "policy": {"reuse_published_hero": False},
        "categories": {"couples": {"primary": paths, "reserve": []}},
    }


class ArticleImageWorkerTests(unittest.TestCase):
    def test_contract_caps_every_stage_at_three_total_attempts(self):
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["controller_state_schema_version"], 3)
        self.assertEqual(contract["retry"]["max_attempts_per_stage"], 3)
        self.assertEqual(contract["retry"]["backoff_minutes"], [5, 15])
        self.assertTrue(contract["retry"]["attempts_include_initial_run"])
        self.assertEqual(contract["image"]["max_attempts"], 3)
        self.assertEqual(contract["image"]["worker_attempts_per_dispatch"], 1)

    def test_provider_order_and_quality_contract(self):
        image = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["image"]
        self.assertEqual(
            image["provider_order"],
            ["gemini", "pexels", "pixabay", "local-curated"],
        )
        self.assertEqual(image["owned_generation_variants"], 3)
        self.assertEqual(image["local_fallback_candidates_per_category"], 40)
        self.assertEqual(image["local_fallback_reuse_cooldown_days"], 90)
        self.assertEqual(image["local_fallback_max_lifetime_uses"], 3)
        self.assertEqual(image["local_fallback_policy"], "prefer-unused-then-90-day-cooldown-max-3-uses")
        self.assertFalse(image["abstract_placeholder_allowed"])
        self.assertTrue(image["fallback_must_be_local"])
        self.assertFalse(image["no_image_publication_allowed"])
        self.assertTrue(image["publication_blocking"])
        self.assertTrue(image["required_for_article"])
        self.assertEqual(image["failure_mode"], "blocking-retry")
        self.assertEqual(image["gemini_model"], "gemini-3.1-flash-image")
        self.assertEqual(image["visual_verifier_model"], "gemini-3.5-flash")
        self.assertTrue(image["external_stock_requires_pixel_verification"])

    def test_all_external_failures_fall_through_to_local(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_fallback_test")
        calls: list[str] = []
        worker.try_gemini_variants = lambda post, attempts, **kwargs: (attempts.append("gemini-1"), calls.append("gemini"), None)[2]
        worker.try_pexels = lambda post, attempts, **kwargs: (attempts.append("pexels"), calls.append("pexels"), None)[2]
        worker.try_pixabay = lambda post, attempts, **kwargs: (attempts.append("pixabay"), calls.append("pixabay"), None)[2]
        worker.local_fallback = lambda repo, post, ref, token, attempts, **kwargs: worker.core.ImageCandidate(
            "Local",
            fake_png(),
            "png",
            "local://public/images/generated/blog/dating-communication-early-stages.jpg",
            "זוג בשיחה פנים אל פנים המדגישה הקשבה ותקשורת באופן ברור",
            attempts + ["local-curated"],
        )
        candidate = worker.choose_candidate("o/r", {"title": "שיחה זוגית", "id": "x"}, "sha", "token")
        self.assertEqual(calls, ["gemini", "pexels", "pixabay"])
        self.assertEqual(candidate.provider, "Local")
        self.assertEqual(
            candidate.attempts,
            ["gemini-1", "pexels", "pixabay", "local-curated"],
        )

    def test_manifest_has_40_unique_real_jpg_candidates_per_category(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_manifest_test")
        manifest = worker.load_seed_manifest()
        expected = {"dating", "singles", "relocation", "premarital", "parenting", "gifted", "adhd", "couples"}
        self.assertEqual(set(manifest["categories"]), expected)

        for category, block in manifest["categories"].items():
            paths = list(block.get("primary") or []) + list(block.get("reserve") or [])
            self.assertGreaterEqual(len(paths), 40, category)
            self.assertGreaterEqual(len(set(paths)), 40, category)
            for source_path in paths:
                self.assertTrue(source_path.endswith(".jpg"), (category, source_path))
                data = (ROOT / source_path).read_bytes()
                width, height, ext = worker.core.validate_candidate(data)
                self.assertGreaterEqual(width, 640, (category, source_path))
                self.assertGreaterEqual(height, 360, (category, source_path))
                self.assertEqual(ext, "jpg", (category, source_path))

    def test_local_fallback_reads_only_from_trusted_checkout(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_trusted_checkout_test")
        with tempfile.TemporaryDirectory() as tmp:
            worker.REPO_ROOT = Path(tmp)
            source_path = "public/images/generated/blog/fallback.jpg"
            worker.load_seed_manifest = lambda: fake_manifest([source_path])
            worker.load_bank_manifest = lambda: {"version": 1, "assets": []}
            target = worker.REPO_ROOT / source_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(fake_png())
            with mock.patch.object(worker.core, "github_content", side_effect=AssertionError("local fallback must not use GitHub API")):
                candidate = worker.local_fallback(
                    "o/r", {"title": "שיחה", "id": "x"}, "untrusted-pr-sha", "t", []
                )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.provider, "Local")
        self.assertEqual(candidate.data, fake_png())
        self.assertEqual(candidate.attempts, ["local-curated"])

    def test_local_fallback_skips_invalid_candidate_and_uses_next(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_runtime_fallback_test")
        with tempfile.TemporaryDirectory() as tmp:
            worker.REPO_ROOT = Path(tmp)
            bad = "public/images/generated/blog/bad.jpg"
            good = "public/images/generated/blog/good.jpg"
            worker.load_seed_manifest = lambda: fake_manifest([bad, good])
            worker.load_bank_manifest = lambda: {"version": 1, "assets": []}
            root = worker.REPO_ROOT / "public/images/generated/blog"
            root.mkdir(parents=True, exist_ok=True)
            (root / "bad.jpg").write_bytes(fake_png(200, 100))
            (root / "good.jpg").write_bytes(fake_png())
            candidate = worker.local_fallback("o/r", {"title": "שיחה", "id": "x"}, "sha", "t", [])
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertTrue(candidate.source_url.endswith("good.jpg"))

    def test_provider_preflight_never_requires_external_secrets(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_preflight_test")
        with mock.patch.dict("os.environ", {}, clear=True):
            availability = worker.provider_preflight()
        self.assertEqual(
            availability,
            {"gemini": False, "pexels": False, "pixabay": False, "local": True},
        )

    def test_gemini_generation_uses_current_official_generate_content_shape(self):
        source = WORKER_PATH.read_text(encoding="utf-8")
        self.assertIn(f"/v1/models/{{GEMINI_MODEL}}:generateContent", source)
        self.assertIn('"responseModalities": ["IMAGE"]', source)
        self.assertIn('"responseFormat": {"image": {"aspectRatio": "16:9"}}', source)
        self.assertIn('part.get("inlineData")', source)
        self.assertNotIn("/v1beta/interactions", source)

    def test_external_stock_is_never_accepted_from_search_metadata_alone(self):
        source = WORKER_PATH.read_text(encoding="utf-8")
        self.assertIn("verify_pixels(post, data, ext)", source)
        self.assertIn("Do not claim anything not visible", source)

    def test_partial_github_failure_is_recoverable_by_writing_evidence_before_commit(self):
        worker = load(WORKER_PATH, "article_image_worker_v3_atomicity_test")
        source = inspect.getsource(worker.ensure_image)
        self.assertLess(source.index("patch_pr_body"), source.index("commit_files("))
        self.assertIn("trusted_image_present", source)

    def test_summary_generation_matches_publishable_content_policy(self):
        worker = load(WORKER_PATH, "article_image_worker_v3_summary_test")
        thick = {
            "id": "thick",
            "title": "כותרת",
            "date": "2026-08-20",
            "category": "זוגיות",
            "excerpt": "תקציר",
            "content": "<p>" + ("מילה " * 500) + "</p>" + ("<h3>שאלה</h3>" * 5),
        }
        thin = {
            "id": "thin",
            "title": "ישן",
            "date": "2024-01-01",
            "category": "זוגיות",
            "excerpt": "ישן",
            "content": "<p>קצר</p>",
        }
        self.assertEqual([row["id"] for row in worker.summaries([thick, thin])], ["thick"])

    def test_worker_accepts_only_article_sized_png_or_jpeg(self):
        worker = load(WORKER_PATH, "article_image_worker_v3_dimensions_test")
        self.assertEqual(worker.core.validate_candidate(fake_png())[:2], (1200, 675))
        with self.assertRaisesRegex(RuntimeError, "too small"):
            worker.core.validate_candidate(fake_png(320, 180))

    def test_production_article_gate_forbids_no_image(self):
        controller = load(CONTROLLER_PATH, "article_controller_best_effort_test")
        validator = controller.load_validator_best_effort()
        base = [{"id": "old"}]
        new = {
            "id": "new",
            "title": "כותרת",
            "date": "2026-08-20",
            "category": "זוגיות",
            "excerpt": "תקציר",
            "content": "<p>" + ("מילה " * 700) + "</p>" + ("<h3>שאלה</h3>" * 5),
        }
        pr = {
            "state": "open",
            "draft": False,
            "title": "Publish Kesher article: new",
            "body": "",
            "base": {"ref": "main", "repo": {"full_name": "x/y"}},
            "head": {"repo": {"full_name": "x/y"}},
        }
        errors = validator.evaluate(
            pr,
            [{"filename": "src/data/posts.json"}],
            [{"name": "verify", "conclusion": "success"}],
            base,
            base + [new],
            lambda _: b"",
        )
        self.assertTrue(any("no-image publication is forbidden" in error for error in errors), errors)

    def test_workflow_is_controller_owned_and_executes_only_trusted_main_worker(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        trigger = workflow.split("permissions:", 1)[0]
        self.assertNotIn("pull_request_target:", trigger)
        self.assertIn("workflow_dispatch:", trigger)
        self.assertIn("run-name: Kesher Image PR", workflow)
        self.assertIn("ref: main", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("article-image-worker-v4.py", workflow)
        self.assertIn("GOOGLE_API_KEY", workflow)
        self.assertNotIn("UNSPLASH_ACCESS_KEY", workflow)
        self.assertIn("PEXELS_API_KEY", workflow)
        self.assertIn("PIXABAY_API_KEY", workflow)
        self.assertIn("actions/workflows/ci.yml/dispatches", workflow)
        self.assertNotIn("actions/checkout@v", workflow)

    def test_recent_local_image_reuse_is_blocked_by_cooldown(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_recent_reuse_test")
        fake_data = fake_png()
        fake_sha = hashlib.sha256(fake_data).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            worker.REPO_ROOT = Path(tmp)
            source_path = "public/images/generated/blog/recent.jpg"
            worker.load_seed_manifest = lambda: fake_manifest([source_path])
            worker.load_bank_manifest = lambda: {"version": 1, "assets": []}
            target = worker.REPO_ROOT / source_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(fake_data)
            candidate = worker.local_fallback(
                "o/r",
                {"title": "שיחה", "id": "x"},
                "sha",
                "t",
                [],
                existing_hashes={fake_sha},
                existing_usage={fake_sha: 1},
                last_used={fake_sha: date.today()},
                banned_paths=set(),
            )
        self.assertIsNone(candidate)

    def test_local_image_can_be_reused_after_cooldown_below_use_cap(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_cooled_reuse_test")
        fake_data = fake_png()
        fake_sha = hashlib.sha256(fake_data).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            worker.REPO_ROOT = Path(tmp)
            source_path = "public/images/generated/blog/cooled.jpg"
            worker.load_seed_manifest = lambda: fake_manifest([source_path])
            worker.load_bank_manifest = lambda: {"version": 1, "assets": []}
            target = worker.REPO_ROOT / source_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(fake_data)
            candidate = worker.local_fallback(
                "o/r",
                {"title": "שיחה", "id": "x"},
                "sha",
                "t",
                [],
                existing_hashes={fake_sha},
                existing_usage={fake_sha: 2},
                last_used={fake_sha: date.today() - timedelta(days=91)},
                banned_paths=set(),
            )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.provider, "Local")

    def test_local_image_reuse_is_blocked_at_three_lifetime_uses(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_use_cap_test")
        fake_data = fake_png()
        fake_sha = hashlib.sha256(fake_data).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            worker.REPO_ROOT = Path(tmp)
            source_path = "public/images/generated/blog/maxed.jpg"
            worker.load_seed_manifest = lambda: fake_manifest([source_path])
            worker.load_bank_manifest = lambda: {"version": 1, "assets": []}
            target = worker.REPO_ROOT / source_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(fake_data)
            candidate = worker.local_fallback(
                "o/r",
                {"title": "שיחה", "id": "x"},
                "sha",
                "t",
                [],
                existing_hashes={fake_sha},
                existing_usage={fake_sha: 3},
                last_used={fake_sha: date.today() - timedelta(days=365)},
                banned_paths=set(),
            )
        self.assertIsNone(candidate)

    def test_managed_bank_is_preferred_over_generic_seed_when_both_are_unused(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_bank_priority_test")
        with tempfile.TemporaryDirectory() as tmp:
            worker.REPO_ROOT = Path(tmp)
            bank = "public/images/fallback/couples/couples-001-bank.jpg"
            seed = "public/images/generated/blog/generic-seed.jpg"
            worker.load_seed_manifest = lambda: fake_manifest([seed])
            worker.load_bank_manifest = lambda: {
                "version": 1,
                "assets": [{"category": "couples", "path": bank}],
            }
            for path_name, marker in ((bank, b"bank"), (seed, b"seed")):
                target = worker.REPO_ROOT / path_name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(fake_png(marker=marker))
            candidate = worker.local_fallback(
                "o/r",
                {"title": "שיחה זוגית", "category": "זוגיות", "id": "x"},
                "sha",
                "t",
                [],
                existing_hashes=set(),
                banned_paths=set(),
            )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertTrue(candidate.source_url.endswith("couples-001-bank.jpg"))

    def test_topic_matching_prefers_specific_local_asset(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_topic_test")
        with tempfile.TemporaryDirectory() as tmp:
            worker.REPO_ROOT = Path(tmp)
            generic = "public/images/generated/blog/couples-communication-distance.jpg"
            specific = "public/images/generated/blog/first-grade-preparation-morning-routine.jpg"
            worker.load_seed_manifest = lambda: fake_manifest([generic, specific])
            worker.load_bank_manifest = lambda: {"version": 1, "assets": []}
            root = worker.REPO_ROOT / "public/images/generated/blog"
            root.mkdir(parents=True, exist_ok=True)
            (root / "couples-communication-distance.jpg").write_bytes(fake_png(marker=b"generic"))
            (root / "first-grade-preparation-morning-routine.jpg").write_bytes(fake_png(marker=b"specific"))
            candidate = worker.local_fallback(
                "o/r",
                {"title": "הכנה לכיתה א ושגרת בוקר", "category": "זוגיות", "id": "x"},
                "sha",
                "t",
                [],
            )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertTrue(candidate.source_url.endswith("first-grade-preparation-morning-routine.jpg"))

    def test_production_worker_contains_no_abstract_placeholder_renderer(self):
        source = PRODUCTION_WORKER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("LocalEditorial", source)
        self.assertNotIn("_render_editorial_png", source)
        self.assertIn("fails closed", source)

    def test_legacy_placeholder_repair_is_owned_by_post_merge_migration(self):
        repair_script = (ROOT / "scripts" / "repair-existing-article-heroes.py").read_text(encoding="utf-8")
        repair_workflow = (ROOT / ".github" / "workflows" / "repair-existing-article-heroes.yml").read_text(encoding="utf-8")
        self.assertIn("PLACEHOLDER_RE", repair_script)
        self.assertIn("try_gemini_variants", repair_script)
        self.assertIn("branches:", repair_workflow)
        self.assertIn("- main", repair_workflow)
        self.assertIn("build-article-fallback-library.py --category all --batch-size 8", repair_workflow)

    def test_contextual_stock_queries_generated_from_post_content(self):
        worker = load(PRODUCTION_WORKER_PATH, "article_image_worker_v4_queries_test")
        queries_finance = worker.core.stock_queries({"title": "ניהול תקציב וחשבון משותף לזוגות צעירים", "category": "זוגיות"})
        self.assertTrue(any("money" in q or "finances" in q or "budget" in q for q in queries_finance), queries_finance)

        queries_phone = worker.core.stock_queries({"title": "הסחות דעת ומסכים בקשר הזוגי", "category": "זוגיות"})
        self.assertTrue(any("distraction" in q or "smartphone" in q for q in queries_phone), queries_phone)

        queries_adhd = worker.core.stock_queries({"title": "התארגנות בוקר עם ילד עם הפרעת קשב וריכוז", "category": "הורות"})
        self.assertTrue(any("school" in q or "routine" in q for q in queries_adhd), queries_adhd)


if __name__ == "__main__":
    unittest.main()

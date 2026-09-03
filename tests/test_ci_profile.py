import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".github" / "scripts" / "select-ci-profile.py"


class CiProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("select_ci_profile", MODULE_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load CI profile selector from {MODULE_PATH}")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_article_publication_files_use_article_profile(self):
        paths = [
            "src/data/posts.json",
            "src/data/postSummaries.json",
            "public/sitemap.xml",
            "public/rss.xml",
            "public/llms.txt",
            "public/llms-full.txt",
            "public/images/generated/blog/example.webp",
        ]
        self.assertEqual(self.module.classify_paths(paths), "article")

    def test_any_unrelated_file_forces_full_profile(self):
        paths = [
            "src/data/posts.json",
            "src/components/Home.jsx",
        ]
        self.assertEqual(self.module.classify_paths(paths), "full")

    def test_empty_change_set_is_full_profile(self):
        self.assertEqual(self.module.classify_paths([]), "full")

    def test_workflow_change_is_full_profile(self):
        self.assertEqual(
            self.module.classify_paths([".github/workflows/ci.yml"]),
            "full",
        )


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class KesherArticleImageWorkflowFailClosedTest(unittest.TestCase):
    def test_missing_image_output_is_not_reported_as_success(self):
        text = (ROOT / ".github/workflows/kesher-article-image.yml").read_text(encoding="utf-8")
        self.assertIn("ARTICLE_IMAGE_SKIPPED", text)
        self.assertIn("IMAGE_OUTPUT_MISSING", text)
        self.assertNotIn("Trusted image already present or this is not an article publication PR.", text)


if __name__ == "__main__":
    unittest.main()

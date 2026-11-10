import json
from pathlib import Path
import unittest

from scripts import kesher_article_contract as contract
from scripts.kesher_daily_pipeline import source_metadata
from scripts.kesher_primary_keyword_contract import slug_represents_keyword


class ArticleContractTests(unittest.TestCase):
    def test_rss_is_part_of_article_publication_contract(self):
        self.assertIn("public/rss.xml", contract.ARTICLE_PUBLICATION_PATHS)
        self.assertTrue(contract.is_article_publication_path("public/rss.xml"))

    def test_generated_blog_image_is_allowed(self):
        self.assertTrue(
            contract.is_article_publication_path(
                "public/images/generated/blog/example.jpg"
            )
        )

    def test_unknown_file_is_forbidden(self):
        self.assertEqual(
            contract.forbidden_article_paths(
                ["src/data/posts.json", "src/pages/Home/Home.module.css"]
            ),
            ["src/pages/Home/Home.module.css"],
        )

    def test_kindergarten_play_article_has_canonical_source_identity(self):
        # A newly authored article must not silently enter legacy exclusions
        # because visible Latin journal names or acronyms fail source_metadata.
        root = Path(__file__).resolve().parents[1]
        posts = json.loads((root / "src/data/postsRecent.json").read_text(encoding="utf-8"))
        matches = [post for post in posts if post.get("slug") == "child-not-playing-kindergarten"]
        self.assertEqual(len(matches), 1)
        source = source_metadata(matches[0])
        self.assertEqual(source["slug"], "child-not-playing-kindergarten")
        self.assertEqual(source["canonical_url"], "https://kesher.saharoni.com/blog/child-not-playing-kindergarten")
        self.assertEqual(source["content_sha256"], "60374e686f7857610eeee5594af17f52a80223788650ef467ce27f5ec824dcaa")

    def test_child_poops_in_pants_keyword_maps_to_canonical_slug(self):
        ok, message = slug_represents_keyword(
            "child-poops-in-pants",
            "ילד עושה קקי במכנסיים",
        )
        self.assertTrue(ok, message)


if __name__ == "__main__":
    unittest.main()

import unittest

from scripts import kesher_article_contract as contract


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


if __name__ == "__main__":
    unittest.main()

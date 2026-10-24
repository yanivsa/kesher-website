#!/usr/bin/env python3
import unittest

from scripts.kesher_primary_keyword_contract import slug_represents_keyword


class ChildPoopsPrimaryKeywordRegressionTests(unittest.TestCase):
    def test_child_poops_in_pants_keyword_maps_to_canonical_slug(self):
        ok, message = slug_represents_keyword(
            "child-poops-in-pants",
            "ילד עושה קקי במכנסיים",
        )
        self.assertTrue(ok, message)


if __name__ == "__main__":
    unittest.main()

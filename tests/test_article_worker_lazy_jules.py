import unittest

from scripts.kesher_runtime.article_worker import LazyJules


class LazyJulesTests(unittest.TestCase):
    def test_does_not_construct_provider_until_used(self):
        calls = []
        lazy = LazyJules(lambda: calls.append('created') or object())
        self.assertEqual(calls, [])
        with self.assertRaises(AttributeError):
            lazy.sessions
        self.assertEqual(calls, ['created'])


if __name__ == '__main__':
    unittest.main()

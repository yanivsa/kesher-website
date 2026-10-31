import unittest

from scripts.kesher_runtime.article_worker import LazyJules


class FakeJules:
    def __init__(self):
        self.calls = []

    def sessions(self):
        self.calls.append('sessions')
        return [{'name': 'sessions/legacy'}]


class LazyJulesTests(unittest.TestCase):
    def test_does_not_construct_provider_until_first_real_use_then_reuses_it(self):
        created = []

        def factory():
            instance = FakeJules()
            created.append(instance)
            return instance

        lazy = LazyJules(factory)
        self.assertEqual(created, [])
        self.assertEqual(lazy.sessions(), [{'name': 'sessions/legacy'}])
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].calls, ['sessions'])
        self.assertEqual(lazy.sessions(), [{'name': 'sessions/legacy'}])
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].calls, ['sessions', 'sessions'])


if __name__ == '__main__':
    unittest.main()

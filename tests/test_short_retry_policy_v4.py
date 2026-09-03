import unittest

from scripts.kesher_short_policy import ShortDecision, decide_short_action


class ShortRetryPolicyV4Tests(unittest.TestCase):
    def test_fresh_generation_is_allowed_only_before_four_failed_attempts(self):
        for attempts in range(0, 4):
            with self.subTest(attempts=attempts):
                self.assertEqual(
                    decide_short_action(attempts, has_recoverable_identity=False),
                    ShortDecision.GENERATE,
                )

    def test_fourth_failed_attempt_releases_article_without_short(self):
        self.assertEqual(
            decide_short_action(4, has_recoverable_identity=False),
            ShortDecision.RELEASE_WITHOUT_SHORT,
        )

    def test_fifth_slot_is_recovery_only_for_existing_identity(self):
        self.assertEqual(
            decide_short_action(4, has_recoverable_identity=True),
            ShortDecision.RECOVER,
        )

    def test_no_fresh_generation_after_attempt_five(self):
        self.assertEqual(
            decide_short_action(5, has_recoverable_identity=False),
            ShortDecision.RELEASE_WITHOUT_SHORT,
        )
        self.assertEqual(
            decide_short_action(5, has_recoverable_identity=True),
            ShortDecision.RELEASE_WITHOUT_SHORT,
        )


if __name__ == "__main__":
    unittest.main()

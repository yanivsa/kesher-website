"""Hermetic tests: session recovery must never create a second Jules task."""
import hashlib
import unittest

from scripts import kesher_jules_exact_session_recovery as m


class ExactSessionRecoveryTests(unittest.TestCase):
    def valid(self, slot: str, *, state: str = "IN_PROGRESS") -> dict:
        return {
            "name": f"sessions/{m.ALLOWED[slot][0]}",
            "title": m.expected_title(slot),
            "state": state,
            "sourceContext": {"source": m.REPOSITORY_SOURCE},
            "outputs": [],
        }

    def test_title_is_bound_to_owner_keyword(self):
        for slot, (sid, keyword, idea) in m.ALLOWED.items():
            with self.subTest(slot=slot):
                self.assertEqual(
                    m.expected_title(slot),
                    f"Kesher article {slot} kw-{hashlib.sha256(keyword.encode('utf-8')).hexdigest()[:10]}",
                )
                self.assertIn(idea, m.nudge_prompt(slot))
                self.assertIn("SAME session", m.nudge_prompt(slot))

    def test_existing_exact_session_is_adopted(self):
        for slot in m.ALLOWED:
            self.assertEqual(m.inspect_identity(self.valid(slot), slot), ("IN_PROGRESS", []))

    def test_fails_closed_on_wrong_session_or_repo(self):
        payload = self.valid("2026-11-07")
        payload["name"] = "sessions/1234"
        with self.assertRaises(ValueError):
            m.inspect_identity(payload, "2026-11-07")
        payload = self.valid("2026-11-07")
        payload["sourceContext"]["source"] = "sources/github/attacker/other"
        with self.assertRaises(ValueError):
            m.inspect_identity(payload, "2026-11-07")

    def test_fails_closed_on_wrong_keyword_or_bad_pr_url(self):
        payload = self.valid("2026-11-08")
        payload["title"] = "Kesher article 2026-11-08"
        with self.assertRaises(ValueError):
            m.inspect_identity(payload, "2026-11-08")
        payload = self.valid("2026-11-08")
        payload["outputs"] = [{"pullRequest": {"url": "https://github.com/elsewhere/repo/pull/1"}}]
        with self.assertRaises(ValueError):
            m.inspect_identity(payload, "2026-11-08")

    def test_completed_session_is_visible_without_recreation(self):
        payload = self.valid("2026-11-07", state="COMPLETED")
        payload["outputs"] = [{"pullRequest": {"url": "https://github.com/yanivsa/kesher-website/pull/1301"}}]
        self.assertEqual(m.inspect_identity(payload, "2026-11-07"),
                         ("COMPLETED", ["https://github.com/yanivsa/kesher-website/pull/1301"]))
        self.assertNotIn("COMPLETED", m.ACTIVE)

    def test_source_specific_no_duplicate_prompts(self):
        for slot in m.ALLOWED:
            prompt = m.nudge_prompt(slot)
            self.assertIn("Do NOT create a separate article", prompt)
            self.assertIn("exactly ONE", prompt)
            self.assertIn("CI", prompt)


if __name__ == "__main__":
    unittest.main()

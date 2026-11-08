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
        payload["title"] = "Kesher article 2026-11-09"
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

    def test_exact_pinned_session_supports_legacy_or_redacted_title(self):
        for slot in m.ALLOWED:
            p = self.valid(slot)
            p["title"] = f"Kesher article {slot}"
            self.assertEqual(m.inspect_identity(p, slot), ("IN_PROGRESS", []))
            p.pop("title")
            self.assertEqual(m.inspect_identity(p, slot), ("IN_PROGRESS", []))

    def test_rejects_foreign_original_prompt_when_present(self):
        p = self.valid("2026-11-08")
        p["prompt"] = "Unrelated marketing article about auto insurance"
        with self.assertRaises(ValueError):
            m.inspect_identity(p, "2026-11-08")

    def test_source_specific_no_duplicate_prompts(self):
        for slot in m.ALLOWED:
            prompt = m.nudge_prompt(slot)
            self.assertIn("Do NOT create a separate article", prompt)
            self.assertIn("exactly ONE", prompt)
            self.assertIn("CI", prompt)

    def test_owner_stress_session_is_pinned_without_confusing_nov8_legacy(self):
        key = m.STRESS_SLOT
        sid, keyword, idea = m.STRESS_SESSION
        self.assertEqual(sid, "13248247772650112609")
        self.assertEqual(m.publication_date(key), "2026-11-08")
        self.assertIn("Kesher article 2026-11-08 kw-", m.expected_title(key))
        payload = {
            "name": f"sessions/{sid}",
            "title": m.expected_title(key),
            "state": "IN_PROGRESS",
            "sourceContext": {"source": m.REPOSITORY_SOURCE},
            "prompt": f"owner idea_id={idea}; primary keyword={keyword}",
            "outputs": [],
        }
        self.assertEqual(m.inspect_identity(payload, key), ("IN_PROGRESS", []))
        self.assertIn("Do NOT create a separate article", m.nudge_prompt(key))
        self.assertIn("exactly ONE", m.nudge_prompt(key))
        self.assertIn("SAME session", m.nudge_prompt(key))
        payload["name"] = f"sessions/{m.ALLOWED['2026-11-08'][0]}"
        with self.assertRaises(ValueError):
            m.inspect_identity(payload, key)
        payload["name"] = f"sessions/{sid}"
        payload["prompt"] = "Unrelated auto insurance article"
        with self.assertRaises(ValueError):
            m.inspect_identity(payload, key)
        payload["prompt"] = f"owner idea_id={idea}; primary keyword={keyword}"
        payload["outputs"] = [{"pullRequest": {"url": "https://github.com/attacker/other/pull/1"}}]
        with self.assertRaises(ValueError):
            m.inspect_identity(payload, key)

    def test_owner_stress_session_check_has_zero_creation_capabilities(self):
        key = m.STRESS_SLOT
        self.assertIn("sessions/13248247772650112609", f"sessions/{m.source_spec(key)[0]}")
        with self.assertRaises(ValueError):
            m.source_spec("2026-11-09-stress")


if __name__ == "__main__":
    unittest.main()

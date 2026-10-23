import copy
import unittest

from scripts import kesher_idea_queue as idea_queue


SHA = "7ef7e1056067f070f8beb91388d3a9e3bdf3de2c3899f6665ae6e4b7e257244a"
SLUG = "potty-training-constipation"
ARTICLE_URL = "https://kesher.saharoni.com/blog/potty-training-constipation"
LONG_URL = "https://youtu.be/7YU6BL9BZ98"
SHORT_URL = "https://youtu.be/jdD0h_rGYkA"


def _state():
    return {
        "cycle": "2026-10-23",
        "status": "blocked",
        "last_error": {
            "stage": "controller",
            "code": "IDEA_SLOT_MISMATCH",
            "message": "IDEA_SLOT_MISMATCH",
        },
        "article": {"status": "pending", "attempts": 0},
        "long_video": {"status": "pending", "attempt_count": 0},
        "short": {"status": "pending", "attempt_count": 0},
        "active_idea": {
            "idea_id": "parenting-p1-potty-training-constipation",
            "fingerprint": "fp",
            "topic_brief": "prior idea; Canonical ID required: potty-training-constipation",
            "required_primary_keyword": "עצירות בגמילה מחיתולים",
            "run_now": False,
            "status": "claimed",
            "publication_slot": "2026-10-21",
        },
        "idea_queue": [],
        "idea_history": [],
        "backlog": [
            {
                "cycle": "2026-10-21",
                "status": "article_deploying",
                "exact_slug": SLUG,
                "article": {
                    "status": "pending",
                    "slug": SLUG,
                    "url": ARTICLE_URL,
                    "quality_status": "passed",
                    "quality_content_sha256": SHA,
                    "live": False,
                },
                "media": {
                    "source_slug": SLUG,
                    "source_content_sha256": SHA,
                    "article_url": ARTICLE_URL,
                    "article_live": True,
                    "article_deploy_status": "complete",
                    "long_status": "complete",
                    "long_youtube_url": LONG_URL,
                    "short_status": "complete",
                    "short_youtube_url": SHORT_URL,
                    "short_width": 1080,
                    "short_height": 1920,
                    "complete": True,
                },
            }
        ],
        "history": [
            {
                "at": "2026-10-23T01:04:07+00:00",
                "from": "waiting_for_article_window",
                "to": "waiting_for_article_window",
                "reason": "prior-cycle article media delivery verified without disturbing current cycle",
                "details": {"backlog_cycle": "2026-10-21", "source_slug": SLUG},
            },
            {
                "at": "2026-10-23T05:01:31+00:00",
                "from": "waiting_for_article_window",
                "to": "blocked",
                "reason": "IDEA_SLOT_MISMATCH",
                "details": {"message": "IDEA_SLOT_MISMATCH"},
            },
        ],
    }


class StaleActiveIdeaRolloverTests(unittest.TestCase):
    def test_verified_prior_cycle_finalizes_stale_active_idea_and_unblocks_current_cycle(self):
        state = _state()
        current_stages = copy.deepcopy((state["article"], state["long_video"], state["short"]))

        changed = idea_queue.finalize_if_complete(state, now_iso="2026-10-23T07:45:00+00:00")

        self.assertTrue(changed)
        self.assertIsNone(state["active_idea"])
        self.assertEqual(state["status"], "waiting_for_article_window")
        self.assertIsNone(state["last_error"])
        self.assertEqual((state["article"], state["long_video"], state["short"]), current_stages)
        completed = state["idea_history"][-1]
        self.assertEqual(completed["status"], "complete")
        self.assertEqual(completed["outputs"]["slug"], SLUG)
        self.assertEqual(completed["outputs"]["content_sha256"], SHA)
        self.assertEqual(completed["outputs"]["article_url"], ARTICLE_URL)
        self.assertEqual(completed["outputs"]["long_url"], LONG_URL)
        self.assertEqual(completed["outputs"]["short_url"], SHORT_URL)
        self.assertEqual(completed["completion_source"], "verified_backlog")
        self.assertEqual(state["history"][-1]["reason"], "stale_active_idea_finalized_from_verified_backlog")

    def test_sha_mismatch_fails_closed(self):
        state = _state()
        state["backlog"][0]["media"]["source_content_sha256"] = "a" * 64
        before = copy.deepcopy(state)

        self.assertFalse(idea_queue.finalize_if_complete(state, now_iso="2026-10-23T07:45:00+00:00"))
        self.assertEqual(state, before)

    def test_incomplete_short_fails_closed(self):
        state = _state()
        state["backlog"][0]["media"]["short_status"] = "running"
        before = copy.deepcopy(state)

        self.assertFalse(idea_queue.finalize_if_complete(state, now_iso="2026-10-23T07:45:00+00:00"))
        self.assertEqual(state, before)

    def test_duplicate_backlog_cycle_fails_closed(self):
        state = _state()
        state["backlog"].append(copy.deepcopy(state["backlog"][0]))
        before = copy.deepcopy(state)

        self.assertFalse(idea_queue.finalize_if_complete(state, now_iso="2026-10-23T07:45:00+00:00"))
        self.assertEqual(state, before)

    def test_missing_delivery_verification_event_fails_closed(self):
        state = _state()
        state["history"] = [state["history"][-1]]
        before = copy.deepcopy(state)

        self.assertFalse(idea_queue.finalize_if_complete(state, now_iso="2026-10-23T07:45:00+00:00"))
        self.assertEqual(state, before)

    def test_current_cycle_completion_behavior_is_preserved(self):
        state = _state()
        state["cycle"] = "2026-10-21"
        state["status"] = "complete"
        state["last_error"] = None
        state["article"].update({"slug": SLUG, "url": ARTICLE_URL})
        state["long_video"].update({"youtube_url": LONG_URL})
        state["short"].update({"youtube_url": SHORT_URL})

        self.assertTrue(idea_queue.finalize_if_complete(state, now_iso="2026-10-23T07:45:00+00:00"))
        self.assertIsNone(state["active_idea"])
        self.assertEqual(state["idea_history"][-1]["outputs"]["short_url"], SHORT_URL)


if __name__ == "__main__":
    unittest.main()

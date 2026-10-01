from __future__ import annotations

import unittest

from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_content_controller_v5_runtime as runtime



def make_post(slug, *, date="2026-10-01", managed=True, title=None):
    return {
        "id": slug,
        "slug": slug,
        "title": title or f"כותרת {slug}",
        "date": date,
        "category": "זוגיות",
        "excerpt": "תקציר בדיקה",
        "content": "<p>תוכן בדיקה מלא עבור שרשרת קשר.</p>",
        "controllerManaged": managed,
    }


class _FakeGitHub:
    def __init__(self, posts):
        self.posts = posts

    def contents_json(self, path, ref):
        assert path == "src/data/posts.json"
        assert ref == "main"
        return self.posts


class _FakeSite:
    def __init__(self, posts):
        self.titles = {
            str(post.get("slug") or post.get("id")): str(post.get("title") or "")
            for post in posts
        }

    def get(self, url):
        slug = url.rsplit("/", 1)[-1]
        title = self.titles.get(slug, "")
        return 200, f"<html><h1>{title}</h1></html>"


def controller_for(posts):
    ctl = object.__new__(runtime.RuntimeV5Controller)
    ctl.github = _FakeGitHub(posts)
    ctl.site = _FakeSite(posts)
    return ctl


class KesherV5BacklogPriorityTests(unittest.TestCase):
    def test_newest_recoverable_backlog_wins_over_old_exhausted_short(self):
        rows = [
            {
                "cycle": "2026-09-02",
                "media": {
                    "short_status": "exhausted",
                    "last_error": "BACKLOG_SHORT_ATTEMPTS_EXHAUSTED",
                },
            },
            {"cycle": "2026-09-05", "media": {}},
            {"cycle": "2026-09-03", "media": {}},
        ]

        ordered = runtime.ordered_recoverable_backlog(rows)

        self.assertEqual([row["cycle"] for row in ordered], ["2026-09-05", "2026-09-03"])

    def test_completed_and_terminal_seed_rows_are_not_reselected(self):
        rows = [
            {"cycle": "2026-09-05", "media": {"complete": True}},
            {
                "cycle": "2026-09-04",
                "media": {
                    "long_status": "exhausted",
                    "last_error": "BACKLOG_EXACT_SEED_ATTEMPTS_EXHAUSTED",
                },
            },
            {"cycle": "2026-09-03", "media": {}},
        ]

        ordered = runtime.ordered_recoverable_backlog(rows)

        self.assertEqual([row["cycle"] for row in ordered], ["2026-09-03"])

    def test_incomplete_actionable_current_cycle_blocks_backlog(self):
        self.assertFalse(
            runtime.backlog_may_run(
                {"status": "long_video_running"},
                current_cycle_complete=False,
            )
        )
        self.assertFalse(
            runtime.backlog_may_run(
                {"status": "short_running"},
                current_cycle_complete=False,
            )
        )

    def test_waiting_for_publication_window_can_use_idle_capacity_for_backlog(self):
        self.assertTrue(
            runtime.backlog_may_run(
                {"status": "waiting_for_article_window"},
                current_cycle_complete=False,
            )
        )

    def test_completed_current_cycle_allows_backlog_cleanup(self):
        self.assertTrue(
            runtime.backlog_may_run(
                {"status": "complete"},
                current_cycle_complete=True,
            )
        )


    def test_persisted_article_slug_wins_when_two_posts_share_date(self):
        managed = make_post("adhd-waiting-mode")
        manual = make_post("marriage-hack-7-minutes", managed=False)
        state = {
            "backlog": [{
                "cycle": "2026-10-01",
                "article": {"slug": "adhd-waiting-mode"},
                "media": {},
            }]
        }

        row, source = controller_for([managed, manual])._published_backlog_source(state)

        self.assertIsNotNone(row)
        self.assertEqual(source["slug"], "adhd-waiting-mode")
        self.assertEqual(row["media"]["source_slug"], "adhd-waiting-mode")

    def test_persisted_media_slug_wins_when_article_snapshot_is_sparse(self):
        managed = make_post("adhd-waiting-mode")
        manual = make_post("marriage-hack-7-minutes", managed=False)
        state = {
            "backlog": [{
                "cycle": "2026-10-01",
                "article": {},
                "media": {"source_slug": "marriage-hack-7-minutes"},
            }]
        }

        _, source = controller_for([managed, manual])._published_backlog_source(state)

        self.assertEqual(source["slug"], "marriage-hack-7-minutes")

    def test_managed_post_is_safe_fallback_when_same_day_manual_post_exists(self):
        managed = make_post("adhd-waiting-mode")
        manual = make_post("marriage-hack-7-minutes", managed=False)
        state = {
            "backlog": [{
                "cycle": "2026-10-01",
                "article": {},
                "media": {},
            }]
        }

        _, source = controller_for([manual, managed])._published_backlog_source(state)

        self.assertEqual(source["slug"], "adhd-waiting-mode")

    def test_persisted_media_sha_mismatch_fails_closed(self):
        managed = make_post("adhd-waiting-mode")
        state = {
            "backlog": [{
                "cycle": "2026-10-01",
                "article": {"slug": "adhd-waiting-mode"},
                "media": {
                    "source_slug": "adhd-waiting-mode",
                    "source_content_sha256": "stale-sha",
                },
            }]
        }

        with self.assertRaisesRegex(
            v5.core.ControllerError,
            "BACKLOG_ARTICLE_CONTENT_CHANGED: adhd-waiting-mode",
        ):
            controller_for([managed])._published_backlog_source(state)


if __name__ == "__main__":
    unittest.main()

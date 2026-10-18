"""Regression tests for exact public article identity and verifier fail-closed semantics."""
from __future__ import annotations

import unittest

from scripts.kesher_content_controller import article_is_public

SITE_URL = "https://kesher.saharoni.com"


class ExactPublicArticleIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.slug = "marriage-communication-repair"
        self.title = "תיקון תקשורת בזוגיות"
        self.content_sha = "a" * 64
        self.hero_path = f"/images/generated/blog/{self.slug}.png"
        self.canonical_url = f"{SITE_URL}/blog/{self.slug}"

    def valid_html(self) -> str:
        return (
            f"<!doctype html><html><head><title>{self.title}</title>"
            f"<link rel='canonical' href='{self.canonical_url}'>"
            f"<meta property='og:url' content='{self.canonical_url}'>"
            f"<meta property='og:image' content='{SITE_URL}{self.hero_path}'>"
            f"<meta name='kesher:content-sha256' content='{self.content_sha}'>"
            f"</head><body><h1>{self.title}</h1><img src='{self.hero_path}' alt='Hero'></body></html>"
        )

    def test_exact_proof_passes_when_all_match(self) -> None:
        self.assertTrue(
            article_is_public(
                self.valid_html(),
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
                expected_hero_path=self.hero_path,
            )
        )

    def test_missing_canonical_fails(self) -> None:
        html = (
            f"<!doctype html><html><head><title>{self.title}</title>"
            f"<meta property='og:url' content='{self.canonical_url}'>"
            f"<meta property='og:image' content='{SITE_URL}{self.hero_path}'>"
            f"<meta name='kesher:content-sha256' content='{self.content_sha}'>"
            f"</head><body><h1>{self.title}</h1></body></html>"
        )
        self.assertFalse(
            article_is_public(
                html,
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
                expected_hero_path=self.hero_path,
            )
        )

    def test_wrong_canonical_url_fails(self) -> None:
        html = (
            f"<!doctype html><html><head><title>{self.title}</title>"
            f"<link rel='canonical' href='{SITE_URL}/blog/stale-other-slug'>"
            f"<meta property='og:url' content='{self.canonical_url}'>"
            f"<meta property='og:image' content='{SITE_URL}{self.hero_path}'>"
            f"<meta name='kesher:content-sha256' content='{self.content_sha}'>"
            f"</head><body><h1>{self.title}</h1></body></html>"
        )
        self.assertFalse(
            article_is_public(
                html,
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
                expected_hero_path=self.hero_path,
            )
        )

    def test_wrong_og_url_fails(self) -> None:
        html = (
            f"<!doctype html><html><head><title>{self.title}</title>"
            f"<link rel='canonical' href='{self.canonical_url}'>"
            f"<meta property='og:url' content='{SITE_URL}/blog/stale-other-slug'>"
            f"<meta property='og:image' content='{SITE_URL}{self.hero_path}'>"
            f"<meta name='kesher:content-sha256' content='{self.content_sha}'>"
            f"</head><body><h1>{self.title}</h1></body></html>"
        )
        self.assertFalse(
            article_is_public(
                html,
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
                expected_hero_path=self.hero_path,
            )
        )

    def test_missing_content_sha_fails(self) -> None:
        html = (
            f"<!doctype html><html><head><title>{self.title}</title>"
            f"<link rel='canonical' href='{self.canonical_url}'>"
            f"<meta property='og:url' content='{self.canonical_url}'>"
            f"<meta property='og:image' content='{SITE_URL}{self.hero_path}'>"
            f"</head><body><h1>{self.title}</h1></body></html>"
        )
        self.assertFalse(
            article_is_public(
                html,
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
                expected_hero_path=self.hero_path,
            )
        )

    def test_wrong_content_sha_fails(self) -> None:
        html = (
            f"<!doctype html><html><head><title>{self.title}</title>"
            f"<link rel='canonical' href='{self.canonical_url}'>"
            f"<meta property='og:url' content='{self.canonical_url}'>"
            f"<meta property='og:image' content='{SITE_URL}{self.hero_path}'>"
            f"<meta name='kesher:content-sha256' content='{'b' * 64}'>"
            f"</head><body><h1>{self.title}</h1></body></html>"
        )
        self.assertFalse(
            article_is_public(
                html,
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
                expected_hero_path=self.hero_path,
            )
        )

    def test_missing_hero_evidence_fails(self) -> None:
        html = (
            f"<!doctype html><html><head><title>{self.title}</title>"
            f"<link rel='canonical' href='{self.canonical_url}'>"
            f"<meta property='og:url' content='{self.canonical_url}'>"
            f"<meta name='kesher:content-sha256' content='{self.content_sha}'>"
            f"</head><body><h1>{self.title}</h1></body></html>"
        )
        self.assertFalse(
            article_is_public(
                html,
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
                expected_hero_path=self.hero_path,
            )
        )

    def test_wrong_hero_image_fails_stale_deployment(self) -> None:
        wrong_hero = "/images/generated/blog/stale-previous-hero.png"
        html = (
            f"<!doctype html><html><head><title>{self.title}</title>"
            f"<link rel='canonical' href='{self.canonical_url}'>"
            f"<meta property='og:url' content='{self.canonical_url}'>"
            f"<meta property='og:image' content='{SITE_URL}{wrong_hero}'>"
            f"<meta name='kesher:content-sha256' content='{self.content_sha}'>"
            f"</head><body><h1>{self.title}</h1><img src='{wrong_hero}'></body></html>"
        )
        self.assertFalse(
            article_is_public(
                html,
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
                expected_hero_path=self.hero_path,
            )
        )

    def test_canonical_url_substring_collision_fails(self) -> None:
        html = (
            f"<!doctype html><html><head><title>{self.title}</title>"
            f"<link rel='canonical' href='{self.canonical_url}-other-suffix'>"
            f"<meta property='og:url' content='{self.canonical_url}'>"
            f"<meta property='og:image' content='{SITE_URL}{self.hero_path}'>"
            f"<meta name='kesher:content-sha256' content='{self.content_sha}'>"
            f"</head><body><h1>{self.title}</h1><img src='{self.hero_path}'></body></html>"
        )
        self.assertFalse(
            article_is_public(
                html,
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
                expected_hero_path=self.hero_path,
            )
        )

    def test_og_url_substring_collision_fails(self) -> None:
        html = (
            f"<!doctype html><html><head><title>{self.title}</title>"
            f"<link rel='canonical' href='{self.canonical_url}'>"
            f"<meta property='og:url' content='{self.canonical_url}-other-suffix'>"
            f"<meta property='og:image' content='{SITE_URL}{self.hero_path}'>"
            f"<meta name='kesher:content-sha256' content='{self.content_sha}'>"
            f"</head><body><h1>{self.title}</h1><img src='{self.hero_path}'></body></html>"
        )
        self.assertFalse(
            article_is_public(
                html,
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
                expected_hero_path=self.hero_path,
            )
        )

    def test_hero_bytes_fetch_matching_sha_succeeds(self) -> None:
        import hashlib
        hero_data = b"image-pixel-data-12345"
        hero_sha = hashlib.sha256(hero_data).hexdigest()

        def fetcher(url: str):
            return 200, hero_data

        self.assertTrue(
            article_is_public(
                self.valid_html(),
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
                expected_hero_path=self.hero_path,
                expected_hero_sha256=hero_sha,
                hero_fetcher=fetcher,
            )
        )

    def test_hero_bytes_fetch_wrong_sha_fails_stale_asset(self) -> None:
        import hashlib
        expected_hero_data = b"fresh-image-pixel-data"
        expected_hero_sha = hashlib.sha256(expected_hero_data).hexdigest()
        stale_hero_data = b"stale-cached-old-hero"

        def fetcher(url: str):
            return 200, stale_hero_data

        self.assertFalse(
            article_is_public(
                self.valid_html(),
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
                expected_hero_path=self.hero_path,
                expected_hero_sha256=expected_hero_sha,
                hero_fetcher=fetcher,
            )
        )

    def test_hero_bytes_fetch_http_error_fails(self) -> None:
        def fetcher(url: str):
            return 404, b"Not Found"

        self.assertFalse(
            article_is_public(
                self.valid_html(),
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
                expected_hero_path=self.hero_path,
                expected_hero_sha256="a" * 64,
                hero_fetcher=fetcher,
            )
        )

    def test_stabilized_controller_blocks_long_video_when_hero_bytes_stale(self) -> None:
        from datetime import datetime, timezone
        import hashlib
        from unittest.mock import MagicMock
        from scripts import kesher_content_controller_stabilized as stabilized_mod

        mock_github = MagicMock()
        mock_github.active_workflow_run.return_value = None
        mock_site = MagicMock()

        ctrl = stabilized_mod.StabilizedRuntimeV5Controller(mock_github, mock_site)
        ctrl.now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)

        expected_hero_bytes = b"authoritative-fresh-hero-bytes"
        expected_hero_sha = hashlib.sha256(expected_hero_bytes).hexdigest()
        stale_hero_bytes = b"stale-edge-cached-hero-bytes"

        post = {
            "id": self.slug,
            "slug": self.slug,
            "title": self.title,
            "date": "2026-10-14",
            "content": "<p>" + ("מילה " * 750) + "</p>",
            "category": "זוגיות",
            "excerpt": "תקציר בדיקה העומד בכללים",
            "image": self.hero_path,
            "image_sha256": expected_hero_sha,
        }
        ctrl.posts_on_main = lambda ref: [post]

        # Site returns 200 OK for HTML
        mock_site.get.return_value = (200, self.valid_html())
        # But site returns STALE bytes for hero image asset!
        mock_site.get_bytes.return_value = (200, stale_hero_bytes)

        state = {
            "cycle": "2026-10-14",
            "status": "article_merged",
            "article": {
                "slug": self.slug,
                "status": "merged",
                "quality_content_sha256": self.content_sha,
                "deploy_attempts": 0,
            },
            "video": {"status": "pending"},
            "history": [],
        }

        is_pub, deploy_action = ctrl._ensure_article_public_and_deployed(state)
        # Must fail publication verification!
        self.assertFalse(is_pub)
        self.assertFalse(state["article"]["live"])
        # Action must be dispatch_deploy or wait, NOT advancing to Long video!
        self.assertIsNotNone(deploy_action)
        self.assertEqual(deploy_action.kind, "dispatch_deploy")


if __name__ == "__main__":
    unittest.main()

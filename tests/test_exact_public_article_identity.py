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

    def test_title_and_sha_only_without_canonical_and_without_hero_fails(self) -> None:
        html = (
            f"<!doctype html><html><head><title>{self.title}</title>"
            f"<meta name='kesher:content-sha256' content='{self.content_sha}'>"
            f"</head><body><h1>{self.title}</h1></body></html>"
        )
        self.assertFalse(
            article_is_public(
                html,
                self.title,
                expected_slug=self.slug,
                expected_content_sha256=self.content_sha,
            )
        )


if __name__ == "__main__":
    unittest.main()

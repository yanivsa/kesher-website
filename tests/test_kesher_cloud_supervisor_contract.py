"""Fail-closed three-link quality contract regression tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import kesher_cloud_supervisor as supervisor


class StrictTriadContractTests(unittest.TestCase):
    SHA = "a" * 64
    SLUG = "quality-evidence-test-article"
    LONG = "LongX12345a"
    SHORT = "ShortX1234b"

    def post(self):
        slug = self.SLUG
        return {
            "id": slug, "slug": slug, "date": "2026-11-22",
            "title": "מאמר לבדיקת אימות מקור", "excerpt": "תוכן מחקרי בדוק",
            "category": "הדרכת הורים", "content": "<p>גוף המאמר</p>",
            "image": f"/images/generated/blog/{slug}.jpg",
            "youtubeVideoId": self.LONG, "youtubeShortId": self.SHORT,
        }

    def video_state(self, source_sha=None):
        slug = self.SLUG
        return {"items": [{
            "id": "long-evidence", "uploaded": True, "youtube_id": self.LONG,
            "task_id": "provider-overview-task",
            "visual_pipeline": "remotion-v1-notebooklm-audio",
            "technical_verified": True, "signature_verified": True,
            "media": {"width": 1280, "height": 720},
            "source": {
                "slug": slug, "content_sha256": source_sha or self.SHA,
                "youtube_metadata": {"description": f"https://kesher.saharoni.com/blog/{slug}"},
            },
        }]}

    def short_state(self, source_sha=None):
        slug = self.SLUG
        return {"items": [{
            "id": "short-evidence", "uploaded": True, "youtube_id": self.SHORT,
            "task_id": "provider-native-short-task", "provider_native_short": True,
            "provider_video_format": "short", "shared_provider_identity": False,
            "technical_verified": True, "signature_verified": True,
            "provider_raw_media": {"width": 720, "height": 1280},
            "source": {
                "slug": slug, "content_sha256": source_sha or self.SHA,
                "youtube_metadata": {"description": f"https://kesher.saharoni.com/blog/{slug}"},
            },
        }]}

    def evaluate(self, video=None, short=None):
        post = self.post()
        catalogue = {
            self.SLUG: {"youtubeId": self.LONG, "shortYoutubeId": self.SHORT}
        }
        live_html = f"<title>{post['title']}</title><p>{self.LONG}</p>"
        author = {
            "author_url": f"https://www.youtube.com/channel/{supervisor.YOUTUBE_CHANNEL_ID}",
            "author_name": "KESHER",
        }
        with tempfile.TemporaryDirectory() as tmp:
            hero = Path(tmp) / "public/images/generated/blog" / f"{self.SLUG}.jpg"
            hero.parent.mkdir(parents=True, exist_ok=True)
            hero.write_bytes(b"JPEG fixture with verified dimensions " * 700)
            with (
                patch.object(supervisor, "PROJECT_DIR", Path(tmp)),
                patch.object(supervisor, "get_image_size", return_value=(1200, 675)),
                patch("scripts.kesher_daily_pipeline.source_metadata", return_value={"content_sha256": self.SHA}),
                patch.object(supervisor, "check_site_url", return_value=(True, 200, live_html)),
                patch.object(supervisor, "verify_canonical_url", return_value=True),
                patch.object(supervisor, "verify_youtube_public", return_value=(True, author)),
                patch.object(supervisor, "load_cached_artifact_state", side_effect=[
                    video if video is not None else self.video_state(),
                    short if short is not None else self.short_state(),
                ]),
            ):
                return supervisor.audit_single_triad(post, catalogue)

    def test_empty_excerpt_cannot_fake_article_content(self):
        self.assertFalse(supervisor.article_content_present("כותרת חשובה", "", "תוכן לא קשור"))
        self.assertFalse(supervisor.article_content_present("", "", "גוף כלשהו"))
        self.assertTrue(supervisor.article_content_present("כותרת חשובה", "", "כותרת חשובה בגוף"))
        self.assertTrue(supervisor.article_content_present("כותרת אחרת", "מסקנה מחקרית", "מסקנה מחקרית מפורטת"))

    def test_verified_exact_identity_can_pass(self):
        triad = self.evaluate()
        self.assertTrue(triad["quality_verified"])
        self.assertTrue(triad["complete"])
        self.assertEqual(triad["status"], "COMPLETE")

    def test_wrong_long_source_hash_is_quality_hold_even_with_public_links(self):
        triad = self.evaluate(video=self.video_state("b" * 64))
        self.assertTrue(triad["long_video"]["public"])
        self.assertTrue(triad["cross_links_verified"])
        self.assertFalse(triad["long_video"]["provenance_verified"])
        self.assertFalse(triad["complete"])
        self.assertEqual(triad["status"], "QUALITY_HOLD")

    def test_wrong_short_source_hash_is_quality_hold(self):
        triad = self.evaluate(short=self.short_state("c" * 64))
        self.assertTrue(triad["short"]["public"])
        self.assertFalse(triad["short"]["provenance_verified"])
        self.assertFalse(triad["complete"])

    def test_missing_signature_or_native_portrait_fails_closed(self):
        state = self.short_state()
        state["items"][0]["signature_verified"] = False
        self.assertFalse(self.evaluate(short=state)["complete"])
        state = self.short_state()
        state["items"][0]["provider_raw_media"] = {"width": 1280, "height": 720}
        self.assertFalse(self.evaluate(short=state)["complete"])

    def test_hero_remote_200_is_not_dimensions_proof(self):
        post = self.post()
        with (
            patch.object(supervisor, "check_site_url", return_value=(True, 200, "irrelevant")),
            patch.object(supervisor, "verify_canonical_url", return_value=True),
            patch.object(supervisor, "verify_youtube_public", return_value=(False, {})),
            patch.object(supervisor, "load_cached_artifact_state", return_value=None),
            patch("scripts.kesher_daily_pipeline.source_metadata", return_value={"content_sha256": self.SHA}),
        ):
            result = supervisor.audit_single_triad(post, {})
        self.assertTrue(result["article"].get("remote_hero_available"))
        self.assertFalse(result["article"]["hero_image_verified"])
        self.assertFalse(result["complete"])

    def test_missing_state_never_substituted_by_public_oembed(self):
        triad = self.evaluate(video={"items": []}, short={"items": []})
        self.assertTrue(triad["long_video"]["public"])
        self.assertTrue(triad["short"]["public"])
        self.assertFalse(triad["quality_verified"])
        self.assertEqual(triad["status"], "QUALITY_HOLD")


if __name__ == "__main__":
    unittest.main()

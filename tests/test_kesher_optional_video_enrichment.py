from __future__ import annotations

import unittest

from scripts import kesher_e2e_delivery_guard as guard


class OptionalVideoEnrichmentContractTests(unittest.TestCase):
    def _complete_state(self) -> dict:
        return {
            "article": {
                "live": True,
                "url": "https://kesher.saharoni.com/blog/example",
            },
            "long_video": {
                "verified": True,
                "youtube_url": "https://youtu.be/overview123",
                "enhancement": {
                    "broll_available": False,
                    "assets_available": False,
                    "status": "skipped_no_assets",
                },
            },
            "short": {
                "verified": True,
                "youtube_url": "https://youtu.be/short123",
                "portrait_verified": True,
                "type": guard.CANONICAL_SHORT_TYPE,
                "source_mode": guard.CANONICAL_SHORT_SOURCE_MODE,
                "visual_pipeline": guard.CANONICAL_SHORT_PIPELINE,
                "signature_verified": True,
                "signature_fullscreen": True,
                "signature_duration_seconds": guard.SIGNATURE_DURATION_SECONDS,
                "signature_video_sha256": "signature-video-sha256",
                "enhancement": {
                    "broll_available": False,
                    "assets_available": False,
                    "status": "skipped_no_assets",
                },
            },
        }

    def test_missing_broll_and_assets_never_block_complete_delivery(self) -> None:
        ready, deliverables = guard.delivery_contract(self._complete_state())

        self.assertFalse(guard.ENHANCEMENT_REQUIRED_FOR_PUBLICATION)
        self.assertTrue(ready)
        self.assertEqual(
            deliverables["overview_youtube_url"],
            "https://youtu.be/overview123",
        )
        self.assertEqual(
            deliverables["short_youtube_url"],
            "https://youtu.be/short123",
        )


if __name__ == "__main__":
    unittest.main()

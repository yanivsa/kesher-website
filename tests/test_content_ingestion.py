from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import content_performance_ledger as ledger
from scripts import ingest_content_performance as ingest


def sample_record(clicks: int = 10, content_id: str = "article:marriage-prep") -> dict:
    return {
        "schema_version": 1,
        "content_id": content_id,
        "content_type": "article",
        "slug": content_id.split(":")[-1],
        "publish_date": "2026-09-01",
        "topic": "הכנה לנישואים",
        "public_url": f"https://kesher.saharoni.com/blog/{content_id.split(':')[-1]}",
        "window": "7d",
        "source": "ga4+search-console",
        "observed_at": "2026-09-07T08:00:00+00:00",
        "metrics": {
            "pageviews": 100,
            "sessions": 80,
            "users": 70,
            "lead_clicks": 5,
            "shares": 2,
            "search_clicks": clicks,
            "search_impressions": 500,
            "search_ctr": 0.05,
            "engagement_seconds": 90,
        },
        "decision": "continue_topic",
    }


class ContentIngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.ledger_path = Path(self.tmpdir.name) / "content-performance.jsonl"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_ingest_fails_closed_when_credentials_missing(self):
        """Missing credentials must exit non-zero and leave ledger file non-existent."""
        env = dict(os.environ)
        env.pop(ingest.GA4_PROPERTY_ENV, None)
        env.pop(ingest.GSC_SITE_URL_ENV, None)
        env.pop(ingest.GOOGLE_CREDENTIALS_ENV, None)

        with mock.patch.dict(os.environ, env, clear=True):
            code = ingest.main(["--ledger", str(self.ledger_path)])
            self.assertEqual(code, 1)
            self.assertFalse(self.ledger_path.exists())

    def test_ledger_left_byte_for_byte_unchanged_on_auth_failure(self):
        """When auth fails, existing ledger file must remain byte-for-byte identical."""
        initial_record = sample_record()
        ledger.upsert(self.ledger_path, initial_record)
        initial_sha = hashlib.sha256(self.ledger_path.read_bytes()).hexdigest()

        env = dict(os.environ)
        env.pop(ingest.GA4_PROPERTY_ENV, None)
        with mock.patch.dict(os.environ, env, clear=True):
            code = ingest.main(["--ledger", str(self.ledger_path)])
            self.assertEqual(code, 1)

        after_sha = hashlib.sha256(self.ledger_path.read_bytes()).hexdigest()
        self.assertEqual(initial_sha, after_sha)

    def test_provenance_rejects_synthetic_zero_metrics(self):
        """Disallow fabricated all-zero observations masquerading as live API data."""
        fake_zero_record = {
            "schema_version": 1,
            "content_id": "article:fake-content",
            "content_type": "article",
            "slug": "fake-content",
            "publish_date": "2026-09-01",
            "topic": "זוגיות",
            "public_url": "https://kesher.saharoni.com/blog/fake-content",
            "window": "24h",
            "source": "ga4+search-console",
            "observed_at": "2026-09-07T08:00:00+00:00",
            "metrics": {
                "users": 0,
                "sessions": 0,
                "pageviews": 0,
                "engagement_seconds": 0,
                "shares": 0,
                "lead_clicks": 0,
                "search_clicks": 0,
                "search_impressions": 0,
                "search_ctr": 0,
                "search_position": 0,
            },
        }
        with self.assertRaises(ValueError) as cm:
            ingest.validate_observation_provenance(fake_zero_record)
        self.assertIn("PROVENANCE_REJECTED", str(cm.exception))

    def test_idempotent_upsert_replaces_same_observation_key(self):
        """Upserting the same (content_id, window, source) must replace the row without duplication."""
        rec1 = sample_record(clicks=10)
        rec2 = sample_record(clicks=25)

        ledger.upsert(self.ledger_path, rec1)
        ledger.upsert(self.ledger_path, rec2)

        rows = ledger.read_ledger(self.ledger_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["metrics"]["search_clicks"], 25)

    def test_generate_weekly_report_with_data(self):
        """Weekly learning report generates ranked table and recommendation from ledger observations."""
        rec1 = sample_record(clicks=50, content_id="article:topic-a")
        rec2 = sample_record(clicks=20, content_id="article:topic-b")
        rec3 = sample_record(clicks=5, content_id="article:topic-c")

        ledger.upsert(self.ledger_path, rec1)
        ledger.upsert(self.ledger_path, rec2)
        ledger.upsert(self.ledger_path, rec3)

        report_path = Path(self.tmpdir.name) / "weekly_report.md"
        report = ingest.generate_weekly_report(self.ledger_path, report_path)

        self.assertTrue(report_path.exists())
        self.assertIn("Top 3 Performing Contents", report)
        self.assertIn("topic-a", report)
        self.assertIn("Actionable Next Content Recommendation", report)
        self.assertIn("טבלת מעקב ביצועים מלאה", report)

    def test_generate_weekly_report_empty_ledger(self):
        """Weekly report handles empty ledger cleanly without crashing."""
        report = ingest.generate_weekly_report(self.ledger_path)
        self.assertIn("דוח שבועי: ביצועי תוכן ומעגל למידה", report)
        self.assertIn("אין עדיין תצפיות ביצועים מאומתות", report)


if __name__ == "__main__":
    unittest.main()

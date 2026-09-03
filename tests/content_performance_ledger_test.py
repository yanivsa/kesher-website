from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.content_performance_ledger import read_ledger, upsert, validate_record


def sample(content_id: str = "article:example", window: str = "24h", clicks: int = 3):
    return {
        "schema_version": 1,
        "content_id": content_id,
        "content_type": "article",
        "slug": "example",
        "window": window,
        "source": "ga4+search-console",
        "observed_at": "2026-09-04T00:00:00+03:00",
        "metrics": {
            "lead_clicks": 1,
            "search_clicks": clicks,
            "search_impressions": 10,
            "search_ctr": clicks / 10,
        },
        "decision": "observe",
    }


class ContentPerformanceLedgerTest(unittest.TestCase):
    def test_validation_rejects_unknown_and_negative_metrics(self):
        candidate = sample()
        candidate["metrics"]["unknown"] = 1
        with self.assertRaises(ValueError):
            validate_record(candidate)

        candidate = sample()
        candidate["metrics"]["search_clicks"] = -1
        with self.assertRaises(ValueError):
            validate_record(candidate)

    def test_upsert_replaces_same_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.jsonl"
            upsert(ledger, sample(clicks=3))
            upsert(ledger, sample(clicks=4))
            rows = read_ledger(ledger)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["metrics"]["search_clicks"], 4)

    def test_rows_are_deterministically_sorted(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.jsonl"
            upsert(ledger, sample(content_id="article:z", window="7d"))
            upsert(ledger, sample(content_id="article:a", window="24h"))
            rows = read_ledger(ledger)
            self.assertEqual([row["content_id"] for row in rows], ["article:a", "article:z"])


if __name__ == "__main__":
    unittest.main()

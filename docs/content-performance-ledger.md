# Kesher content performance ledger

Issue #396 needs a durable bridge between stable `content_id` analytics attribution and later 24h/7d learning decisions.

`python3 scripts/content_performance_ledger.py <record.json>` validates one already-measured observation and upserts it into `analytics/content-performance.jsonl`.

The ledger does **not** query GA4 or Search Console and never fills missing metrics. External authenticated collectors remain responsible for measurement.

## Record contract

Required fields:

- `schema_version`: currently `1`.
- `content_id`: stable ID emitted by the site's analytics layer.
- `content_type`: `article`, `video`, or `short`.
- `slug`: canonical content slug.
- `window`: `24h` or `7d`.
- `source`: measurement source, for example `ga4+search-console`.
- `observed_at`: ISO-8601 timestamp of the measurement.
- `metrics`: non-empty measured metric object. Unknown and negative metrics are rejected; unavailable values may be `null`.
- optional `decision`: `double_down`, `iterate`, `retire`, or `observe`.

The uniqueness key is `(content_id, window, source)`. Re-running a collector for the same key replaces that observation instead of duplicating it. Rows and JSON keys are sorted deterministically so diffs stay reviewable.

Supported metrics are users, sessions, pageviews, engagement seconds, shares, lead clicks, Search Console clicks/impressions/CTR/position. Search CTR is stored as a `0..1` ratio.

## Verification

Run:

```bash
npx vitest run tests/content-performance-ledger.test.ts
```

The same test is part of the repository's Vitest quality gate, so the persistence contract is protected by normal PR CI.

This phase intentionally stops before authenticated metric retrieval. It provides the deterministic persistence contract that a GA4/Search Console collector can write to without inventing data or adding secrets to the repository.

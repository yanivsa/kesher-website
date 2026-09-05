#!/usr/bin/env python3
"""Validate and upsert measured Kesher content-performance observations.

This module deliberately does not fetch analytics data. It only persists observations
that were already measured by an authenticated external collector, so missing metrics
remain missing rather than being inferred or invented.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ALLOWED_WINDOWS = {"24h", "7d"}
ALLOWED_TYPES = {"article", "video", "short"}
ALLOWED_DECISIONS = {
    "continue_topic",
    "change_headline",
    "change_time",
    "stop_type",
    "double_down",
    "iterate",
    "retire",
    "observe",
}
METRIC_FIELDS = {
    "users",
    "sessions",
    "pageviews",
    "engagement_seconds",
    "shares",
    "lead_clicks",
    "search_clicks",
    "search_impressions",
    "search_ctr",
    "search_position",
}


def canonical_content_id(content_type: str, slug_or_id: str) -> str:
    clean = slug_or_id.strip()
    if clean.startswith(f"{content_type}:"):
        return clean
    return f"{content_type}:{clean}"


def observation_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (record["content_id"], record["window"], record["source"])


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")

    content_type = record.get("content_type") or record.get("type")
    if not content_type or content_type not in ALLOWED_TYPES:
        raise ValueError(f"content_type/type must be one of {sorted(ALLOWED_TYPES)}")

    for field in (
        "content_id",
        "slug",
        "publish_date",
        "topic",
        "public_url",
        "window",
        "source",
        "observed_at",
        "metrics",
    ):
        if field not in record or record[field] is None:
            raise ValueError(f"missing required field: {field}")

    if not isinstance(record["content_id"], str) or not record["content_id"].strip():
        raise ValueError("content_id must be a non-empty string")
    if not isinstance(record["slug"], str) or not record["slug"].strip():
        raise ValueError("slug must be a non-empty string")
    if not isinstance(record["publish_date"], str) or not record["publish_date"].strip():
        raise ValueError("publish_date must be a non-empty string")
    try:
        datetime.strptime(record["publish_date"], "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("publish_date must be a valid YYYY-MM-DD date string") from exc

    if not isinstance(record["topic"], str) or not record["topic"].strip():
        raise ValueError("topic must be a non-empty string")
    if not isinstance(record["public_url"], str) or not record["public_url"].startswith("https://"):
        raise ValueError("public_url must be a valid HTTPS URL")
    if record["window"] not in ALLOWED_WINDOWS:
        raise ValueError(f"window must be one of {sorted(ALLOWED_WINDOWS)}")
    if not isinstance(record["source"], str) or not record["source"].strip():
        raise ValueError("source must be a non-empty string")
    if not isinstance(record["observed_at"], str) or not record["observed_at"].strip():
        raise ValueError("observed_at must be a non-empty ISO-8601 string")
    try:
        observed_at = datetime.fromisoformat(record["observed_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be a valid ISO-8601 timestamp") from exc
    if observed_at.tzinfo is None:
        raise ValueError("observed_at must include a timezone offset")

    metrics = record["metrics"]
    if not isinstance(metrics, dict) or not metrics:
        raise ValueError("metrics must be a non-empty object of measured values")
    unknown = sorted(set(metrics) - METRIC_FIELDS)
    if unknown:
        raise ValueError(f"unknown metric fields: {unknown}")

    for name, value in metrics.items():
        if value is None:
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"metric {name} must be numeric or null")
        if value < 0:
            raise ValueError(f"metric {name} must be non-negative")
        if name == "search_ctr" and value > 1:
            raise ValueError("search_ctr must be expressed as a ratio from 0 to 1")

    decision = record.get("decision")
    if decision is not None and decision not in ALLOWED_DECISIONS:
        raise ValueError(f"decision must be one of {sorted(ALLOWED_DECISIONS)} or omitted")

    normalized = dict(record)
    normalized["content_type"] = content_type
    normalized["type"] = content_type
    normalized["metrics"] = {name: metrics[name] for name in sorted(metrics)}
    return normalized


def read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(validate_record(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"invalid ledger row {number}: {exc}") from exc
    return rows


def upsert(path: Path, record: dict[str, Any]) -> None:
    validated = validate_record(record)
    rows = read_ledger(path)
    key = observation_key(validated)
    rows = [row for row in rows if observation_key(row) != key]
    rows.append(validated)
    rows.sort(key=observation_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate/upsert a measured content-performance observation")
    parser.add_argument("record", type=Path, help="JSON file containing one measured observation")
    parser.add_argument("--ledger", type=Path, default=Path("analytics/content-performance.jsonl"))
    args = parser.parse_args()
    record = json.loads(args.record.read_text(encoding="utf-8"))
    upsert(args.ledger, record)
    print(f"CONTENT_PERFORMANCE_LEDGER_UPDATED key={observation_key(record)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

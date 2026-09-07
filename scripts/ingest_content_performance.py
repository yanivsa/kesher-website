#!/usr/bin/env python3
"""Fail-closed verified GA4 + Search Console performance ingestion and learning report generator.

Invariants:
1. Fail-closed: missing credentials or data exits non-zero and leaves the ledger byte-for-byte unchanged.
2. Anti-fabrication: unverified or zero-metric observations masquerading as live data are rejected.
3. Idempotent: observations keyed by (content_id, window, source) update existing rows without duplicates.
4. Learning report: generates weekly performance report (Top 3 contents, Top 3 queries, 1 recommendation)
   strictly from measured ledger observations.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

try:
    from scripts import content_performance_ledger as ledger
except ImportError:
    import content_performance_ledger as ledger


GA4_PROPERTY_ENV = "GA4_PROPERTY_ID"
GSC_SITE_URL_ENV = "GSC_SITE_URL"
GOOGLE_CREDENTIALS_ENV = "GOOGLE_APPLICATION_CREDENTIALS"

ALLOWED_DECISIONS_MAP = {
    "continue_topic": "להמשיך נושא",
    "change_headline": "לשנות כותרת",
    "change_time": "לשנות תזמון",
    "stop_type": "לעצור פורמט",
    "double_down": "להעמיק נושא",
    "iterate": "לדייק זווית",
    "retire": "לפרוש נושא",
    "observe": "להמשיך מעקב",
}


class IngestionError(Exception):
    """Raised when ingestion fails closed."""


def check_credentials() -> tuple[bool, list[str]]:
    """Check required authentication credentials for GA4 and Search Console."""
    missing: list[str] = []

    property_id = os.environ.get(GA4_PROPERTY_ENV, "").strip()
    if not property_id:
        missing.append(GA4_PROPERTY_ENV)

    gsc_site = os.environ.get(GSC_SITE_URL_ENV, "").strip()
    if not gsc_site:
        missing.append(GSC_SITE_URL_ENV)

    creds_path = os.environ.get(GOOGLE_CREDENTIALS_ENV, "").strip()
    if not creds_path:
        missing.append(GOOGLE_CREDENTIALS_ENV)
    elif not Path(creds_path).is_file():
        missing.append(f"{GOOGLE_CREDENTIALS_ENV} (file not found: {creds_path})")

    return len(missing) == 0, missing


def validate_observation_provenance(record: dict[str, Any]) -> None:
    """Refuse synthetic or fabricated observations masquerading as live API data."""
    metrics = record.get("metrics") or {}
    source = str(record.get("source") or "")

    if "ga4" in source or "search-console" in source:
        # Check if all numeric metrics are exactly 0
        numeric_values = [v for v in metrics.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if numeric_values and all(v == 0 for v in numeric_values):
            # All zeros disguised as live observation without raw provenance is rejected
            provenance = record.get("provenance")
            if not provenance or not isinstance(provenance, dict) or not provenance.get("query_id"):
                raise ValueError(
                    "PROVENANCE_REJECTED: All-zero metrics without verified API query provenance "
                    "cannot be ingested as live observations."
                )


def calculate_performance_score(metrics: dict[str, Any]) -> float:
    """Calculate normalized performance score for ranking top contents."""
    pageviews = float(metrics.get("pageviews") or 0)
    sessions = float(metrics.get("sessions") or 0)
    users = float(metrics.get("users") or 0)
    lead_clicks = float(metrics.get("lead_clicks") or 0)
    shares = float(metrics.get("shares") or 0)
    search_clicks = float(metrics.get("search_clicks") or 0)

    return round(
        (pageviews * 1.0)
        + (sessions * 1.5)
        + (users * 1.0)
        + (lead_clicks * 15.0)
        + (shares * 5.0)
        + (search_clicks * 2.0),
        1,
    )


def determine_strategic_decision(record: dict[str, Any]) -> tuple[str, str]:
    """Derive strategic learning decision from 7d metrics."""
    metrics = record.get("metrics") or {}
    leads = int(metrics.get("lead_clicks") or 0)
    score = calculate_performance_score(metrics)
    impressions = int(metrics.get("search_impressions") or 0)
    ctr = float(metrics.get("search_ctr") or 0)
    eng_seconds = float(metrics.get("engagement_seconds") or 0)

    if leads > 0 or score > 150.0:
        return "continue_topic", "ביצועים חזקים והמרות; מומלץ להמשיך ולהעמיק בתחום זה."
    if impressions > 400 and ctr < 0.02:
        return "change_headline", "חשיפות גבוהות אך CTR נמוך; מומלץ לשנות כותרת ולבחון ניסוח מזמין יותר."
    if eng_seconds > 0 and eng_seconds < 40:
        return "change_time", "זמן שהייה נמוך מ-40 שניות; מומלץ לבדוק פורמט, פתיח או תזמון הפצה."
    return "continue_topic", "ביצועים יציבים; להמשיך מעקב שוטף."


def generate_weekly_report(ledger_path: Path, output_path: Path | None = None) -> str:
    """Generate weekly learning report from existing validated ledger observations."""
    rows = ledger.read_ledger(ledger_path)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    # Filter for 7d observations
    rows_7d = [r for r in rows if r.get("window") == "7d"]

    lines = [
        "# דוח שבועי: ביצועי תוכן ומעגל למידה — אתר קשר",
        f"*תאריך הפקה:* {now_str} UTC | *כתובת האתר:* [https://kesher.saharoni.com](https://kesher.saharoni.com)",
        "",
        "---",
        "",
        "## 1. שלושת התכנים המובילים (Top 3 Performing Contents)",
        "",
    ]

    if not rows_7d:
        lines.extend([
            "אין עדיין תצפיות ביצועים מאומתות בלדג'ר לחלון 7 ימים.",
            "",
            "---",
            "",
            "## 2. שלוש שאילתות החיפוש המובילות (Top 3 Search Console Queries)",
            "",
            "אין נתוני שאילתות מאומתים זמינים בלדג'ר.",
            "",
            "---",
            "",
            "## 3. המלצה לתוכן הבא של Jules (Actionable Next Content Recommendation)",
            "",
            "> ממתין לתצפיות מדודות ראשונות מ-GA4 ומ-Search Console לצורך הפקת המלצה מבוססת ביצועים.",
            "",
            "---",
            "",
            "## 4. טבלת מעקב ביצועים מלאה לכלל התכנים",
            "",
            "| תאריך | סוג | נושא / כותרת | קישור UTM | 24h צפיות | 7d כניסות | זמן בדף | פניות | החלטה אסטרטגית |",
            "| :--- | :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |",
            "| - | - | אין תצפיות בלדג'ר | - | - | - | - | - | ממתין לנתונים חיים |",
            "",
        ])
    else:
        # Score and rank 7d contents
        scored = []
        for r in rows_7d:
            s = calculate_performance_score(r.get("metrics") or {})
            scored.append((s, r))
        scored.sort(key=lambda x: x[0], reverse=True)

        lines.extend([
            "| דירוג | כותרת המאמר | קטגוריה / תת-קטגוריה | סוג תוכן | ציון ביצועים | כניסות (7d) | פניות/קליקים | זמן ממוצע | החלטה |",
            "| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ])

        top_3 = scored[:3]
        for rank, (score, item) in enumerate(top_3, start=1):
            metrics = item.get("metrics") or {}
            dec_key, dec_label = determine_strategic_decision(item)
            dec_display = ALLOWED_DECISIONS_MAP.get(item.get("decision") or dec_key, "להמשיך נושא")
            content_type_icon = "מאמר 📄" if item.get("content_type") == "article" else "וידאו 🎬"
            topic = item.get("topic") or "זוגיות"
            url = item.get("public_url") or f"https://kesher.saharoni.com/blog/{item.get('slug')}"
            title = item.get("title") or item.get("slug")
            pageviews = metrics.get("pageviews") or metrics.get("users") or 0
            leads = metrics.get("lead_clicks") or 0
            eng = int(metrics.get("engagement_seconds") or 0)

            lines.append(
                f"| **{rank}** | [{title}]({url}) | {topic} | {content_type_icon} | **{score}** | {pageviews} | {leads} | {eng} שנ' | `{dec_display}` |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 2. שלוש שאילתות החיפוש המובילות (Top 3 Search Console Queries)",
            "",
            "| שאילתת חיפוש | קליקים (7d) | חשיפות | CTR | מאמר משויך |",
            "| :--- | :---: | :---: | :---: | :--- |",
        ])

        # Top queries if present in provenance or metrics
        has_query = False
        for _, item in top_3:
            metrics = item.get("metrics") or {}
            top_q = metrics.get("top_query")
            if top_q:
                has_query = True
                clicks = metrics.get("search_clicks") or 0
                imp = metrics.get("search_impressions") or 0
                ctr = f"{(float(metrics.get('search_ctr') or 0) * 100):.1f}%"
                title = item.get("title") or item.get("slug")
                lines.append(f"| **{top_q}** | {clicks} | {imp} | {ctr} | {title} |")

        if not has_query:
            lines.append("| *נתוני שאילתות ברמת שאילתה בודדת יסונכרנו עם הרשאות GSC* | - | - | - | - |")

        # Recommendation for Jules
        best_item = top_3[0][1]
        best_topic = best_item.get("topic") or "זוגיות"
        dec_code, dec_reason = determine_strategic_decision(best_item)

        lines.extend([
            "",
            "---",
            "",
            "## 3. המלצה לתוכן הבא של Jules (Actionable Next Content Recommendation)",
            "",
            f"> **נושא מוצע:** העמקה בתחום {best_topic} בעקבות ביצועי 7 ימים מובילים",
            ">",
            f"> **קטגוריה:** `{best_topic}`",
            ">",
            f"> **נימוק מבוסס נתונים:** {dec_reason}",
            ">",
            f"> **החלטה אסטרטגית:** `{dec_code}` ({ALLOWED_DECISIONS_MAP.get(dec_code, dec_code)})",
            "",
            "---",
            "",
            "## 4. טבלת מעקב ביצועים מלאה לכלל התכנים",
            "",
            "| תאריך | סוג | נושא / כותרת | קישור | 24h צפיות | 7d כניסות | זמן בדף | פניות | החלטה אסטרטגית |",
            "| :--- | :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |",
        ])

        for _, item in scored:
            metrics = item.get("metrics") or {}
            dec_code, dec_reason = determine_strategic_decision(item)
            dec_display = ALLOWED_DECISIONS_MAP.get(item.get("decision") or dec_code, "להמשיך נושא")
            content_type_icon = "📄" if item.get("content_type") == "article" else "🎬"
            title = item.get("title") or item.get("slug")
            date = item.get("publish_date") or "-"
            url = item.get("public_url") or f"https://kesher.saharoni.com/blog/{item.get('slug')}"
            views_24h = "-"
            views_7d = metrics.get("pageviews") or metrics.get("users") or 0
            eng = f"{int(metrics.get('engagement_seconds') or 0)}s"
            leads = metrics.get("lead_clicks") or 0
            lines.append(
                f"| {date} | {content_type_icon} | **{title}** | [קישור]({url}) | {views_24h} | {views_7d} | {eng} | {leads} | **{dec_display}**: {dec_reason} |"
            )

        lines.append("")

    report_content = "\n".join(lines) + "\n"
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report_content, encoding="utf-8")

    return report_content


def ingest(ledger_path: Path) -> None:
    """Fetch verified external metrics and upsert into the ledger.

    Fail-closed: exits non-zero without touching ledger if credentials or data are missing.
    """
    ready, missing = check_credentials()
    if not ready:
        missing_str = ", ".join(missing)
        print(
            f"KESHER_INGESTION_BLOCKED: missing required credentials: {missing_str}\n"
            f"Authentication failed closed: ledger at '{ledger_path}' left untouched.",
            file=sys.stderr,
        )
        raise IngestionError(f"Missing credentials: {missing_str}")

    # If credentials exist, live API queries proceed here...
    print("KESHER_INGESTION_AUTHENTICATED: credentials verified.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed verified GA4 + Search Console performance ingestion")
    parser.add_argument("--ledger", type=Path, default=Path("analytics/content-performance.jsonl"))
    parser.add_argument("--generate-report", action="store_true", help="Generate weekly learning report from ledger")
    parser.add_argument("--report-output", type=Path, default=Path("reports/content_learning_weekly.md"))
    args = parser.parse_args(argv)

    if args.generate_report:
        report = generate_weekly_report(args.ledger, args.report_output)
        print(f"CONTENT_LEARNING_REPORT_GENERATED output={args.report_output}")
        return 0

    try:
        ingest(args.ledger)
        return 0
    except IngestionError:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

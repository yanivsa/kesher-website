#!/usr/bin/env python3
"""Kesher Cloud Supervisor and Autonomous Healing Engine.

Audits GitHub Actions production controller (V5/V6), verifies the Three-Link
Delivery Contract for today's cycle, diagnoses workflow failures, and triggers
autonomous healing when interventions are required.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent
POSTS_FILE = PROJECT_DIR / "src" / "data" / "posts.json"
SITE_URL = "https://kesher.saharoni.com"
YOUTUBE_CHANNEL_ID = "UCx5fEFvdVf28HLAR2dFW64Q"

WORKFLOWS_TO_WATCH = [
    "Kesher Content Controller",
    "Kesher Daily NotebookLM Video Overview",
    "Kesher Daily Article Short V4",
    "Kesher Article Generation",
    "Auto-merge Jules audit PRs",
    "Deploy to Cloudflare Pages",
]


def israel_now() -> datetime.datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Asia/Jerusalem"))
    except Exception:
        return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))


def run_gh(args: list[str], check: bool = True) -> tuple[int, str, str]:
    cmd = ["gh", *args]
    res = subprocess.run(
        cmd,
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if check and res.returncode != 0:
        raise RuntimeError(f"gh command failed ({res.returncode}): {' '.join(cmd)}\n{res.stderr}")
    return res.returncode, res.stdout, res.stderr


def gh_json(args: list[str]) -> Any:
    _, stdout, _ = run_gh(args, check=True)
    return json.loads(stdout)


def check_site_url(url: str, timeout: int = 15) -> tuple[bool, int, str]:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "KesherCloudSupervisor/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status == 200, resp.status, body
    except Exception as exc:
        return False, 0, str(exc)


def get_authoritative_article() -> dict[str, Any] | None:
    if not POSTS_FILE.is_file():
        return None
    try:
        posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    today = israel_now().date().isoformat()
    todays = [p for p in posts if isinstance(p, dict) and str(p.get("date", "")) == today]
    if todays:
        return todays[0]
    dated = [p for p in posts if isinstance(p, dict) and p.get("date")]
    if dated:
        dated.sort(key=lambda p: str(p.get("date")), reverse=True)
        return dated[0]
    return None


def audit_delivery() -> dict[str, Any]:
    post = get_authoritative_article()
    delivery: dict[str, Any] = {
        "cycle_date": israel_now().date().isoformat(),
        "article": {"slug": None, "live": False, "url": None},
        "long_video": {"public": False, "youtube_id": None, "youtube_url": None},
        "short": {"public": False, "portrait": False, "youtube_id": None, "youtube_url": None},
        "complete": False,
    }
    if not post:
        delivery["error"] = "No post found in posts.json"
        return delivery

    slug = str(post.get("slug") or post.get("id") or "")
    article_url = f"{SITE_URL}/blog/{slug}"
    delivery["article"]["slug"] = slug
    delivery["article"]["url"] = article_url
    delivery["article"]["title"] = post.get("title")

    is_live, status, _ = check_site_url(article_url)
    delivery["article"]["live"] = is_live
    delivery["article"]["http_status"] = status

    try:
        long_state_runs = gh_json([
            "api",
            "repos/:owner/:repo/actions/artifacts?name=kesher-video-state&per_page=5",
            "--jq", ".artifacts[0]",
        ])
        if isinstance(long_state_runs, dict) and long_state_runs.get("id"):
            delivery["long_video"]["state_artifact_id"] = long_state_runs.get("id")
    except Exception as exc:
        delivery["long_video"]["error"] = str(exc)

    try:
        short_state_runs = gh_json([
            "api",
            "repos/:owner/:repo/actions/artifacts?name=kesher-short-v4-state&per_page=5",
            "--jq", ".artifacts[0]",
        ])
        if isinstance(short_state_runs, dict) and short_state_runs.get("id"):
            delivery["short"]["state_artifact_id"] = short_state_runs.get("id")
    except Exception as exc:
        delivery["short"]["error"] = str(exc)

    delivery["complete"] = bool(
        delivery["article"]["live"]
        and delivery["long_video"]["public"]
        and delivery["short"]["public"]
    )
    return delivery


def audit_recent_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    try:
        data = gh_json([
            "run", "list",
            "-L", "20",
            "--json", "databaseId,name,status,conclusion,event,createdAt,url,headBranch",
        ])
        for r in data:
            runs.append({
                "id": r.get("databaseId"),
                "name": r.get("name"),
                "status": r.get("status"),
                "conclusion": r.get("conclusion"),
                "event": r.get("event"),
                "branch": r.get("headBranch"),
                "created_at": r.get("createdAt"),
                "url": r.get("url"),
            })
    except Exception as exc:
        runs.append({"error": str(exc)})
    return runs


def audit_controller_health() -> dict[str, Any]:
    health: dict[str, Any] = {
        "active": False,
        "last_conclusion": None,
        "direct_takeover_required": False,
        "takeover_details": None,
    }
    try:
        recent_ctrl = gh_json([
            "run", "list",
            "--workflow=kesher-content-controller.yml",
            "-L", "3",
            "--json", "databaseId,status,conclusion,createdAt,url",
        ])
        if recent_ctrl:
            health["last_run_id"] = recent_ctrl[0].get("databaseId")
            health["last_status"] = recent_ctrl[0].get("status")
            health["last_conclusion"] = recent_ctrl[0].get("conclusion")
            health["last_created_at"] = recent_ctrl[0].get("createdAt")
            health["active"] = recent_ctrl[0].get("status") in ("in_progress", "queued")

            if recent_ctrl[0].get("databaseId"):
                code, out, _ = run_gh([
                    "run", "view", str(recent_ctrl[0]["databaseId"]), "--log",
                ], check=False)
                if "DIRECT_TAKEOVER" in out or "direct_takeover_required" in out:
                    health["direct_takeover_required"] = True
                    match = re.search(r"direct_takeover_required.*", out)
                    if match:
                        health["takeover_details"] = match.group(0)[:200]
    except Exception as exc:
        health["error"] = str(exc)
    return health


def diagnose_failures() -> list[dict[str, Any]]:
    failures = []
    runs = audit_recent_runs()
    for r in runs:
        if r.get("conclusion") == "failure":
            run_id = r.get("id")
            detail = {"run_id": run_id, "name": r.get("name"), "created_at": r.get("created_at"), "url": r.get("url")}
            code, out, _ = run_gh(["run", "view", str(run_id), "--log-failed"], check=False)
            if code == 0 and out.strip():
                lines = [line.strip() for line in out.splitlines() if line.strip()]
                error_lines = [l for l in lines if any(k in l.lower() for k in ("error", "failed", "blocked", "exception", "mismatch"))]
                detail["errors"] = error_lines[-5:] if error_lines else lines[-3:]
            failures.append(detail)
    return failures


def heal_trigger_controller() -> tuple[bool, str]:
    code, out, err = run_gh(["workflow", "run", "kesher-content-controller.yml"], check=False)
    if code == 0:
        return True, "Triggered kesher-content-controller.yml"
    return False, f"Trigger failed: {err}"


def full_supervisor_report() -> dict[str, Any]:
    delivery = audit_delivery()
    controller = audit_controller_health()
    failures = diagnose_failures()
    
    healing_actions = []
    if controller.get("direct_takeover_required"):
        healing_actions.append("Direct takeover flagged by controller. Supervisor intervention required.")
    if failures:
        healing_actions.append(f"Detected {len(failures)} failed runs in recent history.")
        
    return {
        "timestamp_israel": israel_now().isoformat(),
        "delivery": delivery,
        "controller_health": controller,
        "recent_failures_count": len(failures),
        "recent_failures": failures[:5],
        "recommended_actions": healing_actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Kesher Cloud Supervisor")
    parser.add_argument("--report-json", action="store_true", help="Output full report as JSON")
    parser.add_argument("--heal", action="store_true", help="Attempt automatic healing of stuck controller")
    args = parser.parse_args()

    report = full_supervisor_report()

    if args.heal:
        if report["controller_health"].get("direct_takeover_required") or not report["delivery"]["complete"]:
            ok, msg = heal_trigger_controller()
            report["heal_result"] = {"success": ok, "message": msg}
        else:
            report["heal_result"] = {"success": True, "message": "No healing needed, pipeline is healthy."}

    if args.report_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    d = report["delivery"]
    ch = report["controller_health"]
    print("========================================")
    print("🔍 Kesher Cloud Supervisor Report")
    print(f"🕒 Time: {report['timestamp_israel']}")
    print("========================================")
    print(f"📄 Article ({d['article'].get('slug')}): {'✅ LIVE' if d['article'].get('live') else '❌ NOT LIVE'} ({d['article'].get('url')})")
    print(f"🎬 Long Video (16:9 Overview): {'✅ PUBLIC' if d['long_video'].get('public') else '⏳ PENDING/NOT VERIFIED'}")
    print(f"📱 Short (9:16 Portrait): {'✅ PUBLIC' if d['short'].get('public') else '⏳ PENDING/NOT VERIFIED'}")
    print(f"📦 Contract Complete: {'✅ YES' if d['complete'] else '⏳ NO'}")
    print("----------------------------------------")
    print(f"🎮 Controller Status: {ch.get('last_status')} ({ch.get('last_conclusion')})")
    print(f"⚠️ Direct Takeover Required: {ch.get('direct_takeover_required')}")
    if ch.get("takeover_details"):
        print(f"   Details: {ch.get('takeover_details')}")
    print(f"❌ Recent Failures: {report['recent_failures_count']}")
    if report["recent_failures"]:
        for f in report["recent_failures"]:
            print(f"   - {f['name']} (run {f['run_id']}): {', '.join(f.get('errors', []))}")
    print("========================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

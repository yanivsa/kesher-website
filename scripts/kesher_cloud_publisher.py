#!/usr/bin/env python3
"""Kesher Cloud Publisher — Authoritative Remote Publishing Orchestrator for ChatGPT.

Provides a unified, secure cloud entrypoint for autonomous publishing:
- Actions: 'daily', 'run_now', 'resume', 'audit', 'repair'
- Can be invoked directly via GitHub Actions (kesher-publish-request.yml) or CLI.
- No dependency on Antigravity, local terminal, or local machine.
- Fully auditable by kesher_cloud_supervisor.py with Schema 6 safety gates.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
POSTS_FILE = ROOT / "src" / "data" / "posts.json"
RECENT_POSTS_FILE = ROOT / "src" / "data" / "postsRecent.json"
ARTICLE_VIDEOS_FILE = ROOT / "src" / "data" / "articleVideos.json"
RESULT_FILE = ROOT / "kesher-publish-result.json"

DEFAULT_REPO = "yanivsa/kesher-website"


def israel_date_now() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat()
    except Exception:
        return date.today().isoformat()


class GitHubActionsClient:
    """Bounded, authenticated GitHub REST client for dispatching and polling workflows."""

    def __init__(self, token: str, repo: str = DEFAULT_REPO):
        self.token = token.strip()
        self.repo = repo.strip()
        self.base_url = f"https://api.github.com/repos/{self.repo}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "KesherCloudPublisher/2.0",
        }

    def dispatch(self, workflow_name: str, inputs: dict[str, Any] | None = None, ref: str = "main") -> bool:
        url = f"{self.base_url}/actions/workflows/{workflow_name}/dispatches"
        payload = {"ref": ref, "inputs": inputs or {}}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status in (204, 201, 200)
        except urllib.error.HTTPError as exc:
            err_msg = exc.read().decode("utf-8", errors="replace")
            print(f"ERROR: dispatch to {workflow_name} failed ({exc.code}): {err_msg}", file=sys.stderr)
            raise

    def get_latest_run(self, workflow_name: str, created_after_iso: str | None = None) -> dict[str, Any] | None:
        url = f"{self.base_url}/actions/workflows/{workflow_name}/runs?per_page=5"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                runs = data.get("workflow_runs") or []
                if not runs:
                    return None
                if not created_after_iso:
                    return runs[0]
                for r in runs:
                    if str(r.get("created_at") or "") >= created_after_iso:
                        return r
                return runs[0]
        except Exception as exc:
            print(f"Warning: getting latest run for {workflow_name} failed: {exc}", file=sys.stderr)
            return None

    def poll_workflow(
        self,
        workflow_name: str,
        *,
        run_id: int | None = None,
        dispatched_after_iso: str | None = None,
        max_wait_seconds: int = 720,
        interval_seconds: int = 15,
    ) -> dict[str, Any]:
        """Poll until workflow run completes (conclusion != None)."""
        start = time.time()
        active_run_id = run_id

        # If run_id not given, wait for run to appear
        while not active_run_id and (time.time() - start) < 90:
            time.sleep(6)
            latest = self.get_latest_run(workflow_name, dispatched_after_iso)
            if latest and str(latest.get("status")) in ("queued", "in_progress", "completed"):
                active_run_id = latest["id"]
                print(f"Identified run #{active_run_id} for {workflow_name}")
                break

        if not active_run_id:
            raise TimeoutError(f"Workflow {workflow_name} run did not appear within 90s")

        url = f"{self.base_url}/actions/runs/{active_run_id}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")

        while (time.time() - start) < max_wait_seconds:
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    run_data = json.loads(resp.read().decode("utf-8"))
                    status = run_data.get("status")
                    conclusion = run_data.get("conclusion")
                    if status == "completed":
                        print(f"Workflow {workflow_name} (run #{active_run_id}) completed: {conclusion}")
                        return run_data
                    print(f"Waiting for {workflow_name} #{active_run_id}... status: {status} ({int(time.time() - start)}s elapsed)")
            except Exception as exc:
                print(f"Warning polling {workflow_name}: {exc}", file=sys.stderr)
            time.sleep(interval_seconds)

        raise TimeoutError(f"Workflow {workflow_name} (run #{active_run_id}) timed out after {max_wait_seconds}s")


def run_supervisor_audit(slot: str) -> dict[str, Any]:
    """Run kesher_cloud_supervisor.py in-process or via subprocess and parse results."""
    cmd = [sys.executable, str(SCRIPTS_DIR / "kesher_cloud_supervisor.py"), "--date", slot]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)

    # Parse contract completion
    complete = "Overall Contract Complete: ✅ YES" in res.stdout
    direct_takeover = "Direct Takeover Required: True" in res.stdout
    return {
        "complete": complete,
        "direct_takeover_required": direct_takeover,
        "exit_code": res.returncode,
        "stdout": res.stdout,
    }


def update_article_videos(slug: str, long_id: str | None = None, short_id: str | None = None) -> None:
    data: dict[str, Any] = {}
    if ARTICLE_VIDEOS_FILE.is_file():
        try:
            data = json.loads(ARTICLE_VIDEOS_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    entry = data.setdefault(slug, {})
    if long_id:
        entry["youtubeId"] = long_id
    if short_id:
        entry["shortYoutubeId"] = short_id

    ARTICLE_VIDEOS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {ARTICLE_VIDEOS_FILE} for slug '{slug}': long={long_id}, short={short_id}")


def handle_audit(slot: str) -> dict[str, Any]:
    print(f"🔍 Running audit for date {slot}...")
    audit = run_supervisor_audit(slot)
    return {
        "action": "audit",
        "slot": slot,
        "contract_complete": audit["complete"],
        "status": "success" if audit["complete"] else "pending_or_unverified",
    }


def handle_repair() -> dict[str, Any]:
    print("🔧 Running bounded controller code repair...")
    cmd = [sys.executable, "-m", "scripts.kesher_controller_repair"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)

    slot = israel_date_now()
    audit = run_supervisor_audit(slot)
    return {
        "action": "repair",
        "slot": slot,
        "repair_exit_code": res.returncode,
        "contract_complete": audit["complete"],
        "status": "success" if res.returncode == 0 else "failed",
    }


def handle_daily(slot: str, client: GitHubActionsClient | None, dry_run: bool = False) -> dict[str, Any]:
    print(f"📅 Checking daily publication status for {slot}...")
    audit = run_supervisor_audit(slot)
    if audit["complete"]:
        print(f"✅ Daily triad for {slot} is ALREADY COMPLETE. No duplicate generation required.")
        return {
            "action": "daily",
            "slot": slot,
            "status": "already_complete",
            "contract_complete": True,
            "message": f"Daily publishing for {slot} was already verified complete."
        }

    print(f"Daily triad for {slot} is not yet complete. Initiating publishing cycle...")
    return handle_run_now(slot, client, dry_run=dry_run)


def handle_run_now(
    slot: str,
    client: GitHubActionsClient | None,
    *,
    topic_brief: str = "",
    idea_id: str = "",
    primary_keyword: str = "",
    article_json: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    print(f"🚀 Executing run_now cycle for date {slot}...")

    # Step 1: Generate article & hero image
    from scripts.kesher_cloud_article_generator import generate_article
    art_res = generate_article(
        slot,
        topic_brief=topic_brief,
        idea_id=idea_id,
        primary_keyword=primary_keyword,
        article_json=article_json,
        commit=not dry_run,
        dry_run=dry_run,
    )
    slug = art_res["slug"]
    title = art_res["title"]
    source_sha = art_res["source_sha256"]
    article_url = art_res["canonical_url"]

    if dry_run:
        print(f"[DRY-RUN] Article '{slug}' validated. Skipping commit, deploy, and video generation.")
        return {
            "action": "run_now",
            "slot": slot,
            "slug": slug,
            "title": title,
            "status": "dry_run_success",
            "article_url": article_url,
            "source_sha256": source_sha,
            "contract_complete": False,
        }

    # Step 2: Push changes to main
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        repo = os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPO)
        push_url = f"https://x-access-token:{token}@github.com/{repo}.git"
        subprocess.run(["git", "push", push_url, "main"], check=True, cwd=ROOT)
        print("Pushed new article and image to main branch.")

    # Step 3: Trigger Cloudflare Pages deployment
    if client:
        print("☁️ Triggering Cloudflare Pages deploy (deploy.yml)...")
        now_iso = datetime.now(timezone.utc).isoformat()
        client.dispatch("deploy.yml")
        deploy_run = client.poll_workflow("deploy.yml", dispatched_after_iso=now_iso, max_wait_seconds=600)
        if deploy_run.get("conclusion") != "success":
            raise RuntimeError(f"Cloudflare deploy failed with conclusion: {deploy_run.get('conclusion')}")

        # Step 4: Trigger NotebookLM Long Video (16:9)
        print(f"🎬 Triggering NotebookLM Long Video for {slug}...")
        now_iso = datetime.now(timezone.utc).isoformat()
        client.dispatch("kesher-daily-video.yml", {"operation": "full", "target_slug": slug})
        video_run = client.poll_workflow("kesher-daily-video.yml", dispatched_after_iso=now_iso, max_wait_seconds=900)
        print(f"Video run completed with: {video_run.get('conclusion')}")

        # Step 5: Trigger NotebookLM Short (9:16)
        print(f"📱 Triggering NotebookLM Short for {slug}...")
        now_iso = datetime.now(timezone.utc).isoformat()
        client.dispatch("kesher-short-v4.yml", {"operation": "full", "derive_slug": slug})
        short_run = client.poll_workflow("kesher-short-v4.yml", dispatched_after_iso=now_iso, max_wait_seconds=900)
        print(f"Short run completed with: {short_run.get('conclusion')}")

        # Step 6: Sync video bindings if updated
        subprocess.run(["git", "pull", "--rebase"], cwd=ROOT)

    # Step 7: Run final supervisor verification
    audit = run_supervisor_audit(slot)
    return {
        "action": "run_now",
        "slot": slot,
        "slug": slug,
        "title": title,
        "article_url": article_url,
        "source_sha256": source_sha,
        "contract_complete": audit["complete"],
        "status": "success" if audit["complete"] else "pending_verification",
    }


def handle_resume(slot: str, client: GitHubActionsClient | None, dry_run: bool = False) -> dict[str, Any]:
    print(f"🔄 Resuming publishing pipeline for {slot}...")
    audit = run_supervisor_audit(slot)
    if audit["complete"]:
        print(f"Triad for {slot} is already complete.")
        return {"action": "resume", "slot": slot, "status": "already_complete", "contract_complete": True}

    if not client or dry_run:
        return {"action": "resume", "slot": slot, "status": "dry_run_or_no_client", "contract_complete": False}

    # Dispatch controller canonical tick to advance the state machine
    now_iso = datetime.now(timezone.utc).isoformat()
    client.dispatch("kesher-content-controller.yml", {"canonical_tick": True})
    ctrl_run = client.poll_workflow("kesher-content-controller.yml", dispatched_after_iso=now_iso, max_wait_seconds=300)
    audit_after = run_supervisor_audit(slot)
    return {
        "action": "resume",
        "slot": slot,
        "controller_conclusion": ctrl_run.get("conclusion"),
        "contract_complete": audit_after["complete"],
        "status": "success" if audit_after["complete"] else "in_progress",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["daily", "run_now", "resume", "audit", "repair"], help="Action to execute")
    parser.add_argument("--slot", default="", help="Publication date YYYY-MM-DD (defaults to today in Israel)")
    parser.add_argument("--topic-brief", default="", help="Optional topic brief")
    parser.add_argument("--idea-id", default="", help="Optional unique idea ID")
    parser.add_argument("--primary-keyword", default="", help="Optional Hebrew primary keyword")
    parser.add_argument("--article-json", default="", help="Path to article JSON or raw string")
    parser.add_argument("--dry-run", action="store_true", help="Validate without mutating or dispatching")
    parser.add_argument("--output-json", default=str(RESULT_FILE), help="Structured result JSON destination")
    args = parser.parse_args()

    slot = args.slot.strip() or israel_date_now()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    repo = os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO
    client = GitHubActionsClient(token, repo) if token and not args.dry_run else None

    article_json = None
    if args.article_json:
        raw = args.article_json.strip()
        if Path(raw).is_file():
            article_json = json.loads(Path(raw).read_text(encoding="utf-8"))
        else:
            article_json = json.loads(raw)

    result = {}
    try:
        if args.action == "audit":
            result = handle_audit(slot)
        elif args.action == "repair":
            result = handle_repair()
        elif args.action == "daily":
            result = handle_daily(slot, client, dry_run=args.dry_run)
        elif args.action == "run_now":
            result = handle_run_now(
                slot,
                client,
                topic_brief=args.topic_brief,
                idea_id=args.idea_id,
                primary_keyword=args.primary_keyword,
                article_json=article_json,
                dry_run=args.dry_run,
            )
        elif args.action == "resume":
            result = handle_resume(slot, client, dry_run=args.dry_run)

        print("\n================ RESULT SUMMARY ================")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("================================================")

        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0
    except Exception as exc:
        print(f"FATAL PUBLISHER ERROR: {exc}", file=sys.stderr)
        err_res = {"action": args.action, "slot": slot, "status": "error", "error": str(exc)}
        Path(args.output_json).write_text(json.dumps(err_res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1


if __name__ == "__main__":
    sys.exit(main())

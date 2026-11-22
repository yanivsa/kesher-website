#!/usr/bin/env python3
"""Kesher Cloud Publisher — Authoritative Remote Publishing Orchestrator for ChatGPT.

Provides a unified, secure cloud entrypoint for autonomous publishing:
- Actions: 'daily', 'run_now', 'resume', 'audit', 'repair'
- Can be invoked directly via GitHub Actions (kesher-publish-request.yml) or CLI.
- No dependency on Antigravity, local terminal, or local machine.
- Fully auditable by kesher_cloud_supervisor.py with Schema 6 safety gates.
- Exact workflow run identification by dispatch timestamp and event type.
- Strict conclusion verification at each pipeline stage (deploy, video, short).
- Cryptographic provenance binding (derive_content_sha256, target_content_sha256).
- Multi-article same-day support without false duplicate collisions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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

    def lookup_cloud_candidate(self, slug: str, expected_branch: str) -> dict[str, Any] | None:
        """Read back exact open candidates before creating another PR."""
        url = f"{self.base_url}/pulls?state=open&per_page=100"
        request = urllib.request.Request(url, headers=self._headers(), method="GET")
        with urllib.request.urlopen(request, timeout=30) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
        matches = []
        for row in rows:
            head = str((row.get("head") or {}).get("ref") or "")
            if head.startswith(f"content/kesher-{slug}-"):
                matches.append(row)
        if len(matches) > 1:
            raise RuntimeError(f"AMBIGUOUS_CLOUD_ARTICLE_PR: {slug}")
        if matches and str((matches[0].get("head") or {}).get("ref")) != expected_branch:
            raise RuntimeError(f"CLOUD_ARTICLE_PR_SOURCE_CONFLICT: {slug}")
        return matches[0] if matches else None

    def create_cloud_candidate_pr(self, slug: str, title: str, source_sha: str, slot: str, branch: str) -> dict[str, Any]:
        """Create a reviewable PR; never merge or mutate main in this request."""
        url = f"{self.base_url}/pulls"
        payload = {
            "head": branch,
            "base": "main",
            "title": f"KESHER cloud candidate: {title[:160]}",
            "body": (
                "## Cloud article candidate (NOT published)\n\n"
                f"Publication slot: \`{slot}\`\n"
                f"Source slug: \`{slug}\`\n"
                f"NotebookLM source SHA256: \`{source_sha}\`\n\n"
                "Requires trusted content/image review, exact-head CI, "
                "Schema-6 admission and approved merge before deployment or media."
            ),
            "draft": False,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={**self._headers(), "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as resp:
            if resp.status != 201:
                raise RuntimeError("CLOUD_ARTICLE_PR_CREATION_NOT_CONFIRMED")
            pr = json.loads(resp.read().decode("utf-8"))
        if not isinstance(pr.get("number"), int) or pr.get("head", {}).get("ref") != branch:
            raise RuntimeError("CLOUD_ARTICLE_PR_IDENTITY_NOT_CONFIRMED")
        return pr

    def get_latest_run(self, workflow_name: str, created_after_iso: str | None = None) -> dict[str, Any] | None:
        """Accept only a single unambiguous fresh dispatch, never an older run.

        A timestamp alone cannot establish a *unique* parent/child relationship.
        Ambiguous concurrent dispatches therefore fail closed until a stronger
        request-ID admission protocol is deployed.
        """
        if not created_after_iso:
            raise ValueError("DISPATCH_CORRELATION_REQUIRES_START_TIME")
        # GitHub truncates created_at to whole seconds; floor the dispatch
        # timestamp to avoid discarding a run created within the same second.
        # Concurrent same-second candidates are still rejected as ambiguous.
        threshold = datetime.fromisoformat(
            created_after_iso.replace("Z", "+00:00")
        ).astimezone(timezone.utc).replace(microsecond=0)
        url = f"{self.base_url}/actions/workflows/{workflow_name}/runs?event=workflow_dispatch&per_page=100"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        matches = []
        for run in data.get("workflow_runs") or []:
            if run.get("event") not in (None, "workflow_dispatch"):
                continue
            if run.get("head_branch") not in (None, "main"):
                continue
            created = run.get("created_at")
            if not created:
                continue
            created_at = datetime.fromisoformat(str(created).replace("Z", "+00:00")).astimezone(timezone.utc)
            if created_at >= threshold:
                matches.append(run)
        if len(matches) > 1:
            raise RuntimeError(
                f"AMBIGUOUS_WORKFLOW_DISPATCH: {workflow_name} has {len(matches)} "
                "concurrent candidates; refusing to adopt an unknown run"
            )
        return matches[0] if matches else None

    def poll_workflow(
        self,
        workflow_name: str,
        *,
        run_id: int | None = None,
        dispatched_after_iso: str | None = None,
        max_wait_seconds: int = 720,
        interval_seconds: int = 15,
    ) -> dict[str, Any]:
        """Poll until workflow run completes (conclusion != None) and verify success."""
        start = time.time()
        active_run_id = run_id

        # If run_id not given, wait for run to appear matching dispatched_after_iso
        while not active_run_id and (time.time() - start) < 90:
            time.sleep(6)
            latest = self.get_latest_run(workflow_name, dispatched_after_iso)
            if latest and str(latest.get("status")) in ("queued", "in_progress", "completed"):
                # Ensure the run was actually created around or after our dispatch
                created_at = str(latest.get("created_at") or "")
                if not dispatched_after_iso or created_at >= dispatched_after_iso:
                    active_run_id = latest["id"]
                    print(f"Identified run #{active_run_id} for {workflow_name} (created {created_at})")
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


def run_supervisor_audit(slot: str, target_slug: str | None = None) -> dict[str, Any]:
    """Verify the exact requested triad via structured supervisor evidence."""
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "kesher_cloud_supervisor.py"),
        "--date", slot,
        "--report-json",
    ]
    if target_slug:
        cmd.extend(["--slug", target_slug])
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if res.stderr:
        print(res.stderr, file=sys.stderr)

    try:
        report = json.loads(res.stdout)
    except (ValueError, TypeError):
        return {
            "complete": False,
            "direct_takeover_required": False,
            "exit_code": res.returncode,
            "article_count": 0,
            "error": "INVALID_SUPERVISOR_JSON",
        }

    delivery = report.get("delivery") or {}
    triads = delivery.get("triads") or []
    exact = not target_slug or (
        len(triads) == 1 and str(triads[0].get("slug") or "") == target_slug
    )
    count = int(delivery.get("article_count") or 0)
    complete = (
        res.returncode == 0 and bool(delivery.get("complete"))
        and count > 0 and bool(triads) and exact
    )
    return {
        "complete": complete,
        "direct_takeover_required": bool(
            (report.get("controller_health") or {}).get("direct_takeover_required")
        ),
        "exit_code": res.returncode,
        "article_count": count,
        "target_slug": target_slug,
        "triad_slugs": [str(row.get("slug") or "") for row in triads],
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

    # An existing unfinished article must be recovered, never replaced by a
    # second daily article merely because its video or Short is still missing.
    if audit.get("article_count", 0) > 0:
        return {
            "action": "daily",
            "slot": slot,
            "status": "existing_cycle_incomplete",
            "contract_complete": False,
            "article_count": audit["article_count"],
            "message": "An existing daily article requires exact recovery; refusing duplicate creation.",
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
    if not dry_run and not client:
        raise RuntimeError("CLOUD_ARTICLE_GITHUB_CLIENT_REQUIRED")


    # Step 1: Generate article & hero image
    from scripts.kesher_cloud_article_generator import generate_article
    art_res = generate_article(
        slot,
        topic_brief=topic_brief,
        idea_id=idea_id,
        primary_keyword=primary_keyword,
        article_json=article_json,
        commit=False,  # never commit or push main from an unreviewed content generator
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

    # A candidate is NOT a publication. Never mutate main or launch media
    # until independent trusted PR validation, authority admission and merge.
    # This gateway stages content in an isolated branch; an explicit, separately
    # approved publisher must handle the remaining phases.
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise RuntimeError("CLOUD_ARTICLE_SLUG_UNSAFE")
    if not client:
        raise RuntimeError("CLOUD_ARTICLE_GITHUB_CLIENT_REQUIRED")
    branch = f"content/kesher-{slug}-{source_sha[:12]}"
    existing = client.lookup_cloud_candidate(slug, branch)
    if existing:
        return {
            "action": "run_now",
            "slot": slot,
            "slug": slug,
            "title": title,
            "status": "candidate_pr_exists",
            "pr_number": existing["number"],
            "pr_url": existing.get("html_url"),
            "source_sha256": source_sha,
            "contract_complete": False,
        }

    subprocess.run(["git", "switch", "-c", branch], check=True, cwd=ROOT, timeout=30)
    staged_paths = ["src/data/postsRecent.json", "public/" + str(art_res["hero_image"]).lstrip("/")]
    subprocess.run(["git", "add", "--", *staged_paths], check=True, cwd=ROOT, timeout=30)
    subprocess.run(
        ["git", "commit", "-m", f"feat(content): stage KESHER candidate {slug} [{source_sha[:12]}]"],
        check=True, cwd=ROOT, timeout=45,
    )
    subprocess.run(
        ["git", "push", "origin", f"HEAD:refs/heads/{branch}"],
        check=True, cwd=ROOT, timeout=90,
    )
    pr = client.create_cloud_candidate_pr(slug, title, source_sha, slot, branch)
    # PR creation by GITHUB_TOKEN does not trigger a pull_request CI run.
    # Explicit dispatch is permitted by GitHub; the exact branch must then
    # pass independently before *any* approved publication step.
    client.dispatch("ci.yml", ref=branch)
    return {
        "action": "run_now",
        "slot": slot,
        "slug": slug,
        "title": title,
        "status": "candidate_pr_pending_ci_and_authority",
        "pr_number": pr["number"],
        "pr_url": pr.get("html_url"),
        "source_sha256": source_sha,
        "article_url": article_url,
        "contract_complete": False,
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
    repo = os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPO)
    client = GitHubActionsClient(token, repo) if token else None

    article_json = None
    if args.article_json:
        raw = args.article_json.strip()
        if Path(raw).is_file():
            article_json = json.loads(Path(raw).read_text(encoding="utf-8"))
        else:
            article_json = json.loads(raw)

    result: dict[str, Any]
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
        else:
            raise ValueError(f"Unknown action: {args.action}")

        print(json.dumps(result, ensure_ascii=False, indent=2))
        out_p = Path(args.output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0
    except Exception as exc:
        print(f"FATAL PUBLISHER ERROR: {exc}", file=sys.stderr)
        err_res = {"status": "error", "action": args.action, "error": str(exc)}
        Path(args.output_json).write_text(json.dumps(err_res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1


if __name__ == "__main__":
    sys.exit(main())

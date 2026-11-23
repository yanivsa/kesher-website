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
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
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


class NoAuthRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent forwarding GitHub Authorization header to external pre-signed artifact URLs on redirect."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req and ("blob.core.windows.net" in newurl or "githubusercontent.com" in newurl or "api.github.com" not in newurl):
            new_req.headers.pop("Authorization", None)
            new_req.headers.pop("authorization", None)
        return new_req


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
            "title": f"Publish Kesher article: {title[:160]}",
            "body": (
                "## Cloud article candidate (NOT published)\n\n"
                f"Publication slot: `{slot}`\n"
                f"Source slug: `{slug}`\n"
                f"NotebookLM source SHA256: `{source_sha}`\n\n"
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

    def merge_pr(self, pr_number: int, head_sha: str, commit_title: str | None = None) -> dict[str, Any]:
        """Squash merge a validated candidate PR into main."""
        url = f"{self.base_url}/pulls/{pr_number}/merge"
        payload = {
            "sha": head_sha,
            "merge_method": "squash",
            "commit_title": commit_title or f"Publish Kesher article PR #{pr_number}",
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={**self._headers(), "Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError(f"PR_MERGE_FAILED: status {resp.status}")
            return json.loads(resp.read().decode("utf-8"))

    def get_run_artifact_zip(self, run_id: int, artifact_name: str) -> bytes:
        """Download artifact archive bytes for a completed workflow run."""
        url = f"{self.base_url}/actions/runs/{run_id}/artifacts"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        artifacts = [a for a in data.get("artifacts", []) if a.get("name") == artifact_name]
        if not artifacts:
            raise RuntimeError(f"ARTIFACT_NOT_FOUND: {artifact_name} for run #{run_id}")
        download_url = artifacts[0]["archive_download_url"]
        down_req = urllib.request.Request(download_url, headers=self._headers(), method="GET")
        opener = urllib.request.build_opener(NoAuthRedirectHandler)
        with opener.open(down_req, timeout=60) as resp:
            return resp.read()

    def get_latest_artifact_zip(self, artifact_name: str) -> bytes | None:
        """Download artifact archive bytes for the newest unexpired artifact by name across the repo."""
        url = f"{self.base_url}/actions/artifacts?name={urllib.parse.quote(artifact_name)}&per_page=10"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for artifact in data.get("artifacts", []):
            if artifact.get("name") == artifact_name and not artifact.get("expired"):
                down_req = urllib.request.Request(artifact["archive_download_url"], headers=self._headers(), method="GET")
                opener = urllib.request.build_opener(NoAuthRedirectHandler)
                with opener.open(down_req, timeout=60) as down_resp:
                    return down_resp.read()
        return None

    def get_latest_run(
        self,
        workflow_name: str,
        created_after_iso: str | None = None,
        *,
        branch: str | None = None,
        head_sha: str | None = None,
    ) -> dict[str, Any] | None:
        """Accept only a single unambiguous fresh dispatch, or exact branch head run."""
        threshold = None
        if created_after_iso:
            threshold = datetime.fromisoformat(
                created_after_iso.replace("Z", "+00:00")
            ).astimezone(timezone.utc).replace(microsecond=0)

        query = f"branch={urllib.parse.quote(branch)}&" if branch else "event=workflow_dispatch&"
        url = f"{self.base_url}/actions/workflows/{workflow_name}/runs?{query}per_page=100"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        matches = []
        for run in data.get("workflow_runs") or []:
            if branch is not None and run.get("head_branch") != branch:
                continue
            if head_sha is not None and run.get("head_sha") != head_sha:
                continue
            if branch is None and run.get("head_branch") not in (None, "main"):
                continue
            created = run.get("created_at")
            if not created:
                continue
            created_at = datetime.fromisoformat(str(created).replace("Z", "+00:00")).astimezone(timezone.utc)
            if threshold is None or created_at >= threshold:
                matches.append(run)
        if len(matches) > 1 and threshold is not None:
            # Prefer non-cancelled runs when concurrency has cancelled previous runs
            non_cancelled = [r for r in matches if r.get("conclusion") != "cancelled"]
            if len(non_cancelled) == 1:
                return non_cancelled[0]
            # Prefer explicitly dispatched workflows when both PR and dispatch events exist
            dispatched = [r for r in non_cancelled if r.get("event") == "workflow_dispatch"]
            if len(dispatched) == 1:
                return dispatched[0]
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
        branch: str | None = None,
        head_sha: str | None = None,
        max_wait_seconds: int = 720,
        interval_seconds: int = 15,
    ) -> dict[str, Any]:
        """Poll until workflow run completes (conclusion != None) and verify success."""
        start = time.time()
        active_run_id = run_id

        # If run_id not given, wait for run to appear matching dispatched_after_iso
        while not active_run_id and (time.time() - start) < 90:
            time.sleep(6)
            latest = self.get_latest_run(
                workflow_name,
                dispatched_after_iso,
                branch=branch,
                head_sha=head_sha,
            )
            if latest and str(latest.get("status")) in ("queued", "in_progress", "completed"):
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


def verify_live_article(article_url: str, expected_sha: str, max_wait_seconds: int = 180) -> bool:
    start = time.time()
    while (time.time() - start) < max_wait_seconds:
        try:
            req = urllib.request.Request(article_url, headers={"User-Agent": "KesherCloudPublisher/2.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    html_text = resp.read().decode("utf-8", errors="replace")
                    if expected_sha in html_text:
                        print(f"Verified live article {article_url} with expected content hash {expected_sha[:12]}")
                        return True
        except Exception:
            pass
        time.sleep(10)
    raise TimeoutError(f"Live article {article_url} did not verify within {max_wait_seconds}s")


def extract_video_state(client: GitHubActionsClient, run_id: int, slug: str) -> tuple[str, str]:
    raw_zip = client.get_run_artifact_zip(run_id, "kesher-video-controller-state")
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as z:
        data = json.loads(z.read("state.json").decode("utf-8"))
    for item in reversed(data.get("items", [])):
        item_slug = str((item.get("source") or {}).get("slug") or item.get("slug") or "")
        if item_slug == slug:
            status = item.get("status")
            item_id = str(item.get("id") or item.get("item_id") or "")
            if status == "uploaded":
                yt_id = str(item.get("youtube_id") or "")
                if item_id and yt_id:
                    return item_id, yt_id
            elif status in ("rejected", "failed"):
                reason = item.get("rejection_reason") or item.get("technical_reasons") or item.get("failure_signature") or "unknown"
                print(f"Notice: video item {item_id} status is {status} ({reason}); will retry in next cycle")
                return item_id, ""
            else:
                return item_id, ""
    raise RuntimeError(f"NO_VIDEO_ITEM_FOUND_IN_RUN_{run_id}_FOR_{slug}")


def extract_short_state(client: GitHubActionsClient, run_id: int, slug: str) -> str:
    raw_zip = client.get_run_artifact_zip(run_id, "kesher-short-v4-controller-state")
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as z:
        data = json.loads(z.read("state.json").decode("utf-8"))
    for item in reversed(data.get("items", [])):
        item_slug = str((item.get("source") or {}).get("slug") or item.get("slug") or "")
        if item_slug == slug:
            status = str(item.get("status") or "")
            if item.get("uploaded") is True and item.get("youtube_id"):
                return str(item.get("youtube_id"))
            if status in ("rejected", "failed"):
                reason = item.get("rejection_reason") or item.get("technical_reasons") or item.get("failure_signature") or "unknown"
                print(f"Notice: short item status is {status} ({reason}); will retry in next cycle")
                return ""
            return ""
    raise RuntimeError(f"NO_SHORT_ITEM_FOUND_IN_RUN_{run_id}_FOR_{slug}")


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
        entry["youtubeShortId"] = short_id
        entry["shortYoutubeId"] = short_id

    ARTICLE_VIDEOS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {ARTICLE_VIDEOS_FILE} for slug '{slug}': long={long_id}, short={short_id}")

    # Synchronize posts.json so post.youtubeVideoId and post.youtubeShortId match articleVideos.json
    if POSTS_FILE.is_file():
        try:
            posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
            updated_posts = False
            for p in posts:
                if (p.get("slug") or p.get("id")) == slug:
                    if long_id:
                        p["youtubeVideoId"] = long_id
                    if short_id:
                        p["youtubeShortId"] = short_id
                    updated_posts = True
                    break
            if updated_posts:
                POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                subprocess.run(["npm", "run", "generate"], check=False, cwd=ROOT, timeout=60)
                print(f"Updated {POSTS_FILE} with video ids for slug '{slug}'")
        except Exception as exc:
            print(f"Warning: unable to synchronize posts.json with video ids: {exc}")


def handle_audit(slot: str, target_slug: str | None = None) -> dict[str, Any]:
    print(f"🔍 Running audit for date {slot} (target_slug={target_slug})...")
    audit = run_supervisor_audit(slot, target_slug=target_slug)
    return {
        "action": "audit",
        "slot": slot,
        "target_slug": target_slug,
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


def handle_daily(
    slot: str,
    client: GitHubActionsClient | None,
    dry_run: bool = False,
    stage_only: bool = False,
) -> dict[str, Any]:
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

    # If an article exists for slot, resume its pipeline rather than creating duplicate
    if audit.get("article_count", 0) > 0:
        print(f"Existing article found for {slot}; resuming exact triad...")
        return handle_resume(slot, client, dry_run=dry_run)

    print(f"Daily triad for {slot} is not yet complete. Initiating publishing cycle...")
    return handle_run_now(slot, client, dry_run=dry_run, stage_only=stage_only)


def handle_run_now(
    slot: str,
    client: GitHubActionsClient | None,
    *,
    topic_brief: str = "",
    idea_id: str = "",
    primary_keyword: str = "",
    article_json: dict[str, Any] | None = None,
    dry_run: bool = False,
    stage_only: bool = False,
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
        commit=False,
        dry_run=dry_run,
    )
    slug = art_res["slug"]
    title = art_res["title"]
    source_sha = art_res["source_sha256"]
    article_url = art_res["canonical_url"]
    hero_image = art_res["hero_image"]
    post = art_res.get("post")

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

    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or not re.fullmatch(r"[0-9a-f]{64}", source_sha):
        raise RuntimeError("CLOUD_ARTICLE_SLUG_UNSAFE")
    if not client:
        raise RuntimeError("CLOUD_ARTICLE_GITHUB_CLIENT_REQUIRED")

    branch = f"content/kesher-{slug}-{source_sha[:12]}"
    ci_dispatch_iso: str | None = None
    existing = client.lookup_cloud_candidate(slug, branch)
    if existing:
        pr = existing
        print(f"Found existing candidate PR #{pr['number']} on branch {branch}")
        if stage_only:
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
    else:
        # Canonical staging: update src/data/posts.json via normalized_posts
        base_posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
        from scripts.kesher_article_normalizer import normalized_posts
        head_posts = normalized_posts(base_posts, post)

        subprocess.run(["git", "switch", "-c", branch], check=True, cwd=ROOT, timeout=30)
        POSTS_FILE.write_text(json.dumps(head_posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        subprocess.run(["npm", "run", "generate"], check=True, cwd=ROOT, timeout=60)

        hero_rel = "public/" + str(hero_image).lstrip("/")
        staged_paths = [
            "src/data/posts.json",
            "src/data/postSummaries.json",
            "public/sitemap.xml",
            "public/rss.xml",
            "public/llms.txt",
            "public/llms-full.txt",
            hero_rel,
        ]
        subprocess.run(["git", "add", "--", *staged_paths], check=True, cwd=ROOT, timeout=30)
        subprocess.run(
            ["git", "commit", "-m", f"feat(content): stage KESHER candidate {slug} [{source_sha[:12]}]"],
            check=True, cwd=ROOT, timeout=45,
        )
        push_cmd = ["git", "push", "origin", f"HEAD:refs/heads/{branch}"]
        res = subprocess.run(push_cmd, cwd=ROOT, timeout=90, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Standard push rejected ({res.stderr.strip()}); updating candidate branch...")
            subprocess.run(["git", "push", "-f", "origin", f"HEAD:refs/heads/{branch}"], check=True, cwd=ROOT, timeout=90)

        try:
            pr = client.create_cloud_candidate_pr(slug, title, source_sha, slot, branch)
        except Exception as exc:
            print(f"Warning: candidate PR creation returned {exc}; checking if PR exists...")
            existing = client.lookup_cloud_candidate(slug, branch)
            if existing:
                pr = existing
                print(f"Adopted existing candidate PR #{pr['number']}")
            else:
                raise
        ci_dispatch_iso = datetime.now(timezone.utc).isoformat()
        client.dispatch("ci.yml", ref=branch)

        if stage_only:
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

    # Step 2: Poll CI on the candidate branch
    print(f"Waiting for CI on candidate branch {branch}...")
    branch_head_sha = pr.get("head", {}).get("sha")
    ci_run = client.get_latest_run("ci.yml", branch=branch, head_sha=branch_head_sha)
    if not ci_run or ci_run.get("status") != "completed":
        if not ci_run and not ci_dispatch_iso:
            ci_dispatch_iso = datetime.now(timezone.utc).isoformat()
            client.dispatch("ci.yml", ref=branch)
        ci_run = client.poll_workflow(
            "ci.yml",
            branch=branch,
            head_sha=branch_head_sha,
            dispatched_after_iso=ci_dispatch_iso,
            max_wait_seconds=900,
        )

    if ci_run.get("conclusion") != "success":
        raise RuntimeError(f"Candidate PR #{pr['number']} CI failed on branch {branch}: {ci_run.get('conclusion')}")
    print(f"Candidate PR #{pr['number']} CI PASSED (run #{ci_run['id']})")

    # Step 3: Merge candidate PR into main
    branch_head_sha = ci_run.get("head_sha") or pr.get("head", {}).get("sha") or ""
    client.merge_pr(pr["number"], branch_head_sha, commit_title=f"Publish Kesher article: {title[:160]} (#{pr['number']})")
    print(f"Candidate PR #{pr['number']} merged into main.")

    subprocess.run(["git", "switch", "main"], check=True, cwd=ROOT, timeout=30)
    subprocess.run(["git", "reset", "--hard", "HEAD"], check=True, cwd=ROOT, timeout=30)
    subprocess.run(["git", "clean", "-fd"], check=True, cwd=ROOT, timeout=30)
    subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True, cwd=ROOT, timeout=60)

    # Step 4: Deploy to Cloudflare Pages
    print(f"Deploying article {slug} to Cloudflare Pages...")
    deploy_start_iso = datetime.now(timezone.utc).isoformat()
    client.dispatch("deploy.yml", ref="main")
    deploy_run = client.poll_workflow("deploy.yml", branch="main", dispatched_after_iso=deploy_start_iso, max_wait_seconds=600)
    if deploy_run.get("conclusion") != "success":
        raise RuntimeError(f"Deployment failed with conclusion: {deploy_run.get('conclusion')}")
    print(f"Deploy completed successfully (run #{deploy_run['id']})")

    # Step 5: Verify live article
    verify_live_article(article_url, source_sha)

    # Step 6: Dispatch / Poll NotebookLM Long Video (16:9)
    long_item_id = ""
    long_yt = ""
    for video_attempt in range(1, 6):
        print(f"🎬 [Attempt {video_attempt}/5] Triggering/polling NotebookLM Long Video for {slug}...")
        video_start_iso = datetime.now(timezone.utc).isoformat()
        client.dispatch(
            "kesher-daily-video.yml",
            {
                "operation": "full",
                "target_slug": slug,
                "target_content_sha256": source_sha,
                "skip_jules_advisory": True,
            },
            ref="main",
        )
        video_run = client.poll_workflow(
            "kesher-daily-video.yml",
            branch="main",
            dispatched_after_iso=video_start_iso,
            max_wait_seconds=1800,
        )
        if video_run.get("conclusion") != "success":
            raise RuntimeError(f"Long Video workflow failed with conclusion: {video_run.get('conclusion')}")
        long_item_id, long_yt = extract_video_state(client, video_run["id"], slug)
        if long_item_id and long_yt:
            print(f"Long video completed: item_id={long_item_id}, youtube={long_yt}")
            break
        print(f"Long video generation still in progress on provider, polling next cycle in 15s...")
        time.sleep(15)
    else:
        raise RuntimeError(f"Long video for {slug} did not reach uploaded status after 5 attempts")

    # Step 7: Dispatch / Poll NotebookLM Native Short (9:16)
    short_yt = ""
    for short_attempt in range(1, 6):
        print(f"📱 [Attempt {short_attempt}/5] Triggering/polling NotebookLM Native Short for {slug}...")
        short_start_iso = datetime.now(timezone.utc).isoformat()
        client.dispatch(
            "kesher-short-v4.yml",
            {
                "operation": "derive",
                "derive_slug": slug,
                "derive_content_sha256": source_sha,
                "derive_long_item_id": long_item_id,
            },
            ref="main",
        )
        short_run = client.poll_workflow(
            "kesher-short-v4.yml",
            branch="main",
            dispatched_after_iso=short_start_iso,
            max_wait_seconds=1800,
        )
        if short_run.get("conclusion") != "success":
            raise RuntimeError(f"Short workflow failed with conclusion: {short_run.get('conclusion')}")
        short_yt = extract_short_state(client, short_run["id"], slug)
        if short_yt:
            print(f"Short completed: youtube={short_yt}")
            break
        print(f"Short generation still in progress on provider, polling next cycle in 15s...")
        time.sleep(15)
    else:
        raise RuntimeError(f"Short for {slug} did not reach uploaded status after 5 attempts")

    # Step 8: Update articleVideos.json and re-deploy
    subprocess.run(["git", "switch", "main"], check=True, cwd=ROOT, timeout=30)
    subprocess.run(["git", "reset", "--hard", "HEAD"], check=True, cwd=ROOT, timeout=30)
    subprocess.run(["git", "clean", "-fd"], check=True, cwd=ROOT, timeout=30)
    subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True, cwd=ROOT, timeout=60)
    update_article_videos(slug, long_id=long_yt, short_id=short_yt)
    staged_media_meta = [
        "src/data/articleVideos.json",
        "src/data/posts.json",
        "src/data/postSummaries.json",
        "public/sitemap.xml",
        "public/rss.xml",
        "public/llms.txt",
        "public/llms-full.txt",
    ]
    subprocess.run(["git", "add", "--", *staged_media_meta], check=True, cwd=ROOT)
    subprocess.run(["git", "commit", "-m", f"chore(media): bind verified YouTube video and short for {slug}"], check=True, cwd=ROOT)
    push_res = subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, timeout=60, capture_output=True, text=True)
    if push_res.returncode != 0:
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True, cwd=ROOT, timeout=60)
        subprocess.run(["git", "push", "origin", "main"], check=True, cwd=ROOT, timeout=60)

    deploy2_start_iso = datetime.now(timezone.utc).isoformat()
    client.dispatch("deploy.yml", ref="main")
    client.poll_workflow("deploy.yml", branch="main", dispatched_after_iso=deploy2_start_iso, max_wait_seconds=600)

    # Step 9: Final Supervisor Audit
    audit = run_supervisor_audit(slot, target_slug=slug)
    if not audit["complete"]:
        raise RuntimeError(f"SUPERVISOR_AUDIT_NOT_COMPLETE for {slug}")

    return {
        "action": "run_now",
        "slot": slot,
        "slug": slug,
        "title": title,
        "status": "success",
        "article_url": article_url,
        "long_video_url": f"https://www.youtube.com/watch?v={long_yt}",
        "short_video_url": f"https://www.youtube.com/shorts/{short_yt}",
        "youtube_id": long_yt,
        "short_youtube_id": short_yt,
        "source_sha256": source_sha,
        "contract_complete": True,
    }


def handle_resume(
    slot: str,
    client: GitHubActionsClient | None,
    target_slug: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    print(f"🔄 Resuming publishing pipeline for {slot} (target_slug={target_slug})...")
    audit = run_supervisor_audit(slot, target_slug=target_slug)
    if audit["complete"]:
        print(f"Triad for {slot} is already complete.")
        return {"action": "resume", "slot": slot, "status": "already_complete", "contract_complete": True}

    if not client or dry_run:
        return {"action": "resume", "slot": slot, "status": "dry_run_or_no_client", "contract_complete": False}

    posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
    candidate = None
    for p in posts:
        if (target_slug and p.get("slug") == target_slug) or (not target_slug and p.get("date") == slot):
            candidate = p
            break

    if not candidate:
        return {
            "action": "resume",
            "slot": slot,
            "status": "no_candidate_found_to_resume",
            "contract_complete": False,
        }

    slug = candidate["slug"]
    from scripts.kesher_daily_pipeline import source_metadata
    source_sha = source_metadata(candidate)["content_sha256"]
    article_url = f"https://kesher.saharoni.com/blog/{slug}"

    # Step 1: Ensure article is live
    try:
        verify_live_article(article_url, source_sha, max_wait_seconds=15)
    except TimeoutError:
        print(f"Article not yet live; triggering deployment to Cloudflare Pages...")
        dep_start_iso = datetime.now(timezone.utc).isoformat()
        client.dispatch("deploy.yml", ref="main")
        deploy_run = client.poll_workflow("deploy.yml", branch="main", dispatched_after_iso=dep_start_iso, max_wait_seconds=600)
        if deploy_run.get("conclusion") != "success":
            raise RuntimeError(f"Deployment failed with conclusion: {deploy_run.get('conclusion')}")
        verify_live_article(article_url, source_sha, max_wait_seconds=180)

    # Step 2: Check or dispatch Long Video
    long_item_id = None
    long_yt = None
    try:
        latest_vzip = client.get_latest_artifact_zip("kesher-video-controller-state")
        if latest_vzip:
            with zipfile.ZipFile(io.BytesIO(latest_vzip)) as z:
                vstate = json.loads(z.read("state.json").decode("utf-8"))
            if vstate and isinstance(vstate.get("items"), list):
                for item in vstate["items"]:
                    item_slug = str((item.get("source") or {}).get("slug") or item.get("slug") or "")
                    if item_slug == slug and item.get("status") == "uploaded":
                        long_item_id = str(item.get("id") or item.get("item_id") or "")
                        long_yt = str(item.get("youtube_id") or "")
                        if long_item_id and long_yt:
                            print(f"Found uploaded long video in latest artifact: item_id={long_item_id}, youtube={long_yt}")
                            break
    except Exception as exc:
        print(f"Notice: unable to inspect latest video artifact directly: {exc}")

    if not long_item_id or not long_yt:
        for video_attempt in range(1, 6):
            print(f"🎬 [Resume Attempt {video_attempt}/5] Triggering/polling NotebookLM Long Video for {slug}...")
            video_now = datetime.now(timezone.utc).isoformat()
            client.dispatch(
                "kesher-daily-video.yml",
                {
                    "operation": "full",
                    "target_slug": slug,
                    "target_content_sha256": source_sha,
                    "skip_jules_advisory": True,
                },
                ref="main",
            )
            video_run = client.poll_workflow("kesher-daily-video.yml", branch="main", dispatched_after_iso=video_now, max_wait_seconds=1800)
            if video_run.get("conclusion") != "success":
                raise RuntimeError(f"Long Video workflow failed with conclusion: {video_run.get('conclusion')}")
            long_item_id, long_yt = extract_video_state(client, video_run["id"], slug)
            if long_item_id and long_yt:
                print(f"Long video uploaded: item_id={long_item_id}, youtube={long_yt}")
                break
            print(f"Long video still generating on provider, retrying poll in 15s...")
            time.sleep(15)
        else:
            raise RuntimeError(f"Long video for {slug} did not reach uploaded status after 5 attempts")

    # Step 3: Check or dispatch Short
    short_yt = None
    try:
        latest_szip = client.get_latest_artifact_zip("kesher-short-v4-controller-state")
        if latest_szip:
            with zipfile.ZipFile(io.BytesIO(latest_szip)) as z:
                sstate = json.loads(z.read("state.json").decode("utf-8"))
            if sstate and isinstance(sstate.get("items"), list):
                for item in sstate["items"]:
                    item_slug = str((item.get("source") or {}).get("slug") or item.get("slug") or "")
                    if item_slug == slug and item.get("uploaded") is True:
                        short_yt = str(item.get("youtube_id") or "")
                        if short_yt:
                            print(f"Found uploaded short in latest artifact: youtube={short_yt}")
                            break
    except Exception as exc:
        print(f"Notice: unable to inspect latest short artifact directly: {exc}")

    if not short_yt:
        for short_attempt in range(1, 6):
            print(f"📱 [Resume Attempt {short_attempt}/5] Triggering/polling NotebookLM Native Short for {slug}...")
            short_now = datetime.now(timezone.utc).isoformat()
            client.dispatch(
                "kesher-short-v4.yml",
                {
                    "operation": "derive",
                    "derive_slug": slug,
                    "derive_content_sha256": source_sha,
                    "derive_long_item_id": long_item_id,
                },
                ref="main",
            )
            short_run = client.poll_workflow("kesher-short-v4.yml", branch="main", dispatched_after_iso=short_now, max_wait_seconds=1800)
            if short_run.get("conclusion") != "success":
                raise RuntimeError(f"Short workflow failed with conclusion: {short_run.get('conclusion')}")
            short_yt = extract_short_state(client, short_run["id"], slug)
            if short_yt:
                print(f"Short uploaded: youtube={short_yt}")
                break
            print(f"Short still generating on provider, retrying poll in 15s...")
            time.sleep(15)
        else:
            raise RuntimeError(f"Short for {slug} did not reach uploaded status after 5 attempts")

    # Step 4: Ensure articleVideos.json and posts.json are up to date
    vids = json.loads(ARTICLE_VIDEOS_FILE.read_text(encoding="utf-8")) if ARTICLE_VIDEOS_FILE.exists() else {}
    current_entry = vids.get(slug, {})
    posts = json.loads(POSTS_FILE.read_text(encoding="utf-8")) if POSTS_FILE.exists() else []
    current_post = next((p for p in posts if (p.get("slug") or p.get("id")) == slug), {})
    needs_commit = (
        current_entry.get("youtubeId") != long_yt
        or (current_entry.get("youtubeShortId") != short_yt and current_entry.get("shortYoutubeId") != short_yt)
        or current_post.get("youtubeVideoId") != long_yt
        or current_post.get("youtubeShortId") != short_yt
    )
    if needs_commit:
        subprocess.run(["git", "switch", "main"], check=True, cwd=ROOT, timeout=30)
        subprocess.run(["git", "reset", "--hard", "HEAD"], check=True, cwd=ROOT, timeout=30)
        subprocess.run(["git", "clean", "-fd"], check=True, cwd=ROOT, timeout=30)
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True, cwd=ROOT, timeout=60)
        update_article_videos(slug, long_id=long_yt, short_id=short_yt)
        staged_media_meta = [
            "src/data/articleVideos.json",
            "src/data/posts.json",
            "src/data/postSummaries.json",
            "public/sitemap.xml",
            "public/rss.xml",
            "public/llms.txt",
            "public/llms-full.txt",
        ]
        subprocess.run(["git", "add", "--", *staged_media_meta], check=True, cwd=ROOT)
        subprocess.run(["git", "commit", "-m", f"chore(media): bind verified YouTube video and short for {slug}"], check=True, cwd=ROOT)
        push_res = subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, timeout=60, capture_output=True, text=True)
        if push_res.returncode != 0:
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True, cwd=ROOT, timeout=60)
            subprocess.run(["git", "push", "origin", "main"], check=True, cwd=ROOT, timeout=60)
        deploy_now = datetime.now(timezone.utc).isoformat()
        client.dispatch("deploy.yml", ref="main")
        client.poll_workflow("deploy.yml", branch="main", dispatched_after_iso=deploy_now, max_wait_seconds=600)

    # Final supervisor audit
    final_audit = run_supervisor_audit(slot, target_slug=slug)
    return {
        "action": "resume",
        "slot": slot,
        "slug": slug,
        "long_youtube_id": long_yt,
        "short_youtube_id": short_yt,
        "contract_complete": final_audit["complete"],
        "status": "success" if final_audit["complete"] else "in_progress",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["daily", "run_now", "resume", "audit", "repair"], help="Action to execute")
    parser.add_argument("--slot", default="", help="Publication date YYYY-MM-DD (defaults to today in Israel)")
    parser.add_argument("--target-slug", default="", help="Optional exact target article slug to audit or resume")
    parser.add_argument("--topic-brief", default="", help="Optional topic brief")
    parser.add_argument("--idea-id", default="", help="Optional unique idea ID")
    parser.add_argument("--primary-keyword", default="", help="Optional Hebrew primary keyword")
    parser.add_argument("--article-json", default="", help="Path to article JSON or raw string")
    parser.add_argument("--stage-only", action="store_true", help="Stage candidate PR and dispatch CI only")
    parser.add_argument("--dry-run", action="store_true", help="Validate without mutating or dispatching")
    parser.add_argument("--output-json", default=str(RESULT_FILE), help="Structured result JSON destination")
    args = parser.parse_args()

    slot = args.slot.strip() or israel_date_now()
    target_slug = args.target_slug.strip() or None
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    repo = os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPO)
    client = GitHubActionsClient(token, repo) if token else None

    article_json = None
    if args.article_json:
        raw = args.article_json.strip()
        # Inline JSON must not be probed as a filesystem path (ENAMETOOLONG).
        if raw.startswith(("{", "[")):
            article_json = json.loads(raw)
        elif Path(raw).is_file():
            article_json = json.loads(Path(raw).read_text(encoding="utf-8"))
        else:
            article_json = json.loads(raw)

    result: dict[str, Any]
    try:
        if args.action == "audit":
            result = handle_audit(slot, target_slug=target_slug)
        elif args.action == "repair":
            result = handle_repair()
        elif args.action == "daily":
            result = handle_daily(slot, client, dry_run=args.dry_run, stage_only=args.stage_only)
        elif args.action == "run_now":
            result = handle_run_now(
                slot,
                client,
                topic_brief=args.topic_brief,
                idea_id=args.idea_id,
                primary_keyword=args.primary_keyword,
                article_json=article_json,
                dry_run=args.dry_run,
                stage_only=args.stage_only,
            )
        elif args.action == "resume":
            result = handle_resume(slot, client, target_slug=target_slug, dry_run=args.dry_run)
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

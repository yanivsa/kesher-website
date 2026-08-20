#!/usr/bin/env python3
"""Autonomous Kesher article -> video orchestration.

GitHub Actions remains the execution surface for secret-bearing jobs. This
controller owns ordering, idempotency, durable state, retries and public success
checks so a later heartbeat can always resume from reality instead of starting
another copy of the same work.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

SITE_URL = "https://kesher.saharoni.com"
STATE_REF = os.environ.get("KESHER_CONTROLLER_STATE_REF", "automation-state")
STATE_PATH = ".kesher-controller/state.json"
STATE_SCHEMA_VERSION = 1
ARTICLE_WORKFLOW = "kesher-article-generation.yml"
VIDEO_WORKFLOW = "kesher-daily-video.yml"
DEPLOY_WORKFLOW = "deploy.yml"
VIDEO_STATE_ARTIFACT = "kesher-video-state"
YOUTUBE_CHANNEL_ID = "UCx5fEFvdVf28HLAR2dFW64Q"
ACTIVE_RUN_STATUSES = {"queued", "in_progress", "waiting", "requested", "pending"}
ACTIVE_VIDEO_STATUSES = {
    "source_selected", "source_added", "generating", "downloaded",
    "pending_review", "approved", "uploading",
}
MAX_ATTEMPTS = {"article": 4, "deploy": 3, "video": 4}
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
HEBCAL_ASHDOD_URL = (
    "https://www.hebcal.com/zmanim?cfg=json&geonameid=295629&date={date}&sec=1"
)


class ControllerError(RuntimeError):
    pass


@dataclass(frozen=True)
class Action:
    kind: str
    reason: str
    inputs: dict[str, str] | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_slug(post: dict[str, Any]) -> str:
    return str(post.get("slug") or post.get("id") or "").strip()


def today_articles(posts: list[dict[str, Any]], day: date) -> list[dict[str, Any]]:
    expected = day.isoformat()
    return [
        post for post in posts
        if isinstance(post, dict)
        and str(post.get("date") or "").strip() == expected
        and canonical_slug(post)
    ]


def article_is_public(html_text: str, expected_title: str) -> bool:
    page = re.sub(r"\s+", " ", html_text)
    title = re.sub(r"\s+", " ", expected_title.strip())
    return bool(title) and title in page


def verified_youtube_item(item: dict[str, Any], slug: str) -> bool:
    source = item.get("source") or {}
    source_slug = str(source.get("slug") or source.get("id") or "").strip()
    verification = item.get("youtube_verification") or {}
    return bool(
        source_slug == slug
        and item.get("uploaded") is True
        and item.get("status") == "uploaded"
        and item.get("youtube_id")
        and item.get("youtube_url")
        and verification.get("channel_id") == YOUTUBE_CHANNEL_ID
        and verification.get("privacy_status") == "public"
        and verification.get("processing_status") == "succeeded"
    )


def matching_video_items(video_state: dict[str, Any], slug: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for item in video_state.get("items") or []:
        if not isinstance(item, dict):
            continue
        source = item.get("source") or {}
        source_slug = str(source.get("slug") or source.get("id") or "").strip()
        if source_slug == slug:
            matches.append(item)
    return matches


def new_cycle_state(day: date, old: dict[str, Any] | None = None) -> dict[str, Any]:
    history = list((old or {}).get("history") or [])[-80:]
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "cycle": day.isoformat(),
        "status": "article_needed",
        "article": {"attempts": 0, "deploy_attempts": 0},
        "video": {"attempts": 0, "resume_dispatches": 0},
        "last_error": None,
        "history": history,
        "updated_at": utc_now(),
    }


def transition(state: dict[str, Any], status: str, reason: str, **details: Any) -> None:
    previous = state.get("status")
    if previous != status or details:
        event: dict[str, Any] = {
            "at": utc_now(), "from": previous, "to": status, "reason": reason,
        }
        if details:
            event["details"] = details
        state.setdefault("history", []).append(event)
        state["history"] = state["history"][-100:]
    state["status"] = status
    state["updated_at"] = utc_now()
    state["last_error"] = None


def block(state: dict[str, Any], stage: str, code: str, message: str) -> None:
    previous = state.get("status")
    state["status"] = "blocked"
    state["last_error"] = {
        "stage": stage, "code": code, "message": message, "at": utc_now(),
    }
    state.setdefault("history", []).append({
        "at": utc_now(), "from": previous, "to": "blocked", "reason": code,
        "details": {"message": message},
    })
    state["history"] = state["history"][-100:]
    state["updated_at"] = utc_now()


def article_window_open(now: datetime, saturday_sunset: datetime | None = None) -> bool:
    local = now.astimezone(ISRAEL_TZ)
    weekday = local.isoweekday()
    clock = local.timetz().replace(tzinfo=None)
    if weekday in {7, 1, 2, 3, 4}:  # Sunday-Thursday
        return clock >= dt_time(0, 35)
    if weekday == 5:  # Friday
        return clock >= dt_time(8, 0)
    if weekday == 6:
        if saturday_sunset is None:
            return False
        return local >= saturday_sunset.astimezone(ISRAEL_TZ) + timedelta(hours=1)
    return False


class GitHubClient:
    def __init__(self, repo: str, token: str):
        self.repo = repo
        self.token = token
        self.api = f"https://api.github.com/repos/{repo}"

    def request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
        *,
        raw: bool = False,
        allow_404: bool = False,
    ) -> Any:
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        last: Exception | None = None
        for attempt in range(4):
            request = urllib.request.Request(
                url, data=data, method=method,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                    "User-Agent": "kesher-content-controller",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    payload = response.read()
                    if raw:
                        return payload
                    return json.loads(payload.decode("utf-8")) if payload else {}
            except urllib.error.HTTPError as exc:
                if allow_404 and exc.code == 404:
                    return None
                detail = exc.read().decode("utf-8", errors="replace")[:1500]
                if exc.code not in {429, 500, 502, 503, 504}:
                    raise ControllerError(
                        f"GITHUB_HTTP_{exc.code}: {method} {url} failed: {detail}"
                    ) from exc
                last = exc
            except urllib.error.URLError as exc:
                last = exc
            time.sleep(2 ** attempt)
        raise ControllerError(f"GITHUB_TRANSIENT_FAILURE: {method} {url}: {last}")

    def download_artifact_archive(self, url: str) -> bytes:
        """Download an Actions artifact without forwarding GitHub auth to signed blob storage."""

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirect())
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "kesher-content-controller",
        }
        last: Exception | None = None
        for attempt in range(4):
            request = urllib.request.Request(url, method="GET", headers=headers)
            try:
                with opener.open(request, timeout=45) as response:
                    return response.read()
            except urllib.error.HTTPError as exc:
                if exc.code in {301, 302, 303, 307, 308}:
                    location = exc.headers.get("Location")
                    if not location:
                        raise ControllerError("GITHUB_ARTIFACT_REDIRECT_MISSING") from exc
                    signed_request = urllib.request.Request(
                        location,
                        method="GET",
                        headers={"User-Agent": "kesher-content-controller"},
                    )
                    try:
                        with urllib.request.urlopen(signed_request, timeout=60) as response:
                            return response.read()
                    except (urllib.error.HTTPError, urllib.error.URLError) as signed_exc:
                        last = signed_exc
                elif exc.code in {429, 500, 502, 503, 504}:
                    last = exc
                else:
                    detail = exc.read().decode("utf-8", errors="replace")[:1000]
                    raise ControllerError(
                        f"GITHUB_ARTIFACT_HTTP_{exc.code}: artifact download failed: {detail}"
                    ) from exc
            except urllib.error.URLError as exc:
                last = exc
            time.sleep(2 ** attempt)
        raise ControllerError(f"GITHUB_ARTIFACT_DOWNLOAD_FAILED: {last}")

    def contents_json(self, path: str, ref: str = "main") -> Any:
        quoted = urllib.parse.quote(path, safe="/")
        payload = self.request(
            "GET", f"{self.api}/contents/{quoted}?ref={urllib.parse.quote(ref, safe='')}"
        )
        if not isinstance(payload, dict) or payload.get("encoding") != "base64":
            raise ControllerError(f"GITHUB_CONTENT_INVALID: {path}@{ref}")
        return json.loads(base64.b64decode(payload.get("content") or "").decode("utf-8"))

    def open_article_prs(self) -> list[dict[str, Any]]:
        prs = self.request("GET", f"{self.api}/pulls?state=open&per_page=100")
        if not isinstance(prs, list):
            raise ControllerError("GITHUB_PRS_INVALID")
        matches: list[dict[str, Any]] = []
        for pr in prs:
            if not isinstance(pr, dict) or not str(pr.get("title") or "").startswith(
                "Publish Kesher article:"
            ):
                continue
            number = pr.get("number")
            if not number:
                continue
            files = self.request("GET", f"{self.api}/pulls/{number}/files?per_page=100")
            if isinstance(files, list) and any(
                isinstance(row, dict) and row.get("filename") == "src/data/posts.json"
                for row in files
            ):
                matches.append(pr)
        return matches

    def workflow_runs(self, workflow: str, limit: int = 20) -> list[dict[str, Any]]:
        name = urllib.parse.quote(workflow, safe="")
        payload = self.request(
            "GET", f"{self.api}/actions/workflows/{name}/runs?per_page={limit}"
        )
        if not isinstance(payload, dict):
            return []
        return [row for row in payload.get("workflow_runs") or [] if isinstance(row, dict)]

    def active_workflow_run(
        self, workflow: str, *, production_only: bool = False
    ) -> dict[str, Any] | None:
        for run in self.workflow_runs(workflow):
            if production_only and str(run.get("event") or "") == "pull_request":
                continue
            if str(run.get("status") or "") in ACTIVE_RUN_STATUSES:
                return run
        return None

    def dispatch(self, workflow: str, inputs: dict[str, str] | None = None) -> None:
        body: dict[str, Any] = {"ref": "main"}
        if inputs:
            body["inputs"] = inputs
        name = urllib.parse.quote(workflow, safe="")
        self.request("POST", f"{self.api}/actions/workflows/{name}/dispatches", body)

    def main_sha(self) -> str:
        payload = self.request("GET", f"{self.api}/git/ref/heads/main")
        return str(((payload or {}).get("object") or {}).get("sha") or "")

    def ensure_state_ref(self) -> None:
        encoded = urllib.parse.quote(STATE_REF, safe="")
        if self.request("GET", f"{self.api}/git/ref/heads/{encoded}", allow_404=True):
            return
        sha = self.main_sha()
        if not sha:
            raise ControllerError("GITHUB_MAIN_REF_MISSING")
        self.request("POST", f"{self.api}/git/refs", {
            "ref": f"refs/heads/{STATE_REF}", "sha": sha,
        })

    def load_controller_state(self) -> dict[str, Any] | None:
        self.ensure_state_ref()
        quoted = urllib.parse.quote(STATE_PATH, safe="/")
        payload = self.request(
            "GET",
            f"{self.api}/contents/{quoted}?ref={urllib.parse.quote(STATE_REF, safe='')}",
            allow_404=True,
        )
        if payload is None:
            return None
        if not isinstance(payload, dict) or payload.get("encoding") != "base64":
            raise ControllerError("CONTROLLER_STATE_INVALID")
        state = json.loads(base64.b64decode(payload.get("content") or "").decode("utf-8"))
        if not isinstance(state, dict):
            raise ControllerError("CONTROLLER_STATE_INVALID")
        return state

    def save_controller_state(self, state: dict[str, Any]) -> None:
        self.ensure_state_ref()
        quoted = urllib.parse.quote(STATE_PATH, safe="/")
        current = self.request(
            "GET",
            f"{self.api}/contents/{quoted}?ref={urllib.parse.quote(STATE_REF, safe='')}",
            allow_404=True,
        )
        body: dict[str, Any] = {
            "message": f"state: Kesher controller {state.get('cycle')} {state.get('status')}",
            "content": base64.b64encode(
                (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            ).decode("ascii"),
            "branch": STATE_REF,
        }
        if isinstance(current, dict) and current.get("sha"):
            body["sha"] = current["sha"]
        self.request("PUT", f"{self.api}/contents/{quoted}", body)

    def newest_video_state(self) -> dict[str, Any]:
        payload = self.request(
            "GET",
            f"{self.api}/actions/artifacts?name={VIDEO_STATE_ARTIFACT}&per_page=100",
        )
        artifacts = [
            row for row in (payload.get("artifacts") or [])
            if isinstance(row, dict) and not row.get("expired")
        ] if isinstance(payload, dict) else []
        artifacts.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        failures: list[str] = []
        for artifact in artifacts:
            artifact_id = artifact.get("id") or "unknown"
            archive_url = artifact.get("archive_download_url")
            if not archive_url:
                failures.append(f"artifact {artifact_id}: missing archive_download_url")
                continue
            try:
                raw = self.download_artifact_archive(str(archive_url))
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    names = [name for name in archive.namelist() if name.endswith("state.json")]
                    if not names:
                        failures.append(f"artifact {artifact_id}: missing state.json")
                        continue
                    state = json.loads(archive.read(names[0]).decode("utf-8"))
                    if isinstance(state, dict) and isinstance(state.get("items"), list):
                        return state
                    failures.append(f"artifact {artifact_id}: unsupported state schema")
            except ControllerError as exc:
                failures.append(f"artifact {artifact_id}: {exc}")
                continue
            except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, KeyError) as exc:
                failures.append(f"artifact {artifact_id}: {type(exc).__name__}")
                continue
        if artifacts:
            detail = " | ".join(failures[-5:]) or "no valid state artifact"
            raise ControllerError(f"VIDEO_STATE_ARTIFACTS_UNRECOVERABLE: {detail}")
        return {"version": 1, "items": []}


class PublicSiteClient:
    def get(self, url: str) -> tuple[int, str]:
        request = urllib.request.Request(
            url, headers={"User-Agent": "Kesher-Content-Controller/1.0"}
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return int(response.status), response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return int(exc.code), exc.read().decode("utf-8", errors="replace")


def fetch_ashdod_sunset(day: date) -> datetime:
    request = urllib.request.Request(
        HEBCAL_ASHDOD_URL.format(date=day.isoformat()),
        headers={"User-Agent": "Kesher-Content-Controller/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    raw = ((payload or {}).get("times") or {}).get("sunset")
    if not raw:
        raise ControllerError("HEBCAL_SUNSET_MISSING")
    sunset = datetime.fromisoformat(str(raw))
    if sunset.tzinfo is None:
        sunset = sunset.replace(tzinfo=ISRAEL_TZ)
    return sunset.astimezone(ISRAEL_TZ)


class Controller:
    def __init__(
        self,
        github: GitHubClient,
        site: PublicSiteClient,
        *,
        now: datetime | None = None,
        saturday_sunset: datetime | None = None,
    ):
        self.github = github
        self.site = site
        self.now = (now or datetime.now(ISRAEL_TZ)).astimezone(ISRAEL_TZ)
        self.saturday_sunset = saturday_sunset

    def state(self) -> dict[str, Any]:
        existing = self.github.load_controller_state()
        if (
            not isinstance(existing, dict)
            or existing.get("schema_version") != STATE_SCHEMA_VERSION
            or existing.get("cycle") != self.now.date().isoformat()
        ):
            return new_cycle_state(self.now.date(), existing)
        return existing

    def article_slot_open(self) -> bool:
        sunset = self.saturday_sunset
        if self.now.isoweekday() == 6 and sunset is None:
            sunset = fetch_ashdod_sunset(self.now.date())
        return article_window_open(self.now, sunset)

    def tick(self) -> tuple[dict[str, Any], Action]:
        state = self.state()
        try:
            action = self._tick(state)
        except ControllerError as exc:
            code = str(exc).split(":", 1)[0]
            block(state, "controller", code, str(exc))
            action = Action("blocked", str(exc))
        self.github.save_controller_state(state)
        return state, action

    def _tick(self, state: dict[str, Any]) -> Action:
        if not self.article_slot_open():
            transition(state, "waiting_for_article_window", "publication slot has not opened")
            return Action("wait", "article window not open")

        posts = self.github.contents_json("src/data/posts.json", "main")
        if not isinstance(posts, list):
            raise ControllerError("ARTICLE_SOURCE_INVALID")
        todays = today_articles(posts, self.now.date())
        if len(todays) > 1:
            block(state, "article", "DUPLICATE_ARTICLE_DATE",
                  f"{len(todays)} articles share Israel date {self.now.date()}")
            return Action("blocked", "duplicate published articles")

        open_prs = self.github.open_article_prs()
        if not todays:
            if len(open_prs) > 1:
                block(state, "article", "DUPLICATE_ARTICLE_PRS",
                      f"{len(open_prs)} open article PRs modify posts.json")
                return Action("blocked", "duplicate article PRs")
            if len(open_prs) == 1:
                pr = open_prs[0]
                state["article"].update({
                    "pr_number": pr.get("number"), "pr_url": pr.get("html_url"),
                })
                transition(state, "article_pr_open", "existing article PR is authoritative")
                return Action("wait", "article PR already open")
            active = self.github.active_workflow_run(ARTICLE_WORKFLOW)
            if active:
                state["article"]["run_id"] = active.get("id")
                transition(state, "article_generating", "article workflow already active")
                return Action("wait", "article workflow active")
            attempts = int(state["article"].get("attempts") or 0)
            if attempts >= MAX_ATTEMPTS["article"]:
                block(state, "article", "ARTICLE_ATTEMPTS_EXHAUSTED",
                      f"article generation exhausted {attempts} attempts")
                return Action("blocked", "article attempts exhausted")
            inputs = {"slot": self.now.date().isoformat()}
            self.github.dispatch(ARTICLE_WORKFLOW, inputs)
            state["article"].update({
                "attempts": attempts + 1, "last_dispatch_at": utc_now(),
            })
            transition(state, "article_generating", "article workflow dispatched",
                       attempt=attempts + 1)
            return Action("dispatch_article", "no article or PR exists", inputs)

        article = todays[0]
        slug = canonical_slug(article)
        title = str(article.get("title") or "").strip()
        url = f"{SITE_URL}/blog/{slug}"
        state["article"].update({
            "slug": slug, "title": title, "url": url,
            "published_date": str(article.get("date") or ""),
        })
        if open_prs:
            block(state, "article", "STALE_OR_DUPLICATE_ARTICLE_PR",
                  f"published article exists while {len(open_prs)} article PR(s) remain open")
            return Action("blocked", "published article plus open article PR")

        status, page = self.site.get(url)
        if status != 200 or not article_is_public(page, title):
            if self.github.active_workflow_run(DEPLOY_WORKFLOW):
                transition(state, "article_deploying", "deployment already active")
                return Action("wait", "deployment active")
            attempts = int(state["article"].get("deploy_attempts") or 0)
            if attempts >= MAX_ATTEMPTS["deploy"]:
                block(state, "article", "ARTICLE_DEPLOY_ATTEMPTS_EXHAUSTED",
                      f"article page not public after {attempts} deploy attempts")
                return Action("blocked", "article deploy attempts exhausted")
            self.github.dispatch(DEPLOY_WORKFLOW)
            state["article"].update({
                "deploy_attempts": attempts + 1, "last_deploy_dispatch_at": utc_now(),
            })
            transition(state, "article_deploying", "public article check failed; deploy dispatched",
                       http_status=status, attempt=attempts + 1)
            return Action("dispatch_deploy", "article not public yet")

        state["article"].update({"live": True, "live_verified_at": utc_now()})
        transition(state, "article_live", "HTTP 200 and expected title verified")

        video_state = self.github.newest_video_state()
        matches = matching_video_items(video_state, slug)
        verified = [item for item in matches if verified_youtube_item(item, slug)]
        if verified:
            item = sorted(
                verified,
                key=lambda row: str(row.get("uploaded_at") or row.get("updated_at") or ""),
                reverse=True,
            )[0]
            state["video"].update({
                "item_id": item.get("id"), "status": "uploaded",
                "youtube_id": item.get("youtube_id"), "youtube_url": item.get("youtube_url"),
                "verified": True,
            })
            transition(state, "complete", "public article and YouTube video verified")
            return Action("complete", "public article and video verified")

        active_matches = [
            item for item in matches
            if item.get("status") in ACTIVE_VIDEO_STATUSES or item.get("status") == "rejected"
        ]
        if len(active_matches) > 1:
            block(state, "video", "DUPLICATE_VIDEO_ITEMS",
                  f"{len(active_matches)} active/rejected video items exist for {slug}")
            return Action("blocked", "duplicate video items")

        item = active_matches[0] if active_matches else (matches[-1] if matches else None)
        active_run = self.github.active_workflow_run(VIDEO_WORKFLOW, production_only=True)
        if active_run:
            state["video"]["run_id"] = active_run.get("id")
            if item:
                state["video"].update({"item_id": item.get("id"), "status": item.get("status")})
            transition(state, "video_running", "video workflow already active")
            return Action("wait", "video workflow active")

        if item:
            state["video"].update({"item_id": item.get("id"), "status": item.get("status")})
            if item.get("status") == "uploaded":
                block(state, "video", "UPLOADED_VIDEO_NOT_VERIFIED",
                      "video has upload identity but lacks authoritative public verification")
                return Action("blocked", "uploaded video requires reconciliation")

            if item.get("technical_verified") is True and item.get("status") in {
                "pending_review", "approved", "rejected", "uploading"
            }:
                operation = "upload"
            else:
                operation = "full"
            inputs = {"operation": operation}
            self.github.dispatch(VIDEO_WORKFLOW, inputs)
            resumes = int(state["video"].get("resume_dispatches") or 0) + 1
            state["video"].update({
                "resume_dispatches": resumes, "last_dispatch_at": utc_now(),
            })
            transition(state, "video_running", "existing video item dispatched/resumed",
                       operation=operation, resume=resumes)
            return Action("dispatch_video", "existing article video is incomplete", inputs)

        attempts = int(state["video"].get("attempts") or 0)
        if attempts >= MAX_ATTEMPTS["video"]:
            block(state, "video", "VIDEO_ATTEMPTS_EXHAUSTED",
                  f"video pipeline exhausted {attempts} start attempts")
            return Action("blocked", "video start attempts exhausted")

        inputs = {"operation": "full"}
        self.github.dispatch(VIDEO_WORKFLOW, inputs)
        state["video"].update({
            "attempts": attempts + 1, "last_dispatch_at": utc_now(),
        })
        transition(state, "video_running", "new video workflow dispatched",
                   operation="full", attempt=attempts + 1)
        return Action("dispatch_video", "article live and no matching video item exists", inputs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "yanivsa/kesher-website"))
    parser.add_argument("--report-json", action="store_true")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise ControllerError("GITHUB_TOKEN_MISSING")
    state, action = Controller(GitHubClient(args.repo, token), PublicSiteClient()).tick()
    if args.report_json:
        print(json.dumps({"action": action.kind, "reason": action.reason, "state": state},
                         ensure_ascii=False, indent=2))
    else:
        print(f"KESHER_CONTROLLER cycle={state.get('cycle')} status={state.get('status')} "
              f"action={action.kind} reason={action.reason}")
        article = state.get("article") or {}
        video = state.get("video") or {}
        if article.get("url"):
            print(f"ARTICLE {article.get('slug')} {article.get('url')}")
        if video.get("youtube_url"):
            print(f"VIDEO {video.get('youtube_url')}")
    return 1 if action.kind == "blocked" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ControllerError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"KESHER_CONTROLLER_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

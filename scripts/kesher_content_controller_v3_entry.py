#!/usr/bin/env python3
"""Production Kesher controller v3 hardening layer.

This adapter closes the remaining gap between the canonical v3 contract and
runtime behavior:
- article, image and video are explicit durable stages;
- every stage has at most three controller-owned dispatch attempts;
- retries use 5/15 minute backoff and failed child events wait for heartbeat;
- the trusted image worker is controller-dispatched, correlated and retryable;
- current provider/run identities are persisted before subsequent work;
- legacy schema-v2 state is migrated without losing recovery history.

The mature base controller remains the reconciliation engine. This module adds
only the missing production invariants and then delegates to the existing
queue-aware entrypoint.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

if __package__:
    from . import kesher_article_contract as article_contract
    from . import kesher_content_controller as core
    from . import kesher_content_controller_entry as entry
else:
    import kesher_article_contract as article_contract
    import kesher_content_controller as core
    import kesher_content_controller_entry as entry

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
STATE_SCHEMA_VERSION = 3
IMAGE_WORKFLOW = "kesher-article-image.yml"
IMAGE_WORKFLOW_NAME = "Kesher Trusted Article Image"
MAX_STAGE_ATTEMPTS = 3
BACKOFF_MINUTES = (5, 15)
IMAGE_PROVIDERS = set(article_contract.IMAGE_PROVIDER_RULES)
IMAGE_RESULTS = {"generated", "stock", "local_fallback"}


class StageAttemptsExhausted(core.ControllerError):
    def __init__(self, stage: str, code: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.code = code


def _stage_template() -> dict[str, Any]:
    return {
        "attempt_count": 0,
        "status": "pending",
        "last_error": None,
        "next_retry_at": None,
        "run_id": None,
        "processed_run_id": None,
        "provider_id": None,
        "failure_fingerprint": None,
        "same_failure_streak": 0,
        "failure_count_by_type": {},
    }


def _legacy_attempt_count(state: dict[str, Any], stage: str) -> int:
    current = state.get(stage) if isinstance(state.get(stage), dict) else {}
    if stage == "article":
        return int(current.get("attempt_count") or current.get("attempts") or 0)
    if stage == "video":
        if current.get("attempt_count") is not None:
            return int(current.get("attempt_count") or 0)
        # A schema-v2 video workflow resume was a real controller dispatch too.
        return int(current.get("attempts") or 0) + int(current.get("resume_dispatches") or 0)
    return int(current.get("attempt_count") or 0)


def normalize_state(existing: dict[str, Any] | None, day) -> dict[str, Any]:
    if not isinstance(existing, dict) or existing.get("cycle") != day.isoformat():
        state = core.new_cycle_state(day, existing)
        state["schema_version"] = STATE_SCHEMA_VERSION
        state["image"] = _stage_template()
        for stage in ("article", "video"):
            merged = _stage_template()
            merged.update(state.get(stage) or {})
            merged["attempt_count"] = 0
            state[stage] = merged
        state.setdefault("history", []).append({
            "at": core.utc_now(),
            "from": None,
            "to": state.get("status"),
            "reason": "controller state initialized at schema v3",
        })
        return state

    state = copy.deepcopy(existing)
    previous_schema = state.get("schema_version")
    state["schema_version"] = STATE_SCHEMA_VERSION
    for stage in ("article", "image", "video"):
        original = state.get(stage) if isinstance(state.get(stage), dict) else {}
        merged = _stage_template()
        merged.update(original)
        merged["attempt_count"] = _legacy_attempt_count(state, stage)
        state[stage] = merged
    if previous_schema != STATE_SCHEMA_VERSION:
        state.setdefault("history", []).append({
            "at": core.utc_now(),
            "from": state.get("status"),
            "to": state.get("status"),
            "reason": f"controller state migrated from schema {previous_schema} to schema v3",
        })
        state["history"] = state["history"][-100:]
    state["updated_at"] = core.utc_now()
    return state


exact_field = article_contract.exact_field

class V3GitHubClient(core.GitHubClient):
    def _article_pr_image_proof(
        self,
        pr: dict[str, Any],
        *,
        require_head: bool,
    ) -> tuple[bool, dict[str, str]]:
        try:
            base_posts = self.contents_json("src/data/posts.json", str((pr.get("base") or {}).get("sha") or "main"))
            head_posts = self.contents_json("src/data/posts.json", str((pr.get("head") or {}).get("sha") or ""))
        except core.ControllerError:
            return False, {}
        if not isinstance(base_posts, list) or not isinstance(head_posts, list):
            return False, {}
        base_ids = {core.canonical_slug(row) for row in base_posts if isinstance(row, dict)}
        new_posts = [row for row in head_posts if isinstance(row, dict) and core.canonical_slug(row) not in base_ids]
        if len(new_posts) != 1:
            return False, {}
        post = new_posts[0]
        head_sha = str((pr.get("head") or {}).get("sha") or "")
        body = str(pr.get("body") or "")
        evidence_head = str(article_contract.exact_field(body, "Image Evidence Head") or "").strip().lower()
        effective_head = head_sha
        if require_head and evidence_head and head_sha.lower() != evidence_head:
            curr = head_sha
            for _ in range(6):
                try:
                    commit_payload = self.request("GET", f"{self.api}/commits/{curr}", allow_404=True)
                    parents = [
                        str(p.get("sha") or "").strip().lower()
                        for p in (commit_payload.get("parents") or [])
                        if isinstance(p, dict)
                    ]
                    if len(parents) < 2:
                        break
                    curr = parents[0]
                    if curr == evidence_head:
                        effective_head = evidence_head
                        break
                except Exception:
                    break
        if article_contract.image_proof_errors(post, body, effective_head, require_head=require_head):
            return False, {}
        quoted = urllib_quote("public" + post["image"])
        try:
            payload = self.request(
                "GET", f"{self.api}/contents/{quoted}?ref={urllib_quote(head_sha)}", allow_404=True,
            )
            if not isinstance(payload, dict):
                return False, {}
            # Contents API omits inline bytes above 1 MiB. Fetch the exact blob
            # returned for this head, never a mutable download URL.
            if payload.get("encoding") != "base64" and re.fullmatch(r"[a-f0-9]{40}", str(payload.get("sha") or "")):
                payload = self.request("GET", f"{self.api}/git/blobs/{payload['sha']}", allow_404=True)
            if not isinstance(payload, dict) or payload.get("encoding") != "base64" or not payload.get("content"):
                return False, {}
            data = base64.b64decode(payload["content"])
        except (core.ControllerError, ValueError, TypeError):
            return False, {}
        if article_contract.image_proof_errors(
            post,
            body,
            effective_head,
            data,
            require_head=require_head,
        ):
            return False, {}
        actual_sha = hashlib.sha256(data).hexdigest()
        actual_pixels = None
        try:
            actual_pixels = article_contract.image_pixel_sha256(data)
        except Exception:
            pass
        post_img = str(post.get("image") or "").strip()
        body_source = str(article_contract.exact_field(body, "Image Source URL") or "").strip()
        comparison_posts = list(base_posts)
        try:
            recent_posts = self.contents_json("src/data/postsRecent.json", str((pr.get("base") or {}).get("sha") or "main"))
            if isinstance(recent_posts, list):
                comparison_posts.extend([p for p in recent_posts if isinstance(p, dict)])
        except Exception:
            pass
        for base_post in comparison_posts:
            if not isinstance(base_post, dict):
                continue
            base_img = str(base_post.get("image") or "").strip()
            if base_img and base_img == post_img:
                return False, {}
            if body_source and base_img and body_source == f"local://public{base_img}":
                return False, {}
            base_sha = str(base_post.get("imageSha256") or "").strip()
            if base_sha and base_sha == actual_sha:
                return False, {}
            if base_img:
                local_base = Path(__file__).resolve().parents[1] / "public" / base_img.lstrip("/")
                if local_base.is_file():
                    try:
                        base_bytes = local_base.read_bytes()
                        if hashlib.sha256(base_bytes).hexdigest() == actual_sha:
                            return False, {}
                        if actual_pixels and article_contract.image_pixel_sha256(base_bytes) == actual_pixels:
                            return False, {}
                    except Exception:
                        return False, {}
        return True, {
            "provider": article_contract.exact_field(body, "Image Provider"),
            "sha256": article_contract.exact_field(body, "Image SHA-256"),
            "source": article_contract.exact_field(body, "Image Source URL"),
            "article_id": str(post["id"]),
            "article_sha256": article_contract.article_sha256(post),
            "head_sha": head_sha,
        }

    def article_pr_image_ready(self, pr: dict[str, Any]) -> tuple[bool, dict[str, str]]:
        return self._article_pr_image_proof(pr, require_head=True)

    def article_pr_image_rebindable(self, pr: dict[str, Any]) -> tuple[bool, dict[str, str]]:
        """Return true only when exact article/pixels proof is valid except for head binding."""
        return self._article_pr_image_proof(pr, require_head=False)

    def article_pr_prior_image_recoverable(self, pr: dict[str, Any]) -> tuple[bool, dict[str, str]]:
        """Prove an immutable prior image artifact can be reattached to this normalized article.

        Recovery is deliberately narrower than ordinary rebind: the current head
        must have lost only ``image``/``imageAlt`` while its exact editorial record
        remains identical to the historically proven image head.
        """
        body = str(pr.get("body") or "")
        evidence_head = str(article_contract.exact_field(body, "Image Evidence Head") or "").strip().lower()
        current_head = str((pr.get("head") or {}).get("sha") or "").strip().lower()
        if (
            not re.fullmatch(r"[a-f0-9]{40}", evidence_head)
            or not re.fullmatch(r"[a-f0-9]{40}", current_head)
            or evidence_head == current_head
        ):
            return False, {}

        historical_pr = dict(pr)
        historical_pr["head"] = dict(pr.get("head") or {})
        historical_pr["head"]["sha"] = evidence_head
        proven, evidence = self._article_pr_image_proof(historical_pr, require_head=True)
        if not proven:
            return False, {}

        try:
            base_ref = str((pr.get("base") or {}).get("sha") or "main")
            base_posts = self.contents_json("src/data/posts.json", base_ref)
            current_posts = self.contents_json("src/data/posts.json", current_head)
            historical_posts = self.contents_json("src/data/posts.json", evidence_head)
        except core.ControllerError:
            return False, {}
        if not all(isinstance(rows, list) for rows in (base_posts, current_posts, historical_posts)):
            return False, {}

        article_id = str(evidence.get("article_id") or "").strip()
        if not article_id:
            return False, {}
        current_matches = [row for row in current_posts if isinstance(row, dict) and str(row.get("id") or "").strip() == article_id]
        historical_matches = [row for row in historical_posts if isinstance(row, dict) and str(row.get("id") or "").strip() == article_id]
        if len(current_matches) != 1 or len(historical_matches) != 1:
            return False, {}
        current_post = current_matches[0]
        historical_post = historical_matches[0]
        if str(current_post.get("image") or "").strip() or str(current_post.get("imageAlt") or "").strip():
            return False, {}

        if article_contract.image_visual_identity(current_post) != article_contract.image_visual_identity(historical_post):
            return False, {}

        base_ids = {core.canonical_slug(row) for row in base_posts if isinstance(row, dict)}
        current_new = [row for row in current_posts if isinstance(row, dict) and core.canonical_slug(row) not in base_ids]
        if len(current_new) != 1 or str(current_new[0].get("id") or "").strip() != article_id:
            return False, {}
        return True, evidence

    def active_image_run(self, pr_number: int) -> dict[str, Any] | None:
        expected = f"Kesher Image PR {pr_number}"
        for run in self.workflow_runs(IMAGE_WORKFLOW):
            if str(run.get("event") or "") != "workflow_dispatch":
                continue
            if str(run.get("display_title") or "") != expected:
                continue
            if str(run.get("status") or "") in core.ACTIVE_RUN_STATUSES:
                return run
        return None


def urllib_quote(value: str) -> str:
    import urllib.parse
    return urllib.parse.quote(value, safe="/")


def _backoff_for(streak: int) -> int:
    return BACKOFF_MINUTES[min(max(int(streak), 1) - 1, len(BACKOFF_MINUTES) - 1)]


def record_stage_failure(
    state: dict[str, Any],
    stage: str,
    code: str,
    message: str,
    *,
    run_id: Any = None,
) -> None:
    current = state[stage]
    counts = current.setdefault("failure_count_by_type", {})
    counts[code] = int(counts.get(code) or 0) + 1
    if current.get("failure_fingerprint") == code:
        streak = int(current.get("same_failure_streak") or 0) + 1
    else:
        streak = 1
    current["failure_fingerprint"] = code
    current["same_failure_streak"] = streak
    retry_at = datetime.now(timezone.utc) + timedelta(minutes=_backoff_for(streak))
    current["next_retry_at"] = retry_at.isoformat()
    current["status"] = "retry_wait"
    current["last_error"] = {
        "code": code,
        "message": message,
        "retryable": True,
        "retry_at": current["next_retry_at"],
        "at": core.utc_now(),
    }
    if run_id:
        current["last_failed_run_id"] = run_id
    state["last_error"] = {"stage": stage, **current["last_error"]}
    previous = state.get("status")
    state["status"] = f"{stage}_retry_wait"
    state.setdefault("history", []).append({
        "at": core.utc_now(),
        "from": previous,
        "to": state["status"],
        "reason": code,
        "details": {
            "message": message,
            "retry_at": current["next_retry_at"],
            "failure_streak": streak,
            "run_id": run_id,
        },
    })
    state["history"] = state["history"][-100:]
    state["updated_at"] = core.utc_now()


def clear_stage_failure(stage_state: dict[str, Any]) -> None:
    stage_state["failure_fingerprint"] = None
    stage_state["same_failure_streak"] = 0
    stage_state["next_retry_at"] = None
    stage_state["last_error"] = None


class V3Controller(core.Controller):
    def state(self) -> dict[str, Any]:
        return normalize_state(self.github.load_controller_state(), self.now.date())

    def tick(self) -> tuple[dict[str, Any], core.Action]:
        state = self.state()
        try:
            action = self._tick(state)
        except StageAttemptsExhausted as exc:
            core.block(state, exc.stage, exc.code, str(exc))
            state[exc.stage]["status"] = "exhausted"
            state[exc.stage]["last_error"] = state.get("last_error")
            action = core.Action("blocked", str(exc))
        except core.ControllerError as exc:
            code = str(exc).split(":", 1)[0]
            core.block(state, "controller", code, str(exc))
            action = core.Action("blocked", str(exc))
        self._sync_stage_views(state, action)
        self.github.save_controller_state(state)
        return state, action

    def _sync_stage_views(self, state: dict[str, Any], action: core.Action) -> None:
        last_error = state.get("last_error") if isinstance(state.get("last_error"), dict) else None
        for stage in ("article", "image", "video"):
            current = state[stage]
            current.setdefault("attempt_count", 0)
            current.setdefault("status", "pending")
            current.setdefault("last_error", None)
            current.setdefault("next_retry_at", None)
            current.setdefault("run_id", None)
            current.setdefault("provider_id", None)
            if last_error and last_error.get("stage") == stage:
                current["last_error"] = dict(last_error)
        if state.get("status") == "complete":
            state["article"]["status"] = "complete"
            state["image"]["status"] = "complete"
            state["video"]["status"] = "complete"
        elif action.kind == "dispatch_article":
            state["article"]["status"] = "running"
        elif action.kind == "dispatch_image":
            state["image"]["status"] = "running"
        elif action.kind == "dispatch_video":
            state["video"]["status"] = "running"

    def _dispatch_budgeted(
        self,
        state: dict[str, Any],
        stage: str,
        workflow: str,
        inputs: dict[str, str] | None,
    ) -> None:
        current = state[stage]
        count = int(current.get("attempt_count") or 0)
        if count >= MAX_STAGE_ATTEMPTS:
            raise StageAttemptsExhausted(
                stage,
                f"{stage.upper()}_ATTEMPTS_EXHAUSTED",
                f"{stage} exhausted {MAX_STAGE_ATTEMPTS} total controller dispatch attempts",
            )
        core.GitHubClient.dispatch(self.github, workflow, inputs)
        current["attempt_count"] = count + 1
        current["last_dispatch_at"] = core.utc_now()
        current["status"] = "running"
        current["next_retry_at"] = None

    def _reconcile_image_run(
        self,
        state: dict[str, Any],
        pr: dict[str, Any],
    ) -> core.Action | None:
        image = state["image"]
        run_id = image.get("run_id")
        if not run_id or image.get("processed_run_id") == run_id:
            return None
        run = self._workflow_run(run_id)
        if not run or str(run.get("status") or "") != "completed":
            return None
        image["processed_run_id"] = run_id
        image["last_run_conclusion"] = run.get("conclusion")
        ready, evidence = self.github.article_pr_image_ready(pr)
        if ready:
            clear_stage_failure(image)
            image.update({
                "status": "complete",
                "provider_id": evidence.get("provider"),
                "artifact_sha256": evidence.get("sha256"),
                "source_id": evidence.get("source"),
            })
            return None
        conclusion = str(run.get("conclusion") or "unknown")
        code = "IMAGE_OUTPUT_MISSING" if conclusion == "success" else "IMAGE_WORKFLOW_FAILED"
        record_stage_failure(
            state,
            "image",
            code,
            f"trusted image run {run_id} completed with conclusion={conclusion} but no validated image is present",
            run_id=run_id,
        )
        return core.Action("wait", code)

    def _handle_open_article_pr(
        self,
        state: dict[str, Any],
        pr: dict[str, Any],
    ) -> core.Action:
        number = int(pr.get("number") or 0)
        state["article"].update({"pr_number": number, "pr_url": pr.get("html_url")})
        ready, evidence = self.github.article_pr_image_ready(pr)
        if ready:
            clear_stage_failure(state["image"])
            state["image"].update({
                "status": "complete",
                "provider_id": evidence.get("provider"),
                "artifact_sha256": evidence.get("sha256"),
                "source_id": evidence.get("source"),
            })
            core.transition(state, "article_pr_open", "article PR has trusted image and remains authoritative")
            return core.Action("wait", "article PR image ready; waiting for gate/merge")

        active = self.github.active_image_run(number)
        if active:
            state["image"]["run_id"] = active.get("id")
            # Recover a dispatch that happened before durable state was saved.
            if int(state["image"].get("attempt_count") or 0) == 0:
                state["image"]["attempt_count"] = 1
            state["image"]["status"] = "running"
            core.transition(state, "article_image_running", "trusted image workflow already active")
            return core.Action("wait", "trusted image workflow active")

        reconciled = self._reconcile_image_run(state, pr)
        if reconciled is not None:
            return reconciled

        if not core.retry_ready(state["image"], self.now):
            retry_at = state["image"].get("next_retry_at")
            core.transition(state, "image_retry_wait", "trusted image retry backoff is active", retry_at=retry_at)
            return core.Action("wait", f"image retry scheduled for {retry_at}")

        self._dispatch_budgeted(state, "image", IMAGE_WORKFLOW, {"pr_number": str(number)})
        core.transition(
            state,
            "article_image_running",
            "controller dispatched one trusted image worker attempt",
            attempt=state["image"]["attempt_count"],
            pr_number=number,
        )
        return core.Action("dispatch_image", "article PR requires trusted image", {"pr_number": str(number)})

    def _tick(self, state: dict[str, Any]) -> core.Action:
        # Intercept the article-PR state because the base controller predates the
        # explicit image stage.
        posts = self.posts_on_main("main")
        todays = self._reconcile_existing_current_day_article(state, posts)
        if not todays and self.article_slot_open():
            open_prs = self.github.open_article_prs(self.now.date().isoformat())
            if len(open_prs) > 1:
                core.block(
                    state,
                    "article",
                    "DUPLICATE_ARTICLE_PRS",
                    f"{len(open_prs)} open article PRs modify posts.json",
                )
                return core.Action("blocked", "duplicate article PRs")
            if len(open_prs) == 1:
                return self._handle_open_article_pr(state, open_prs[0])

        has_dispatch = hasattr(self.github, "dispatch")
        original_dispatch = getattr(self.github, "dispatch", None)

        def guarded_dispatch(workflow: str, inputs: dict[str, str] | None = None) -> None:
            if workflow == core.ARTICLE_WORKFLOW:
                self._dispatch_budgeted(state, "article", workflow, inputs)
                return
            if workflow == core.VIDEO_WORKFLOW:
                self._dispatch_budgeted(state, "video", workflow, inputs)
                return
            if workflow == core.DEPLOY_WORKFLOW:
                if int(state["article"].get("deploy_attempts") or 0) >= MAX_STAGE_ATTEMPTS:
                    raise StageAttemptsExhausted(
                        "article",
                        "ARTICLE_DEPLOY_ATTEMPTS_EXHAUSTED",
                        f"article deployment exhausted {MAX_STAGE_ATTEMPTS} recovery attempts",
                    )
            if original_dispatch:
                original_dispatch(workflow, inputs)

        if has_dispatch:
            self.github.dispatch = guarded_dispatch  # type: ignore[method-assign]
        try:
            return super()._tick(state)
        finally:
            if has_dispatch:
                self.github.dispatch = original_dispatch  # type: ignore[method-assign]
            elif hasattr(self.github, "dispatch"):
                delattr(self.github, "dispatch")


# Patch the queue-aware entrypoint so image workflow completions are correlated
# exactly like article/video child runs.
_original_trigger_stage = entry._trigger_stage
_original_adopt_latest = entry.adopt_latest_dispatched_children


def v3_trigger_stage(workflow_name: str):
    if workflow_name in {IMAGE_WORKFLOW_NAME, "Kesher Article Hero Image"}:
        return "image", IMAGE_WORKFLOW
    return _original_trigger_stage(workflow_name)


def v3_adopt_latest(github: Any, state: dict[str, Any] | None, cycle: str) -> bool:
    changed = _original_adopt_latest(github, state, cycle)
    if not isinstance(state, dict) or state.get("cycle") != cycle:
        return changed
    image = state.get("image") if isinstance(state.get("image"), dict) else None
    if not image or not image.get("last_dispatch_at"):
        return changed
    try:
        runs = github.workflow_runs(IMAGE_WORKFLOW)
    except core.ControllerError:
        return changed
    production = [
        run for run in runs
        if isinstance(run, dict) and str(run.get("event") or "") == "workflow_dispatch"
    ]
    candidate = entry._nearest_dispatched_run(production, image)
    if candidate is None or entry._same_id(image.get("run_id"), candidate.get("id")):
        return changed
    image["run_id"] = candidate.get("id")
    github.save_controller_state(state)
    print(f"KESHER_DISPATCH_CORRELATED stage=image run_id={candidate.get('id')} cycle={cycle}", flush=True)
    return True


def main() -> int:
    from scripts.kesher_runtime.legacy_retirement import retired_entrypoint
    retired_entrypoint()
    core.STATE_SCHEMA_VERSION = STATE_SCHEMA_VERSION
    core.GitHubClient = V3GitHubClient
    core.Controller = V3Controller
    entry._trigger_stage = v3_trigger_stage
    entry.adopt_latest_dispatched_children = v3_adopt_latest
    return entry.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (core.ControllerError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"KESHER_CONTROLLER_V3_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

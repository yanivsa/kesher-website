#!/usr/bin/env python3
"""Production adapter: article images are best effort, never a publication gate.

The underlying v3 controller owns retries and image orchestration. This adapter
keeps image terminal failure non-blocking and distinguishes a real video worker
attempt from a heartbeat that merely resumes the exact same persisted NotebookLM
task. Provider polling must not consume the three-attempt retry budget.

Article auto-merge remains fully automatic, but only after the controller-owned
image stage has reached a persisted terminal state. The first tick records that
terminal state; a later heartbeat dispatches the existing auto-merge workflow,
which prevents the merge workflow from racing ahead of the image attempt.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

if __package__:
    from . import kesher_content_controller_v3_entry as v3
else:
    import kesher_content_controller_v3_entry as v3


VIDEO_PROVIDER_PROGRESS = {"generating"}
AUTO_MERGE_WORKFLOW = "auto-merge-article-prs.yml"
IMAGE_TERMINAL_STATES = {"complete", "deferred"}
AUTO_MERGE_REDISPATCH_SECONDS = 15 * 60
MAX_AUTO_MERGE_DISPATCHES = 3
FALSE_DUPLICATE_RECOVERY_MARKER = "slot_scoped_duplicate_recovery_applied"


class BestEffortController(v3.V3Controller):
    def state(self) -> dict[str, Any]:
        """Recover once from attempt exhaustion caused by the old global PR guard.

        Before the article worker became slot-scoped, unrelated open publication
        PRs from older dates could return DUPLICATE_ARTICLE_PRS and consume all
        three attempts without ever creating a Jules session or PR for the
        current slot. Once this code is deployed, that historical failure is
        safe to retry exactly once: the corrected worker will only consider PRs
        that actually contain the current publication date.
        """
        state = super().state()
        article = state.get("article") if isinstance(state.get("article"), dict) else {}
        worker_result = article.get("last_worker_result") if isinstance(article.get("last_worker_result"), dict) else {}
        top_error = state.get("last_error") if isinstance(state.get("last_error"), dict) else {}

        should_recover = bool(
            state.get("status") == "blocked"
            and article.get("status") == "exhausted"
            and str(top_error.get("code") or "") == "ARTICLE_ATTEMPTS_EXHAUSTED"
            and str(worker_result.get("outcome") or "") == "DUPLICATE_ARTICLE_PRS"
            and not str(worker_result.get("session_id") or "").strip()
            and not str(worker_result.get("pr_url") or "").strip()
            and not article.get(FALSE_DUPLICATE_RECOVERY_MARKER)
        )
        if not should_recover:
            return state

        previous = str(state.get("status") or "blocked")
        article[FALSE_DUPLICATE_RECOVERY_MARKER] = True
        article["attempt_count"] = 0
        article["attempts"] = 0
        article["status"] = "pending"
        article["last_error"] = None
        article["next_retry_at"] = None
        article["run_id"] = None
        article["processed_run_id"] = None
        article["provider_id"] = None
        article["failure_fingerprint"] = None
        article["same_failure_streak"] = 0
        article["failure_count_by_type"] = {}
        state["status"] = "article_needed"
        state["last_error"] = None
        state.setdefault("history", []).append({
            "at": v3.core.utc_now(),
            "from": previous,
            "to": "article_needed",
            "reason": "slot_scoped_duplicate_guard_recovery",
            "details": {
                "previous_worker_outcome": "DUPLICATE_ARTICLE_PRS",
                "attempt_budget_reset": True,
            },
        })
        state["history"] = state["history"][-100:]
        state["updated_at"] = v3.core.utc_now()
        return state

    def _dispatch_auto_merge_after_persisted_image_terminal(
        self,
        state: dict[str, Any],
        *,
        image_was_terminal: bool,
    ) -> None:
        """Dispatch or recover auto-merge only after a persisted image terminal state."""
        if not image_was_terminal:
            return
        article = state["article"]

        # Merge recovery belongs to the exact image attempt that reached a
        # persisted terminal state. If a later trusted-image retry replaces or
        # revalidates that attempt, stale merge dispatches must not consume the
        # new attempt's recovery budget. Persisting the attempt marker also lets
        # an already-running cycle recover immediately after this fix lands.
        image_attempt_count = int((state.get("image") or {}).get("attempt_count") or 0)
        if (
            "merge_image_attempt_count" not in article
            or int(article.get("merge_image_attempt_count") or 0) != image_attempt_count
        ):
            article["merge_dispatch_at"] = None
            article["merge_dispatch_count"] = 0
            article["merge_image_attempt_count"] = image_attempt_count

        if self.github.active_workflow_run(AUTO_MERGE_WORKFLOW, production_only=True):
            return

        now = datetime.now(timezone.utc)
        last_dispatch = v3.core.parse_timestamp(article.get("merge_dispatch_at"))
        dispatch_count = int(article.get("merge_dispatch_count") or 0)
        if last_dispatch is not None:
            age_seconds = (now - last_dispatch).total_seconds()
            if age_seconds < AUTO_MERGE_REDISPATCH_SECONDS:
                return
        if dispatch_count >= MAX_AUTO_MERGE_DISPATCHES:
            return

        self.github.dispatch(AUTO_MERGE_WORKFLOW)
        article["merge_dispatch_at"] = now.isoformat()
        article["merge_dispatch_count"] = dispatch_count + 1

    def _reconcile_image_run(self, state, pr):
        """Re-read the PR after an image child completes before validating its output."""
        number = int(pr.get("number") or 0)
        request = getattr(self.github, "request", None)
        api = str(getattr(self.github, "api", "") or "")
        if number and callable(request) and api:
            latest = request(
                "GET",
                f"{api}/pulls/{number}",
                allow_404=True,
            )
            if isinstance(latest, dict):
                pr = latest
        return super()._reconcile_image_run(state, pr)

    def _handle_open_article_pr(self, state, pr):
        number = int(pr.get("number") or 0)
        state["article"].update({"pr_number": number, "pr_url": pr.get("html_url")})
        image_was_terminal = str((state.get("image") or {}).get("status") or "") in IMAGE_TERMINAL_STATES

        ready, evidence = self.github.article_pr_image_ready(pr)
        if ready:
            v3.clear_stage_failure(state["image"])
            state["image"].update({
                "status": "complete",
                "provider_id": evidence.get("provider"),
                "artifact_sha256": evidence.get("sha256"),
                "source_id": evidence.get("source"),
            })
            v3.core.transition(
                state,
                "article_pr_open",
                "article PR has trusted image and remains authoritative",
            )
            self._dispatch_auto_merge_after_persisted_image_terminal(
                state,
                image_was_terminal=image_was_terminal,
            )
            return v3.core.Action("wait", "article PR image ready; waiting for gate/merge")

        image = state["image"]
        if int(image.get("attempt_count") or 0) >= v3.MAX_STAGE_ATTEMPTS:
            image["status"] = "deferred"
            image["next_retry_at"] = None
            image["deferred_reason"] = "best_effort_attempts_exhausted"
            if isinstance(image.get("last_error"), dict):
                image["last_error"]["retryable"] = False
            if isinstance(state.get("last_error"), dict) and state["last_error"].get("stage") == "image":
                state["last_warning"] = dict(state["last_error"])
                state["last_error"] = None
            v3.core.transition(
                state,
                "article_pr_open",
                "image best-effort exhausted; article publication remains allowed",
                pr_number=number,
            )
            self._dispatch_auto_merge_after_persisted_image_terminal(
                state,
                image_was_terminal=image_was_terminal,
            )
            return v3.core.Action(
                "wait",
                "image best-effort exhausted; article publication remains allowed",
            )

        return super()._handle_open_article_pr(state, pr)

    @staticmethod
    def _video_item_sort_key(item: dict[str, Any]) -> tuple[str, str, str]:
        source = item.get("source") or {}
        return (
            str(source.get("date") or item.get("israel_date") or item.get("created_at") or "9999-12-31"),
            str(item.get("created_at") or ""),
            str(item.get("id") or ""),
        )

    def _persisted_provider_resume(self) -> dict[str, Any] | None:
        """Return the oldest exact NotebookLM task that is still generating."""
        try:
            video_state = self.github.newest_video_state()
        except v3.core.ControllerError:
            return None
        items = [
            item for item in (video_state.get("items") or [])
            if isinstance(item, dict)
            and item.get("uploaded") is not True
            and item.get("status") in VIDEO_PROVIDER_PROGRESS
        ]
        if not items:
            return None
        item = sorted(items, key=self._video_item_sort_key)[0]
        source_id = str(item.get("source_id") or "").strip()
        task_id = str(item.get("task_id") or "").strip()
        artifact_id = str(item.get("artifact_id") or "").strip()
        if not source_id or not task_id or not artifact_id or task_id != artifact_id:
            return None
        return item

    def _dispatch_budgeted(self, state, stage, workflow, inputs):
        # A persisted NotebookLM task already represents the real provider
        # attempt. A later heartbeat that dispatches the worker only to poll and
        # resume that exact task is recovery, not another generation attempt.
        if stage == "video":
            item = self._persisted_provider_resume()
            if item is not None:
                v3.core.GitHubClient.dispatch(self.github, workflow, inputs)
                current = state["video"]
                current["attempt_count"] = max(1, int(current.get("attempt_count") or 0))
                current["resume_dispatches"] = int(current.get("resume_dispatches") or 0) + 1
                current["last_dispatch_at"] = v3.core.utc_now()
                current["status"] = "running"
                current["next_retry_at"] = None
                current["source_id"] = item.get("source_id")
                current["artifact_id"] = item.get("artifact_id")
                current["provider_id"] = item.get("task_id")
                return
        if stage == "article":
            current = state["article"]
            last_error = current.get("last_error") or {}
            last_code = str(last_error.get("code") or "")
            last_session = current.get("last_jules_session_id")
            # If the previous worker run timed out or completed without PR while preserving
            # an active session, resuming that session is session recovery, not a new semantic generation attempt.
            if last_session and last_code in {"JULES_TIMEOUT_SESSION_ACTIVE", "COMPLETED_WITHOUT_PR"}:
                v3.core.GitHubClient.dispatch(self.github, workflow, inputs)
                current["attempt_count"] = max(1, int(current.get("attempt_count") or 0))
                current["resume_dispatches"] = int(current.get("resume_dispatches") or 0) + 1
                current["last_dispatch_at"] = v3.core.utc_now()
                current["status"] = "running"
                current["next_retry_at"] = None
                return
        return super()._dispatch_budgeted(state, stage, workflow, inputs)

    def _sync_stage_views(self, state, action):
        image_was_deferred = (state.get("image") or {}).get("status") == "deferred"
        super()._sync_stage_views(state, action)
        if image_was_deferred and state.get("status") == "complete":
            state["image"]["status"] = "deferred"


def main() -> int:
    v3.core.STATE_SCHEMA_VERSION = v3.STATE_SCHEMA_VERSION
    v3.core.GitHubClient = v3.V3GitHubClient
    v3.core.Controller = BestEffortController
    v3.entry._trigger_stage = v3.v3_trigger_stage
    v3.entry.adopt_latest_dispatched_children = v3.v3_adopt_latest
    return v3.entry.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (v3.core.ControllerError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"KESHER_CONTROLLER_BEST_EFFORT_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

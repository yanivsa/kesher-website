#!/usr/bin/env python3
"""Production Kesher V5 runtime with fail-closed article and media-quality preflights."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import re
import sys
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

if __package__:
    from . import article_claim_quality as quality
    from . import kesher_article_contract as article_contract
    from . import kesher_content_controller_v5 as v5
    from . import kesher_content_controller_v5_runtime as runtime
    from . import kesher_idea_queue as idea_queue
else:
    import article_claim_quality as quality
    import kesher_article_contract as article_contract
    import kesher_content_controller_v5 as v5
    import kesher_content_controller_v5_runtime as runtime
    import kesher_idea_queue as idea_queue


_ORIGINAL_PUBLIC_SITE_GET = v5.core.PublicSiteClient.get
_SOURCE_BINDING_EXHAUSTION_RECOVERY_MARKER = "source_binding_exhaustion_recovery_applied"
_REMOTION_REBUILD_EXHAUSTION_RECOVERY_MARKER = "remotion_rebuild_exhaustion_recovery_applied"


def _unicode_safe_public_site_get(self, url: str):
    """Percent-encode non-ASCII URL components before urllib builds the request."""
    parts = urllib.parse.urlsplit(url)
    safe_url = urllib.parse.urlunsplit((
        parts.scheme,
        parts.netloc,
        urllib.parse.quote(parts.path, safe="/%:@"),
        urllib.parse.quote(parts.query, safe="=&%:@/?+"),
        urllib.parse.quote(parts.fragment, safe="%:@/?+"),
    ))
    return _ORIGINAL_PUBLIC_SITE_GET(self, safe_url)


def _current_cycle_video_matching(video_state, requested_slug):
    """Keep current-cycle media selection on the requested article only.

    Prior-cycle media recovery is owned explicitly by RuntimeV5Controller's
    backlog preflight. Reusing the legacy queue-aware matcher here can bind
    today's article to an unrelated historical provider item.
    """
    return v5.v3.entry._base_matching(video_state, requested_slug)


ARTICLE_AUTO_MERGE_WORKFLOW = runtime.ARTICLE_AUTO_MERGE_WORKFLOW
DISPATCH_VISIBILITY_LAG_SECONDS = 90
VALID_CHILD_CONCLUSIONS: frozenset[str] = frozenset({
    "success",
    "failure",
    "cancelled",
    "skipped",
    "timed_out",
    "neutral",
    "action_required",
    "stale",
})


class _DuplicateDispatchSuppressed(Exception):
    def __init__(self, workflow: str, reason: str) -> None:
        super().__init__(reason)
        self.workflow = workflow
        self.reason = reason


class StabilizedRuntimeV5Controller(runtime.RuntimeV5Controller):
    """Prevent advancement/completion unless article and canonical media evidence are durable."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._in_memory_verified_articles: set[str] = set()

    @staticmethod
    def _run_now_active(state: dict | None) -> bool:
        active = (state or {}).get("active_idea") if isinstance(state, dict) else None
        return bool(isinstance(active, dict) and active.get("run_now") is True and str(active.get("status") or "") != "complete")

    @staticmethod
    def _active_idea_slot(state: dict | None) -> str:
        active = (state or {}).get("active_idea") if isinstance(state, dict) else None
        if not isinstance(active, dict) or str(active.get("status") or "") == "complete":
            return ""
        value = str(active.get("publication_slot") or "").strip()
        try:
            date.fromisoformat(value)
        except ValueError:
            return ""
        return value

    @classmethod
    def _run_now_slot(cls, state: dict | None) -> str:
        active = (state or {}).get("active_idea") if isinstance(state, dict) else None
        if not isinstance(active, dict) or active.get("run_now") is not True:
            return ""
        return cls._active_idea_slot(state)

    def _first_free_publication_slot(self, posts: list[dict]) -> str:
        """Assign the authoritative publication slot for a run_now cycle.

        For run_now, the publication date must be the current business calendar date
        in Israel (self.now.date()). It must never bump forward into future dates
        just because existing posts or archived cycles share today's date, because
        that would violate future-date validation (updatedAt > today in Asia/Jerusalem).
        """
        return self.now.date().isoformat()

    def _reset_for_run_now(self, state: dict, publication_slot: str) -> None:
        active = state.get("active_idea")
        if not isinstance(active, dict):
            raise v5.core.ControllerError("IDEA_RUN_NOW_ACTIVE_MISSING")
        archive = state.setdefault("owner_cycle_archive", [])
        archive.append({
            "cycle": state.get("cycle"),
            "status": state.get("status"),
            "article": copy.deepcopy(state.get("article") or {}),
            "long_video": copy.deepcopy(state.get("long_video") or {}),
            "short": copy.deepcopy(state.get("short") or {}),
            "archived_at": v5.core.utc_now(),
            "reason": "owner_run_now_cycle_started",
        })
        state["owner_cycle_archive"] = archive[-20:]
        active.update({"status": "claimed", "publication_slot": publication_slot, "claimed_at": v5.core.utc_now()})
        state["cycle"] = publication_slot
        stage = v5.v3._stage_template
        state["article"] = stage()
        state["article"].update({"attempts": 0, "deploy_attempts": 0})
        state["image"] = stage()
        state["long_video"] = stage()
        state["short"] = stage()
        state.pop("video", None)
        state["status"] = "article_needed"
        state["last_error"] = None
        state["pending_dispatches"] = {}
        state["processed_child_notifications"] = []
        state.setdefault("history", []).append({
            "at": v5.core.utc_now(),
            "from": "complete",
            "to": "article_needed",
            "reason": "owner_run_now_cycle_started",
            "details": {"idea_id": active.get("idea_id"), "publication_slot": publication_slot},
        })
        state["history"] = state["history"][-100:]

    def _begin_run_now_cycle(self, state: dict) -> bool:
        if self._run_now_active(state):
            return True
        if str(state.get("status") or "") != "complete":
            return False
        queue = state.get("idea_queue") if isinstance(state.get("idea_queue"), list) else []
        idx = next((i for i, row in enumerate(queue) if isinstance(row, dict) and row.get("run_now") is True), None)
        if idx is None:
            return False
        row = copy.deepcopy(queue.pop(idx))
        state["idea_queue"] = queue
        state["active_idea"] = row
        posts = self.posts_on_main("main")
        if not isinstance(posts, list):
            raise v5.core.ControllerError("ARTICLE_SOURCE_INVALID")
        slot = self._first_free_publication_slot(posts)
        self._reset_for_run_now(state, slot)
        return True

    def _run_now_article_phase(self, state: dict):
        if not self._run_now_active(state):
            return None
        slot = self._run_now_slot(state)
        if not slot:
            raise v5.core.ControllerError("IDEA_RUN_NOW_SLOT_INVALID")
        posts = self.posts_on_main("main")
        targets = self._reconcile_existing_current_day_article(state, posts)
        if len(targets) > 1:
            v5.core.block(state, "article", "DUPLICATE_ARTICLE_DATE", f"{len(targets)} articles share owner publication slot {slot}")
            return v5.core.Action("blocked", "duplicate owner publication-slot articles")
        if targets:
            return None

        # A run-now request may legitimately span midnight, so an old slot by
        # itself is not stale. Defer only when that prior slot is now occupied
        # by another adoptable main article; attempting to normalize the old PR
        # would otherwise fail forever because the slot is no longer available.
        slot_date = date.fromisoformat(slot)
        occupied_slot_posts = [
            post
            for post in posts
            if isinstance(post, dict)
            and str(post.get("date") or "") == slot
            and v5.core.is_controller_adoptable_post(post)
        ]
        if slot_date < self.now.date() and occupied_slot_posts:
            prior_status = str(state.get("status") or "")
            active = state.get("active_idea")
            if isinstance(active, dict):
                deferred = copy.deepcopy(active)
                deferred.pop("publication_slot", None)
                deferred.pop("claimed_at", None)
                deferred["run_now"] = False
                deferred["status"] = "queued"
                deferred["deferred_reason"] = "RUN_NOW_SLOT_OCCUPIED_AFTER_ROLLOVER"
                deferred["deferred_at"] = v5.core.utc_now()
                queue = state.get("idea_queue") if isinstance(state.get("idea_queue"), list) else []
                idea_id = str(deferred.get("idea_id") or "")
                fingerprint = str(deferred.get("fingerprint") or "")
                if not any(
                    isinstance(row, dict)
                    and (
                        (idea_id and str(row.get("idea_id") or "") == idea_id)
                        or (fingerprint and str(row.get("fingerprint") or "") == fingerprint)
                    )
                    for row in queue
                ):
                    queue.append(deferred)
                state["idea_queue"] = queue
                state["active_idea"] = None
            state["status"] = "complete"
            state["last_error"] = None
            state.setdefault("history", []).append({
                "at": v5.core.utc_now(),
                "from": prior_status,
                "to": "complete",
                "reason": "run_now_slot_occupied_after_rollover",
                "details": {
                    "publication_slot": slot,
                    "occupied_slugs": [
                        str(post.get("slug") or post.get("id") or "")
                        for post in occupied_slot_posts
                    ],
                },
            })
            state["history"] = state["history"][-100:]
            return v5.core.Action(
                "defer_stale_run_now",
                "stale run-now slot occupied after rollover; idea returned to queue",
            )

        open_prs = self.github.open_article_prs(slot)
        if len(open_prs) > 1:
            v5.core.block(state, "article", "DUPLICATE_ARTICLE_PRS", f"{len(open_prs)} open article PRs share owner publication slot {slot}")
            return v5.core.Action("blocked", "duplicate owner article PRs")
        if len(open_prs) == 1:
            return self._handle_open_article_pr(state, open_prs[0])
        active_run = self.github.active_workflow_run(v5.core.ARTICLE_WORKFLOW)
        if active_run:
            state["article"]["run_id"] = active_run.get("id")
            v5.core.transition(state, "article_generating", "owner run-now article workflow already active", publication_slot=slot)
            return v5.core.Action("wait", "owner run-now article workflow active")
        reconciled = self._reconcile_completed_article_run(state)
        if reconciled is not None:
            return reconciled
        if not v5.core.retry_ready(state["article"], self.now):
            retry_at = state["article"].get("next_retry_at")
            v5.core.transition(state, "article_retry_wait", "owner run-now article retry backoff is active", retry_at=retry_at)
            return v5.core.Action("wait", f"article retry scheduled for {retry_at}")
        payload = idea_queue.article_dispatch_inputs(state, {"slot": slot})
        self.github.dispatch(v5.core.ARTICLE_WORKFLOW, payload)
        attempts = int(state["article"].get("attempts") or 0) + 1
        state["article"].update({
            "attempts": attempts,
            "attempt_count": attempts,
            "last_dispatch_at": v5.core.utc_now(),
            "next_retry_at": None,
            "status": "running",
        })
        v5.core.transition(state, "article_generating", "owner run-now article dispatched immediately", attempt=attempts, publication_slot=slot)
        return v5.core.Action("dispatch_article", "owner run-now idea started immediately", payload)

    def _scheduled_active_article_phase(self, state: dict):
        """Continue a claimed scheduled article on its original slot after midnight."""
        active = state.get("active_idea") if isinstance(state, dict) else None
        if (
            not isinstance(active, dict)
            or active.get("run_now") is True
            or str(active.get("status") or "") == "complete"
        ):
            return None
        slot = self._active_idea_slot(state)
        if not slot or slot == self.now.date().isoformat():
            return None

        posts = self.posts_on_main("main")
        targets = self._reconcile_existing_current_day_article(state, posts)
        if len(targets) > 1:
            v5.core.block(
                state,
                "article",
                "DUPLICATE_ARTICLE_DATE",
                f"{len(targets)} articles share claimed publication slot {slot}",
            )
            return v5.core.Action("blocked", "duplicate claimed publication-slot articles")
        if targets:
            return None

        open_prs = self.github.open_article_prs(slot)
        if len(open_prs) > 1:
            v5.core.block(
                state,
                "article",
                "DUPLICATE_ARTICLE_PRS",
                f"{len(open_prs)} open article PRs share claimed publication slot {slot}",
            )
            return v5.core.Action("blocked", "duplicate claimed article PRs")
        if len(open_prs) == 1:
            return self._handle_open_article_pr(state, open_prs[0])

        active_run = self.github.active_workflow_run(v5.core.ARTICLE_WORKFLOW)
        if active_run:
            state.setdefault("article", {})["run_id"] = active_run.get("id")
            v5.core.transition(
                state,
                "article_generating",
                "claimed scheduled article workflow remains active across rollover",
                publication_slot=slot,
            )
            return v5.core.Action("wait", "claimed scheduled article workflow active")

        reconciled = self._reconcile_completed_article_run(state)
        if reconciled is not None:
            return reconciled
        if not v5.core.retry_ready(state["article"], self.now):
            retry_at = state["article"].get("next_retry_at")
            v5.core.transition(
                state,
                "article_retry_wait",
                "claimed scheduled article retry backoff remains active across rollover",
                retry_at=retry_at,
            )
            return v5.core.Action("wait", f"article retry scheduled for {retry_at}")

        attempts = int(state.get("article", {}).get("attempts") or 0)
        if attempts <= 0:
            v5.core.block(
                state,
                "article",
                "ACTIVE_IDEA_ROLLOVER_EVIDENCE_MISSING",
                f"claimed idea for {slot} has no durable article attempt to recover",
            )
            return v5.core.Action("blocked", "claimed rollover article has no durable attempt evidence")

        payload = idea_queue.article_dispatch_inputs(state, {"slot": slot})
        self.github.dispatch(v5.core.ARTICLE_WORKFLOW, payload)
        attempts += 1
        state["article"].update({
            "attempts": attempts,
            "attempt_count": attempts,
            "last_dispatch_at": v5.core.utc_now(),
            "next_retry_at": None,
            "status": "running",
        })
        v5.core.transition(
            state,
            "article_generating",
            "claimed scheduled article retry dispatched on original publication slot",
            attempt=attempts,
            publication_slot=slot,
        )
        return v5.core.Action("dispatch_article", "continue claimed scheduled article after rollover", payload)

    def _safe_newest_video_state(self) -> dict:
        getter = getattr(self.github, "newest_video_state", None)
        if callable(getter):
            try:
                res = getter()
                if isinstance(res, dict):
                    return res
            except Exception:
                pass
        return {"version": 1, "items": []}

    def _safe_newest_short_state(self) -> dict:
        getter = getattr(self.github, "newest_short_state", None)
        if callable(getter):
            try:
                res = getter()
                if isinstance(res, dict):
                    return res
            except Exception:
                pass
        return {"version": 1, "items": []}

    def _selected_article(self, posts=None, state: dict | None = None):
        """Resolve one authoritative article without regressing to date-only selection."""
        if posts is None or isinstance(posts, dict):
            posts = self.posts_on_main("main")
        target_slug = os.environ.get("KESHER_TARGET_MEDIA_SLUG", "").strip()
        if target_slug:
            matches = [
                post for post in posts
                if isinstance(post, dict)
                and str(post.get("slug") or post.get("id") or "").strip() == target_slug
            ]
            if len(matches) != 1:
                raise v5.core.ControllerError(
                    f"TARGET_MEDIA_SOURCE_AMBIGUOUS: {target_slug} matched {len(matches)} articles"
                )
            return matches[0]

        active_state = state if isinstance(state, dict) else getattr(self, "_active_state_ref", None)
        if isinstance(active_state, dict):
            todays = self._reconcile_existing_current_day_article(active_state, posts)
        else:
            existing = self.github.load_controller_state()
            if isinstance(existing, dict):
                todays = self._reconcile_existing_current_day_article(existing, posts)
            else:
                todays = v5.core.today_articles(posts, self.now.date())
        if len(todays) <= 1:
            return todays[0] if todays else None

        # Multiple articles can legitimately share a publication date. In that
        # case the durable controller state is stronger evidence than date order.
        # Preserve the exact previously-adopted article identity when possible
        # and fail closed if the state cannot disambuate the candidates.
        existing = active_state if isinstance(active_state, dict) else self.github.load_controller_state()
        article_state = existing.get("article") if isinstance(existing, dict) else {}
        if not isinstance(article_state, dict):
            article_state = {}

        stored_slug = str(article_state.get("slug") or "").strip()
        stored_sha = str(article_state.get("quality_content_sha256") or "").strip()
        if stored_slug:
            slug_matches = [
                post for post in todays
                if str(post.get("slug") or post.get("id") or "").strip() == stored_slug
            ]
            if len(slug_matches) == 1:
                candidate = slug_matches[0]
                candidate_source = v5.article_source_identity(candidate)
                if not stored_sha or candidate_source["content_sha256"] == stored_sha:
                    return candidate

        raise v5.core.ControllerError(
            f"BACKLOG_ARTICLE_IDENTITY_AMBIGUOUS: {self.now.date().isoformat()}"
        )

    def _article_source(self, state: dict | None = None):
        posts = self.posts_on_main("main")
        if not isinstance(posts, list):
            raise v5.core.ControllerError("ARTICLE_SOURCE_INVALID")
        article = self._selected_article(posts, state=state)
        return v5.article_source_identity(article) if article is not None else None

    def _recover_stale_source_binding_exhaustion(self, state):
        """Reset one historical V5 attempt budget only when stale source binding is proven.

        Before the source-binding repair, the inherited provider-resume lookup could
        bind the current cycle to an unrelated FIFO NotebookLM item and consume the
        three-attempt budget. After the repair is deployed, that persisted exhaustion
        would otherwise remain terminal forever. Recover exactly once, and only when
        durable video state contains an unresolved item for the authoritative source
        while the controller's stored item/provider identifiers point elsewhere.
        """
        long_video = state.get("long_video") if isinstance(state.get("long_video"), dict) else {}
        last_error = state.get("last_error") if isinstance(state.get("last_error"), dict) else {}
        if (
            state.get("status") != "blocked"
            or long_video.get("status") != "exhausted"
            or str(last_error.get("code") or "") != "VIDEO_ATTEMPTS_EXHAUSTED"
            or long_video.get(_SOURCE_BINDING_EXHAUSTION_RECOVERY_MARKER)
        ):
            return state

        source = self._article_source()
        if source is None:
            return state
        snapshot = self._safe_newest_video_state()
        exact_verified = v5._verified_exact(snapshot, source)
        if exact_verified:
            verified_item = v5._newest(exact_verified)
            previous = {
                "attempt_count": long_video.get("attempt_count"),
                "item_id": long_video.get("item_id"),
                "provider_id": long_video.get("provider_id"),
                "artifact_id": long_video.get("artifact_id"),
                "source_id": long_video.get("source_id"),
                "watchdog": long_video.get("watchdog"),
            }
            long_video[_SOURCE_BINDING_EXHAUSTION_RECOVERY_MARKER] = True
            long_video["source_binding_recovery_previous"] = previous
            long_video["attempt_count"] = 0
            long_video["status"] = "complete"
            long_video["last_error"] = None
            long_video["next_retry_at"] = None
            long_video["run_id"] = None
            long_video["processed_run_id"] = None
            long_video["provider_id"] = verified_item.get("task_id")
            long_video["artifact_id"] = verified_item.get("artifact_id")
            long_video["source_id"] = verified_item.get("source_id")
            long_video["item_id"] = verified_item.get("id")
            long_video["youtube_id"] = verified_item.get("youtube_id")
            long_video["youtube_url"] = verified_item.get("youtube_url")
            long_video["verified"] = True
            long_video["last_dispatch_at"] = None
            long_video["last_run_conclusion"] = None
            long_video["resume_dispatches"] = 0
            long_video["failure_fingerprint"] = None
            long_video["same_failure_streak"] = 0
            long_video["failure_count_by_type"] = {}
            long_video.pop("watchdog", None)
            v5.v3.clear_stage_failure(long_video)

            state["status"] = "article_live"
            state["last_error"] = None
            state.setdefault("history", []).append({
                "at": v5.core.utc_now(),
                "from": "blocked",
                "to": "article_live",
                "reason": "verified_overview_exhaustion_recovery",
                "details": {
                    "slug": source["slug"],
                    "item_id": verified_item.get("id"),
                    "youtube_url": verified_item.get("youtube_url"),
                },
            })
            return state

        exact = [
            item for item in v5._exact_items(snapshot, source)
            if item.get("uploaded") is not True
        ]
        if len(exact) != 1:
            return state

        exact_item = exact[0]
        exact_ids = {str(exact_item.get("id") or "").strip()}
        exact_provider_ids = {str(exact_item.get("task_id") or "").strip()}
        exact_artifact_ids = {str(exact_item.get("artifact_id") or "").strip()}
        exact_source_ids = {str(exact_item.get("source_id") or "").strip()}
        exact_ids.discard("")
        exact_provider_ids.discard("")
        exact_artifact_ids.discard("")
        exact_source_ids.discard("")

        bindings = (
            ("item_id", exact_ids),
            ("provider_id", exact_provider_ids),
            ("artifact_id", exact_artifact_ids),
            ("source_id", exact_source_ids),
        )
        stale_fields = [
            field for field, valid in bindings
            if str(long_video.get(field) or "").strip()
            and str(long_video.get(field) or "").strip() not in valid
        ]
        if not stale_fields:
            return state

        previous = {
            "attempt_count": long_video.get("attempt_count"),
            "item_id": long_video.get("item_id"),
            "provider_id": long_video.get("provider_id"),
            "artifact_id": long_video.get("artifact_id"),
            "source_id": long_video.get("source_id"),
            "watchdog": long_video.get("watchdog"),
        }
        long_video[_SOURCE_BINDING_EXHAUSTION_RECOVERY_MARKER] = True
        long_video["source_binding_recovery_previous"] = previous
        long_video["attempt_count"] = 0
        long_video["status"] = "pending"
        long_video["last_error"] = None
        long_video["next_retry_at"] = None
        long_video["run_id"] = None
        long_video["processed_run_id"] = None
        long_video["provider_id"] = None
        long_video["artifact_id"] = None
        long_video["source_id"] = None
        long_video["item_id"] = None
        long_video["last_dispatch_at"] = None
        long_video["last_run_conclusion"] = None
        long_video["resume_dispatches"] = 0
        long_video["failure_fingerprint"] = None
        long_video["same_failure_streak"] = 0
        long_video["failure_count_by_type"] = {}
        long_video.pop("watchdog", None)

        state["status"] = "article_live"
        state["last_error"] = None
        state.setdefault("history", []).append({
            "at": v5.core.utc_now(),
            "from": "blocked",
            "to": "article_live",
            "reason": "source_binding_exhaustion_recovery",
            "details": {
                "slug": source["slug"],
                "content_sha256": source["content_sha256"],
                "exact_item_id": exact_item.get("id"),
                "stale_fields": stale_fields,
                "attempt_budget_reset": True,
            },
        })
        state["history"] = state["history"][-100:]
        state["updated_at"] = v5.core.utc_now()
        return state

    def _recover_exact_rejected_exhaustion(self, state):
        """Give one fresh budget to an exact rejected Overview that needs Remotion repair.

        A rejected exact item is not a provider-generation failure. Re-dispatching the
        normal full operation only reselects the same rejected artifact and burns the
        controller budget. Recover once when the exact item lacks a verified full-screen
        signature so the next dispatch can use the dedicated Remotion rebuild operation.
        """
        long_video = state.get("long_video") if isinstance(state.get("long_video"), dict) else {}
        last_error = state.get("last_error") if isinstance(state.get("last_error"), dict) else {}
        if (
            state.get("status") != "blocked"
            or long_video.get("status") != "exhausted"
            or str(last_error.get("code") or "") != "VIDEO_ATTEMPTS_EXHAUSTED"
            or long_video.get(_REMOTION_REBUILD_EXHAUSTION_RECOVERY_MARKER)
        ):
            return state

        source = self._article_source()
        if source is None:
            return state
        snapshot = self._safe_newest_video_state()
        exact_rejected = [
            item for item in v5._exact_items(snapshot, source)
            if item.get("uploaded") is not True
            and str(item.get("status") or "") == "rejected"
            and item.get("signature_fullscreen") is not True
        ]
        if len(exact_rejected) != 1:
            return state

        item = exact_rejected[0]
        previous = {
            "attempt_count": long_video.get("attempt_count"),
            "item_id": long_video.get("item_id"),
            "provider_id": long_video.get("provider_id"),
            "artifact_id": long_video.get("artifact_id"),
            "source_id": long_video.get("source_id"),
            "last_error": long_video.get("last_error"),
        }
        long_video[_REMOTION_REBUILD_EXHAUSTION_RECOVERY_MARKER] = True
        long_video["remotion_rebuild_recovery_previous"] = previous
        long_video["attempt_count"] = 0
        long_video["status"] = "pending"
        long_video["last_error"] = None
        long_video["next_retry_at"] = None
        long_video["run_id"] = None
        long_video["processed_run_id"] = None
        long_video["last_dispatch_at"] = None
        long_video["last_run_conclusion"] = None
        long_video["failure_fingerprint"] = None
        long_video["same_failure_streak"] = 0
        long_video["failure_count_by_type"] = {}
        long_video.pop("watchdog", None)
        long_video.update({
            "item_id": item.get("id"),
            "provider_id": item.get("task_id"),
            "artifact_id": item.get("artifact_id"),
            "source_id": item.get("source_id"),
        })

        state["status"] = "article_live"
        state["last_error"] = None
        state.setdefault("history", []).append({
            "at": v5.core.utc_now(),
            "from": "blocked",
            "to": "article_live",
            "reason": "exact_rejected_overview_remotion_recovery",
            "details": {
                "slug": source["slug"],
                "content_sha256": source["content_sha256"],
                "item_id": item.get("id"),
                "attempt_budget_reset": True,
            },
        })
        state["history"] = state["history"][-100:]
        state["updated_at"] = v5.core.utc_now()
        return state

    def _reconcile_existing_current_day_article(self, state: dict, posts=None):
        if posts is None:
            posts = self.posts_on_main("main")
        if not isinstance(posts, list):
            return []

        slot = self._active_idea_slot(state)
        target_day = date.fromisoformat(slot) if slot else self.now.date()
        expected_date = target_day.isoformat()

        article_state = state.setdefault("article", {})
        state_slug = str(article_state.get("slug") or "").strip()
        state_sha = str(article_state.get("quality_content_sha256") or "").strip()

        # Collect slugs from prior cycles to prevent false-positive adoption
        # of already-completed or archived articles on the same calendar date.
        archived_slugs: set[str] = set()
        for archived in state.get("owner_cycle_archive") or []:
            if isinstance(archived, dict):
                arch_art = archived.get("article")
                if isinstance(arch_art, dict):
                    s = str(arch_art.get("slug") or "").strip()
                    if s:
                        archived_slugs.add(s)
        for hist in state.get("idea_history") or []:
            if isinstance(hist, dict):
                outputs = hist.get("outputs") or {}
                art_slug = str(outputs.get("slug") or "").strip()
                if not art_slug and outputs.get("article_url"):
                    art_slug = str(outputs["article_url"]).rstrip("/").split("/")[-1].strip()
                if art_slug:
                    archived_slugs.add(art_slug)

        candidates = [
            post for post in posts
            if isinstance(post, dict)
            and str(post.get("date") or "").strip() == expected_date
            and v5.core.is_controller_adoptable_post(
                post,
                state_slug=state_slug,
                state_content_sha256=state_sha,
            )
        ]

        if state_slug:
            matching = [p for p in candidates if v5.core.canonical_slug(p) == state_slug]
            if state_sha:
                matching_sha = [p for p in matching if v5.core._post_source_sha256(p) == state_sha]
                if matching_sha:
                    matching = matching_sha
            if matching:
                candidates = matching

        if not state_slug and candidates:
            candidates = [p for p in candidates if v5.core.canonical_slug(p) not in archived_slugs]

        if len(candidates) == 1:
            original_now = self.now
            try:
                self.now = original_now.replace(year=target_day.year, month=target_day.month, day=target_day.day)
                return super()._reconcile_existing_current_day_article(state, candidates)
            finally:
                self.now = original_now

        return candidates

    @staticmethod
    def _rollover_shell_is_empty(state: dict) -> bool:
        article = state.get("article") if isinstance(state.get("article"), dict) else {}
        if (
            article.get("pr_number")
            or article.get("slug")
            or article.get("run_id")
            or int(article.get("attempts") or 0) > 0
            or int(article.get("attempt_count") or 0) > 0
            or int(article.get("deploy_attempts") or 0) > 0
        ):
            return False
        for name in ("image", "long_video", "short"):
            stage = state.get(name) if isinstance(state.get(name), dict) else {}
            if (
                stage.get("run_id")
                or stage.get("provider_id")
                or stage.get("item_id")
                or stage.get("youtube_id")
                or int(stage.get("attempt_count") or 0) > 0
            ):
                return False
        return not bool(state.get("pending_dispatches"))

    def _restore_incomplete_active_cycle_from_backlog(self, state: dict) -> dict:
        """Undo an old rollover only when an exact active slot has a single inert shell."""
        slot = self._active_idea_slot(state)
        current_cycle = str(state.get("cycle") or "").strip()
        if not slot or not current_cycle or slot == current_cycle:
            return state
        if not self._rollover_shell_is_empty(state):
            return state

        backlog = state.get("backlog") if isinstance(state.get("backlog"), list) else []
        matches = [row for row in backlog if isinstance(row, dict) and str(row.get("cycle") or "") == slot]
        if len(matches) != 1:
            return state
        row = matches[0]
        if str(row.get("status") or "") == "complete":
            return state
        if row.get("media"):
            return state
        article = row.get("article") if isinstance(row.get("article"), dict) else {}
        if not (article.get("pr_number") or int(article.get("attempts") or 0) > 0):
            return state
        if not isinstance(row.get("image"), dict) and (article.get("image_head_sha") or article.get("merge_candidate_sha")):
            return state

        def restored_stage(raw):
            value = copy.deepcopy(raw) if isinstance(raw, dict) else {}
            for key, default in v5.v3._stage_template().items():
                value.setdefault(key, copy.deepcopy(default))
            return value

        prior_cycle = current_cycle
        state["cycle"] = slot
        state["status"] = str(row.get("status") or "article_needed")
        state["article"] = restored_stage(article)
        state["article"].setdefault("attempts", int(article.get("attempt_count") or 0))
        state["article"].setdefault("deploy_attempts", 0)
        state["article"].setdefault("normalization_status", "pending")
        state["image"] = restored_stage(row.get("image"))
        state["long_video"] = restored_stage(row.get("long_video"))
        state["short"] = restored_stage(row.get("short"))
        state.pop("video", None)
        state["pending_dispatches"] = {}
        state["backlog"] = [entry for entry in backlog if entry is not row]

        terminal = row.get("terminal_state") if isinstance(row.get("terminal_state"), dict) else {}
        if article.get("status") == "exhausted" or terminal.get("article_exhausted") is True:
            pr_number = int(article.get("pr_number") or 0)
            dispatches = int(article.get("merge_dispatch_count") or 0)
            message = (
                f"PR #{pr_number} exceeded maximum auto-merge dispatch budget ({dispatches} dispatches)"
                if pr_number > 0 and dispatches > 0
                else "article cycle has durable terminal attempt exhaustion"
            )
            state["last_error"] = {
                "stage": "article",
                "code": "ARTICLE_ATTEMPTS_EXHAUSTED",
                "message": message,
                "at": v5.core.utc_now(),
            }
            state["article"]["status"] = "exhausted"
            state["status"] = "blocked"
        else:
            state["last_error"] = None

        state.setdefault("history", []).append({
            "at": v5.core.utc_now(),
            "from": prior_cycle,
            "to": slot,
            "reason": "incomplete_active_cycle_restored_from_backlog",
            "details": {
                "idea_id": str((state.get("active_idea") or {}).get("idea_id") or ""),
                "publication_slot": slot,
                "pr_number": state["article"].get("pr_number"),
            },
        })
        state["history"] = state["history"][-100:]
        state["updated_at"] = v5.core.utc_now()
        return state

    def state(self):
        previous = self.github.load_controller_state() if getattr(self, "github", None) is not None else None
        preserve_active_cycle = bool(
            isinstance(previous, dict)
            and previous.get("schema_version") == v5.STATE_SCHEMA_VERSION
            and self._active_idea_slot(previous)
        )
        if preserve_active_cycle:
            state = copy.deepcopy(previous)
            for stage_name in ("article", "image", "long_video", "short"):
                current = state.setdefault(stage_name, {})
                for key, value in v5.v3._stage_template().items():
                    current.setdefault(key, copy.deepcopy(value))
            state.pop("video", None)
        else:
            state = super().state()
        idea_queue.carry_forward(state, previous)
        state = self._restore_incomplete_active_cycle_from_backlog(state)
        if isinstance(state, dict) and isinstance(state.get("article"), dict):
            state["article"].pop("_tick_live_verified", None)
        try:
            self._reconcile_existing_current_day_article(state)
        except v5.core.ControllerError:
            pass
        state = self._recover_stale_source_binding_exhaustion(state)
        state = self._recover_exact_rejected_exhaustion(state)
        self._active_state_ref = state
        self._correlate_child_notification_fields(state)
        return state

    def _recover_exhausted_article_after_late_head_change(self, state):
        """Resume the exact open PR when Jules mutates it after merge budget exhaustion.

        Recovery is deliberately fail-closed: only an article-stage
        ARTICLE_ATTEMPTS_EXHAUSTED block with the same stored PR number and a
        different live PR head may reopen. The previous auto-merge intent is
        invalid for the new head and is discarded before the PR re-enters the
        trusted normalize -> image -> merge gates.
        """
        if not isinstance(state, dict) or str(state.get("status") or "") != "blocked":
            return None
        last_error = state.get("last_error") if isinstance(state.get("last_error"), dict) else {}
        article = state.get("article") if isinstance(state.get("article"), dict) else {}
        if (
            str(last_error.get("stage") or "") != "article"
            or str(last_error.get("code") or "") != "ARTICLE_ATTEMPTS_EXHAUSTED"
            or str(article.get("status") or "") != "exhausted"
        ):
            return None

        try:
            pr_number = int(article.get("pr_number") or 0)
        except (TypeError, ValueError):
            return None
        observed_head = str(article.get("current_pr_head_sha") or "").strip().lower()
        if pr_number <= 0 or not observed_head:
            return None

        api = getattr(self.github, "api", "") or f"https://api.github.com/repos/{getattr(self.github, 'repo', 'yanivsa/kesher-website')}"
        try:
            pr = self.github.request(
                "GET",
                f"{api}/pulls/{pr_number}",
                allow_404=True,
            )
        except Exception:
            return None
        if not isinstance(pr, dict) or not pr:
            return None
        try:
            actual_number = int(pr.get("number") or 0)
        except (TypeError, ValueError):
            return None
        live_head = str((pr.get("head") or {}).get("sha") or "").strip().lower()
        if (
            actual_number != pr_number
            or str(pr.get("state") or "").lower() != "open"
            or not live_head
            or live_head == observed_head
        ):
            return None

        pending = state.get("pending_dispatches")
        if isinstance(pending, dict):
            pending.pop(ARTICLE_AUTO_MERGE_WORKFLOW, None)
        article["merge_dispatch_count"] = 0
        article["merge_dispatch_at"] = None
        article["status"] = "running"
        article["last_error"] = None
        state["status"] = "article_pr_open"
        state["last_error"] = None
        state.setdefault("history", []).append({
            "at": v5.core.utc_now(),
            "from": "blocked",
            "to": "article_pr_open",
            "reason": "late_article_head_after_merge_exhaustion_recovery",
            "details": {
                "pr_number": pr_number,
                "previous_head_sha": observed_head,
                "current_head_sha": live_head,
            },
        })
        state["history"] = state["history"][-100:]
        return self._handle_open_article_pr(state, pr)

    def _quality_preflight(self, state):
        posts = self.posts_on_main("main")
        if not isinstance(posts, list):
            raise v5.core.ControllerError("ARTICLE_SOURCE_INVALID")
        article = self._selected_article(posts, state=state)
        if article is None:
            return None

        source = v5.article_source_identity(article)
        violations = quality.full_article_violations(article)
        state["article"].update({
            "quality_status": "failed" if violations else "passed",
            "quality_content_sha256": source["content_sha256"],
            "quality_checked_at": v5.core.utc_now(),
            "quality_violations": violations,
        })
        if not violations:
            return None

        message = " | ".join(violations[:3])
        v5.core.block(
            state,
            "article",
            quality.ERROR_CODE,
            f"article quality gate failed for {source['slug']}@{source['content_sha256'][:12]}: {message}",
        )
        self.github.save_controller_state(state)
        return v5.core.Action("blocked", "article content quality failed before deploy/media")

    def _dispatch_exact_rejected_rebuild(self, state):
        """Preempt legacy V5 rejection handling and rebuild the exact item with Remotion."""
        source = self._article_source(state)
        if source is None:
            return None
        snapshot = self._safe_newest_video_state()
        exact_rejected = [
            item for item in v5._exact_items(snapshot, source)
            if item.get("uploaded") is not True
            and str(item.get("status") or "") == "rejected"
            and item.get("signature_fullscreen") is not True
        ]
        if len(exact_rejected) > 1:
            v5.core.block(
                state,
                "long_video",
                "DUPLICATE_REJECTED_LONG_VIDEO_ITEMS",
                f"{len(exact_rejected)} rejected exact Overview items exist for {source['slug']}",
            )
            self.github.save_controller_state(state)
            return state, v5.core.Action("blocked", "duplicate rejected long-video items")
        if not exact_rejected:
            return None

        item = exact_rejected[0]
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            v5.core.block(state, "long_video", "REJECTED_LONG_VIDEO_ITEM_ID_MISSING", "rejected exact Overview has no item id")
            self.github.save_controller_state(state)
            return state, v5.core.Action("blocked", "rejected long-video item id missing")

        active = self.github.active_workflow_run(v5.LONG_VIDEO_WORKFLOW, production_only=True)
        if active:
            current = state["long_video"]
            current["run_id"] = active.get("id")
            current["status"] = "running"
            v5.core.transition(state, "long_video_running", "exact rejected Overview rebuild workflow already active", item_id=item_id)
            self.github.save_controller_state(state)
            return state, v5.core.Action("wait", "long-video rebuild workflow active")

        current = state["long_video"]
        count = int(current.get("attempt_count") or 0)
        if count >= v5.v3.MAX_STAGE_ATTEMPTS:
            return None

        rebuild_inputs = {
            "operation": "rebuild",
            "rebuild_item_id": item_id,
            "target_slug": source["slug"],
            "target_content_sha256": source["content_sha256"],
            "target_item_id": item_id,
        }
        v5.core.GitHubClient.dispatch(self.github, v5.LONG_VIDEO_WORKFLOW, rebuild_inputs)
        current["attempt_count"] = count + 1
        current["remotion_rebuild_dispatches"] = int(current.get("remotion_rebuild_dispatches") or 0) + 1
        current["last_dispatch_at"] = v5.core.utc_now()
        current["status"] = "running"
        current["next_retry_at"] = None
        current["item_id"] = item.get("id")
        current["source_id"] = item.get("source_id")
        current["artifact_id"] = item.get("artifact_id")
        current["provider_id"] = item.get("task_id")
        v5.core.transition(
            state,
            "long_video_running",
            "exact rejected Overview dispatched to Remotion rebuild",
            item_id=item_id,
        )
        self.github.save_controller_state(state)
        return state, v5.core.Action("dispatch_long_video", "rebuild exact rejected Overview", rebuild_inputs)

    def _dispatch_budgeted(self, state, stage, workflow, inputs):
        """Bind every long-video action to the authoritative source identity and recovery mode."""
        bound_inputs = dict(inputs or {})
        if stage != "video" or workflow != v5.LONG_VIDEO_WORKFLOW:
            return super()._dispatch_budgeted(state, stage, workflow, bound_inputs)

        try:
            source = self._article_source(state)
        except TypeError:
            source = self._article_source()
        if source is None:
            raise v5.core.ControllerError("LONG_VIDEO_SOURCE_IDENTITY_UNAVAILABLE")
        operation = str(bound_inputs.get("operation") or "full").strip().lower()
        bound_inputs["operation"] = operation
        target_slug = str(bound_inputs.get("target_slug") or "").strip()
        if target_slug and target_slug != source["slug"]:
            raise v5.core.ControllerError("LONG_VIDEO_SOURCE_IDENTITY_MISMATCH")
        bound_inputs["target_slug"] = source["slug"]

        snapshot = self._safe_newest_video_state()
        exact_existing = [item for item in v5._exact_items(snapshot, source)
                          if item.get('uploaded') is not True
                          and item.get('status') in (v5.core.ACTIVE_VIDEO_STATUSES | {'rejected'})]
        exact_uploaded_unverified = [
            item for item in v5._exact_items(snapshot, source)
            if bool(str(item.get("youtube_id") or "").strip())
            and not v5.core.verified_youtube_item(item, source["slug"])
        ]
        requested_id = str(bound_inputs.get('target_item_id') or '')
        if requested_id:
            exact_existing = [item for item in exact_existing if item.get('id') == requested_id]
            exact_uploaded_unverified = [
                item for item in exact_uploaded_unverified if item.get("id") == requested_id
            ]
            if len(exact_existing) != 1 and not (operation == "upload" and len(exact_uploaded_unverified) == 1):
                raise v5.core.ControllerError('LONG_VIDEO_EXACT_ITEM_NOT_UNIQUE')
        elif len(exact_existing) > 1:
            raise v5.core.ControllerError('LONG_VIDEO_EXACT_ITEM_ID_REQUIRED')
        bound_inputs['target_content_sha256'] = source['content_sha256']
        if operation == "upload" and exact_uploaded_unverified:
            reverify_item = v5._newest(exact_uploaded_unverified) or exact_uploaded_unverified[-1]
            reverify_id = str(reverify_item.get("id") or "").strip()
            if not reverify_id:
                raise v5.core.ControllerError("LONG_VIDEO_ITEM_ID_MISSING")
            bound_inputs["operation"] = "upload"
            bound_inputs["target_item_id"] = reverify_id
            if isinstance(inputs, dict):
                inputs.update(bound_inputs)
            v5.v3.V3Controller._dispatch_budgeted(self, state, stage, workflow, bound_inputs)
            current = state["video"]
            current["item_id"] = reverify_id
            current["youtube_id"] = reverify_item.get("youtube_id")
            current["youtube_url"] = reverify_item.get("youtube_url")
            current["verified"] = False
            current["source_id"] = reverify_item.get("source_id")
            current["artifact_id"] = reverify_item.get("artifact_id")
            current["provider_id"] = reverify_item.get("task_id")
            return
        if exact_existing:
            bound_inputs['target_item_id'] = str(exact_existing[0].get('id') or '')
            if not bound_inputs['target_item_id']:
                raise v5.core.ControllerError('LONG_VIDEO_ITEM_ID_MISSING')
        elif operation == "rebuild":
            # Rebuild is identity-preserving. Never reinterpret a stale rebuild
            # request as fresh generation for today's article.
            raise v5.core.ControllerError('LONG_VIDEO_EXACT_ITEM_NOT_UNIQUE')
        elif operation == "upload":
            # A legacy cross-cycle matcher could choose an old approved item and
            # hand us an unbound upload request. With no exact current item,
            # convert that stale resume into bounded fresh generation for the
            # authoritative current source and clear only the stale media IDs.
            current = state.get("video") if isinstance(state.get("video"), dict) else {}
            previous = {
                field: current.get(field)
                for field in ("item_id", "provider_id", "artifact_id", "source_id")
                if current.get(field)
            }
            for field in ("item_id", "provider_id", "artifact_id", "source_id"):
                current[field] = None
            if previous:
                current["stale_source_binding_previous"] = previous
                state.setdefault("history", []).append({
                    "at": v5.core.utc_now(),
                    "from": state.get("status"),
                    "to": state.get("status"),
                    "reason": "current_cycle_stale_video_binding_cleared",
                    "details": {
                        "slug": source["slug"],
                        "content_sha256": source["content_sha256"],
                        "previous": previous,
                    },
                })
                state["history"] = state["history"][-100:]
            bound_inputs = {
                "operation": "full",
                "target_slug": source["slug"],
                "target_content_sha256": source["content_sha256"],
            }
            operation = "full"
        exact_rejected = [
            item for item in exact_existing
            if item.get("uploaded") is not True
            and str(item.get("status") or "") == "rejected"
            and item.get("signature_fullscreen") is not True
        ]
        if len(exact_rejected) > 1:
            raise v5.core.ControllerError("DUPLICATE_REJECTED_LONG_VIDEO_ITEMS")
        if exact_rejected:
            item = exact_rejected[0]
            rebuild_inputs = {
                "operation": "rebuild",
                "rebuild_item_id": str(item.get("id") or ""),
                "target_slug": source["slug"],
                "target_content_sha256": source["content_sha256"],
                "target_item_id": str(item.get("id") or ""),
            }
            if not rebuild_inputs["rebuild_item_id"]:
                raise v5.core.ControllerError("REJECTED_LONG_VIDEO_ITEM_ID_MISSING")
            v5.v3.V3Controller._dispatch_budgeted(self, state, stage, workflow, rebuild_inputs)
            current = state["video"]
            current["remotion_rebuild_dispatches"] = int(current.get("remotion_rebuild_dispatches") or 0) + 1
            current["item_id"] = item.get("id")
            current["source_id"] = item.get("source_id")
            current["artifact_id"] = item.get("artifact_id")
            current["provider_id"] = item.get("task_id")
            return

        exact_generating = [
            item for item in exact_existing
            if item.get("uploaded") is not True
            and str(item.get("status") or "") == "generating"
            and str(item.get("source_id") or "").strip()
            and str(item.get("task_id") or "").strip()
            and str(item.get("artifact_id") or "").strip()
            and str(item.get("task_id") or "").strip() == str(item.get("artifact_id") or "").strip()
        ]
        if len(exact_generating) > 1:
            raise v5.core.ControllerError("DUPLICATE_LONG_VIDEO_PROVIDER_TASKS")
        if exact_generating:
            item = exact_generating[0]
            v5.core.GitHubClient.dispatch(self.github, workflow, bound_inputs)
            current = state["video"]
            current["attempt_count"] = max(1, int(current.get("attempt_count") or 0))
            current["resume_dispatches"] = int(current.get("resume_dispatches") or 0) + 1
            current["last_dispatch_at"] = v5.core.utc_now()
            current["status"] = "running"
            current["next_retry_at"] = None
            current["item_id"] = item.get("id")
            current["source_id"] = item.get("source_id")
            current["artifact_id"] = item.get("artifact_id")
            current["provider_id"] = item.get("task_id")
            return

        # No exact provider task is currently generating. Use the bounded V3
        # dispatch budget rather than the legacy global FIFO provider-resume
        # lookup, which can bind a different article's provider identity.
        return v5.v3.V3Controller._dispatch_budgeted(self, state, stage, workflow, bound_inputs)

    def _dispatch_targeted_short_rebuild_from_full_state(self, state, source, long_item):
        """Recover one exact resolution-rejected Short from full durable state."""
        # Fresh public evidence must win over an older rejected durable snapshot.
        # Otherwise a controller tick that races a successful Short upload can
        # dispatch a redundant rebuild from stale heavyweight state.
        newest_short_state = getattr(self.github, "newest_short_state", None)
        if callable(newest_short_state):
            try:
                fresh_short_snapshot = newest_short_state()
            except v5.core.ControllerError:
                fresh_short_snapshot = {"items": []}
            if v5._newest(v5._verified_exact(fresh_short_snapshot, source)) is not None:
                return None

        reader = getattr(self.github, "newest_state_for_artifact", None)
        if not callable(reader):
            return None
        try:
            snapshot = reader(v5.SHORT_STATE_ARTIFACT)
        except v5.core.ControllerError:
            return None
        exact_rejected = [
            item for item in v5._exact_items(snapshot, source)
            if item.get("uploaded") is not True
            and str(item.get("status") or "") == "rejected"
            and "1080x1920" in str(((item.get("review_notes") or {}).get("technical") or ""))
        ]
        if len(exact_rejected) > 1:
            v5.core.block(
                state,
                "short",
                "DUPLICATE_RESOLUTION_REJECTED_SHORTS",
                f"{len(exact_rejected)} exact resolution-rejected Shorts exist for {source['slug']}",
            )
            if hasattr(self, "github") and self.github is not None and hasattr(self.github, "save_controller_state"):
                self.github.save_controller_state(state)
            return v5.core.Action("blocked", "duplicate resolution-rejected Shorts")
        if not exact_rejected:
            return None

        item = exact_rejected[0]
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            return None
        active = self.github.active_workflow_run(v5.SHORT_WORKFLOW, production_only=True)
        if active:
            state["short"]["status"] = "running"
            state["short"]["run_id"] = active.get("id")
            return v5.core.Action("wait", "exact Short rebuild workflow already active")

        count = int(state["short"].get("remotion_rebuild_count") or 0)
        if count >= v5.MAX_SHORT_REMOTION_REBUILDS:
            v5.core.block(
                state,
                "short",
                "SHORT_REMOTION_REBUILDS_EXHAUSTED",
                "exact Short Remotion rebuild attempts exhausted",
            )
            state["short"]["status"] = "exhausted"
            return v5.core.Action("blocked", "Short Remotion rebuild attempts exhausted")

        inputs = {"operation": "rebuild", "rebuild_item_id": item_id}
        v5.core.GitHubClient.dispatch(self.github, v5.SHORT_WORKFLOW, inputs)
        state["short"].update({
            "status": "running",
            "remotion_rebuild_count": count + 1,
            "last_dispatch_at": v5.core.utc_now(),
            "provider_id": item.get("task_id") or long_item.get("task_id"),
            "artifact_id": item.get("artifact_id") or long_item.get("artifact_id"),
            "source_id": item.get("source_id") or long_item.get("source_id"),
            "adopted_from_long_item_id": long_item.get("id"),
        })
        v5.core.transition(
            state,
            "short_running",
            "targeted recovery dispatched exact resolution-rejected Short to current Remotion contract",
            item_id=item_id,
        )
        self.github.save_controller_state(state)
        return v5.core.Action(
            "dispatch_short_rebuild",
            "rebuild exact resolution-rejected Short without new provider generation",
            inputs,
        )

    def _tick_targeted_media_recovery(self, state):
        """Advance only the explicitly requested existing article media chain."""
        posts = self.posts_on_main("main")
        if not isinstance(posts, list):
            raise v5.core.ControllerError("ARTICLE_SOURCE_INVALID")
        article = self._selected_article(posts)
        if article is None:
            raise v5.core.ControllerError("TARGET_MEDIA_SOURCE_UNAVAILABLE")

        source = v5.article_source_identity(article)
        title = str(article.get("title") or "").strip()
        url = f"{v5.core.SITE_URL}/blog/{source['slug']}"
        status, body = self.site.get(url)
        if status != 200 or not v5.core.article_is_public(body, title):
            v5.core.block(
                state,
                "article",
                "TARGET_MEDIA_ARTICLE_NOT_PUBLIC",
                f"targeted media article is not publicly verified: {source['slug']}",
            )
            self.github.save_controller_state(state)
            return state, v5.core.Action("blocked", "targeted media article is not public")

        target = state.setdefault("targeted_media_recovery", {})
        previous_identity = (
            str(target.get("slug") or "").strip(),
            str(target.get("content_sha256") or "").strip(),
        )
        current_identity = (source["slug"], source["content_sha256"])
        if any(previous_identity) and previous_identity != current_identity:
            # A targeted-recovery switch starts a new source identity. Never
            # carry public URLs/provider IDs from the prior target into the
            # new target, because that can create a false A+B+C completion.
            state["long_video"] = copy.deepcopy(v5.v3._stage_template())
            state["short"] = copy.deepcopy(v5.v3._stage_template())
            deliverables = state.get("deliverables")
            if isinstance(deliverables, dict):
                for key in (
                    "overview_youtube_url",
                    "short_youtube_url",
                    "overview_edit_verified",
                    "short_portrait_verified",
                    "short_signature_verified",
                    "short_origin_verified",
                ):
                    if key.endswith("_verified"):
                        deliverables[key] = False
                    else:
                        deliverables[key] = None
            target.clear()
            state.setdefault("history", []).append({
                "at": v5.core.utc_now(),
                "from": previous_identity[0] or None,
                "to": source["slug"],
                "reason": "targeted_media_source_identity_reset",
                "details": {
                    "previous_slug": previous_identity[0] or None,
                    "previous_content_sha256": previous_identity[1] or None,
                    "content_sha256": source["content_sha256"],
                },
            })
            state["history"] = state["history"][-100:]

        target.update({
            "slug": source["slug"],
            "content_sha256": source["content_sha256"],
            "article_url": url,
            "article_verified": True,
            "updated_at": v5.core.utc_now(),
        })

        snapshot = self._safe_newest_video_state()
        long_item = v5._newest(v5._verified_exact(snapshot, source))
        if long_item is None:
            long_item = self._verified_long_from_artifact_history(source)

        if long_item is None:
            # Fresh exact evidence wins over inherited controller fields. If no
            # exact Overview exists for this source, old public identifiers
            # must not survive merely because the target dictionary was already
            # switched on an earlier tick.
            stale_long_evidence = any(
                state["long_video"].get(key)
                for key in ("youtube_id", "youtube_url", "item_id", "provider_id", "artifact_id", "source_id")
            )
            if stale_long_evidence:
                preserved_run_id = state["long_video"].get("run_id")
                state["long_video"] = copy.deepcopy(v5.v3._stage_template())
                state["long_video"]["run_id"] = preserved_run_id

            newest_short_state = getattr(self.github, "newest_short_state", None)
            short_snapshot = newest_short_state() if callable(newest_short_state) else {"items": []}
            exact_short = v5._newest(v5._verified_exact(short_snapshot, source))
            if exact_short is not None:
                self._adopt_existing_short(state, source)
                target["short_status"] = "complete"
                target["short_youtube_url"] = state["short"].get("youtube_url")
            else:
                stale_short_evidence = any(
                    state["short"].get(key)
                    for key in ("youtube_id", "youtube_url", "item_id", "provider_id", "artifact_id", "source_id")
                )
                if stale_short_evidence:
                    state["short"] = copy.deepcopy(v5.v3._stage_template())
                target["short_status"] = state["short"].get("status") or "pending"
                target.pop("short_youtube_url", None)

            target["complete"] = False
            target.pop("completed_at", None)
            target.pop("long_youtube_url", None)
            target.pop("long_item_id", None)

            deliverables = state.get("deliverables")
            if isinstance(deliverables, dict):
                deliverables["overview_youtube_url"] = None
                deliverables["overview_edit_verified"] = False
                if exact_short is None:
                    deliverables["short_youtube_url"] = None
                    deliverables["short_portrait_verified"] = False
                    deliverables["short_signature_verified"] = False
                    deliverables["short_origin_verified"] = False

            active = self.github.active_workflow_run(v5.LONG_VIDEO_WORKFLOW, production_only=True)
            if active:
                state["long_video"]["run_id"] = active.get("id")
                state["long_video"]["status"] = "running"
                target["long_status"] = "running"
                self.github.save_controller_state(state)
                return state, v5.core.Action("wait", "targeted long-video workflow active")

            state["video"] = state["long_video"]
            try:
                self._dispatch_budgeted(
                    state,
                    "video",
                    v5.LONG_VIDEO_WORKFLOW,
                    {"operation": "full", "target_slug": source["slug"]},
                )
                state["long_video"] = state["video"]
            finally:
                state.pop("video", None)
            state["long_video"]["status"] = "running"
            target["long_status"] = "running"
            target["long_last_dispatch_at"] = v5.core.utc_now()
            self.github.save_controller_state(state)
            return state, v5.core.Action(
                "dispatch_long_video",
                "targeted media recovery dispatched exact Video Overview",
                {"operation": "full", "target_slug": source["slug"]},
            )

        state["long_video"].update({
            "item_id": long_item.get("id"),
            "status": "complete",
            "youtube_id": long_item.get("youtube_id"),
            "youtube_url": long_item.get("youtube_url"),
            "verified": True,
            "provider_id": long_item.get("task_id"),
            "artifact_id": long_item.get("artifact_id"),
            "source_id": long_item.get("source_id"),
        })
        target.update({
            "long_status": "complete",
            "long_youtube_url": long_item.get("youtube_url"),
            "long_item_id": long_item.get("id"),
        })

        rebuild_action = self._dispatch_targeted_short_rebuild_from_full_state(
            state, source, long_item
        )
        if rebuild_action is not None:
            target["short_status"] = state["short"].get("status") or "running"
            return state, rebuild_action

        action = self._tick_short(state, source, long_item)
        if action.kind == "complete":
            target["short_status"] = "complete"
            target["short_youtube_url"] = state["short"].get("youtube_url")
            target["complete"] = True
            target["completed_at"] = v5.core.utc_now()
        elif state["short"].get("status"):
            target["short_status"] = state["short"].get("status")
        self.github.save_controller_state(state)
        return state, action

    def _overview_evidence_preflight(self, state):
        """Copy exact public Overview edit evidence into durable controller state."""
        source = self._article_source(state)
        if source is None:
            return

        # Production is fail-closed: once an authoritative article exists, a
        # public URL alone is never sufficient to complete the Overview stage.
        state["long_video"]["overview_evidence_required"] = True

        snapshot = self._safe_newest_video_state()
        item = v5._newest(v5._verified_exact(snapshot, source))
        if item is None:
            item = self._verified_long_from_artifact_history(source)
        if item is None:
            return

        media = item.get("media") or {}
        state["long_video"].update({
            "item_id": item.get("id"),
            "youtube_id": item.get("youtube_id"),
            "youtube_url": item.get("youtube_url"),
            "verified": True,
            "technical_verified": item.get("technical_verified") is True,
            "visual_pipeline": item.get("visual_pipeline"),
            "codec": media.get("codec"),
            "width": media.get("width"),
            "height": media.get("height"),
            "duration": media.get("duration"),
            "content_duration_seconds": item.get("content_duration_seconds"),
            "signature_duration_seconds": item.get("signature_duration_seconds"),
            "signature_overlay": item.get("signature_overlay"),
            "signature_fullscreen": item.get("signature_fullscreen"),
            "signature_asset_sha256": item.get("signature_asset_sha256"),
            "provider_id": item.get("task_id"),
            "artifact_id": item.get("artifact_id"),
            "source_id": item.get("source_id"),
        })

    @staticmethod
    def _child_notification_env() -> dict[str, str]:
        return {
            "trigger": str(
                os.environ.get("KESHER_TRIGGER_EVENT")
                or os.environ.get("GITHUB_EVENT_NAME")
                or ""
            ).strip(),
            "workflow": str(os.environ.get("KESHER_CHILD_WORKFLOW") or "").strip(),
            "run_id": str(os.environ.get("KESHER_CHILD_RUN_ID") or "").strip(),
            "run_attempt": str(os.environ.get("KESHER_CHILD_RUN_ATTEMPT") or "").strip(),
            "conclusion": str(os.environ.get("KESHER_CHILD_CONCLUSION") or "").strip().lower(),
            "source_slug": str(os.environ.get("KESHER_CHILD_SOURCE_SLUG") or "").strip(),
            "source_sha": str(
                os.environ.get("KESHER_CHILD_SOURCE_SHA")
                or os.environ.get("KESHER_CHILD_SOURCE_CONTENT_SHA256")
                or ""
            ).strip(),
            "slot": str(os.environ.get("KESHER_CHILD_SLOT") or "").strip(),
        }

    @staticmethod
    def _workflow_stage_and_file(workflow_name: str) -> tuple[str, str, str] | None:
        if workflow_name == "Kesher Article Generation":
            return "article", "run_id", v5.core.ARTICLE_WORKFLOW
        if workflow_name == "Kesher Normalize Article PR":
            return "article", "normalization_run_id", "normalize-article-pr.yml"
        if workflow_name == "Kesher Trusted Article Image":
            return "image", "run_id", v5.v3.IMAGE_WORKFLOW
        if workflow_name == "Auto-merge Kesher article PRs":
            return "article", "merge_run_id", ARTICLE_AUTO_MERGE_WORKFLOW
        if workflow_name == "Deploy to Cloudflare Pages":
            return "article", "deploy_run_id", v5.core.DEPLOY_WORKFLOW
        if workflow_name in {"Kesher Daily NotebookLM Video Overview", "Kesher Daily Video Overview"}:
            return "long_video", "run_id", v5.LONG_VIDEO_WORKFLOW
        if workflow_name in {"Kesher Daily Article Short V4", "Kesher Article Short V4"}:
            return "short", "run_id", v5.SHORT_WORKFLOW
        return None

    def _validate_child_notification(self, state: dict) -> tuple[bool, str]:
        info = self._child_notification_env()
        workflow = info["workflow"]
        raw_id = info["run_id"]
        conclusion = info["conclusion"]

        if not workflow and not raw_id and not conclusion and not info["source_slug"] and not info["slot"] and not info["source_sha"]:
            return True, ""

        if not workflow or workflow not in v5.v3.entry.ADMITTED_CHILD_WORKFLOW_NAMES:
            return False, f"invalid or unadmitted child workflow: {workflow or 'missing'}"

        mapping = self._workflow_stage_and_file(workflow)
        if mapping is None:
            return False, f"unmapped child workflow: {workflow}"
        stage_name, run_field, workflow_file = mapping

        if not raw_id or not raw_id.isdigit() or int(raw_id) <= 0:
            return False, f"missing or invalid child run_id: {raw_id or 'missing'}"

        if not conclusion or conclusion not in VALID_CHILD_CONCLUSIONS:
            return False, f"missing or invalid child conclusion: {conclusion or 'missing'}"

        if info["slot"] and state.get("cycle"):
            allowed_slots = {str(state.get("cycle"))}
            run_now_slot = self._run_now_slot(state)
            if run_now_slot:
                allowed_slots.add(run_now_slot)
            if info["slot"] not in allowed_slots:
                return False, f"stale child completion slot ignored: {info['slot']}"

        parsed_id = int(raw_id)
        stage_dict = state.get(stage_name) if isinstance(state.get(stage_name), dict) else {}
        if stage_dict.get("processed_run_id") is not None and v5.v3.entry._same_id(stage_dict.get("processed_run_id"), parsed_id):
            return False, f"stale child run_id already processed: {parsed_id}"

        # Media workflows strictly require authoritative exact source identity
        if stage_name in {"long_video", "short"}:
            if not info["source_slug"]:
                return False, f"untrusted media notification: missing mandatory source_slug for {stage_name}"
            current_slug = str((state.get("article") or {}).get("slug") or "").strip()
            if not current_slug:
                src = self._article_source(state)
                if src and src.get("slug"):
                    current_slug = str(src.get("slug")).strip()
            backlog_sha = ""
            if current_slug and info["source_slug"] != current_slug:
                backlog_matches = [
                    row for row in (state.get("backlog") or [])
                    if isinstance(row, dict) and (str(row.get("slug") or "") == info["source_slug"] or str(row.get("exact_slug") or "") == info["source_slug"])
                ]
                if not backlog_matches:
                    return False, f"child notification source_slug mismatch: {info['source_slug']} != {current_slug}"
                b_row = backlog_matches[0]
                backlog_sha = str(
                    b_row.get("content_sha256")
                    or (b_row.get("article") or {}).get("quality_content_sha256")
                    or (b_row.get("article") or {}).get("content_sha256")
                    or ""
                ).strip()

            current_sha = backlog_sha
            if not current_sha:
                current_sha = str((state.get("article") or {}).get("quality_content_sha256") or "").strip()
            if not current_sha:
                current_sha = str((state.get("article") or {}).get("content_sha256") or "").strip()
            if not current_sha:
                src = self._article_source(state)
                if src and src.get("content_sha256"):
                    current_sha = str(src.get("content_sha256")).strip()

            if current_sha:
                if not info.get("source_sha"):
                    return False, f"untrusted media notification: missing mandatory source_sha for {stage_name}"
                if info["source_sha"] != current_sha:
                    return False, f"child notification source_sha mismatch: {info['source_sha']} != {current_sha}"
        elif info["source_slug"]:
            current_slug = str((state.get("article") or {}).get("slug") or "").strip()
            if not current_slug:
                src = self._article_source(state)
                if src and src.get("slug"):
                    current_slug = str(src.get("slug")).strip()
            if current_slug and info["source_slug"] != current_slug:
                backlog_matches = [
                    row for row in (state.get("backlog") or [])
                    if isinstance(row, dict) and str(row.get("slug") or "") == info["source_slug"]
                ]
                if not backlog_matches:
                    return False, f"child notification source_slug mismatch: {info['source_slug']} != {current_slug}"

        actual_run = super()._workflow_run(parsed_id)
        if not isinstance(actual_run, dict) or not actual_run:
            return False, f"child run {parsed_id} cannot be retrieved or verified from GitHub API"
        if str(actual_run.get("event") or "") == "pull_request":
            return False, f"pull_request child run ignored: {parsed_id}"
        actual_path = str(actual_run.get("path") or "").strip()
        normalized_path = actual_path.split("@", 1)[0].removeprefix(".github/workflows/")
        if normalized_path:
            if normalized_path != workflow_file:
                return False, (
                    f"child run workflow path mismatch: run {parsed_id} belongs to "
                    f"{actual_path}, not {workflow_file}"
                )
        else:
            run_name = str(actual_run.get("name") or "").strip()
            if run_name and run_name not in {workflow, workflow_file}:
                return False, f"child run workflow mismatch: run {parsed_id} belongs to {run_name}, not {workflow}"
        actual_attempt = actual_run.get("run_attempt")
        if info["run_attempt"] and actual_attempt and int(info["run_attempt"]) != int(actual_attempt):
            return False, f"child run_attempt mismatch: {info['run_attempt']} != {actual_attempt}"
        if actual_attempt and stage_dict.get("run_attempt") and int(actual_attempt) < int(stage_dict["run_attempt"]):
            return False, f"stale child run_attempt ignored: {actual_attempt} < {stage_dict['run_attempt']}"
        actual_conclusion = str(actual_run.get("conclusion") or "").strip().lower()
        if actual_conclusion and actual_conclusion != info["conclusion"]:
            return False, f"child run conclusion mismatch: notification={info['conclusion']} != actual={actual_conclusion}"

        return True, ""

    def _correlate_child_notification_fields(self, state: dict) -> None:
        valid, _ = self._validate_child_notification(state)
        if not valid:
            return
        info = self._child_notification_env()
        workflow = info["workflow"]
        if not workflow:
            return
        mapping = self._workflow_stage_and_file(workflow)
        if mapping is None:
            return
        stage_name, run_field, workflow_file = mapping
        parsed_id = int(info["run_id"])

        if workflow == "Kesher Article Generation":
            state.setdefault("article", {})["run_id"] = parsed_id
        elif workflow == "Kesher Normalize Article PR":
            state.setdefault("article", {})["normalization_run_id"] = parsed_id
        elif workflow == "Kesher Trusted Article Image":
            state.setdefault("image", {})["run_id"] = parsed_id
        elif workflow == "Auto-merge Kesher article PRs":
            state.setdefault("article", {})["merge_run_id"] = parsed_id
        elif workflow == "Deploy to Cloudflare Pages":
            article = state.setdefault("article", {})
            article["deploy_run_id"] = parsed_id
            if not article.get("next_deploy_retry_at"):
                article["next_deploy_retry_at"] = (
                    self.now.astimezone(v5.core.timezone.utc) + v5.core.timedelta(minutes=5)
                ).isoformat()
        elif workflow in {"Kesher Daily NotebookLM Video Overview", "Kesher Daily Video Overview"}:
            long_video = state.setdefault("long_video", {})
            long_video["run_id"] = parsed_id
            if not long_video.get("next_retry_at"):
                long_video["next_retry_at"] = (
                    self.now.astimezone(v5.core.timezone.utc) + v5.core.timedelta(minutes=5)
                ).isoformat()
        elif workflow in {"Kesher Daily Article Short V4", "Kesher Article Short V4"}:
            state.setdefault("short", {})["run_id"] = parsed_id

        if isinstance(state.get("pending_dispatches"), dict):
            state["pending_dispatches"].pop(workflow_file, None)

        state["last_child_notification"] = {
            "workflow": workflow,
            "run_id": parsed_id,
            "conclusion": info["conclusion"] or "success",
            "source_slug": info["source_slug"] or None,
            "slot": info["slot"] or state.get("cycle"),
        }

    def _safe_save_controller_state(self, state: dict) -> None:
        if isinstance(state, dict) and isinstance(state.get("article"), dict):
            state["article"].pop("_tick_live_verified", None)
        if hasattr(self, "github") and self.github is not None and hasattr(self.github, "save_controller_state"):
            if not getattr(self.github, "_controller_state_loaded", False):
                try:
                    self.github.load_controller_state()
                except Exception:
                    pass
                if not getattr(self.github, "_controller_state_loaded", False):
                    self.github._controller_state_loaded = True
                    self.github._controller_state_document = copy.deepcopy(state)
            self.github.save_controller_state(state)

    def _guarded_dispatch(self, state: dict, workflow: str, inputs: dict | None, raw_dispatch) -> None:
        """Enforce pre-dispatch intent ledger, visibility-lag grace, and Short dispatch gate."""
        active_state = getattr(self, "_active_state_ref", state)
        if workflow == v5.SHORT_WORKFLOW:
            op = (inputs or {}).get("operation")
            if op in {"derive", "full"}:
                short_state = active_state.get("short") if isinstance(active_state.get("short"), dict) else {}
                count = int(short_state.get("attempt_count") or 0)
                if count >= v5.v3.MAX_STAGE_ATTEMPTS:
                    raise v5.core.ControllerError(
                        f"SHORT_ATTEMPTS_EXHAUSTED: Short exhausted {v5.v3.MAX_STAGE_ATTEMPTS} fresh generation attempts"
                    )
            if op == "derive" or "derive_content_sha256" in (inputs or {}):
                slug = str((inputs or {}).get("derive_slug") or "").strip()
                sha = str((inputs or {}).get("derive_content_sha256") or "").strip()
                if not slug or len(sha) != 64 or not all(c in "0123456789abcdefABCDEF" for c in sha):
                    raise v5.core.ControllerError(
                        "SHORT_SOURCE_IDENTITY_MISSING: Short dispatch requires non-empty derive_slug and 64-hex derive_content_sha256"
                    )
                snapshot = self._safe_newest_video_state()
                exact_long = v5._newest(v5._verified_exact(snapshot, {"slug": slug, "content_sha256": sha}))
                if exact_long is None and hasattr(self, "_verified_long_from_artifact_history"):
                    exact_long = self._verified_long_from_artifact_history({"slug": slug, "content_sha256": sha})
                if exact_long is None or not v5.core.verified_youtube_item(exact_long, slug):
                    raise v5.core.ControllerError(
                        "SHORT_REQUIRES_VERIFIED_LONG_VIDEO: Short dispatch blocked because exact Long Video is not public and verified"
                    )
        elif workflow == v5.LONG_VIDEO_WORKFLOW:
            op = (inputs or {}).get("operation")
            target_item_id = str((inputs or {}).get("target_item_id") or "").strip()
            if op == "full" and not target_item_id:
                long_state = active_state.get("long_video") if isinstance(active_state.get("long_video"), dict) else {}
                count = int(long_state.get("attempt_count") or 0)
                if count >= v5.v3.MAX_STAGE_ATTEMPTS:
                    raise v5.core.ControllerError(
                        f"VIDEO_ATTEMPTS_EXHAUSTED: Long Video exhausted {v5.v3.MAX_STAGE_ATTEMPTS} fresh generation attempts"
                    )
        elif workflow == v5.core.ARTICLE_WORKFLOW:
            try:
                if not isinstance(active_state.get("active_idea"), dict) and active_state.get("idea_queue"):
                    idea_queue.claim_next(
                        active_state, str((inputs or {}).get("slot") or active_state.get("cycle") or "").strip(),
                        now_iso=v5.core.utc_now(),
                    )
                inputs = idea_queue.article_dispatch_inputs(active_state, inputs)
            except idea_queue.IdeaQueueError as exc:
                raise v5.core.ControllerError(str(exc)) from exc
            art_state = active_state.get("article") if isinstance(active_state.get("article"), dict) else {}
            count = int(art_state.get("attempts") or 0)
            if count >= v5.v3.MAX_STAGE_ATTEMPTS:
                raise v5.core.ControllerError(
                    f"ARTICLE_ATTEMPTS_EXHAUSTED: Article exhausted {v5.v3.MAX_STAGE_ATTEMPTS} fresh generation attempts"
                )
        elif workflow == v5.v3.IMAGE_WORKFLOW:
            img_state = active_state.get("image") if isinstance(active_state.get("image"), dict) else {}
            count = int(img_state.get("attempt_count") or 0)
            if count >= v5.v3.MAX_STAGE_ATTEMPTS and active_state.get("status") != "article_image_rebinding":
                raise v5.core.ControllerError(
                    f"IMAGE_ATTEMPTS_EXHAUSTED: Image exhausted {v5.v3.MAX_STAGE_ATTEMPTS} fresh generation attempts"
                )

        stage_field_map = {
            v5.core.ARTICLE_WORKFLOW: ("article", "run_id"),
            "normalize-article-pr.yml": ("article", "normalization_run_id"),
            v5.v3.IMAGE_WORKFLOW: ("image", "run_id"),
            ARTICLE_AUTO_MERGE_WORKFLOW: ("article", "merge_run_id"),
            v5.core.DEPLOY_WORKFLOW: ("article", "deploy_run_id"),
            v5.LONG_VIDEO_WORKFLOW: ("long_video", "run_id"),
            v5.SHORT_WORKFLOW: ("short", "run_id"),
        }
        mapping = stage_field_map.get(workflow)
        stage_name, run_field = mapping if mapping else (None, None)
        pending_map = active_state.setdefault("pending_dispatches", {})
        pending = pending_map.get(workflow)

        # Deploy is a singleton logical mutation for a cycle. workflow_dispatch does not
        # return a run id, so time alone can never authorize a second POST. A retry is
        # allowed only after one exact run for the recorded main SHA is observed completed
        # with a non-success conclusion. Ambiguous/missing evidence remains fail-closed.
        if (
            workflow == v5.core.DEPLOY_WORKFLOW
            and isinstance(pending, dict)
            and pending.get("cycle") == active_state.get("cycle")
            and pending.get("status") in {"intent", "uncertain", "dispatched", "active", "completed_success"}
            and (inputs or {}) == (pending.get("inputs") or {})
        ):
            dispatch_sha = str(pending.get("dispatch_head_sha") or "").strip()
            current_main_sha = ""
            if hasattr(self.github, "main_sha"):
                try:
                    current_main_sha = str(self.github.main_sha() or "").strip()
                except Exception:
                    current_main_sha = ""

            exact_runs: list[dict] = []
            if dispatch_sha and hasattr(self.github, "workflow_runs"):
                try:
                    intent_dt = v5.core.parse_timestamp(pending.get("intent_at"))
                    for run in (self.github.workflow_runs(workflow) or []):
                        if not isinstance(run, dict) or str(run.get("event") or "") != "workflow_dispatch":
                            continue
                        if str(run.get("head_sha") or "").strip() != dispatch_sha:
                            continue
                        head_branch = str(run.get("head_branch") or "").strip()
                        if head_branch and head_branch != "main":
                            continue
                        run_created = v5.core.parse_timestamp(run.get("created_at") or run.get("run_started_at"))
                        if intent_dt and run_created and run_created < (intent_dt - v5.core.timedelta(seconds=30)):
                            continue
                        exact_runs.append(run)
                except Exception:
                    exact_runs = []

            if len(exact_runs) == 1:
                exact_run = exact_runs[0]
                run_id = exact_run.get("id")
                if run_id:
                    pending["observed_active_run_id"] = run_id
                run_status = str(exact_run.get("status") or "")
                if run_status == "completed":
                    conclusion = str(exact_run.get("conclusion") or "").lower()
                    pending["conclusion"] = conclusion or "success"
                    pending["status"] = "completed_failed" if conclusion and conclusion != "success" else "completed_success"
                else:
                    pending["status"] = "active"

            if current_main_sha and dispatch_sha and current_main_sha != dispatch_sha:
                active_state.setdefault("deploy_history", []).append({
                    "workflow": workflow,
                    "superseded_sha": dispatch_sha,
                    "current_sha": current_main_sha,
                    "superseded_at": v5.core.utc_now(),
                    "superseded_status": pending.get("status"),
                    "superseded_run_id": pending.get("observed_active_run_id") or active_state.get("article", {}).get("deploy_run_id"),
                    "superseded_conclusion": pending.get("conclusion"),
                    "reason": f"deploy for SHA {dispatch_sha} superseded by newer main SHA {current_main_sha}",
                })
                pending_map.pop(workflow, None)
                self._safe_save_controller_state(active_state)
                pending = None

            if pending is not None and len(exact_runs) > 1:
                pending["matching_run_ids"] = [run.get("id") for run in exact_runs if run.get("id")]
                self._safe_save_controller_state(active_state)
                raise _DuplicateDispatchSuppressed(
                    workflow,
                    f"{workflow} has multiple exact runs for dispatch SHA {dispatch_sha}; refusing blind retry",
                )

            if pending is not None and len(exact_runs) == 1:
                exact_run = exact_runs[0]
                run_id = exact_run.get("id")
                if run_id:
                    active_state.setdefault("article", {})["deploy_run_id"] = run_id
                    pending["observed_active_run_id"] = run_id
                run_status = str(exact_run.get("status") or "")
                if run_status == "completed":
                    conclusion = str(exact_run.get("conclusion") or "").lower()
                    if conclusion and conclusion != "success":
                        pending_map.pop(workflow, None)
                        self._safe_save_controller_state(active_state)
                        pending = None
                    else:
                        pending["status"] = "completed_success"
                        pending["conclusion"] = conclusion or "success"
                        self._safe_save_controller_state(active_state)
                        raise _DuplicateDispatchSuppressed(
                            workflow,
                            f"{workflow} exact run {run_id} completed successfully; waiting for public deployment evidence",
                        )
                else:
                    pending["status"] = "active"
                    self._safe_save_controller_state(active_state)
                    raise _DuplicateDispatchSuppressed(
                        workflow,
                        f"{workflow} exact run {run_id} is {run_status or 'active'}; suppressing duplicate dispatch",
                    )

            if pending is not None:
                raise _DuplicateDispatchSuppressed(
                    workflow,
                    f"{workflow} already has a durable {pending.get('status')} intent for this cycle; suppressing blind duplicate POST",
                )

        if isinstance(pending, dict) and pending.get("cycle") == active_state.get("cycle"):
            if hasattr(self.github, "workflow_runs"):
                try:
                    recent_runs = self.github.workflow_runs(workflow)
                    intent_dt = v5.core.parse_timestamp(pending.get("intent_at"))
                    for run in (recent_runs or []):
                        if not isinstance(run, dict) or str(run.get("event") or "") != "workflow_dispatch":
                            continue
                        run_created = v5.core.parse_timestamp(run.get("created_at") or run.get("run_started_at"))
                        if intent_dt and run_created and run_created >= (intent_dt - v5.core.timedelta(seconds=30)):
                            if str(run.get("status") or "") != "completed":
                                if stage_name and run_field:
                                    active_state.setdefault(stage_name, {})[run_field] = run.get("id")
                                pending["observed_active_run_id"] = run.get("id")
                                pending["status"] = "active"
                                self._safe_save_controller_state(active_state)
                                raise _DuplicateDispatchSuppressed(
                                    workflow,
                                    f"{workflow} active child run {run.get('id')} reconciled; suppressing duplicate dispatch",
                                )
                            if pending.get("status") in {"intent", "uncertain"}:
                                if stage_name and run_field:
                                    active_state.setdefault(stage_name, {})[run_field] = run.get("id")
                                pending_map.pop(workflow, None)
                                self._safe_save_controller_state(active_state)
                                raise _DuplicateDispatchSuppressed(
                                    workflow,
                                    f"{workflow} uncertain dispatch reconciled to completed run {run.get('id')}",
                                )
                            pending_map.pop(workflow, None)
                            pending = None
                            break
                except (v5.core.ControllerError, _DuplicateDispatchSuppressed):
                    raise
                except Exception:
                    pass

        if isinstance(pending, dict) and pending.get("cycle") == active_state.get("cycle"):
            stage_dict = active_state.get(stage_name) if stage_name else {}
            if stage_dict and run_field:
                current_run_id = stage_dict.get(run_field)
                if current_run_id and current_run_id != pending.get("previous_run_id"):
                    run_info = super()._workflow_run(current_run_id)
                    if isinstance(run_info, dict) and str(run_info.get("status") or "") == "completed":
                        pending_map.pop(workflow, None)
                        pending = None
            if pending and pending.get("observed_active_run_id"):
                active_now = self.github.active_workflow_run(workflow, production_only=True)
                if not active_now:
                    pending_map.pop(workflow, None)
                    pending = None

        if isinstance(pending, dict) and pending.get("cycle") == active_state.get("cycle"):
            if pending.get("status") in {"intent", "uncertain"}:
                raise _DuplicateDispatchSuppressed(
                    workflow,
                    f"{workflow} dispatch outcome is {pending.get('status')}; suppressing duplicate POST until reconciled",
                )
            if pending.get("status") == "dispatched" and (inputs or {}) == (pending.get("inputs") or {}):
                intent_dt = v5.core.parse_timestamp(pending.get("dispatched_at") or pending.get("intent_at"))
                elapsed_str = f" {int((self.now.astimezone(v5.core.timezone.utc) - intent_dt).total_seconds())}s ago" if intent_dt else ""
                raise _DuplicateDispatchSuppressed(
                    workflow,
                    f"{workflow} already dispatched for this cycle{elapsed_str}; waiting for GitHub run visibility without duplicate POST",
                )
            if pending.get("status") == "active":
                raise _DuplicateDispatchSuppressed(
                    workflow,
                    f"{workflow} run {pending.get('observed_active_run_id')} is active; suppressing duplicate dispatch",
                )

        now_iso = self.now.astimezone(v5.core.timezone.utc).isoformat()
        stage_dict = active_state.get(stage_name) if stage_name else None
        dispatch_head_sha = ""
        if workflow == v5.core.DEPLOY_WORKFLOW and hasattr(self.github, "main_sha"):
            try:
                dispatch_head_sha = str(self.github.main_sha() or "").strip()
            except Exception:
                dispatch_head_sha = ""
        pending_entry = {
            "workflow": workflow,
            "cycle": active_state.get("cycle"),
            "inputs": copy.deepcopy(inputs or {}),
            "intent_at": now_iso,
            "status": "intent",
            "previous_run_id": stage_dict.get(run_field) if isinstance(stage_dict, dict) and run_field else None,
            "observed_active_run_id": None,
        }
        if workflow == v5.core.DEPLOY_WORKFLOW and dispatch_head_sha:
            pending_entry["dispatch_head_sha"] = dispatch_head_sha
        pending_map[workflow] = pending_entry
        self._safe_save_controller_state(active_state)

        try:
            raw_dispatch(workflow, inputs)
        except v5.core.ControllerError as exc:
            if str(exc).startswith("GITHUB_MUTATION_UNCERTAIN") or "outcome unknown" in str(exc):
                pending_entry["status"] = "uncertain"
                pending_entry["error"] = str(exc)
                self._safe_save_controller_state(active_state)
                raise _DuplicateDispatchSuppressed(
                    workflow,
                    f"{workflow} dispatch POST outcome uncertain; persisted intent without re-POSTing",
                ) from exc
            pending_map.pop(workflow, None)
            self._safe_save_controller_state(active_state)
            raise
        except Exception:
            pending_map.pop(workflow, None)
            self._safe_save_controller_state(active_state)
            raise

        pending_entry["status"] = "dispatched"
        pending_entry["dispatched_at"] = now_iso
        active_now = self.github.active_workflow_run(workflow, production_only=True)
        if isinstance(active_now, dict) and active_now.get("id"):
            pending_entry["observed_active_run_id"] = active_now.get("id")

    def _dispatch_auto_merge_v4(self, state):
        if self._child_notification_env()["workflow"] == "Auto-merge Kesher article PRs":
            return
        return super()._dispatch_auto_merge_v4(state)

    def _pr_repair_status(self, pr: dict[str, Any]) -> tuple[int, set[str]]:
        number = int(pr.get("number") or 0)
        api = getattr(self.github, "api", "")
        req = getattr(self.github, "request", None)
        if not number:
            raise v5.core.ControllerError("PR_REPAIR_HISTORY_UNREADABLE: missing or invalid PR number")
        if not api or not callable(req):
            return 0, set()

        repair_marker = re.compile(r"<!-- kesher-article-repair attempt=(\d+) head=([a-f0-9]{40}) -->")
        max_attempt = 0
        repaired_heads: set[str] = set()

        page = 1
        while True:
            try:
                comments = req("GET", f"{api}/issues/{number}/comments?per_page=100&page={page}", allow_404=False)
            except Exception as exc:
                raise v5.core.ControllerError(
                    f"PR_REPAIR_HISTORY_UNREADABLE: failed to fetch comments page {page} for PR #{number}: {exc}"
                ) from exc
            if not isinstance(comments, list):
                raise v5.core.ControllerError(
                    f"PR_REPAIR_HISTORY_UNREADABLE: comments page {page} for PR #{number} returned non-list"
                )
            for comment in comments:
                if not isinstance(comment, dict):
                    continue
                for match in repair_marker.finditer(str(comment.get("body") or "")):
                    max_attempt = max(max_attempt, int(match.group(1)))
                    repaired_heads.add(match.group(2).lower())
            if len(comments) < 100:
                break
            page += 1

        return max_attempt, repaired_heads

    def _is_repair_in_flight(self, pr: dict[str, Any], head_sha: str) -> bool:
        number = int(pr.get("number") or 0)
        api = getattr(self.github, "api", "")
        req = getattr(self.github, "request", None)
        if not number or not api or not callable(req):
            return False

        repair_marker = re.compile(rf"<!--\s*kesher-article-repair\s+attempt=\d+\s+head={re.escape(head_sha)}\s*-->", re.I)
        now = self.now if getattr(self, "now", None) else datetime.now(timezone.utc)
        timeout = timedelta(minutes=10)

        page = 1
        while True:
            try:
                comments = req("GET", f"{api}/issues/{number}/comments?per_page=100&page={page}", allow_404=False)
            except Exception:
                return True
            if not isinstance(comments, list):
                return True
            for comment in comments:
                if not isinstance(comment, dict):
                    continue
                if repair_marker.search(str(comment.get("body") or "")):
                    created_at_raw = comment.get("created_at")
                    if created_at_raw:
                        try:
                            created_at = datetime.fromisoformat(str(created_at_raw).replace("Z", "+00:00"))
                            if created_at.tzinfo is None:
                                created_at = created_at.replace(tzinfo=timezone.utc)
                            if (now - created_at) >= timeout:
                                return False
                        except Exception:
                            pass
                    return True
            if len(comments) < 100:
                break
            page += 1

        return False

    def _pr_content_structure_errors(self, pr: dict[str, Any]) -> list[str]:
        head_sha = str((pr.get("head") or {}).get("sha") or "")
        base_sha = str((pr.get("base") or {}).get("sha") or "main")
        try:
            head_posts = self.github.contents_json("src/data/posts.json", head_sha)
            base_posts = self.github.contents_json("src/data/posts.json", base_sha)
        except Exception as exc:
            raise v5.core.ControllerError(
                f"CONTENT_PREFLIGHT_CATALOG_UNREADABLE: failed to load src/data/posts.json for PR: {exc}"
            ) from exc
        if not isinstance(head_posts, list) or not isinstance(base_posts, list):
            raise v5.core.ControllerError(
                "CONTENT_PREFLIGHT_CATALOG_INVALID: head or base src/data/posts.json is not a list"
            )
        base_ids = {v5.core.canonical_slug(row) for row in base_posts if isinstance(row, dict)}
        new_posts = [row for row in head_posts if isinstance(row, dict) and v5.core.canonical_slug(row) not in base_ids]
        if len(new_posts) == 0:
            raise v5.core.ControllerError(
                f"CONTENT_PREFLIGHT_ZERO_NEW_POSTS: zero new article posts found in PR head compared to base"
            )
        if len(new_posts) > 1:
            raise v5.core.ControllerError(
                f"CONTENT_PREFLIGHT_MULTIPLE_NEW_POSTS: expected exactly 1 new post, found {len(new_posts)}"
            )
        post = new_posts[0]
        raw_content = str(post.get("content") or "")
        errors = []
        h3_count = len(re.findall(r"<h3(?:\s|>)", raw_content, re.I))
        if h3_count < 5:
            errors.append(f"New article must contain at least five H3 sections (found {h3_count})")
        words = len([w for w in re.split(r"\s+", raw_content.strip()) if w])
        if not (700 <= words <= 1100):
            errors.append(f"New article word count must be 700-1100 (found {words})")
        if post.get("video"):
            errors.append("New article may not contain a video field")
        errors.extend(quality.full_article_violations(post))
        return errors

    def _request_article_text_repair(self, pr: dict[str, Any], errors: list[str]) -> bool:
        """Request bounded same-PR text repair without entering the image/merge bridge."""
        key = os.environ.get("JULES_API_KEY", "").strip()
        if not key:
            raise RuntimeError("JULES_REPAIR_CREDENTIAL_MISSING")
        path = Path(__file__).resolve().parents[1] / ".github/scripts/article-pr-controller-v3.py"
        spec = importlib.util.spec_from_file_location("kesher_pre_image_repair", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("JULES_REPAIR_ADAPTER_UNAVAILABLE")
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        return adapter.send_jules_repair_v3(
            self.github.repo, pr, errors, None, self.github.token, key,
        )

    def _refund_deferred_auto_merge_success(self, state: dict, pr: dict) -> bool:
        """Refund one raw merge dispatch when an exact successful child left the PR open.

        A successful auto-merge workflow can legitimately defer publication while a
        trusted repair/check is still converging. That is not a failed content
        attempt. Refunds are exact-run idempotent and bounded so persistent no-op
        success cannot create an infinite publication loop.
        """
        info = self._child_notification_env()
        if str(info.get("workflow") or "") != "Auto-merge Kesher article PRs":
            return False
        if str(info.get("conclusion") or "") != "success":
            return False
        raw_run_id = str(info.get("run_id") or "").strip()
        if not raw_run_id.isdigit() or int(raw_run_id) <= 0:
            return False
        run_id = int(raw_run_id)

        article = state.get("article") if isinstance(state.get("article"), dict) else {}
        pr_number = int(pr.get("number") or 0)
        if pr_number <= 0 or int(article.get("pr_number") or 0) != pr_number:
            return False
        if str(pr.get("state") or "open") != "open":
            return False
        pr_head = str((pr.get("head") or {}).get("sha") or "").strip().lower()
        current_head = str(article.get("current_pr_head_sha") or "").strip().lower()
        if not pr_head or not current_head or pr_head != current_head:
            return False
        if int(article.get("last_refunded_auto_merge_run_id") or 0) == run_id:
            return False

        refund_count = int(article.get("deferred_auto_merge_refund_count") or 0)
        if refund_count >= 3:
            return False
        dispatch_count = int(article.get("merge_dispatch_count") or 0)
        if dispatch_count <= 0:
            return False

        article["merge_dispatch_count"] = dispatch_count - 1
        article["last_refunded_auto_merge_run_id"] = run_id
        article["deferred_auto_merge_refund_count"] = refund_count + 1
        history = state.setdefault("history", [])
        history.append({
            "at": v5.core.utc_now(),
            "from": str(state.get("status") or ""),
            "to": str(state.get("status") or ""),
            "reason": "successful_deferred_auto_merge_refunded",
            "details": {
                "run_id": run_id,
                "pr_number": pr_number,
                "head_sha": pr_head,
                "merge_dispatch_count": article["merge_dispatch_count"],
                "refund_count": article["deferred_auto_merge_refund_count"],
            },
        })
        state["history"] = history[-100:]
        return True

    def _handle_open_article_pr(self, state, pr):
        number = int(pr.get("number") or 0)
        state.setdefault("article", {})["pr_number"] = number
        state["article"]["pr_url"] = pr.get("html_url")
        head_sha = str((pr.get("head") or {}).get("sha") or "").strip().lower()
        previously_observed_head_sha = str(state["article"].get("current_pr_head_sha") or "").strip().lower()
        state["article"]["current_pr_head_sha"] = head_sha
        self._refund_deferred_auto_merge_success(state, pr)
        if previously_observed_head_sha and head_sha and previously_observed_head_sha != head_sha:
            pending = state.get("pending_dispatches")
            if isinstance(pending, dict):
                pending.pop(ARTICLE_AUTO_MERGE_WORKFLOW, None)
        if not state["article"].get("jules_head_sha"):
            state["article"]["jules_head_sha"] = head_sha

        normalized_head_sha = str(state["article"].get("normalized_head_sha") or "").strip().lower()
        evidence_head = str(
            article_contract.exact_field(str(pr.get("body") or ""), "Image Evidence Head") or ""
        ).strip().lower()
        if not normalized_head_sha and evidence_head:
            normalized_head_sha = evidence_head

        # The trusted image worker advances the normalized branch itself. Only
        # its full exact-head article/bytes/pixels proof can authorize adopting
        # that commit; a PR-body marker alone must never suppress normalization.
        if normalized_head_sha and normalized_head_sha != head_sha and evidence_head == head_sha:
            image_ready, image_evidence = self.github.article_pr_image_ready(pr)
            if image_ready:
                normalized_head_sha = head_sha
                state["article"].update({
                    "normalized_head_sha": head_sha,
                    "image_head_sha": head_sha,
                    "merge_candidate_sha": head_sha,
                    "normalization_drift_count": 0,
                    "merge_dispatch_count": 0,
                    "merge_dispatch_at": None,
                })
                state.setdefault("image", {}).update({
                    "status": "complete",
                    "provider_id": image_evidence.get("provider"),
                    "artifact_sha256": image_evidence.get("sha256"),
                    "source_id": image_evidence.get("source"),
                })

        if normalized_head_sha and normalized_head_sha != head_sha:
            is_auto_sync_merge = False
            curr = head_sha
            for _ in range(6):
                try:
                    api = getattr(self.github, "api", "") or f"https://api.github.com/repos/{getattr(self.github, 'repo', 'yanivsa/kesher-website')}"
                    commit_payload = self.github.request(
                        "GET",
                        f"{api}/commits/{curr}",
                    )
                    parents = [
                        str(p.get("sha") or "").strip().lower()
                        for p in (commit_payload.get("parents") or [])
                        if isinstance(p, dict)
                    ]
                    if len(parents) < 2:
                        break
                    curr = parents[0]
                    if curr == normalized_head_sha:
                        is_auto_sync_merge = True
                        break
                except Exception:
                    break

            if is_auto_sync_merge:
                state["article"]["normalization_drift_count"] = 0
                state["article"]["normalized_head_sha"] = head_sha
                state["article"]["image_head_sha"] = head_sha
                state["article"]["merge_candidate_sha"] = head_sha
                state["article"]["merge_dispatch_count"] = 0
                state["article"]["merge_dispatch_at"] = None
                img_provider = str(article_contract.exact_field(str(pr.get("body") or ""), "Image Provider") or "").strip()
                img_sha = str(article_contract.exact_field(str(pr.get("body") or ""), "Image SHA-256") or "").strip()
                img_source = str(article_contract.exact_field(str(pr.get("body") or ""), "Image Source URL") or "").strip()
                if img_provider and img_sha and img_source:
                    state.setdefault("image", {})
                    state["image"]["status"] = "complete"
                    state["image"]["provider_id"] = img_provider
                    state["image"]["artifact_sha256"] = img_sha
                    state["image"]["source_id"] = img_source
                if state.get("status") == "blocked":
                    state["status"] = "article_pr_open"
                    state["article"]["status"] = "running"
                    state.pop("last_error", None)
                    state["article"].pop("last_error", None)
            else:
                last_drift_head_sha = str(state["article"].get("last_normalization_drift_head_sha") or "").strip().lower()
                if not last_drift_head_sha:
                    # Older controller versions counted every poll of the same
                    # mismatched PR head as a fresh mutation. Start a distinct-
                    # head counter when migrating that durable state so a stable
                    # branch can self-heal without a manual state edit.
                    drift_count = 1
                elif last_drift_head_sha == head_sha:
                    drift_count = int(state["article"].get("normalization_drift_count") or 1)
                    blocked_for_drift = (
                        str(state.get("status") or "") == "blocked"
                        and str((state.get("last_error") or {}).get("code") or "") == "ARTICLE_JULES_UNSTABLE_MUTATION"
                        and previously_observed_head_sha == head_sha
                    )
                    if blocked_for_drift and drift_count > 3:
                        # A branch that stopped mutating after the fail-closed
                        # threshold gets one fresh normalization attempt. Any
                        # subsequent distinct head is counted again normally.
                        drift_count = 1
                        state.pop("last_error", None)
                        state["article"].pop("last_error", None)
                else:
                    drift_count = int(state["article"].get("normalization_drift_count") or 0) + 1
                state["article"]["normalization_drift_count"] = drift_count
                state["article"]["last_normalization_drift_head_sha"] = head_sha
                if drift_count > 3:
                    v5.core.block(
                        state,
                        "article",
                        "ARTICLE_JULES_UNSTABLE_MUTATION",
                        f"Article PR head mutated repeatedly ({drift_count} times) after trusted stages; branch quiescence failed",
                    )
                    state["article"]["status"] = "blocked"
                    return v5.core.Action("blocked", "Article PR head mutated repeatedly; branch quiescence failed")

                state["article"]["normalization_status"] = "pending"
                state["article"].pop("normalized_head_sha", None)
                state["article"].pop("image_head_sha", None)
                state["article"].pop("merge_candidate_sha", None)
                state["article"]["merge_dispatch_count"] = 0
                state["article"]["merge_dispatch_at"] = None
                if state.get("status") == "blocked" and state.get("article", {}).get("status") in {"blocked", "exhausted"}:
                    state["status"] = "article_pr_open"
                    state["article"]["status"] = "running"
                    state["article"].pop("last_error", None)
                    if previously_observed_head_sha == head_sha:
                        state.pop("last_error", None)
                if str((state.get("image") or {}).get("status") or "") in {"running", "complete"}:
                    state["image"]["status"] = "pending"
                    state["image"].pop("run_id", None)
        elif normalized_head_sha and normalized_head_sha == head_sha:
            img_provider = str(article_contract.exact_field(str(pr.get("body") or ""), "Image Provider") or "").strip()
            img_sha = str(article_contract.exact_field(str(pr.get("body") or ""), "Image SHA-256") or "").strip()
            img_source = str(article_contract.exact_field(str(pr.get("body") or ""), "Image Source URL") or "").strip()
            if img_provider and img_sha and img_source:
                state.setdefault("image", {})
                state["image"]["status"] = "complete"
                state["image"]["provider_id"] = img_provider
                state["image"]["artifact_sha256"] = img_sha
                state["image"]["source_id"] = img_source

        merge_candidate_sha = str(state["article"].get("merge_candidate_sha") or "").strip().lower()
        if merge_candidate_sha and merge_candidate_sha != head_sha:
            state["article"]["merge_dispatch_count"] = 0
            state["article"]["merge_dispatch_at"] = None
            if state.get("status") == "blocked" and state.get("article", {}).get("status") in {"blocked", "exhausted"}:
                state["status"] = "article_pr_open"
                state["article"]["status"] = "running"
                state["article"].pop("last_error", None)

        # 1. Cap auto-merge dispatches to budget (max 3 dispatches)
        merge_dispatches = int(state["article"].get("merge_dispatch_count") or 0)
        if merge_dispatches >= 3:
            v5.core.block(
                state,
                "article",
                "ARTICLE_ATTEMPTS_EXHAUSTED",
                f"PR #{number} exceeded maximum auto-merge dispatch budget ({merge_dispatches} dispatches)",
            )
            state["article"]["status"] = "exhausted"
            return v5.core.Action("blocked", f"auto-merge dispatch budget exhausted for PR #{number}")

        # 2. Check if autonomous repairs on this PR are exhausted
        try:
            max_attempt, repaired_heads = self._pr_repair_status(pr)
        except v5.core.ControllerError as exc:
            code = str(exc).split(":", 1)[0]
            v5.core.block(state, "article", code, str(exc))
            return v5.core.Action("blocked", str(exc))

        if max_attempt >= 2 and head_sha in repaired_heads:
            v5.core.block(
                state,
                "article",
                "ARTICLE_ATTEMPTS_EXHAUSTED",
                f"PR #{number} exhausted 3 total article content attempts (initial + {max_attempt} repairs)",
            )
            state["article"]["status"] = "exhausted"
            return v5.core.Action("blocked", f"article content attempts exhausted for PR #{number}")

        # 3. Check if repair is actively in flight for current head
        if head_sha in repaired_heads and self._is_repair_in_flight(pr, head_sha):
            return v5.core.Action("wait", f"Jules text repair attempt {max_attempt} in flight for PR #{number}")

        # 4. Normalization check
        needs_normalization, slot = self.github.article_pr_normalization_required(pr)
        if needs_normalization:
            if (
                self._child_notification_env()["workflow"] == "Kesher Normalize Article PR"
                and str(self._child_notification_env().get("conclusion") or "").lower() != "success"
            ):
                v5.core.transition(
                    state,
                    "article_normalizing",
                    "normalize child completed without success while PR still requires normalization; retrying normalization",
                )
            active = self.github.active_normalizer_run(number)
            if active:
                state["article"].update({
                    "normalization_status": "running",
                    "normalization_run_id": active.get("id"),
                    "normalization_slot": slot,
                })
                v5.core.transition(state, "article_normalizing", "trusted article normalization already active")
                return v5.core.Action("wait", "article normalization active")
            self.github.dispatch(
                "normalize-article-pr.yml",
                {"pr_number": str(number), "slot": slot},
            )
            state["article"].update({
                "normalization_status": "running",
                "normalization_slot": slot,
                "normalization_dispatched_at": v5.core.utc_now(),
            })
            v5.core.transition(
                state,
                "article_normalizing",
                "dirty or stale article PR dispatched to trusted normalizer",
                pr_number=number,
                slot=slot,
            )
            return v5.core.Action(
                "dispatch_normalize",
                "article PR must be normalized before image or Jules repair",
                {"pr_number": str(number), "slot": slot},
            )

        state["article"]["normalization_status"] = "complete"
        state["article"]["normalized_head_sha"] = head_sha

        # 5. Check content structure gates BEFORE consuming image attempts
        try:
            content_errors = self._pr_content_structure_errors(pr)
        except v5.core.ControllerError as exc:
            code = str(exc).split(":", 1)[0]
            v5.core.block(state, "article", code, str(exc))
            return v5.core.Action("blocked", str(exc))

        if content_errors:
            if max_attempt >= 2:
                v5.core.block(state, "article", "ARTICLE_ATTEMPTS_EXHAUSTED",
                              f"PR #{number} remains invalid after two same-PR repairs")
                state["article"]["status"] = "exhausted"
                return v5.core.Action("blocked", "article content repair budget exhausted")
            requested = self._request_article_text_repair(pr, content_errors)
            if not requested:
                v5.core.block(state, "article", "ARTICLE_TEXT_REPAIR_NOT_REQUESTED",
                              f"PR #{number} has invalid content and no new bounded repair was requested")
                return v5.core.Action("blocked", "same-PR text repair did not start")
            return v5.core.Action(
                "request_text_repair",
                f"article PR #{number} has content errors: {' | '.join(content_errors)}; same-PR text repair requested",
            )

        return super()._handle_open_article_pr(state, pr)

    def _ensure_article_public_and_deployed(self, state: dict) -> tuple[bool, v5.core.Action | None]:
        if isinstance(state, dict) and isinstance(state.get("article"), dict):
            state["article"].pop("_tick_live_verified", None)

        if getattr(self, "github", None) is None or getattr(self, "site", None) is None:
            return True, None
        posts = self.posts_on_main("main")
        todays = self._reconcile_existing_current_day_article(state, posts)
        if len(todays) > 1:
            v5.core.block(state, "article", "DUPLICATE_ARTICLE_DATE",
                          f"{len(todays)} articles share Israel date {self.now.date()}")
            return False, v5.core.Action("blocked", "duplicate published articles")
        if not todays:
            return True, None

        article = todays[0]
        slug = v5.core.canonical_slug(article)
        title = str(article.get("title") or "").strip()
        url = f"{v5.core.SITE_URL}/blog/{slug}"
        content_sha = str(state.get("article", {}).get("quality_content_sha256") or "").strip()
        hero_path = str(article.get("image") or article.get("hero_image") or "").strip()
        expected_hero_sha = str(
            article.get("image_sha256")
            or article.get("hero_image_sha256")
            or (state.get("image", {}) or {}).get("image_sha256")
            or (state.get("article", {}) or {}).get("image_sha256")
            or ""
        ).strip()
        if not expected_hero_sha and hero_path:
            local_hero = Path("public") / hero_path.lstrip("/")
            if local_hero.is_file():
                try:
                    expected_hero_sha = hashlib.sha256(local_hero.read_bytes()).hexdigest()
                except Exception:
                    pass
            elif hasattr(self.github, "file_content"):
                try:
                    content = self.github.file_content("main", f"public/{hero_path.lstrip('/')}")
                    if isinstance(content, (bytes, str)):
                        raw_b = content.encode("utf-8") if isinstance(content, str) else content
                        expected_hero_sha = hashlib.sha256(raw_b).hexdigest()
                except Exception:
                    pass

        # In-memory session tracking only: guaranteed fresh HTTP check on controller restart
        if slug in self._in_memory_verified_articles:
            return True, None

        status, page = self.site.get(url)
        is_pub = (
            status == 200
            and v5.core.article_is_public(
                page,
                title,
                expected_slug=slug,
                expected_content_sha256=content_sha,
                expected_hero_path=hero_path or None,
                expected_hero_sha256=expected_hero_sha or None,
                hero_fetcher=self.site,
            )
        )
        if is_pub:
            self._in_memory_verified_articles.add(slug)
            state.setdefault("article", {}).update({
                "live": True,
                "live_verified_at": v5.core.utc_now(),
                "next_deploy_retry_at": None,
            })
            state.get("article", {}).pop("_tick_live_verified", None)
            is_media_blocked = (
                (state.get("last_error") or {}).get("stage") in {"long_video", "short", "image", "video", "media"}
                or (state.get("long_video") or {}).get("status") in {"blocked", "exhausted"}
                or (state.get("short") or {}).get("status") in {"blocked", "exhausted"}
            )
            if not is_media_blocked and state.get("status") in {"blocked", "article_deploying", "article_deploy_wait", "article_generating", "article_retry_wait"}:
                v5.core.transition(state, "article_live", "HTTP 200 and expected title verified")
            return True, None

        state.setdefault("article", {})["live"] = False
        if self.github.active_workflow_run(v5.core.DEPLOY_WORKFLOW):
            v5.core.transition(state, "article_deploying", "deployment already active")
            return False, v5.core.Action("wait", "deployment active")

        current_main_sha = ""
        if hasattr(self.github, "main_sha"):
            try:
                current_main_sha = str(self.github.main_sha() or "").strip()
            except Exception:
                current_main_sha = ""

        pending_deploy = (state.get("pending_dispatches") or {}).get(v5.core.DEPLOY_WORKFLOW)
        if isinstance(pending_deploy, dict) and pending_deploy.get("cycle") == state.get("cycle"):
            dispatch_sha = str(pending_deploy.get("dispatch_head_sha") or "").strip()
            if current_main_sha and dispatch_sha and current_main_sha != dispatch_sha:
                state.setdefault("deploy_history", []).append({
                    "workflow": v5.core.DEPLOY_WORKFLOW,
                    "superseded_sha": dispatch_sha,
                    "current_sha": current_main_sha,
                    "superseded_at": v5.core.utc_now(),
                    "superseded_status": pending_deploy.get("status"),
                    "superseded_run_id": pending_deploy.get("observed_active_run_id") or state.get("article", {}).get("deploy_run_id"),
                    "reason": f"deploy for SHA {dispatch_sha} superseded by newer main SHA {current_main_sha}",
                })
                state["pending_dispatches"].pop(v5.core.DEPLOY_WORKFLOW, None)
                self._safe_save_controller_state(state)
                pending_deploy = None
            elif pending_deploy.get("status") in {"intent", "uncertain"}:
                v5.core.transition(state, "article_deploying", "deployment dispatch intent pending")
                return False, v5.core.Action("wait", "deployment dispatch pending reconciliation")
            elif pending_deploy.get("status") == "dispatched":
                intent_dt = v5.core.parse_timestamp(pending_deploy.get("dispatched_at") or pending_deploy.get("intent_at"))
                if intent_dt is not None:
                    elapsed = (self.now.astimezone(v5.core.timezone.utc) - intent_dt).total_seconds()
                    if 0 <= elapsed < 180:
                        v5.core.transition(state, "article_deploying", "deployment dispatched; waiting for run visibility")
                        return False, v5.core.Action("wait", f"deployment dispatched {int(elapsed)}s ago; waiting for run visibility")

        next_deploy = v5.core.parse_timestamp(state["article"].get("next_deploy_retry_at"))
        if next_deploy and self.now.astimezone(v5.core.timezone.utc) < next_deploy:
            v5.core.transition(state, "article_deploy_wait", "deploy retry backoff is active",
                               retry_at=next_deploy.isoformat())
            return False, v5.core.Action("wait", f"deploy retry scheduled for {next_deploy.isoformat()}")

        current_attempts = int(state["article"].get("deploy_attempts") or 0)
        if current_attempts >= v5.core.MAX_DEPLOY_ATTEMPTS or state["article"].get("deploy_status") == "exhausted":
            state["article"]["deploy_status"] = "exhausted"
            if state.get("status") != "blocked":
                v5.core.block(state, "article", "DEPLOY_ATTEMPTS_EXHAUSTED",
                              f"Article deployment exhausted maximum allowed attempts ({v5.core.MAX_DEPLOY_ATTEMPTS})")
            return False, v5.core.Action("block", f"deploy attempts exhausted ({v5.core.MAX_DEPLOY_ATTEMPTS})")

        attempts = current_attempts + 1
        self.github.dispatch(v5.core.DEPLOY_WORKFLOW)
        delay_index = max(1, attempts - v5.core.MAX_DEPLOY_ATTEMPTS_BEFORE_LONG_BACKOFF + 1)
        delay = 5 if attempts <= v5.core.MAX_DEPLOY_ATTEMPTS_BEFORE_LONG_BACKOFF else v5.core.article_retry_backoff_minutes(delay_index)
        state["article"].update({
            "deploy_attempts": attempts,
            "last_deploy_dispatch_at": v5.core.utc_now(),
            "next_deploy_retry_at": (self.now.astimezone(v5.core.timezone.utc) + v5.core.timedelta(minutes=delay)).isoformat(),
        })
        v5.core.transition(
            state,
            "article_deploying",
            "public article check failed; recovery deploy dispatched",
            http_status=status,
            attempt=attempts,
        )
        return False, v5.core.Action("dispatch_deploy", "article not public yet")

    def tick(self):
        state = self.state()
        self._active_state_ref = state
        if (
            state.get("status") == "blocked"
            and isinstance(state.get("last_error"), dict)
            and state["last_error"].get("code") == "IDEA_QUEUE_FULL"
        ):
            state["status"] = "complete"
            state["last_error"] = None
            state.setdefault("history", []).append({
                "at": v5.core.utc_now(),
                "from": "blocked",
                "to": "complete",
                "reason": "idea_queue_full_recovery",
            })
            state["history"] = state["history"][-100:]
            self._safe_save_controller_state(state)
        if idea_queue.finalize_if_complete(state, now_iso=v5.core.utc_now()):
            self._safe_save_controller_state(state)
        try:
            idea_result = idea_queue.ingest_from_env(state, os.environ, now_iso=v5.core.utc_now())
        except idea_queue.IdeaQueueError as exc:
            state["last_error"] = {
                "stage": "controller",
                "code": str(exc),
                "message": str(exc),
                "at": v5.core.utc_now(),
            }
            self._safe_save_controller_state(state)
            return state, v5.core.Action("rejected", str(exc))
        if idea_result == "run_now_queued":
            try:
                started = self._begin_run_now_cycle(state)
            except v5.core.ControllerError as exc:
                v5.core.block(state, "controller", str(exc), str(exc))
                self._safe_save_controller_state(state)
                return state, v5.core.Action("blocked", str(exc))
            if not started:
                self._safe_save_controller_state(state)
                return state, v5.core.Action("idea_queued", "owner run-now idea queued behind the active content cycle")
            self._safe_save_controller_state(state)
        elif idea_result in {"queued", "duplicate"}:
            self._safe_save_controller_state(state)
            return state, v5.core.Action(
                "idea_queued",
                "owner idea queued for the next controller-authorized article slot"
                if idea_result == "queued" else "owner idea already exists; duplicate submission ignored",
            )
        if v5.v3.entry.irrelevant_child_workflow_run():
            return state, v5.core.Action(
                "wait",
                f"irrelevant workflow_run ignored: {os.environ.get('KESHER_CHILD_WORKFLOW') or 'unknown'}",
            )
        info = self._child_notification_env()
        notification_key = (
            f"{info['workflow']}:{info['run_id']}"
            if info["workflow"] and info["run_id"]
            else ""
        )
        if any(info[k] for k in ("workflow", "run_id", "conclusion", "source_slug", "slot")):
            valid, reject_reason = self._validate_child_notification(state)
            if not valid:
                return state, v5.core.Action("wait", reject_reason)
            processed = state.get("processed_child_notifications")
            if not isinstance(processed, list):
                processed = []
            if notification_key and notification_key in processed:
                return state, v5.core.Action(
                    "wait",
                    f"duplicate child completion notification ignored: {notification_key}",
                )
            env_for_heartbeat = {
                "KESHER_TRIGGER_EVENT": info["trigger"],
                "KESHER_CHILD_WORKFLOW": info["workflow"],
                "KESHER_CHILD_CONCLUSION": info["conclusion"],
            }
            if v5.v3.entry.failed_child_waits_for_heartbeat(env_for_heartbeat):
                if notification_key:
                    processed.append(notification_key)
                    state["processed_child_notifications"] = processed[-100:]
                stage_mapping = self._workflow_stage_and_file(info["workflow"])
                stage_name = stage_mapping[0] if stage_mapping else None
                if stage_name and stage_name in state and isinstance(state[stage_name], dict):
                    state[stage_name]["last_run_conclusion"] = info.get("conclusion")
                    v5.v3.record_stage_failure(
                        state,
                        stage_name,
                        f"{stage_name.upper()}_WORKFLOW_FAILED",
                        f"child workflow {info['workflow']} completed with {info.get('conclusion')}",
                        run_id=info.get("run_id"),
                    )
                stage_budget_exhausted = False
                attempts = 0
                if stage_name:
                    stage_data = state.get(stage_name) or {}
                    attempts = int(stage_data.get("attempt_count") or stage_data.get("attempts") or 0)
                    if attempts >= v5.v3.MAX_STAGE_ATTEMPTS:
                        stage_budget_exhausted = True
                if stage_budget_exhausted:
                    v5.core.block(
                        state,
                        stage_name or "controller",
                        f"{stage_name.upper() if stage_name else 'CHILD'}_STAGE_BUDGET_EXHAUSTED",
                        f"failed child {info['workflow']} exhausted stage budget ({attempts}/{v5.v3.MAX_STAGE_ATTEMPTS})",
                    )
                    self._safe_save_controller_state(state)
                    return state, v5.core.Action(
                        "blocked",
                        f"failed child {info['workflow']} exhausted stage budget",
                    )
                self._safe_save_controller_state(state)
                retry_at = (state.get(stage_name) or {}).get("next_retry_at") if stage_name else None
                return state, v5.core.Action(
                    "wait",
                    f"failed child {info['workflow']} reconciled; retry scheduled for {retry_at or 'next tick'}; deferred to recovery heartbeat",
                )

        has_gh = hasattr(self, "github") and self.github is not None
        has_gh_dispatch = has_gh and hasattr(self.github, "dispatch")
        orig_gh_dispatch = getattr(self.github, "dispatch", None) if has_gh else None
        orig_core_dispatch = v5.core.GitHubClient.dispatch

        def guarded_gh_dispatch(workflow: str, inputs: dict | None = None) -> None:
            if orig_gh_dispatch:
                self._guarded_dispatch(self._active_state_ref, workflow, inputs, orig_gh_dispatch)

        def guarded_core_dispatch(client: Any, workflow: str, inputs: dict | None = None) -> None:
            def raw_core(w, i):
                orig_core_dispatch(client, w, i)
            self._guarded_dispatch(self._active_state_ref, workflow, inputs, raw_core)

        if has_gh_dispatch:
            self.github.dispatch = guarded_gh_dispatch  # type: ignore[method-assign]
        v5.core.GitHubClient.dispatch = guarded_core_dispatch  # type: ignore[method-assign]

        try:
            late_head_action = self._recover_exhausted_article_after_late_head_change(state)
            if late_head_action is not None:
                self._safe_save_controller_state(state)
                return state, late_head_action

            run_now_action = self._run_now_article_phase(state)
            if run_now_action is not None:
                self._safe_save_controller_state(state)
                return state, run_now_action

            scheduled_action = self._scheduled_active_article_phase(state)
            if scheduled_action is not None:
                self._safe_save_controller_state(state)
                return state, scheduled_action

            blocker = self._quality_preflight(state)
            if blocker is not None:
                return state, blocker

            if os.environ.get("KESHER_TARGET_MEDIA_SLUG", "").strip():
                direct_rebuild = self._dispatch_exact_rejected_rebuild(state)
                if direct_rebuild is not None:
                    return direct_rebuild
                return self._tick_targeted_media_recovery(state)

            is_pub, deploy_action = self._ensure_article_public_and_deployed(state)
            if not is_pub and deploy_action is not None:
                _, deliverables = runtime.delivery_guard.delivery_contract(state)
                state["deliverables"] = deliverables
                self._safe_save_controller_state(state)
                return state, deploy_action

            self._overview_evidence_preflight(state)
            direct_rebuild = self._dispatch_exact_rejected_rebuild(state)
            if direct_rebuild is not None:
                return direct_rebuild

            self._safe_save_controller_state(state)
            state, action = super().tick()
            self._active_state_ref = state
            if idea_queue.finalize_if_complete(state, now_iso=v5.core.utc_now()):
                self._safe_save_controller_state(state)
            if info["workflow"] and notification_key:
                processed = state.get("processed_child_notifications")
                if not isinstance(processed, list):
                    processed = []
                if notification_key not in processed:
                    processed.append(notification_key)
                state["processed_child_notifications"] = processed[-100:]
                self._safe_save_controller_state(state)
            return state, action
        except _DuplicateDispatchSuppressed as suppressed:
            _, deliverables = runtime.delivery_guard.delivery_contract(self._active_state_ref)
            self._active_state_ref["deliverables"] = deliverables
            self._safe_save_controller_state(self._active_state_ref)
            return self._active_state_ref, v5.core.Action("wait", suppressed.reason)
        except v5.core.ControllerError as exc:
            code = str(exc).split(":", 1)[0]
            v5.core.block(state, "controller", code, str(exc))
            action = v5.core.Action("blocked", str(exc))
            _, deliverables = runtime.delivery_guard.delivery_contract(state)
            state["deliverables"] = deliverables
            self._safe_save_controller_state(state)
            return state, action
        finally:
            if has_gh_dispatch:
                self.github.dispatch = orig_gh_dispatch  # type: ignore[method-assign]
            elif has_gh and hasattr(self.github, "dispatch"):
                delattr(self.github, "dispatch")
            v5.core.GitHubClient.dispatch = orig_core_dispatch  # type: ignore[method-assign]


def install_runtime() -> None:
    runtime.install_runtime()
    # The stabilized V5 runtime owns prior-cycle backlog explicitly. Keep the
    # base current-cycle matcher exact to the requested article instead of
    # inheriting the legacy global FIFO fallback.
    v5.v3.entry.queue_aware_matching = _current_cycle_video_matching
    v5.core.PublicSiteClient.get = _unicode_safe_public_site_get
    v5.V5Controller = StabilizedRuntimeV5Controller


def main() -> int:
    from scripts.kesher_runtime.legacy_retirement import retired_entrypoint
    retired_entrypoint()
    install_runtime()
    return v5.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (v5.core.ControllerError, ValueError, KeyError, json.JSONDecodeError) as exc:
        import traceback
        traceback.print_exc()
        print(f"KESHER_CONTROLLER_STABILIZED_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

#!/usr/bin/env python3
"""Kesher production controller V5.

V5 restores the regular NotebookLM Video Overview as the sole provider-generation
stage and adds a separate derivative Short stage. One article identity therefore
owns one NotebookLM provider identity and two YouTube publications.
"""

from __future__ import annotations

import copy
import hashlib
import html
import json
import os
import re
import sys
from html.parser import HTMLParser
from typing import Any

if __package__:
    from . import kesher_content_controller as core
    from . import kesher_content_controller_v3_entry as v3
    from . import kesher_content_controller_v4 as v4
    from . import kesher_content_watchdog as watchdog
    from . import jules_article_runner_core as jules
else:
    import kesher_content_controller as core
    import kesher_content_controller_v3_entry as v3
    import kesher_content_controller_v4 as v4
    import kesher_content_watchdog as watchdog
    import jules_article_runner_core as jules

STATE_SCHEMA_VERSION = 5
LONG_VIDEO_WORKFLOW = "kesher-daily-video.yml"
LONG_VIDEO_WORKFLOW_NAME = "Kesher Daily NotebookLM Video Overview"
LONG_VIDEO_STATE_ARTIFACT = "kesher-video-state"
LONG_VIDEO_CONTROLLER_STATE_ARTIFACT = "kesher-video-controller-state"
SHORT_WORKFLOW = "kesher-short-v4.yml"
SHORT_WORKFLOW_NAME = "Kesher Daily Article Short V4"
SHORT_STATE_ARTIFACT = "kesher-short-v4-state"
SHORT_CONTROLLER_STATE_ARTIFACT = "kesher-short-v4-controller-state"
MAX_SHORT_DISPATCH_ATTEMPTS = 4
MAX_SHORT_REMOTION_REBUILDS = 2


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = re.sub(r"\s+", " ", data).strip()
        if value:
            self.parts.append(value)


def _clean_article_html(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    return html.unescape("\n\n".join(parser.parts))


def article_source_identity(post: dict[str, Any]) -> dict[str, Any]:
    """Return the same source identity used by kesher_daily_pipeline.source_metadata."""
    required = ("id", "title", "date", "category", "excerpt", "content")
    missing = [field for field in required if not str(post.get(field, "")).strip()]
    if missing:
        raise core.ControllerError(f"ARTICLE_IDENTITY_MISSING: {', '.join(missing)}")
    slug = str(post.get("slug") or post["id"]).strip()
    title = str(post["title"]).strip()
    excerpt = _clean_article_html(str(post["excerpt"]))
    article_text = _clean_article_html(str(post["content"]))
    canonical_url = f"{core.SITE_URL}/blog/{slug}"
    body = "\n\n".join(part for part in (title, excerpt, article_text, f"מקור: {canonical_url}") if part)
    return {
        "slug": slug,
        "content_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }


def _source_identity(item: dict[str, Any]) -> tuple[str, str]:
    source = item.get("source") or {}
    return (
        str(source.get("slug") or source.get("id") or "").strip(),
        str(source.get("content_sha256") or "").strip(),
    )


def _exact_items(video_state: dict[str, Any], source: dict[str, str]) -> list[dict[str, Any]]:
    return [
        row for row in (video_state.get("items") or [])
        if isinstance(row, dict)
        and _source_identity(row) == (source["slug"], source["content_sha256"])
    ]


def _verified_exact(video_state: dict[str, Any], source: dict[str, str]) -> list[dict[str, Any]]:
    return [row for row in _exact_items(video_state, source) if core.verified_youtube_item(row, source["slug"])]


def _newest(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return sorted(
        rows,
        key=lambda row: str(row.get("uploaded_at") or row.get("updated_at") or row.get("created_at") or ""),
        reverse=True,
    )[0]


class V5GitHubClient(v4.V4GitHubClient):
    def newest_state_for_artifact(self, artifact_name: str) -> dict[str, Any]:
        previous = core.VIDEO_STATE_ARTIFACT
        core.VIDEO_STATE_ARTIFACT = artifact_name
        try:
            return super().newest_video_state()
        finally:
            core.VIDEO_STATE_ARTIFACT = previous

    def _artifact_available(self, artifact_name: str) -> bool:
        payload = self.request(
            "GET",
            f"{self.api}/actions/artifacts?name={artifact_name}&per_page=3",
        )
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
        return any(
            isinstance(row, dict) and row.get("expired") is not True
            for row in (artifacts or [])
        )

    def _preferred_controller_state(
        self,
        lightweight_artifact: str,
        durable_artifact: str,
    ) -> dict[str, Any]:
        # The lightweight companion is an optimization only. Listing or reading
        # it must never make production less reliable than the durable fallback.
        try:
            lightweight_available = self._artifact_available(lightweight_artifact)
        except core.ControllerError:
            lightweight_available = False
        if lightweight_available:
            try:
                return self.newest_state_for_artifact(lightweight_artifact)
            except core.ControllerError:
                pass
        return self.newest_state_for_artifact(durable_artifact)

    def save_video_state(self, state: dict[str, Any]) -> None:
        self._video_state = copy.deepcopy(state)
        try:
            from scripts import kesher_daily_pipeline as pipeline
            pipeline.save_state(state)
        except Exception:
            pass

    def newest_video_state(self) -> dict[str, Any]:
        if getattr(self, "_video_state", None) is not None:
            return copy.deepcopy(self._video_state)
        # The full durable artifact may contain large MP4/evidence files needed
        # by the video worker for resume. Controller V5 only needs state.json.
        return self._preferred_controller_state(
            LONG_VIDEO_CONTROLLER_STATE_ARTIFACT,
            LONG_VIDEO_STATE_ARTIFACT,
        )

    def newest_short_state(self) -> dict[str, Any]:
        return self._preferred_controller_state(
            SHORT_CONTROLLER_STATE_ARTIFACT,
            SHORT_STATE_ARTIFACT,
        )

    def article_session_snapshot(self, slot: str) -> dict[str, Any] | None:
        return self._article_session_snapshot(slot)

    def owner_article_session_snapshot(self, slot: str, keyword: str) -> dict[str, Any] | None:
        return self._article_session_snapshot(slot, exact_title=jules.owner_slot_session_title(slot, keyword))

    def _article_session_snapshot(self, slot: str, *, exact_title: str | None = None) -> dict[str, Any] | None:
        api_key = os.environ.get("JULES_API_KEY", "").strip()
        if not api_key:
            return None
        recovered = (jules.recover_active_slot_session(api_key, slot, exact_title=exact_title)
                     if exact_title is not None else jules.recover_active_slot_session(api_key, slot))
        if not recovered:
            return None
        session_name, _ = recovered
        sid = session_name.removeprefix("sessions/")
        payload = jules.request_json(
            "GET",
            f"{jules.API_BASE}/sessions/{sid}",
            jules.jules_headers(api_key),
        )
        current = payload if isinstance(payload, dict) else {}
        state = str(current.get("state") or "UNKNOWN").upper()
        urls = jules.pr_urls(current)
        progress_payload = {
            "state": state,
            "update_time": current.get("updateTime") or current.get("updatedAt") or current.get("lastActivityTime"),
            "outputs": current.get("outputs") or [],
            "pr_urls": urls,
        }
        fingerprint = hashlib.sha256(
            json.dumps(progress_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        return {
            "session_id": session_name,
            "state": state,
            "pr_urls": urls,
            "fingerprint": fingerprint,
        }

    def nudge_article_session(self, session_id: str) -> None:
        api_key = os.environ.get("JULES_API_KEY", "").strip()
        if not api_key:
            raise core.ControllerError("JULES_API_KEY_MISSING")
        jules.send_message(
            api_key,
            session_id.removeprefix("sessions/"),
            "Continue autonomously and finish the existing article task, validate it, and create the required PR. Do not start a new task or ask a question.",
        )

    def cancel_workflow_run(self, run_id: int | str) -> None:
        self.request("POST", f"{self.api}/actions/runs/{run_id}/cancel", {})

class V5Controller(v4.V4Controller):
    def state(self) -> dict[str, Any]:
        existing = self.github.load_controller_state()
        from scripts.kesher_runtime.legacy_retirement import validate_legacy_read
        validate_legacy_read(existing)
        today = self.now.date()
        if (
            isinstance(existing, dict)
            and existing.get("cycle") == today.isoformat()
            and existing.get("schema_version") == STATE_SCHEMA_VERSION
        ):
            state = copy.deepcopy(existing)
            for stage in ("article", "image", "long_video", "short"):
                current = state.setdefault(stage, {})
                for key, value in v3._stage_template().items():
                    current.setdefault(key, copy.deepcopy(value))
            state.pop("video", None)
            return state

        base = v4.V4Controller.state(self)
        previous_schema = existing.get("schema_version") if isinstance(existing, dict) else None
        previous_video = copy.deepcopy((base.get("video") or {}))
        state = copy.deepcopy(base)
        state["schema_version"] = STATE_SCHEMA_VERSION
        state["long_video"] = v3._stage_template()
        state["short"] = previous_video if previous_schema == 4 else v3._stage_template()
        for key, value in v3._stage_template().items():
            state["short"].setdefault(key, copy.deepcopy(value))
        state.pop("video", None)
        state.setdefault("migration", {})["v4_short_controller_state"] = previous_video if previous_schema == 4 else None
        state.setdefault("history", []).append({
            "at": core.utc_now(),
            "from": state.get("status"),
            "to": "v5_migrated",
            "reason": f"controller state migrated from schema {previous_schema} to V5 long_video + short stages",
        })
        state["history"] = state["history"][-100:]
        if state.get("status") in {"complete", "article_complete_without_short"}:
            state["status"] = "article_live" if (state.get("article") or {}).get("live") else "article_needed"
        return state

    def _article_watchdog(self, state: dict[str, Any]) -> core.Action | None:
        # The publication window gates starting new article work, not recovery.
        # Once a worker is already active it must remain supervised across
        # window boundaries (for example a Friday pre-08:00 recovery run).
        posts = self.posts_on_main("main")
        if not isinstance(posts, list) or self._reconcile_existing_current_day_article(state, posts):
            return None
        slot = self.now.date().isoformat()
        open_prs = self.github.open_article_prs(slot)
        if open_prs:
            return None
        active = self.github.active_workflow_run(core.ARTICLE_WORKFLOW)
        if not active:
            return None

        snapshot = watchdog.article_snapshot(self.github, state, slot)
        session_id = str((snapshot or {}).get("session_id") or "").strip() or None
        fingerprint = str((snapshot or {}).get("fingerprint") or "").strip() or None
        watchdog.observe_article(
            state["article"],
            identity=slot,
            run_started_at=active.get("run_started_at") or active.get("created_at"),
            session_id=session_id,
            fingerprint=fingerprint,
            now=self.now,
        )
        state["article"]["run_id"] = active.get("id")
        decision = watchdog.article_decision(state["article"], now=self.now, active_run_id=active.get("id"))

        if decision == "nudge":
            self.github.nudge_article_session(session_id)
            watchdog.mark_article_nudge(state["article"], now=self.now)
            core.transition(state, "article_watchdog_nudge", "article stalled; nudged authoritative Jules session", session_id=session_id)
            return core.Action("article_watchdog_nudge", "nudged same Jules article session")

        if decision == "restart":
            run_id = active.get("id")
            self.github.cancel_workflow_run(run_id)
            self.github.dispatch(core.ARTICLE_WORKFLOW, {"slot": slot})
            watchdog.mark_article_restart(state["article"], now=self.now, run_id=run_id)
            state["article"]["run_id"] = None
            core.transition(state, "article_watchdog_restart", "article stalled after nudge; restarted GitHub worker for same Jules slot/session", session_id=session_id, cancelled_run_id=run_id)
            return core.Action("article_watchdog_restart", "restarted article worker for same slot/session", {"slot": slot})

        if decision == "blocked":
            core.block(state, "article", "ARTICLE_WATCHDOG_RECOVERY_EXHAUSTED", "article worker stalled after two same-session recovery restarts")
            return core.Action("blocked", "article watchdog recovery exhausted")

        core.transition(state, "article_generating", "article workflow active; watchdog observing progress", session_id=session_id)
        return core.Action("wait", "article workflow active")

    def _dispatch_budgeted(self, state, stage, workflow, inputs):
        if stage == "video":
            # V5's legacy-compatible `video` alias always means long-form. Use
            # the proven BestEffort/V3 provider-resume budget, never V4's
            # Short fresh-generation/release policy.
            return v4.legacy.BestEffortController._dispatch_budgeted(self, state, stage, workflow, inputs)
        return super()._dispatch_budgeted(state, stage, workflow, inputs)

    def _article_source(self, state: dict[str, Any] | None = None) -> dict[str, str] | None:
        if state is not None:
            todays = self._reconcile_existing_current_day_article(state)
        else:
            todays = self.posts_for_cycle(self.now.date())
        if len(todays) != 1:
            return None
        return article_source_identity(todays[0])

    @staticmethod
    def _short_dispatch_gate_error(
        source: Any,
        long_item: Any,
    ) -> tuple[str, str] | None:
        if not isinstance(source, dict):
            return (
                "SHORT_SOURCE_IDENTITY_MISSING",
                "Short dispatch requires non-empty canonical slug and 64-hex content_sha256",
            )
        slug = str(source.get("slug") or "").strip()
        sha = str(source.get("content_sha256") or "").strip()
        if not slug or len(sha) != 64 or not all(ch in "0123456789abcdefABCDEF" for ch in sha):
            return (
                "SHORT_SOURCE_IDENTITY_MISSING",
                "Short dispatch requires non-empty canonical slug and 64-hex content_sha256",
            )
        if not isinstance(long_item, dict) or not str(long_item.get("id") or "").strip():
            return (
                "SHORT_REQUIRES_VERIFIED_LONG_VIDEO",
                "Short cannot be dispatched before exact-identity Long Video is public and verified",
            )
        if _source_identity(long_item) != (slug, sha):
            return (
                "SHORT_REQUIRES_VERIFIED_LONG_VIDEO",
                "Short cannot be dispatched when Long Video source identity does not match exact slug and content_sha256",
            )
        if not core.verified_youtube_item(long_item, slug):
            return (
                "SHORT_REQUIRES_VERIFIED_LONG_VIDEO",
                "Short cannot be dispatched before exact-identity Long Video is public and verified on YouTube",
            )
        return None

    def _adopt_existing_short(self, state: dict[str, Any], source: dict[str, str], long_item: dict[str, Any] | None = None) -> dict[str, Any] | None:
        current_short = state.get("short") or {}
        if (
            current_short.get("status") == "complete"
            and current_short.get("verified") is True
            and current_short.get("youtube_id")
            and current_short.get("youtube_url")
        ):
            return current_short
        short_state = self.github.newest_short_state()
        verified = _verified_exact(short_state, source)
        item = _newest(verified)
        if not item:
            return None
        state["short"].update({
            "item_id": item.get("id"),
            "status": "complete",
            "youtube_id": item.get("youtube_id"),
            "youtube_url": item.get("youtube_url"),
            "verified": True,
            "provider_id": item.get("task_id"),
            "artifact_id": item.get("artifact_id"),
            "source_id": item.get("source_id"),
        })
        v3.clear_stage_failure(state["short"])
        return item

    def _reconcile_completed_short_run(self, state: dict[str, Any]) -> None:
        current = state["short"]
        run_id = current.get("run_id")
        if not run_id or current.get("processed_run_id") == run_id:
            return
        run = self._workflow_run(run_id)
        if not run or str(run.get("status") or "") != "completed":
            return
        current["processed_run_id"] = run_id
        conclusion = str(run.get("conclusion") or "unknown")
        current["last_run_conclusion"] = conclusion
        if conclusion == "success":
            v3.clear_stage_failure(current)
            return
        v3.record_stage_failure(
            state,
            "short",
            "SHORT_WORKFLOW_FAILED",
            f"Short derive run {run_id} completed with conclusion={conclusion}",
            run_id=run_id,
        )

    @staticmethod
    def _short_resolution_rebuild_candidate(item: dict[str, Any]) -> bool:
        if not isinstance(item, dict) or item.get("uploaded") is True:
            return False
        if str(item.get("status") or "") != "rejected":
            return False
        note = str(((item.get("review_notes") or {}).get("technical") or ""))
        return (
            "1080x1920" in note
            and bool(item.get("id"))
        )

    def _tick_short(self, state: dict[str, Any], source: dict[str, str], long_item: dict[str, Any]) -> core.Action:
        if isinstance(source, dict) and source.get("slug") and source.get("content_sha256"):
            existing = self._adopt_existing_short(state, source, long_item=long_item)
            if existing:
                core.transition(state, "complete", "article, long-form video and derivative Short verified public")
                state["article"]["status"] = "complete"
                state["image"]["status"] = "complete"
                state["long_video"]["status"] = "complete"
                state["short"]["status"] = "complete"
                return core.Action("complete", "article + long-form + Short verified public")

        gate_error = self._short_dispatch_gate_error(source, long_item)
        if gate_error is not None:
            code, message = gate_error
            core.block(state, "short", code, message)
            return core.Action("blocked", message)

        short_state = self.github.newest_short_state()
        exact = _exact_items(short_state, source)
        unresolved = [
            item for item in exact
            if item.get("uploaded") is not True
            and not bool(str(item.get("youtube_id") or "").strip())
            and str(item.get("status") or "") in (core.ACTIVE_VIDEO_STATUSES | {"rejected"})
        ]
        if len(unresolved) > 1:
            core.block(state, "short", "DUPLICATE_SHORT_ITEMS", f"{len(unresolved)} unresolved Shorts exist for {source['slug']}")
            return core.Action("blocked", "duplicate Short items")
        active = self.github.active_workflow_run(SHORT_WORKFLOW, production_only=True)
        if active:
            state["short"]["run_id"] = active.get("id")
            state["short"]["status"] = "running"
            core.transition(state, "short_running", "Short derive workflow already active")
            return core.Action("wait", "Short workflow active")

        self._reconcile_completed_short_run(state)
        if not core.retry_ready(state["short"], self.now):
            retry_at = state["short"].get("next_retry_at")
            core.transition(state, "short_retry_wait", "Short retry backoff is active", retry_at=retry_at)
            return core.Action("wait", f"Short retry scheduled for {retry_at}")

        uploaded_unverified = [
            item for item in exact
            if (
                item.get("uploaded") is True
                or str(item.get("status") or "") == "uploaded"
                or bool(str(item.get("youtube_id") or "").strip())
            )
            and not core.verified_youtube_item(item, source["slug"])
        ]
        if uploaded_unverified:
            candidate = _newest(uploaded_unverified) or uploaded_unverified[-1]
            if not bool(str(candidate.get("youtube_id") or "").strip()):
                core.block(
                    state,
                    "short",
                    "UPLOADED_SHORT_NOT_VERIFIED",
                    "Short has uploaded status without youtube_id",
                )
                return core.Action("blocked", "uploaded Short requires reconciliation")
            count = int(state["short"].get("attempt_count") or 0)
            if count >= MAX_SHORT_DISPATCH_ATTEMPTS:
                core.block(
                    state,
                    "short",
                    "SHORT_ATTEMPTS_EXHAUSTED",
                    f"Short exhausted {MAX_SHORT_DISPATCH_ATTEMPTS} derive/recovery dispatch attempts",
                )
                state["short"]["status"] = "exhausted"
                return core.Action("blocked", "Short attempts exhausted")
            inputs = {
                "operation": "upload",
                "derive_slug": source["slug"],
                "derive_content_sha256": source["content_sha256"],
                "derive_long_item_id": str(long_item.get("id") or ""),
            }
            core.GitHubClient.dispatch(self.github, SHORT_WORKFLOW, inputs)
            state["short"].update({
                "item_id": candidate.get("id"),
                "attempt_count": count + 1,
                "last_dispatch_at": core.utc_now(),
                "next_retry_at": None,
                "status": "running",
                "youtube_id": candidate.get("youtube_id"),
                "youtube_url": candidate.get("youtube_url"),
                "verified": False,
                "provider_id": candidate.get("task_id") or long_item.get("task_id"),
                "artifact_id": candidate.get("artifact_id") or long_item.get("artifact_id"),
                "source_id": candidate.get("source_id") or long_item.get("source_id"),
                "adopted_from_long_item_id": candidate.get("adopted_from_long_item_id") or long_item.get("id"),
            })
            core.transition(
                state,
                "short_running",
                "uploaded Short has youtube_id but lacks complete verification; re-verifying without regeneration",
                item_id=candidate.get("id"),
                youtube_id=candidate.get("youtube_id"),
            )
            return core.Action(
                "dispatch_short_reverify",
                "uploaded Short requires public verification without regeneration",
                inputs,
            )

        if unresolved:
            current_item = unresolved[0]
            adopted = str(current_item.get("adopted_from_long_item_id") or "")
            if adopted and adopted != str(long_item.get("id") or ""):
                core.block(state, "short", "SHORT_PROVIDER_IDENTITY_MISMATCH", "existing Short derives from a different long-form provider item")
                return core.Action("blocked", "Short provider identity mismatch")

            if self._short_resolution_rebuild_candidate(current_item):
                rebuild_count = int(state["short"].get("remotion_rebuild_count") or 0)
                if rebuild_count < MAX_SHORT_REMOTION_REBUILDS:
                    inputs = {
                        "operation": "rebuild",
                        "rebuild_item_id": str(current_item.get("id") or ""),
                    }
                    core.GitHubClient.dispatch(self.github, SHORT_WORKFLOW, inputs)
                    state["short"].update({
                        "status": "running",
                        "remotion_rebuild_count": rebuild_count + 1,
                        "last_dispatch_at": core.utc_now(),
                        "provider_id": current_item.get("task_id") or long_item.get("task_id"),
                        "artifact_id": current_item.get("artifact_id") or long_item.get("artifact_id"),
                        "source_id": current_item.get("source_id") or long_item.get("source_id"),
                        "adopted_from_long_item_id": long_item.get("id"),
                    })
                    core.transition(
                        state,
                        "short_running",
                        "rebuilding exact rejected Short after deterministic resolution-contract failure",
                        item_id=current_item.get("id"),
                    )
                    return core.Action(
                        "dispatch_short_rebuild",
                        "rebuild exact rejected Short on current Remotion contract without new provider generation",
                        inputs,
                    )

        count = int(state["short"].get("attempt_count") or 0)
        if count >= MAX_SHORT_DISPATCH_ATTEMPTS:
            core.block(state, "short", "SHORT_ATTEMPTS_EXHAUSTED", f"Short exhausted {MAX_SHORT_DISPATCH_ATTEMPTS} derive/recovery dispatch attempts")
            state["short"]["status"] = "exhausted"
            return core.Action("blocked", "Short attempts exhausted")

        short_mode = os.environ.get("KESHER_SHORT_MODE", "").strip().lower()
        if short_mode in {"direct", "standalone"}:
            # Direct generation must still bind the worker to the current
            # authoritative article. Without derive_slug, the worker resumes
            # whichever stale Short item is newest in durable state.
            inputs = {
                "operation": "full",
                "derive_slug": source["slug"],
            }
        else:
            inputs = {
                "operation": "derive",
                "derive_slug": source["slug"],
                "derive_content_sha256": source["content_sha256"],
                "derive_long_item_id": str(long_item.get("id") or ""),
            }
        core.GitHubClient.dispatch(self.github, SHORT_WORKFLOW, inputs)
        state["short"].update({
            "attempt_count": count + 1,
            "last_dispatch_at": core.utc_now(),
            "next_retry_at": None,
            "status": "running",
            "provider_id": long_item.get("task_id"),
            "artifact_id": long_item.get("artifact_id"),
            "source_id": long_item.get("source_id"),
            "adopted_from_long_item_id": long_item.get("id"),
        })
        core.transition(state, "short_running", "derivative Short dispatched from verified long-form provider identity")
        return core.Action("dispatch_short", "long-form verified; deriving Short from same provider identity", inputs)

    def tick(self) -> tuple[dict[str, Any], core.Action]:
        state = self.state()
        try:
            article_watchdog_action = self._article_watchdog(state)
            if article_watchdog_action is not None:
                self.github.save_controller_state(state)
                return state, article_watchdog_action
            source = self._article_source(state)
            if source is not None:
                # Evidence-only migration: a matching V4 public Short is durable
                # success even while the long-form stage is still missing.
                self._adopt_existing_short(state, source)
        except core.ControllerError as exc:
            code = str(exc).split(":", 1)[0]
            core.block(state, "controller", code, str(exc))
            action = core.Action("blocked", str(exc))
            self.github.save_controller_state(state)
            return state, action

        state["video"] = state["long_video"]
        try:
            try:
                action = super()._tick(state)
            except v3.StageAttemptsExhausted as exc:
                core.block(state, "long_video" if exc.stage == "video" else exc.stage, exc.code, str(exc))
                target = state["video"] if exc.stage == "video" else state[exc.stage]
                target["status"] = "exhausted"
                action = core.Action("blocked", str(exc))
            except core.ControllerError as exc:
                code = str(exc).split(":", 1)[0]
                core.block(state, "controller", code, str(exc))
                action = core.Action("blocked", str(exc))

            state["long_video"] = state["video"]
        finally:
            state.pop("video", None)

        if action.kind == "dispatch_video":
            action = core.Action("dispatch_long_video", action.reason, action.inputs)
            if state.get("status") == "video_running":
                state["status"] = "long_video_running"
        elif state.get("status", "").startswith("video_"):
            state["status"] = "long_" + str(state["status"])

        if action.kind != "complete":
            self.github.save_controller_state(state)
            return state, action

        if source is None:
            source = self._article_source(state)
        if source is None:
            core.block(state, "controller", "ARTICLE_IDENTITY_UNAVAILABLE", "long-form completed but authoritative article identity is unavailable")
            action = core.Action("blocked", "article identity unavailable")
            self.github.save_controller_state(state)
            return state, action

        long_state = self.github.newest_video_state()
        exact_verified = _verified_exact(long_state, source)
        long_item = _newest(exact_verified)
        if not long_item:
            same_slug_verified = [
                row for row in (long_state.get("items") or [])
                if isinstance(row, dict)
                and _source_identity(row)[0] == source["slug"]
                and core.verified_youtube_item(row, source["slug"])
            ]
            code = "LONG_VIDEO_IDENTITY_MISMATCH" if same_slug_verified else "LONG_VIDEO_PUBLIC_EVIDENCE_MISSING"
            core.block(state, "long_video", code, "long-form completion lacks exact slug + content hash public evidence")
            action = core.Action("blocked", "long-form exact identity not verified")
            self.github.save_controller_state(state)
            return state, action

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
        v3.clear_stage_failure(state["long_video"])
        state["status"] = "long_video_complete"
        action = self._tick_short(state, source, long_item)
        self.github.save_controller_state(state)
        return state, action


def v5_trigger_stage(workflow_name: str):
    if workflow_name in {LONG_VIDEO_WORKFLOW_NAME, "Kesher Daily Video Overview"}:
        return "long_video", LONG_VIDEO_WORKFLOW
    if workflow_name in {SHORT_WORKFLOW_NAME, "Kesher Article Short V4"}:
        return "short", SHORT_WORKFLOW
    return v3.v3_trigger_stage(workflow_name)


def v5_adopt_latest(github: Any, state: dict[str, Any] | None, cycle: str) -> bool:
    changed = v3.v3_adopt_latest(github, state, cycle)
    if not isinstance(state, dict) or state.get("cycle") != cycle:
        return changed
    for stage, workflow in (
        ("long_video", LONG_VIDEO_WORKFLOW),
        ("short", SHORT_WORKFLOW),
    ):
        stage_state = state.get(stage) if isinstance(state.get(stage), dict) else None
        if not stage_state or not stage_state.get("last_dispatch_at"):
            continue
        try:
            runs = github.workflow_runs(workflow)
        except core.ControllerError:
            continue
        production = [
            run for run in runs
            if isinstance(run, dict) and str(run.get("event") or "") == "workflow_dispatch"
        ]
        candidate = v3.entry._nearest_dispatched_run(production, stage_state)
        if candidate is None or v3.entry._same_id(stage_state.get("run_id"), candidate.get("id")):
            continue
        stage_state["run_id"] = candidate.get("id")
        changed = True
        print(
            f"KESHER_DISPATCH_CORRELATED stage={stage} run_id={candidate.get('id')} cycle={cycle}",
            flush=True,
        )
    if changed:
        github.save_controller_state(state)
    return changed



def owner_pr_rehome_controller(base_controller):
    """Wrap the stabilized run-now phase with exact prior-slot owner-PR adoption."""
    if not hasattr(base_controller, "_run_now_article_phase"):
        return base_controller

    class OwnerPrRehomeController(base_controller):
        @staticmethod
        def _owner_canonical_id(state: dict[str, Any] | None) -> str:
            active = (state or {}).get("active_idea") if isinstance(state, dict) else None
            if not isinstance(active, dict):
                return ""
            brief = str(active.get("topic_brief") or "")
            match = re.search(r"Canonical ID\s+נדרש\s*:\s*([A-Za-z0-9][A-Za-z0-9_-]*)", brief)
            return match.group(1) if match else ""

        def _exact_owner_open_article_prs(self, state: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
            from scripts import kesher_article_contract as article_contract

            active = state.get("active_idea") if isinstance(state, dict) else None
            if not isinstance(active, dict):
                return []
            keyword = str(active.get("required_primary_keyword") or "").strip()
            canonical_id = self._owner_canonical_id(state)
            if not keyword or not canonical_id:
                return []

            api = str(getattr(self.github, "api", "") or "").strip()
            if not api:
                api = "https://api.github.com/repos/yanivsa/kesher-website"
            try:
                rows = self.github.request("GET", f"{api}/pulls?state=open&per_page=100")
            except Exception as exc:
                raise core.ControllerError("OWNER_ARTICLE_PR_INVENTORY_UNAVAILABLE") from exc
            if not isinstance(rows, list):
                raise core.ControllerError("OWNER_ARTICLE_PR_INVENTORY_INVALID")

            expected_title = f"Publish Kesher article: {canonical_id}"
            matches: list[tuple[dict[str, Any], str]] = []
            for pr in rows:
                if not isinstance(pr, dict) or str(pr.get("title") or "").strip() != expected_title:
                    continue
                if str((pr.get("base") or {}).get("ref") or "") != "main":
                    raise core.ControllerError("OWNER_ARTICLE_PR_BASE_INVALID")
                head = pr.get("head") or {}
                if str((head.get("repo") or {}).get("full_name") or "") != "yanivsa/kesher-website":
                    raise core.ControllerError("OWNER_ARTICLE_PR_REPOSITORY_INVALID")
                head_sha = str(head.get("sha") or "").strip().lower()
                if not re.fullmatch(r"[a-f0-9]{40}", head_sha):
                    raise core.ControllerError("OWNER_ARTICLE_PR_HEAD_INVALID")
                body_keyword = str(
                    article_contract.exact_field(str(pr.get("body") or ""), "Primary Keyword") or ""
                ).strip()
                if body_keyword != keyword:
                    raise core.ControllerError("OWNER_ARTICLE_PR_KEYWORD_MISMATCH")
                try:
                    head_posts = self.github.contents_json("src/data/posts.json", head_sha)
                except Exception as exc:
                    raise core.ControllerError("OWNER_ARTICLE_PR_IDENTITY_UNVERIFIED") from exc
                if not isinstance(head_posts, list):
                    raise core.ControllerError("OWNER_ARTICLE_PR_IDENTITY_UNVERIFIED")
                candidates = [
                    post for post in head_posts
                    if isinstance(post, dict)
                    and core.canonical_slug(post) == canonical_id
                    and core.is_controller_adoptable_post(post)
                ]
                if len(candidates) != 1:
                    raise core.ControllerError("OWNER_ARTICLE_PR_IDENTITY_MISMATCH")
                source_slot = str(candidates[0].get("date") or "").strip()
                try:
                    from datetime import date
                    date.fromisoformat(source_slot)
                except ValueError as exc:
                    raise core.ControllerError("OWNER_ARTICLE_PR_SOURCE_SLOT_INVALID") from exc
                matches.append((pr, source_slot))
            return matches

        def _run_now_article_phase(self, state: dict[str, Any]):
            if not self._run_now_active(state):
                return super()._run_now_article_phase(state)
            slot = self._run_now_slot(state)
            if not slot:
                raise core.ControllerError("IDEA_RUN_NOW_SLOT_INVALID")
            try:
                owner_prs = self._exact_owner_open_article_prs(state)
            except core.ControllerError as exc:
                code = str(exc).split(":", 1)[0]
                core.block(state, "article", code, str(exc))
                return core.Action("blocked", str(exc))
            if len(owner_prs) > 1:
                core.block(
                    state, "article", "DUPLICATE_OWNER_ARTICLE_PRS",
                    f"{len(owner_prs)} open article PRs match the exact run-now owner identity",
                )
                return core.Action("blocked", "duplicate exact owner article PRs")
            if not owner_prs:
                return super()._run_now_article_phase(state)

            owner_pr, source_slot = owner_prs[0]
            if source_slot == slot:
                return self._handle_open_article_pr(state, owner_pr)
            from datetime import date
            if date.fromisoformat(source_slot) > date.fromisoformat(slot):
                core.block(
                    state, "article", "OWNER_ARTICLE_PR_SOURCE_SLOT_INVALID",
                    f"owner article PR source slot {source_slot} is after target slot {slot}",
                )
                return core.Action("blocked", "owner article PR source slot is after target slot")

            number = int(owner_pr.get("number") or 0)
            head_sha = str((owner_pr.get("head") or {}).get("sha") or "").strip().lower()
            article = state.setdefault("article", {})
            article.update({
                "pr_number": number,
                "pr_url": owner_pr.get("html_url"),
                "current_pr_head_sha": head_sha,
                "normalization_slot": slot,
                "owner_rehome_source_slot": source_slot,
                "next_retry_at": None,
                "status": "running",
            })
            active_normalizer = self.github.active_normalizer_run(number)
            if active_normalizer:
                article["normalization_status"] = "running"
                article["normalization_run_id"] = active_normalizer.get("id")
                core.transition(
                    state, "article_normalizing", "exact owner PR rehome normalization already active",
                    pr_number=number, source_slot=source_slot, publication_slot=slot,
                )
                return core.Action("wait", "exact owner PR rehome normalization active")

            payload = {"pr_number": str(number), "slot": slot, "source_slot": source_slot}
            self.github.dispatch("normalize-article-pr.yml", payload)
            article.update({
                "normalization_status": "running",
                "normalization_dispatched_at": core.utc_now(),
            })
            core.transition(
                state, "article_normalizing", "exact prior-slot owner PR dispatched for trusted rehome",
                pr_number=number, source_slot=source_slot, publication_slot=slot,
            )
            return core.Action(
                "dispatch_normalize", "exact owner PR rehomed instead of starting another Jules article", payload
            )

    OwnerPrRehomeController.__name__ = base_controller.__name__
    OwnerPrRehomeController.__qualname__ = base_controller.__qualname__
    return OwnerPrRehomeController


def main() -> int:
    from scripts.kesher_runtime.legacy_retirement import retired_entrypoint
    retired_entrypoint()
    core.STATE_SCHEMA_VERSION = STATE_SCHEMA_VERSION
    core.GitHubClient = V5GitHubClient
    core.Controller = owner_pr_rehome_controller(V5Controller)
    v3.entry._trigger_stage = v5_trigger_stage
    v3.entry.adopt_latest_dispatched_children = v5_adopt_latest
    return v3.entry.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (core.ControllerError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"KESHER_CONTROLLER_V5_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)
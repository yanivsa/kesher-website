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
SHORT_WORKFLOW = "kesher-short-v4.yml"
SHORT_WORKFLOW_NAME = "Kesher Daily Article Short V4"
SHORT_STATE_ARTIFACT = "kesher-short-v4-state"
MAX_SHORT_DISPATCH_ATTEMPTS = 4


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
            return core.GitHubClient.newest_video_state(self)
        finally:
            core.VIDEO_STATE_ARTIFACT = previous

    def newest_video_state(self) -> dict[str, Any]:
        return self.newest_state_for_artifact(LONG_VIDEO_STATE_ARTIFACT)

    def newest_short_state(self) -> dict[str, Any]:
        return self.newest_state_for_artifact(SHORT_STATE_ARTIFACT)

    def article_session_snapshot(self, slot: str) -> dict[str, Any] | None:
        api_key = os.environ.get("JULES_API_KEY", "").strip()
        if not api_key:
            return None
        recovered = jules.recover_active_slot_session(api_key, slot)
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
        if not self.article_slot_open():
            return None
        posts = self.github.contents_json("src/data/posts.json", "main")
        if not isinstance(posts, list) or core.today_articles(posts, self.now.date()):
            return None
        slot = self.now.date().isoformat()
        open_prs = self.github.open_article_prs(slot)
        if open_prs:
            return None
        active = self.github.active_workflow_run(core.ARTICLE_WORKFLOW)
        if not active:
            return None

        snapshot_getter = getattr(self.github, "article_session_snapshot", None)
        snapshot = snapshot_getter(slot) if snapshot_getter is not None else None
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

    def _article_source(self) -> dict[str, str] | None:
        posts = self.github.contents_json("src/data/posts.json", "main")
        if not isinstance(posts, list):
            raise core.ControllerError("ARTICLE_SOURCE_INVALID")
        todays = core.today_articles(posts, self.now.date())
        if len(todays) != 1:
            return None
        return article_source_identity(todays[0])

    def _adopt_existing_short(self, state: dict[str, Any], source: dict[str, str]) -> dict[str, Any] | None:
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

    def _tick_short(self, state: dict[str, Any], source: dict[str, str], long_item: dict[str, Any]) -> core.Action:
        existing = self._adopt_existing_short(state, source)
        if existing:
            core.transition(state, "complete", "article, long-form video and derivative Short verified public")
            state["article"]["status"] = "complete"
            state["image"]["status"] = "complete"
            state["long_video"]["status"] = "complete"
            state["short"]["status"] = "complete"
            return core.Action("complete", "article + long-form + Short verified public")

        short_state = self.github.newest_short_state()
        exact = _exact_items(short_state, source)
        unresolved = [
            item for item in exact
            if item.get("uploaded") is not True
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

        if unresolved:
            current_item = unresolved[0]
            adopted = str(current_item.get("adopted_from_long_item_id") or "")
            if adopted and adopted != str(long_item.get("id") or ""):
                core.block(state, "short", "SHORT_PROVIDER_IDENTITY_MISMATCH", "existing Short derives from a different long-form provider item")
                return core.Action("blocked", "Short provider identity mismatch")

        count = int(state["short"].get("attempt_count") or 0)
        if count >= MAX_SHORT_DISPATCH_ATTEMPTS:
            core.block(state, "short", "SHORT_ATTEMPTS_EXHAUSTED", f"Short exhausted {MAX_SHORT_DISPATCH_ATTEMPTS} derive/recovery dispatch attempts")
            state["short"]["status"] = "exhausted"
            return core.Action("blocked", "Short attempts exhausted")

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
        article_watchdog_action = self._article_watchdog(state)
        if article_watchdog_action is not None:
            self.github.save_controller_state(state)
            return state, article_watchdog_action
        source = self._article_source()
        if source is not None:
            # Evidence-only migration: a matching V4 public Short is durable
            # success even while the long-form stage is still missing.
            self._adopt_existing_short(state, source)

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


def main() -> int:
    core.STATE_SCHEMA_VERSION = STATE_SCHEMA_VERSION
    core.GitHubClient = V5GitHubClient
    core.Controller = V5Controller
    v3.entry._trigger_stage = v3.v3_trigger_stage
    v3.entry.adopt_latest_dispatched_children = v3.v3_adopt_latest
    return v3.entry.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (core.ControllerError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"KESHER_CONTROLLER_V5_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

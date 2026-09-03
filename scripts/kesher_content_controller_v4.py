#!/usr/bin/env python3
"""Kesher production controller V4.

V4 keeps the proven V3 reconciliation engine but removes two sources of
nondeterminism:

* article PRs are normalized onto current ``main`` before the trusted image
  stage or any semantic Jules repair;
* Short creation is bounded: at most four fresh video-generation rounds. A
  fifth controller round is recovery-only for an exact persisted provider or
  upload identity. Otherwise the already-live article is released without a
  Short.

Article success and Short success are deliberately separate. Once an article is
verified live, downstream Short failure can never roll the article back.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from datetime import datetime, timezone
from typing import Any

if __package__:
    from . import kesher_content_controller as core
    from . import kesher_content_controller_v3_entry as v3
    from . import kesher_content_controller_v3_best_effort as legacy
    from .kesher_article_normalizer import normalization_required
    from .kesher_short_policy import ShortDecision, decide_short_action
else:
    import kesher_content_controller as core
    import kesher_content_controller_v3_entry as v3
    import kesher_content_controller_v3_best_effort as legacy
    from kesher_article_normalizer import normalization_required
    from kesher_short_policy import ShortDecision, decide_short_action

STATE_SCHEMA_VERSION = 4
NORMALIZE_WORKFLOW = "normalize-article-pr.yml"
NORMALIZE_WORKFLOW_NAME = "Kesher Normalize Article PR"
AUTO_MERGE_WORKFLOW = "auto-merge-article-prs-v4.yml"
RELEASED_SHORT_STATUS = "released_without_short"

SAFE_RECOVERY_STATUSES = {
    "generating",
    "downloaded",
    "pending_review",
    "approved",
    "uploading",
}


class ShortReleasePending(RuntimeError):
    """The release tombstone workflow was dispatched and must be reconciled."""


class ShortReleased(RuntimeError):
    """The current article is durably complete without a Short."""


def _source_slug(item: dict[str, Any]) -> str:
    source = item.get("source") or {}
    return str(source.get("slug") or source.get("id") or "").strip()


def _source_date(item: dict[str, Any]) -> str:
    source = item.get("source") or {}
    return str(source.get("date") or item.get("israel_date") or item.get("created_at") or "9999-12-31")


def _short_recovery_safe(item: dict[str, Any] | None) -> bool:
    if not isinstance(item, dict) or item.get("uploaded") is True:
        return False
    status = str(item.get("status") or "")
    if status == "rejected" and item.get("technical_verified") is True:
        # A visual-only Remotion rebuild may reuse the exact NotebookLM source.
        return bool(item.get("raw_mp4") or item.get("artifact_id"))
    if status not in SAFE_RECOVERY_STATUSES:
        return False
    if status == "generating":
        return bool(
            item.get("source_id")
            and item.get("task_id")
            and item.get("artifact_id")
            and item.get("task_id") == item.get("artifact_id")
        )
    if status == "downloaded":
        return bool(item.get("raw_mp4") or item.get("artifact_id"))
    return bool(
        item.get("final_mp4")
        or item.get("upload_session_uri")
        or item.get("youtube_id")
        or item.get("artifact_id")
    )


def _oldest_unresolved_item(video_state: dict[str, Any]) -> dict[str, Any] | None:
    items = [
        row
        for row in (video_state.get("items") or [])
        if isinstance(row, dict)
        and row.get("uploaded") is not True
        and str(row.get("status") or "")
        in (core.ACTIVE_VIDEO_STATUSES | {"rejected", RELEASED_SHORT_STATUS})
    ]
    if not items:
        return None
    return sorted(
        items,
        key=lambda row: (
            _source_date(row),
            str(row.get("created_at") or ""),
            str(row.get("id") or ""),
        ),
    )[0]



def _reconcile_video_dispatch_inputs(
    inputs: dict[str, str] | None,
    item: dict[str, Any] | None,
) -> dict[str, str] | None:
    """Revalidate an exact rebuild request against the newest durable Short state.

    Controller decisions and workflow dispatches are separated by API reads. If
    the Short state advances in that window, never dispatch a stale rebuild id
    into a worker that will restore the newer durable state.
    """
    if not isinstance(inputs, dict) or str(inputs.get("operation") or "") != "rebuild":
        return inputs
    if not isinstance(item, dict):
        return None
    if (
        str(item.get("status") or "") != "rejected"
        or item.get("technical_verified") is not True
        or str(item.get("visual_review_status") or "") != "rejected"
    ):
        return None
    fresh_id = str(item.get("id") or "").strip()
    if not fresh_id:
        return None
    reconciled = copy.deepcopy(inputs)
    reconciled["rebuild_item_id"] = fresh_id
    return reconciled

def _infer_slot(pr: dict[str, Any], base_posts: list[dict[str, Any]], head_posts: list[dict[str, Any]]) -> str:
    title = str(pr.get("title") or "")
    matches = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", title)
    if matches:
        return matches[-1]
    base_ids = {
        str(row.get("id") or row.get("slug") or "").strip()
        for row in base_posts
        if isinstance(row, dict)
    }
    dates = {
        str(row.get("date") or "").strip()
        for row in head_posts
        if isinstance(row, dict)
        and str(row.get("id") or row.get("slug") or "").strip() not in base_ids
        and str(row.get("date") or "").strip()
    }
    if len(dates) == 1:
        return next(iter(dates))
    raise core.ControllerError("ARTICLE_SLOT_UNRESOLVED")


class V4GitHubClient(v3.V3GitHubClient):
    def article_pr_normalization_required(self, pr: dict[str, Any]) -> tuple[bool, str]:
        number = int(pr.get("number") or 0)
        head_sha = str((pr.get("head") or {}).get("sha") or "")
        if not number or not head_sha:
            raise core.ControllerError("ARTICLE_PR_IDENTITY_MISSING")
        base_posts = self.contents_json("src/data/posts.json", "main")
        head_posts = self.contents_json("src/data/posts.json", head_sha)
        if not isinstance(base_posts, list) or not isinstance(head_posts, list):
            raise core.ControllerError("ARTICLE_SOURCE_INVALID")
        slot = _infer_slot(pr, base_posts, head_posts)
        files = self.request("GET", f"{self.api}/pulls/{number}/files?per_page=100")
        paths = [
            str(row.get("filename") or "")
            for row in (files if isinstance(files, list) else [])
            if isinstance(row, dict)
        ]
        return normalization_required(base_posts, head_posts, slot, paths), slot

    def active_normalizer_run(self, pr_number: int) -> dict[str, Any] | None:
        expected = f"Kesher Normalize PR {pr_number}"
        for run in self.workflow_runs(NORMALIZE_WORKFLOW):
            if str(run.get("event") or "") != "workflow_dispatch":
                continue
            if str(run.get("display_title") or "") != expected:
                continue
            if str(run.get("status") or "") in core.ACTIVE_RUN_STATUSES:
                return run
        return None


class V4Controller(legacy.BestEffortController):
    def state(self) -> dict[str, Any]:
        existing = self.github.load_controller_state()
        today = self.now.date()
        if isinstance(existing, dict) and existing.get("cycle") == today.isoformat() and existing.get("schema_version") == STATE_SCHEMA_VERSION:
            state = copy.deepcopy(existing)
            for stage in ("article", "image", "video"):
                current = state.setdefault(stage, {})
                for key, value in v3._stage_template().items():
                    current.setdefault(key, copy.deepcopy(value))
            return state
        state = v3.normalize_state(existing, today)
        previous = state.get("schema_version")
        state["schema_version"] = STATE_SCHEMA_VERSION
        state.setdefault("article", {}).setdefault("normalization_status", "pending")
        state.setdefault("video", {}).setdefault("fifth_attempt_recovery_only_used", False)
        state.setdefault("history", []).append({
            "at": core.utc_now(),
            "from": state.get("status"),
            "to": state.get("status"),
            "reason": f"controller state migrated from schema {previous} to schema v4",
        })
        state["history"] = state["history"][-100:]
        return state

    def _dispatch_auto_merge_v4(self, state: dict[str, Any]) -> None:
        active = self.github.active_workflow_run(AUTO_MERGE_WORKFLOW, production_only=True)
        if active:
            return
        core.GitHubClient.dispatch(self.github, AUTO_MERGE_WORKFLOW, None)
        state["article"]["merge_dispatch_at"] = core.utc_now()
        state["article"]["merge_dispatch_count"] = int(state["article"].get("merge_dispatch_count") or 0) + 1

    def _handle_open_article_pr(self, state: dict[str, Any], pr: dict[str, Any]) -> core.Action:
        number = int(pr.get("number") or 0)
        state["article"].update({"pr_number": number, "pr_url": pr.get("html_url")})

        needs_normalization, slot = self.github.article_pr_normalization_required(pr)
        if needs_normalization:
            active = self.github.active_normalizer_run(number)
            if active:
                state["article"].update({
                    "normalization_status": "running",
                    "normalization_run_id": active.get("id"),
                    "normalization_slot": slot,
                })
                core.transition(state, "article_normalizing", "trusted article normalization already active")
                return core.Action("wait", "article normalization active")
            core.GitHubClient.dispatch(
                self.github,
                NORMALIZE_WORKFLOW,
                {"pr_number": str(number), "slot": slot},
            )
            state["article"].update({
                "normalization_status": "running",
                "normalization_slot": slot,
                "normalization_dispatched_at": core.utc_now(),
            })
            core.transition(
                state,
                "article_normalizing",
                "dirty or stale article PR dispatched to trusted normalizer",
                pr_number=number,
                slot=slot,
            )
            return core.Action(
                "dispatch_normalize",
                "article PR must be normalized before image or Jules repair",
                {"pr_number": str(number), "slot": slot},
            )

        state["article"]["normalization_status"] = "complete"
        image_was_complete = str((state.get("image") or {}).get("status") or "") == "complete"
        ready, evidence = self.github.article_pr_image_ready(pr)
        if ready:
            v3.clear_stage_failure(state["image"])
            state["image"].update({
                "status": "complete",
                "provider_id": evidence.get("provider"),
                "artifact_sha256": evidence.get("sha256"),
                "source_id": evidence.get("source"),
            })
            core.transition(
                state,
                "article_pr_open",
                "normalized article PR has required trusted image",
            )
            # The image worker has completed and the PR itself now proves the
            # image evidence. It is safe to let the merge workflow enforce CI.
            if image_was_complete or evidence:
                self._dispatch_auto_merge_v4(state)
            return core.Action("wait", "article PR normalized and image ready; merge gate dispatched")

        # Bypass the historical BestEffortController image-deferred behavior.
        # V3 strict handling blocks after the image retry budget; it never
        # publishes an image-less article.
        return v3.V3Controller._handle_open_article_pr(self, state, pr)

    def _release_short(self, state: dict[str, Any], item: dict[str, Any] | None) -> None:
        slug = _source_slug(item or {}) or str((state.get("article") or {}).get("slug") or "").strip()
        if not slug:
            raise core.ControllerError("SHORT_RELEASE_SLUG_MISSING")
        core.GitHubClient.dispatch(
            self.github,
            core.VIDEO_WORKFLOW,
            {"operation": "release", "release_slug": slug},
        )
        state["video"].update({
            "status": "release_pending",
            "release_slug": slug,
            "release_dispatched_at": core.utc_now(),
        })
        raise ShortReleasePending(f"Short fresh-generation budget exhausted for {slug}")

    def _dispatch_budgeted(
        self,
        state: dict[str, Any],
        stage: str,
        workflow: str,
        inputs: dict[str, str] | None,
    ) -> None:
        if stage != "video":
            return super()._dispatch_budgeted(state, stage, workflow, inputs)

        current = state["video"]
        video_state = self.github.newest_video_state()
        item = _oldest_unresolved_item(video_state)
        if isinstance(inputs, dict) and str(inputs.get("operation") or "") == "rebuild":
            inputs = _reconcile_video_dispatch_inputs(inputs, item)
            if inputs is None:
                return
        if item and str(item.get("status") or "") == RELEASED_SHORT_STATUS:
            raise ShortReleased(_source_slug(item))

        count = int(current.get("attempt_count") or 0)
        recoverable = _short_recovery_safe(item)
        decision = decide_short_action(count, has_recoverable_identity=recoverable)

        if decision == ShortDecision.RELEASE_WITHOUT_SHORT:
            self._release_short(state, item)

        if decision == ShortDecision.RECOVER:
            core.GitHubClient.dispatch(self.github, workflow, inputs)
            current.update({
                "attempt_count": 5,
                "fifth_attempt_recovery_only_used": True,
                "last_dispatch_at": core.utc_now(),
                "status": "running",
                "next_retry_at": None,
            })
            if item:
                current["provider_id"] = item.get("task_id") or item.get("youtube_id")
                current["source_id"] = item.get("source_id")
                current["artifact_id"] = item.get("artifact_id")
            return

        # Before the fourth fresh generation, exact provider/upload recovery is
        # not a new generation attempt and therefore does not consume budget.
        if recoverable:
            core.GitHubClient.dispatch(self.github, workflow, inputs)
            current.update({
                "resume_dispatches": int(current.get("resume_dispatches") or 0) + 1,
                "last_dispatch_at": core.utc_now(),
                "status": "running",
                "next_retry_at": None,
            })
            return

        core.GitHubClient.dispatch(self.github, workflow, inputs)
        current.update({
            "attempt_count": count + 1,
            "last_dispatch_at": core.utc_now(),
            "status": "running",
            "next_retry_at": None,
        })

    def tick(self) -> tuple[dict[str, Any], core.Action]:
        state = self.state()
        try:
            action = self._tick(state)
        except ShortReleasePending as exc:
            core.transition(
                state,
                "short_release_pending",
                str(exc),
            )
            action = core.Action("wait", str(exc))
        except ShortReleased as exc:
            state["video"].update({
                "status": RELEASED_SHORT_STATUS,
                "released_without_short_at": core.utc_now(),
            })
            core.transition(
                state,
                "article_complete_without_short",
                f"article remains live; Short released after bounded attempts ({exc})",
            )
            action = core.Action("complete_without_short", "article live; Short attempt budget exhausted")
        except v3.StageAttemptsExhausted as exc:
            core.block(state, exc.stage, exc.code, str(exc))
            state[exc.stage]["status"] = "exhausted"
            state[exc.stage]["last_error"] = state.get("last_error")
            action = core.Action("blocked", str(exc))
        except core.ControllerError as exc:
            code = str(exc).split(":", 1)[0]
            core.block(state, "controller", code, str(exc))
            action = core.Action("blocked", str(exc))
        self._sync_stage_views(state, action)
        # ``complete_without_short`` is terminal but must not be collapsed into
        # the legacy all-stages-complete view.
        if action.kind == "complete_without_short":
            state["article"]["status"] = "complete"
            state["video"]["status"] = RELEASED_SHORT_STATUS
        self.github.save_controller_state(state)
        return state, action


def main() -> int:
    core.STATE_SCHEMA_VERSION = STATE_SCHEMA_VERSION
    core.GitHubClient = V4GitHubClient
    core.Controller = V4Controller
    v3.entry._trigger_stage = v3.v3_trigger_stage
    v3.entry.adopt_latest_dispatched_children = v3.v3_adopt_latest
    return v3.entry.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (core.ControllerError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"KESHER_CONTROLLER_V4_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

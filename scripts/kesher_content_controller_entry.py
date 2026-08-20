#!/usr/bin/env python3
"""Queue-aware, event-correlated entrypoint for the Kesher content controller.

The base controller owns the state machine. This entrypoint adds two production
invariants that are awkward to express inside GitHub Actions YAML alone:

1. unresolved prior-day videos are drained oldest-first before the current
   article starts a new video;
2. a fast child-workflow completion is correlated back to the exact controller
   dispatch before the base controller evaluates retry/backoff.

The second invariant closes a race where workflow_dispatch returns no run id:
a child can finish before the next 15-minute heartbeat has discovered its run.
Without correlation, a failed fast child could be redispatched immediately and
skip the controller's backoff. Article active-run discovery is also scoped to
the current publication slot so a stale prior-day article worker cannot block a
new day's article.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

if __package__:
    from . import kesher_content_controller as controller
else:
    import kesher_content_controller as controller


_base_matching = controller.matching_video_items
_original_active_workflow_run = controller.GitHubClient.active_workflow_run
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
ARTICLE_WORKFLOW_NAME = "Kesher Article Generation"
VIDEO_WORKFLOW_NAME = "Kesher Daily NotebookLM Video Overview"
_article_correlation_cycle = ""
_article_correlation_state: dict[str, Any] = {}


def source_slug(item: dict) -> str:
    source = item.get("source") or {}
    return str(source.get("slug") or source.get("id") or "").strip()


def source_date(item: dict) -> str:
    source = item.get("source") or {}
    return str(
        source.get("date")
        or item.get("israel_date")
        or item.get("created_at")
        or item.get("updated_at")
        or "9999-12-31"
    )


def needs_recovery(item: dict) -> bool:
    slug = source_slug(item)
    if not slug:
        return False
    if item.get("uploaded") is True or item.get("status") == "uploaded":
        return not controller.verified_youtube_item(item, slug)
    return (
        item.get("status") in controller.ACTIVE_VIDEO_STATUSES
        or item.get("status") == "rejected"
    )


def queue_aware_matching(video_state: dict, requested_slug: str) -> list[dict]:
    direct = _base_matching(video_state, requested_slug)
    backlog = [
        item for item in video_state.get("items") or []
        if isinstance(item, dict)
        and source_slug(item) != requested_slug
        and needs_recovery(item)
    ]
    if backlog:
        oldest = sorted(
            backlog,
            key=lambda item: (
                source_date(item),
                str(item.get("created_at") or ""),
                str(item.get("id") or ""),
            ),
        )[0]
        return [oldest]
    return direct


def _timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def current_cycle() -> str:
    return datetime.now(ISRAEL_TZ).date().isoformat()


def _same_id(left: Any, right: Any) -> bool:
    return bool(left is not None and right is not None and str(left) == str(right))


def article_run_matches_cycle(
    run: dict[str, Any],
    cycle: str,
    article_state: dict[str, Any] | None,
) -> bool:
    """Return True only when an article run belongs to this controller cycle.

    New workers carry the slot in ``display_title``. During a rolling upgrade we
    also accept the exact persisted run id or a run created immediately after
    this cycle's recorded dispatch. That preserves an already-running legacy
    worker without allowing an older day's active worker to block today.
    """

    if not isinstance(run, dict):
        return False
    stage = article_state or {}
    if _same_id(run.get("id"), stage.get("run_id")):
        return True
    if str(run.get("display_title") or "") == f"Kesher Article {cycle}":
        return True
    if str(run.get("event") or "") != "workflow_dispatch":
        return False
    dispatched = _timestamp(stage.get("last_dispatch_at"))
    created = _timestamp(run.get("created_at"))
    if not dispatched or not created:
        return False
    delta = (created - dispatched).total_seconds()
    return -30 <= delta <= 300


def _correlated_active_article_run(
    self: controller.GitHubClient,
    workflow: str,
    *,
    production_only: bool = False,
):
    if workflow != controller.ARTICLE_WORKFLOW:
        return _original_active_workflow_run(
            self, workflow, production_only=production_only
        )

    cycle = _article_correlation_cycle or current_cycle()
    article_state = _article_correlation_state
    for run in self.workflow_runs(workflow):
        if production_only and str(run.get("event") or "") == "pull_request":
            continue
        if str(run.get("status") or "") not in controller.ACTIVE_RUN_STATUSES:
            continue
        if article_run_matches_cycle(run, cycle, article_state):
            return run
    return None


def install_article_run_correlation(
    state: dict[str, Any] | None,
    cycle: str,
) -> None:
    """Scope article active-run discovery to the exact publication cycle."""

    global _article_correlation_cycle, _article_correlation_state
    _article_correlation_cycle = cycle
    _article_correlation_state = {}
    if isinstance(state, dict) and state.get("cycle") == cycle:
        candidate = state.get("article")
        if isinstance(candidate, dict):
            _article_correlation_state = dict(candidate)
    controller.GitHubClient.active_workflow_run = _correlated_active_article_run


def _trigger_stage(workflow_name: str) -> tuple[str, str] | None:
    if workflow_name == ARTICLE_WORKFLOW_NAME:
        return "article", controller.ARTICLE_WORKFLOW
    if workflow_name == VIDEO_WORKFLOW_NAME:
        return "video", controller.VIDEO_WORKFLOW
    return None


def triggered_child_matches_cycle(
    github: Any,
    run: dict[str, Any],
    stage: str,
    cycle: str,
    state: dict[str, Any],
) -> bool:
    stage_state = state.get(stage) if isinstance(state.get(stage), dict) else {}
    if _same_id(run.get("id"), stage_state.get("run_id")):
        return True

    if stage == "article":
        if article_run_matches_cycle(run, cycle, stage_state):
            return True
        try:
            result = github.article_result_for_run(run.get("id"))
        except controller.ControllerError:
            result = None
        return bool(isinstance(result, dict) and result.get("slot") == cycle)

    # Video workflow concurrency is global, so a controller-dispatched completion
    # is safely identified by the persisted dispatch timestamp. This also works
    # during rolling upgrades before video run names carry a cycle token.
    if str(run.get("event") or "") != "workflow_dispatch":
        return False
    dispatched = _timestamp(stage_state.get("last_dispatch_at"))
    created = _timestamp(run.get("created_at"))
    if not dispatched or not created:
        return False
    delta = (created - dispatched).total_seconds()
    return -30 <= delta <= 300


def adopt_triggered_child(
    github: Any,
    state: dict[str, Any] | None,
    cycle: str,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Persist the exact just-completed child run id before controller.tick()."""

    variables = os.environ if env is None else env
    if variables.get("KESHER_TRIGGER_EVENT") != "workflow_run":
        return False
    if not isinstance(state, dict) or state.get("cycle") != cycle:
        return False
    mapping = _trigger_stage(str(variables.get("KESHER_CHILD_WORKFLOW") or ""))
    child_id = str(variables.get("KESHER_CHILD_RUN_ID") or "").strip()
    if mapping is None or not child_id:
        return False
    stage, _ = mapping
    try:
        run = github.workflow_run_by_id(child_id)
    except controller.ControllerError:
        return False
    if not isinstance(run, dict):
        return False
    if str(run.get("event") or "") == "pull_request":
        return False
    if not triggered_child_matches_cycle(github, run, stage, cycle, state):
        return False

    stage_state = state.get(stage)
    if not isinstance(stage_state, dict):
        return False
    if _same_id(stage_state.get("run_id"), run.get("id")):
        return False
    stage_state["run_id"] = run.get("id")
    github.save_controller_state(state)
    print(
        f"KESHER_CHILD_CORRELATED stage={stage} run_id={run.get('id')} cycle={cycle}",
        flush=True,
    )
    return True


def main() -> int:
    controller.matching_video_items = queue_aware_matching

    cycle = current_cycle()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "yanivsa/kesher-website")
    state: dict[str, Any] | None = None
    if token:
        github = controller.GitHubClient(repo, token)
        state = github.load_controller_state()
        adopted = adopt_triggered_child(github, state, cycle)
        if adopted:
            state = github.load_controller_state()

    install_article_run_correlation(state, cycle)
    return controller.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (controller.ControllerError, ValueError, KeyError) as exc:
        print(f"KESHER_CONTROLLER_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

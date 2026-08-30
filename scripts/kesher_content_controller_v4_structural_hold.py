#!/usr/bin/env python3
"""Structural-backlog hold for the Kesher content controller.

The article worker intentionally refuses to create work while multiple article
PRs are open. The controller must therefore observe the same global queue
before dispatching a new daily slot. Otherwise an older backlog PR is invisible
to the date-scoped controller, dispatches are wasted, and the current cycle can
incorrectly exhaust its three-attempt budget on DUPLICATE_ARTICLE_PRS.

This layer preserves the existing Content Controller as sole owner of scheduled
article/video creation. It never creates content itself; it only prevents a new
article dispatch while an older authoritative article PR remains open.
"""

from __future__ import annotations

import json
import sys
from typing import Any

if __package__:
    from . import kesher_content_controller_v3_best_effort as best_effort
else:
    import kesher_content_controller_v3_best_effort as best_effort

v3 = best_effort.v3
core = v3.core

STRUCTURAL_DUPLICATE_OUTCOME = "DUPLICATE_ARTICLE_PRS"
STRUCTURAL_HOLD_STATUS = "article_backlog_hold"


class StructuralHoldController(best_effort.BestEffortController):
    def _structural_article_hold(self, state: dict[str, Any]) -> core.Action | None:
        """Hold a new slot behind older article PRs without consuming retries."""
        if not self.article_slot_open():
            return None

        posts = self.github.contents_json("src/data/posts.json", "main")
        if not isinstance(posts, list):
            return None
        if core.today_articles(posts, self.now.date()):
            return None

        slot = self.now.date().isoformat()
        all_open = self.github.open_article_prs()
        slot_open = self.github.open_article_prs(slot)
        slot_numbers = {int(pr.get("number") or 0) for pr in slot_open}
        backlog = [
            pr for pr in all_open
            if int(pr.get("number") or 0) not in slot_numbers
        ]
        if not backlog:
            state["article"].pop("structural_hold_prs", None)
            state["article"].pop("structural_hold_reason", None)
            return None

        article = state["article"]
        backlog_numbers = sorted(
            int(pr.get("number") or 0) for pr in backlog if pr.get("number")
        )

        # Repair only the erroneous budget consumption caused by this exact
        # structural worker outcome. Do not forgive unrelated real failures.
        worker = article.get("last_worker_result") or {}
        worker_outcome = str(worker.get("outcome") or "")
        last_error = state.get("last_error") if isinstance(state.get("last_error"), dict) else {}
        if worker_outcome == STRUCTURAL_DUPLICATE_OUTCOME:
            article["attempt_count"] = 0
            article["attempts"] = 0
            v3.clear_stage_failure(article)
            if str(last_error.get("stage") or "") == "article" and str(last_error.get("code") or "") in {
                STRUCTURAL_DUPLICATE_OUTCOME,
                "ARTICLE_ATTEMPTS_EXHAUSTED",
            }:
                state["last_error"] = None

        article["status"] = "hold"
        article["next_retry_at"] = None
        article["structural_hold_prs"] = backlog_numbers
        article["structural_hold_reason"] = "open backlog article PRs"
        core.transition(
            state,
            STRUCTURAL_HOLD_STATUS,
            "open backlog article PRs hold current slot without consuming dispatch budget",
            pr_numbers=backlog_numbers,
            slot=slot,
        )
        return core.Action(
            "wait",
            "older article PR backlog must close before current-slot generation",
        )

    def _tick(self, state: dict[str, Any]) -> core.Action:
        hold = self._structural_article_hold(state)
        if hold is not None:
            return hold
        return super()._tick(state)


def main() -> int:
    v3.core.STATE_SCHEMA_VERSION = v3.STATE_SCHEMA_VERSION
    v3.core.GitHubClient = v3.V3GitHubClient
    v3.core.Controller = StructuralHoldController
    v3.entry._trigger_stage = v3.v3_trigger_stage
    v3.entry.adopt_latest_dispatched_children = v3.v3_adopt_latest
    return v3.entry.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (core.ControllerError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"KESHER_CONTROLLER_V4_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

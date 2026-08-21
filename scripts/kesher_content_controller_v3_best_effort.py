#!/usr/bin/env python3
"""Production adapter: article images are best effort, never a publication gate.

The underlying v3 controller still owns retries and image orchestration. This
adapter changes only the terminal image-failure behavior so an article can
publish and the video pipeline can continue after image retries are exhausted.
"""

from __future__ import annotations

import json
import sys

if __package__:
    from . import kesher_content_controller_v3_entry as v3
else:
    import kesher_content_controller_v3_entry as v3


class BestEffortController(v3.V3Controller):
    def _handle_open_article_pr(self, state, pr):
        number = int(pr.get("number") or 0)
        state["article"].update({"pr_number": number, "pr_url": pr.get("html_url")})

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
            return v3.core.Action(
                "wait",
                "image best-effort exhausted; article publication remains allowed",
            )

        return super()._handle_open_article_pr(state, pr)

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

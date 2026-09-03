#!/usr/bin/env python3
"""Production runtime activation for the Kesher V4 controller.

Keep the V4 state machine independent from concrete workflow names, then bind
one production Short worker and its dedicated durable state here. During a
same-day rolling upgrade, legacy Video Overview completion is archived rather
than adopted as Short completion.
"""

from __future__ import annotations

import copy
import sys

if __package__:
    from . import kesher_content_controller_v4 as v4
else:
    import kesher_content_controller_v4 as v4

SHORT_WORKFLOW_FILE = "kesher-short-v4.yml"
SHORT_WORKFLOW_NAME = "Kesher Daily Article Short V4"
SHORT_STATE_ARTIFACT = "kesher-short-v4-state"
ARTICLE_AUTO_MERGE_WORKFLOW = "auto-merge-article-prs.yml"


def _install_v4_state_migration_guard() -> None:
    original_state = v4.V4Controller.state

    def runtime_state(self):
        existing = self.github.load_controller_state()
        same_day_legacy = bool(
            isinstance(existing, dict)
            and existing.get("cycle") == self.now.date().isoformat()
            and existing.get("schema_version") != v4.STATE_SCHEMA_VERSION
        )
        legacy_video = copy.deepcopy((existing or {}).get("video") or {}) if same_day_legacy else None
        state = original_state(self)
        if not same_day_legacy:
            return state

        # A V3 Video Overview is a different product from a V4 Article Short.
        # Preserve its evidence for audit/rollback, but never inherit its
        # completion flag, attempts, provider IDs or YouTube ID as Short state.
        state.setdefault("migration", {})["legacy_video_v3"] = legacy_video
        fresh_video = v4.v3._stage_template()
        fresh_video.update({
            "attempts": 0,
            "resume_dispatches": 0,
            "fifth_attempt_recovery_only_used": False,
        })
        state["video"] = fresh_video
        if state.get("status") == "complete":
            state["status"] = "article_live" if (state.get("article") or {}).get("live") else "article_needed"
        state.setdefault("history", []).append({
            "at": v4.core.utc_now(),
            "from": "legacy-video-state",
            "to": state.get("status"),
            "reason": "V4 rolling upgrade archived legacy Video Overview and opened a fresh Short stage",
        })
        state["history"] = state["history"][-100:]
        state["updated_at"] = v4.core.utc_now()
        return state

    v4.V4Controller.state = runtime_state


def install_runtime() -> None:
    v4.core.VIDEO_WORKFLOW = SHORT_WORKFLOW_FILE
    v4.core.VIDEO_STATE_ARTIFACT = SHORT_STATE_ARTIFACT
    v4.v3.entry.VIDEO_WORKFLOW_NAME = SHORT_WORKFLOW_NAME
    # Reuse the proven protected article merge worker; V4 dispatches it only
    # after normalization and trusted-image evidence are complete.
    v4.AUTO_MERGE_WORKFLOW = ARTICLE_AUTO_MERGE_WORKFLOW
    _install_v4_state_migration_guard()


def main() -> int:
    install_runtime()
    return v4.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (v4.core.ControllerError, ValueError, KeyError) as exc:
        print(f"KESHER_CONTROLLER_V4_RUNTIME_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

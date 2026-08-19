#!/usr/bin/env python3
"""Queue-aware entrypoint for the Kesher content controller.

The base controller owns the state machine. This entrypoint adds one cross-day
invariant: an unresolved video from an earlier article is finished before the
current article starts a new video. That preserves the promise of one video per
published daily article even if a run crosses midnight or an external provider
recovers late.
"""

from __future__ import annotations

import sys

if __package__:
    from . import kesher_content_controller as controller
else:
    import kesher_content_controller as controller


_base_matching = controller.matching_video_items


def source_slug(item: dict) -> str:
    source = item.get("source") or {}
    return str(source.get("slug") or source.get("id") or "").strip()


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
    direct_unresolved = [item for item in direct if needs_recovery(item)]

    unresolved = backlog + direct_unresolved
    if len(unresolved) > 1:
        identities = ",".join(str(item.get("id") or "unknown") for item in unresolved)
        raise controller.ControllerError(
            f"VIDEO_BACKLOG_CONFLICT: more than one unresolved daily video exists: {identities}"
        )
    if backlog:
        return backlog
    return direct


def main() -> int:
    controller.matching_video_items = queue_aware_matching
    return controller.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (controller.ControllerError, ValueError, KeyError) as exc:
        print(f"KESHER_CONTROLLER_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

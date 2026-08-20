#!/usr/bin/env python3
"""Queue-aware entrypoint for the Kesher content controller.

The base controller owns the state machine. This entrypoint adds one cross-day
invariant: unresolved prior-day videos are drained oldest-first before the
current article starts a new video. More than one backlog item is a queue, not a
fatal conflict, so an external provider outage cannot permanently stop future
daily recovery.
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


def source_date(item: dict) -> str:
    source = item.get("source") or {}
    return str(
        item.get("israel_date")
        or source.get("date")
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


def main() -> int:
    controller.matching_video_items = queue_aware_matching
    return controller.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (controller.ControllerError, ValueError, KeyError) as exc:
        print(f"KESHER_CONTROLLER_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

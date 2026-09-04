#!/usr/bin/env python3
"""Production runtime activation for Kesher V5 shared-provider publishing."""

from __future__ import annotations

import sys
from typing import Any

if __package__:
    from . import kesher_content_controller_v5 as v5
else:
    import kesher_content_controller_v5 as v5

ARTICLE_AUTO_MERGE_WORKFLOW = "auto-merge-article-prs.yml"
_BASE_NEWEST_VIDEO_STATE = v5.core.GitHubClient.newest_video_state


def _newest_state_for_artifact(self: Any, artifact_name: str) -> dict[str, Any]:
    """Read an arbitrary state artifact without dispatching through V5 again."""
    previous = v5.core.VIDEO_STATE_ARTIFACT
    v5.core.VIDEO_STATE_ARTIFACT = artifact_name
    try:
        return _BASE_NEWEST_VIDEO_STATE(self)
    finally:
        v5.core.VIDEO_STATE_ARTIFACT = previous


def install_runtime() -> None:
    v5.core.VIDEO_WORKFLOW = v5.LONG_VIDEO_WORKFLOW
    v5.core.VIDEO_STATE_ARTIFACT = v5.LONG_VIDEO_STATE_ARTIFACT
    v5.v3.entry.VIDEO_WORKFLOW_NAME = v5.LONG_VIDEO_WORKFLOW_NAME
    v5.v4.AUTO_MERGE_WORKFLOW = ARTICLE_AUTO_MERGE_WORKFLOW
    # v5.main() replaces core.GitHubClient with V5GitHubClient. Preserve the
    # original base implementation for generic artifact reads so the V5
    # override cannot recursively dispatch back into itself.
    v5.V5GitHubClient.newest_state_for_artifact = _newest_state_for_artifact


def main() -> int:
    install_runtime()
    return v5.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (v5.core.ControllerError, ValueError, KeyError) as exc:
        print(f"KESHER_CONTROLLER_V5_RUNTIME_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

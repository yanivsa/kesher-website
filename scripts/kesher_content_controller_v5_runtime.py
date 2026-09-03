#!/usr/bin/env python3
"""Production runtime activation for Kesher V5 shared-provider publishing."""

from __future__ import annotations

import sys

if __package__:
    from . import kesher_content_controller_v5 as v5
else:
    import kesher_content_controller_v5 as v5

ARTICLE_AUTO_MERGE_WORKFLOW = "auto-merge-article-prs.yml"


def install_runtime() -> None:
    v5.core.VIDEO_WORKFLOW = v5.LONG_VIDEO_WORKFLOW
    v5.core.VIDEO_STATE_ARTIFACT = v5.LONG_VIDEO_STATE_ARTIFACT
    v5.v3.entry.VIDEO_WORKFLOW_NAME = v5.LONG_VIDEO_WORKFLOW_NAME
    v5.v4.AUTO_MERGE_WORKFLOW = ARTICLE_AUTO_MERGE_WORKFLOW


def main() -> int:
    install_runtime()
    return v5.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (v5.core.ControllerError, ValueError, KeyError) as exc:
        print(f"KESHER_CONTROLLER_V5_RUNTIME_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

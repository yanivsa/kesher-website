#!/usr/bin/env python3
"""Production runtime activation for the Kesher V4 controller.

Keep the V4 state machine independent from a concrete workflow filename/name,
then bind the single production Short worker here. This prevents the legacy
horizontal Video Overview workflow or its durable state from being adopted by
Short V4.
"""

from __future__ import annotations

import sys

if __package__:
    from . import kesher_content_controller_v4 as v4
else:
    import kesher_content_controller_v4 as v4

SHORT_WORKFLOW_FILE = "kesher-short-v4.yml"
SHORT_WORKFLOW_NAME = "Kesher Daily Article Short V4"
SHORT_STATE_ARTIFACT = "kesher-short-v4-state"


def install_runtime() -> None:
    v4.core.VIDEO_WORKFLOW = SHORT_WORKFLOW_FILE
    v4.core.VIDEO_STATE_ARTIFACT = SHORT_STATE_ARTIFACT
    v4.v3.entry.VIDEO_WORKFLOW_NAME = SHORT_WORKFLOW_NAME


def main() -> int:
    install_runtime()
    return v4.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (v4.core.ControllerError, ValueError, KeyError) as exc:
        print(f"KESHER_CONTROLLER_V4_RUNTIME_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)

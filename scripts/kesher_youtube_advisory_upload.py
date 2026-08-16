#!/usr/bin/env python3
"""Upload the newest technically verified Kesher video regardless of Jules quality review.

Jules review remains advisory. YouTube/public-processing is the only publication gate.
"""

from __future__ import annotations

import re
import sys

import kesher_daily_pipeline as pipeline


def upload_advisory() -> int:
    return pipeline.upload_only()


if __name__ == "__main__":
    try:
        raise SystemExit(upload_advisory())
    except (pipeline.PipelineError, OSError, ValueError) as exc:
        message = re.sub(r"https://accounts\.google\.com/\S+", "Google sign-in redirect", str(exc))
        print(f"YOUTUBE_ADVISORY_UPLOAD_BLOCKED {message}", file=sys.stderr)
        raise SystemExit(1)

#!/usr/bin/env python3
"""Compatibility entrypoint for the Jules article worker.

When imported, this module resolves to the stable runner core so existing tests
and callers keep the same patchable API. When executed by GitHub Actions, it
runs that core and, on failure, performs bounded read-only Jules diagnostics so
COMPLETED_WITHOUT_PR is actionable rather than opaque.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import jules_article_runner_core as _core


if __name__ != "__main__":
    # Preserve the historical import contract. In particular, unittest.mock
    # patches applied to scripts.jules_article_runner must patch the globals that
    # the implementation functions actually use.
    sys.modules[__name__] = _core
else:
    from scripts import jules_article_diagnostics as _diagnostics

    exit_code = 1
    try:
        exit_code = _core.main()
    except (_core.ArticleRunnerError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"JULES_ARTICLE_BLOCKED {exc}", file=sys.stderr, flush=True)
        exit_code = 1

    if exit_code != 0:
        api_key = os.environ.get("JULES_API_KEY", "").strip()
        path = _core.result_path()
        if api_key and path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                session = str((payload or {}).get("session_id") or "").strip()
                if session:
                    diagnostic = _diagnostics.diagnose(api_key, session)
                    _diagnostics.attach_to_result(path, diagnostic)
            except Exception as exc:  # diagnostics must never hide the primary failure
                print(
                    f"JULES_ARTICLE_DIAGNOSTIC_FAILED {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                    flush=True,
                )

    raise SystemExit(exit_code)
